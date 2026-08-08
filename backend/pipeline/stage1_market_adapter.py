"""
Stage 1: Market Adapter.
Bridges existing data fetchers into the normalized MarketSnapshot format.
"""

import logging
from datetime import datetime

import numpy as np
import pandas as pd

import data_fetcher
import data_fetchers
from constants import SECTOR_MAP
from pipeline.base import MarketSnapshot, PipelineStage, TickEvent
from pipeline.config import HAWKES_CONFIG

logger = logging.getLogger("pipeline.market_adapter")


class Stage1MarketAdapter(PipelineStage):
    @property
    def name(self) -> str:
        return "market_adapter"

    def process(self, symbol: str, interval: str = "15m") -> MarketSnapshot:
        """
        Fetch all raw data from existing sources and normalize into MarketSnapshot.
        """
        symbol_upper = symbol.upper()
        logger.info(f"Processing Market Adapter for {symbol_upper} ({interval})")

        # 1. Fetch OHLCV and technical indicators from existing data_fetcher
        ohlc_ind = data_fetcher.fetch_ohlc_and_indicators(symbol_upper, interval)
        if not ohlc_ind or "candles" not in ohlc_ind or not ohlc_ind["candles"]:
            raise ValueError(f"Could not fetch OHLCV candles for symbol {symbol_upper}")

        # Convert candles list of dicts to DataFrame
        candles_list = ohlc_ind["candles"]
        df_raw = pd.DataFrame(candles_list)
        df_raw.set_index("Datetime", inplace=True)

        # Build normalized ohlcv DataFrame with lowercase columns
        ohlcv_df = pd.DataFrame(index=df_raw.index)
        ohlcv_df["open"] = df_raw["Open"].astype(float)
        ohlcv_df["high"] = df_raw["High"].astype(float)
        ohlcv_df["low"] = df_raw["Low"].astype(float)
        ohlcv_df["close"] = df_raw["Close"].astype(float)
        ohlcv_df["volume"] = df_raw["Volume"].astype(float)

        # 2. Extract tick events from 1-min / interval OHLCV for Hawkes process
        # Compute log returns
        close_series = ohlcv_df["close"]
        open_series = ohlcv_df["open"]
        vol_series = ohlcv_df["volume"]

        log_returns = np.log(close_series / close_series.shift(1)).ffill().fillna(0.0)
        ret_std = log_returns.rolling(20).std().ffill().fillna(0.0)
        vol_median = vol_series.rolling(20).median().ffill().fillna(1.0)

        tick_events = []
        price_jump_sigma = HAWKES_CONFIG.get("price_jump_sigma", 2.0)
        vol_multiplier = HAWKES_CONFIG.get("volume_spike_multiplier", 3.0)

        for idx, dt_str in enumerate(ohlcv_df.index):
            try:
                dt_obj = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
                ts = dt_obj.timestamp()
            except ValueError:
                # If index is daily / date only
                try:
                    dt_obj = datetime.strptime(dt_str, "%Y-%m-%d")
                    ts = dt_obj.timestamp()
                except ValueError:
                    ts = datetime.now().timestamp()

            # Price jump check (>2 sigma)
            ret = log_returns.iloc[idx]
            std = ret_std.iloc[idx]
            if std > 1e-6 and abs(ret) > price_jump_sigma * std:
                tick_events.append(
                    TickEvent(
                        timestamp=ts,
                        event_type="price_jump",
                        magnitude=float(abs(ret)),
                        direction=1 if ret > 0 else -1,
                        metadata={
                            "price": float(close_series.iloc[idx]),
                            "return": float(ret),
                        },
                    )
                )

            # Volume spike check (>3x median)
            vol = vol_series.iloc[idx]
            med_vol = vol_median.iloc[idx]
            if vol > vol_multiplier * med_vol and vol > 100:  # ignore tiny volume noise
                tick_events.append(
                    TickEvent(
                        timestamp=ts,
                        event_type="volume_spike",
                        magnitude=float(vol / (med_vol if med_vol > 0 else 1.0)),
                        direction=1
                        if close_series.iloc[idx] >= open_series.iloc[idx]
                        else -1,
                        metadata={
                            "volume": float(vol),
                            "median_volume": float(med_vol),
                        },
                    )
                )

        # Sort events by timestamp
        tick_events.sort(key=lambda x: x.timestamp)

        # 3. Extract pre-computed technical indicators
        indicators = ohlc_ind.get("market_overview", {})

        # 4. Fetch options chain data if available
        options_data = {}
        try:
            raw_options = data_fetcher.fetch_options_chain(symbol_upper)
            if raw_options and "error" not in raw_options:
                options_data = {
                    "pcr": raw_options.get("pcr", {}).get("pcr", 1.0),
                    "pcr_signal": raw_options.get("pcr", {}).get("signal", "NEUTRAL"),
                    "max_pain": raw_options.get("max_pain"),
                    "atm_iv": raw_options.get("atm_iv"),
                    "oi_score": raw_options.get("oi_score", 0.0),
                    "oi_signal": raw_options.get("oi_signal", "neutral"),
                }
        except Exception as opt_err:
            logger.warning(f"Options fetch bypassed for {symbol_upper}: {opt_err}")

        # 5. Fetch institutional data (FII/DII net flows)
        institutional_data = {}
        try:
            fii_dii = data_fetchers.get_fii_dii()
            if fii_dii:
                institutional_data = {
                    "fii_net": fii_dii.get("fii_net", 0.0),
                    "dii_net": fii_dii.get("dii_net", 0.0),
                    "combined": fii_dii.get("combined", 0.0),
                    "fii_bias": fii_dii.get("fii_bias", "NEUTRAL"),
                    "dii_bias": fii_dii.get("dii_bias", "NEUTRAL"),
                    "streak": fii_dii.get("streak", 0),
                }
        except Exception as inst_err:
            logger.warning(f"Institutional FII/DII fetch failed: {inst_err}")

        # 6. Fetch global market context
        global_context = {}
        try:
            vix_data = data_fetchers.get_india_vix()
            global_data = data_fetchers.get_global_markets()
            global_context = {
                "vix": vix_data.get("vix"),
                "vix_regime": vix_data.get("regime", "UNKNOWN"),
                "global_bias": global_data.get("bias", "MIXED"),
                "sp500_pct": global_data.get("sp500", {}).get("chg_pct", 0.0),
                "nasdaq_pct": global_data.get("nasdaq", {}).get("chg_pct", 0.0),
            }
        except Exception as glob_err:
            logger.warning(f"Global context fetch failed: {glob_err}")

        # 7. Fetch news sentiment
        news_sentiment = {}
        try:
            news = data_fetchers.get_news_sentiment(
                f"{symbol_upper} Indian stock market"
            )
            if news:
                news_sentiment = {
                    "score": news.get("score", 0.0),
                    "label": news.get("label", "NEUTRAL"),
                    "positive_count": news.get("positive", 0),
                    "negative_count": news.get("negative", 0),
                }
        except Exception as news_err:
            logger.warning(f"News sentiment fetch failed: {news_err}")

        # 8. Find sector peers
        # Check in SECTOR_MAP (we match symbol.NS or symbol)
        symbol_key = symbol_upper if "." in symbol_upper else symbol_upper + ".NS"
        sector = SECTOR_MAP.get(symbol_key)
        sector_peers = []
        if sector:
            sector_peers = [
                k.replace(".NS", "")
                for k, v in SECTOR_MAP.items()
                if v == sector and k != symbol_key
            ]

        snapshot_dt = datetime.now()
        if candles_list:
            try:
                last_dt_str = candles_list[-1]["Datetime"]
                snapshot_dt = datetime.strptime(last_dt_str, "%Y-%m-%d %H:%M:%S")
            except Exception:
                pass

        snapshot = MarketSnapshot(
            symbol=symbol_upper,
            timestamp=snapshot_dt,
            interval=interval,
            ohlcv=ohlcv_df,
            tick_events=tick_events,
            indicators=indicators,
            options=options_data,
            institutional=institutional_data,
            global_context=global_context,
            news_sentiment=news_sentiment,
            sector_peers=sector_peers,
        )

        return snapshot
