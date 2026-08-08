"""
Stage 5.5: Institutional Positioning Engine.
Computes PCR Momentum, OI Velocity, Strike Migration, Volume/OI Momentum,
Call/Put Walls, Support/Resistance Strength, Gamma Pressure, and Dealer Pressure.
"""

import math
from datetime import datetime

import numpy as np
import pandas as pd

from gamma_squeeze_engine import OptionStrike
from pipeline.base import (
    InstitutionalOutput,
    MarketSnapshot,
    PipelineStage,
    RegimeOutput,
)
from pipeline.db import pipeline_db


def simulate_option_chain(
    symbol: str, spot: float, ohlcv_df: pd.DataFrame, timestamp: datetime
) -> dict:
    """
    Generates a realistic mock options chain for symbol at timestamp using historical price action.
    This is used for backtesting and validation where actual historical options data is absent.
    """
    symbol_upper = symbol.upper()
    strike_step = 100 if "BANK" in symbol_upper else 50
    atm_strike = strike_step * round(spot / strike_step)

    # 2. Extract recent momentum and volatility
    ret_5d = 0.0
    vol_20d = 0.15  # default
    if ohlcv_df is not None and len(ohlcv_df) >= 20:
        closes = ohlcv_df["close"].values
        ret_5d = (
            float((closes[-1] - closes[-6]) / closes[-6]) if len(closes) >= 6 else 0.0
        )
        # annual volatility approximation
        log_rets = np.log(closes[1:] / (closes[:-1] + 1e-12))
        vol_20d = float(np.std(log_rets[-20:]) * np.sqrt(252))
        if np.isnan(vol_20d) or vol_20d < 0.01:
            vol_20d = 0.15

    # 3. Simulate PCR and total OI
    pcr_val = 1.0 + 3.0 * ret_5d
    pcr_val = max(0.6, min(1.4, pcr_val))

    base_oi = 500000.0  # base call OI
    base_pe_oi = base_oi * pcr_val

    # 4. Determine Call Wall and Put Wall strikes
    # Shift walls based on 5d momentum (Strike Migration)
    migration_shift = round(ret_5d * 15.0) * strike_step
    call_wall = atm_strike + 2 * strike_step + migration_shift
    put_wall = atm_strike - 2 * strike_step + migration_shift

    # 5. Generate strikes chain
    strikes = []
    for i in range(-10, 11):
        strike = atm_strike + i * strike_step

        # OI decays as we move away from walls
        c_std = 3.0 * strike_step
        p_std = 3.0 * strike_step

        c_oi = base_oi * math.exp(-((strike - call_wall) ** 2) / (2.0 * c_std**2))
        p_oi = base_pe_oi * math.exp(-((strike - put_wall) ** 2) / (2.0 * p_std**2))

        c_oi = max(5000.0, c_oi)
        p_oi = max(5000.0, p_oi)

        # Simulate change in OI (unwinding near ATM on momentum)
        c_chg_oi = c_oi * 0.1 * (1.0 if ret_5d < 0 else -0.5)
        p_chg_oi = p_oi * 0.1 * (1.0 if ret_5d > 0 else -0.5)

        # IV
        c_iv = vol_20d + 0.02 * (1.0 if strike > spot else -0.5)
        p_iv = vol_20d + 0.02 * (1.0 if strike < spot else -0.5)

        # Volume (highly traded near ATM)
        vol_fac = math.exp(-((strike - spot) ** 2) / (2.0 * (1.5 * strike_step) ** 2))
        c_vol = base_oi * 0.4 * vol_fac
        p_vol = base_pe_oi * 0.4 * vol_fac

        strikes.append(
            {
                "strike": float(strike),
                "ce_oi": float(round(c_oi)),
                "pe_oi": float(round(p_oi)),
                "ce_chg_oi": float(round(c_chg_oi)),
                "pe_chg_oi": float(round(p_chg_oi)),
                "ce_iv": float(c_iv),
                "pe_iv": float(p_iv),
                "ce_ltp": float(spot * 0.02),
                "pe_ltp": float(spot * 0.02),
                "ce_volume": float(round(c_vol)),
                "pe_volume": float(round(p_vol)),
            }
        )

    return {
        "pcr": pcr_val,
        "atm_iv": vol_20d,
        "ce_oi_total": sum(s["ce_oi"] for s in strikes),
        "pe_oi_total": sum(s["pe_oi"] for s in strikes),
        "strikes": strikes,
    }


class Stage5_5Institutional(PipelineStage):
    def __init__(self):
        super().__init__()
        # In-memory history buffer for running in CSV fallback or backtest mode
        self._history_cache = {}

    @property
    def name(self) -> str:
        return "institutional"

    def process(
        self, snapshot: MarketSnapshot, regime: RegimeOutput
    ) -> InstitutionalOutput:
        """
        Processes options chain data and extracts institutional positioning metrics.
        """
        symbol = snapshot.symbol.upper()
        timestamp = snapshot.timestamp
        spot = float(snapshot.ohlcv["close"].values[-1])

        # 1. Fetch options chain (use live if present, otherwise trigger historical simulator)
        raw_chain = snapshot.options
        is_simulated = False

        # Check if snapshot options are missing or hold mock static values
        if not raw_chain or raw_chain.get("pcr") == 1.0 or "strikes" not in raw_chain:
            # Backtest or fallback mode: simulate options chain
            raw_chain = simulate_option_chain(symbol, spot, snapshot.ohlcv, timestamp)
            is_simulated = True
            # Update snapshot to carry the simulated options chain
            snapshot.options = raw_chain

        strikes = raw_chain.get("strikes", [])
        pcr_raw = raw_chain.get("pcr", 1.0)
        if isinstance(pcr_raw, dict):
            pcr = float(pcr_raw.get("pcr", 1.0))
        else:
            pcr = float(pcr_raw)
        atm_iv = float(raw_chain.get("atm_iv") or 0.15)

        ce_oi_total = float(
            raw_chain.get("ce_oi_total", sum(s.get("ce_oi", 0) for s in strikes))
        )
        pe_oi_total = float(
            raw_chain.get("pe_oi_total", sum(s.get("pe_oi", 0) for s in strikes))
        )
        total_oi = ce_oi_total + pe_oi_total

        ce_volume_total = sum(
            s.get("ce_volume", s.get("ce_oi", 0) * 0.1) for s in strikes
        )
        pe_volume_total = sum(
            s.get("pe_volume", s.get("pe_oi", 0) * 0.1) for s in strikes
        )
        total_volume = ce_volume_total + pe_volume_total

        # 2. Get past data to compute momentum and velocity
        prev_pcr = pcr
        prev_oi = total_oi
        prev_volume_oi_ratio = total_volume / (total_oi + 1e-12)
        prev_weighted_strike = spot
        prev_oi_momentum = 0.0

        # Fetch from PostgreSQL if connected
        has_history = False
        if pipeline_db.is_connected and not is_simulated:
            try:
                # Query past 2 records
                import asyncio

                loop = asyncio.get_event_loop()
                # Run sync in thread pool
                past_records = loop.run_until_complete(
                    pipeline_db.get_latest_options_intelligence(symbol, limit=2)
                )
                if len(past_records) >= 1:
                    prev_rec = past_records[0]
                    prev_pcr = prev_rec.get("pcr") or pcr
                    prev_oi = prev_rec.get("open_interest") or total_oi
                    prev_volume_oi_ratio = (
                        prev_rec.get("volume_oi_ratio") or prev_volume_oi_ratio
                    )
                    # calculate previous weighted strike
                    metrics_db = prev_rec.get("metrics") or {}
                    prev_weighted_strike = metrics_db.get("weighted_strike", spot)
                    prev_oi_momentum = prev_rec.get("oi_momentum") or 0.0
                    has_history = True
            except Exception:
                pass

        # Fallback to in-memory cache
        if not has_history:
            if symbol not in self._history_cache:
                self._history_cache[symbol] = []

            history = self._history_cache[symbol]
            if len(history) >= 1:
                prev_rec = history[-1]
                prev_pcr = prev_rec["pcr"]
                prev_oi = prev_rec["open_interest"]
                prev_volume_oi_ratio = prev_rec["volume_oi_ratio"]
                prev_weighted_strike = prev_rec["weighted_strike"]
                prev_oi_momentum = prev_rec["oi_momentum"]
                has_history = True

        # Calculate weighted average strike price
        weighted_strike_sum = sum(
            s["strike"] * (s["ce_oi"] + s["pe_oi"]) for s in strikes
        )
        weighted_strike = (
            weighted_strike_sum / (total_oi + 1e-12) if total_oi > 0 else spot
        )

        # 3. Calculate Phase 2 Indicators
        # A. PCR Momentum
        pcr_momentum = pcr - prev_pcr

        # B. OI Velocity
        oi_velocity = total_oi - prev_oi

        # C. OI Momentum
        oi_momentum = 0.2 * oi_velocity + 0.8 * prev_oi_momentum

        # D. Strike Migration
        strike_migration = weighted_strike - prev_weighted_strike

        # E. Volume/OI Momentum
        volume_oi_ratio = total_volume / (total_oi + 1e-12)
        volume_oi_momentum = volume_oi_ratio - prev_volume_oi_ratio

        # G. Call Wall & Put Wall (Highest OI strikes)
        call_wall = spot
        max_ce_oi = -1
        put_wall = spot
        max_pe_oi = -1
        for s in strikes:
            if s["ce_oi"] > max_ce_oi:
                max_ce_oi = s["ce_oi"]
                call_wall = s["strike"]
            if s["pe_oi"] > max_pe_oi:
                max_pe_oi = s["pe_oi"]
                put_wall = s["strike"]

        # H. Support & Resistance Strength
        support_strength = max_pe_oi
        resistance_strength = max_ce_oi

        # I. Gamma Pressure & Dealer Pressure
        gamma_pressure = 0.0
        dealer_pressure = 0.0

        if strikes:
            try:
                # Lot sizes
                lot_sizes = {
                    "NIFTY": 50,
                    "BANKNIFTY": 15,
                    "FINNIFTY": 40,
                    "MIDCPNIFTY": 75,
                }
                lot_size = lot_sizes.get(symbol, 50)

                # Setup GEX calculation inputs
                # Convert options chain items to OptionStrike format
                strikes_data = []
                for s in strikes:
                    strikes_data.append(
                        OptionStrike(
                            strike=s["strike"],
                            call_oi=s["ce_oi"],
                            put_oi=s["pe_oi"],
                            call_oi_prev=s["ce_oi"] - s.get("ce_chg_oi", 0),
                            put_oi_prev=s["pe_oi"] - s.get("pe_chg_oi", 0),
                            call_iv=s["ce_iv"]
                            if s["ce_iv"] is not None and s["ce_iv"] > 0
                            else atm_iv,
                            put_iv=s["pe_iv"]
                            if s["pe_iv"] is not None and s["pe_iv"] > 0
                            else atm_iv,
                            call_volume=s.get("ce_volume", 0),
                            put_volume=s.get("pe_volume", 0),
                            call_bid=0.0,
                            call_ask=0.0,
                            put_bid=0.0,
                            put_ask=0.0,
                        )
                    )

                calculator = GammaExposureCalculator(symbol)
                # Compute GEX profile (1 day expiry daily options)
                gex_df = calculator.compute_gex_profile(
                    strikes_data, spot, expiry_days=1.0
                )
                if not gex_df.empty:
                    gamma_pressure = float(gex_df["net_gex"].sum())
                    # Dealer Positioning Bias: normalized net GEX
                    total_abs_gex = gex_df["call_gex"].sum() + gex_df["put_gex"].sum()
                    dealer_pressure = gamma_pressure / (total_abs_gex + 1e-12)
            except Exception:
                pass

        # 4. Calculate Positioning Scores (Phase 3)
        # Standardize inputs: -1 to 1 bullish indicator count
        bullish_indicators = 0
        bearish_indicators = 0

        # I. PCR check
        if pcr > 1.15:
            bullish_indicators += 1
        elif pcr < 0.85:
            bearish_indicators += 1

        # II. PCR Momentum
        if pcr_momentum < -0.01:
            bullish_indicators += 1
        elif pcr_momentum > 0.01:
            bearish_indicators += 1

        # III. Strike Migration
        if strike_migration > 0.5:
            bullish_indicators += 1
        elif strike_migration < -0.5:
            bearish_indicators += 1

        # IV. Support vs Resistance
        if support_strength > resistance_strength * 1.1:
            bullish_indicators += 1
        elif resistance_strength > support_strength * 1.1:
            bearish_indicators += 1

        # V. Gamma Pressure
        if gamma_pressure > 50.0:
            bullish_indicators += 1
        elif gamma_pressure < -50.0:
            bearish_indicators += 1

        # VI. Dealer Bias
        if dealer_pressure > 0.1:
            bullish_indicators += 1
        elif dealer_pressure < -0.1:
            bearish_indicators += 1

        total_ind = 6.0
        bullish_score = (bullish_indicators / total_ind) * 100.0
        bearish_score = (bearish_indicators / total_ind) * 100.0
        neutral_score = 100.0 - (bullish_score + bearish_score)

        # Institutional Forecast, Confidence, Positioning Strength
        # net score between -1 and 1
        net_score = (bullish_indicators - bearish_indicators) / total_ind

        # Scale to directional return expectation (-0.5% to +0.5% return)
        forecast = net_score * 0.005
        confidence = abs(net_score)
        positioning_strength = bullish_score if net_score >= 0 else bearish_score

        # Save to cache for next run's history
        history_rec = {
            "pcr": pcr,
            "open_interest": total_oi,
            "volume_oi_ratio": volume_oi_ratio,
            "weighted_strike": weighted_strike,
            "oi_momentum": oi_momentum,
        }
        if symbol not in self._history_cache:
            self._history_cache[symbol] = []
        self._history_cache[symbol].append(history_rec)
        # Keep cache small
        if len(self._history_cache[symbol]) > 20:
            self._history_cache[symbol].pop(0)

        # 5. Return Stage Output
        return InstitutionalOutput(
            forecast=forecast,
            confidence=confidence,
            positioning_strength=positioning_strength,
            open_interest=total_oi,
            oi_change=oi_velocity,
            volume=total_volume,
            volume_oi_ratio=volume_oi_ratio,
            pcr=pcr,
            atm_iv=atm_iv,
            oi_velocity=oi_velocity,
            oi_momentum=oi_momentum,
            pcr_momentum=pcr_momentum,
            strike_migration=strike_migration,
            volume_oi_momentum=volume_oi_momentum,
            call_wall=call_wall,
            put_wall=put_wall,
            support_strength=support_strength,
            resistance_strength=resistance_strength,
            gamma_pressure=gamma_pressure,
            dealer_pressure=dealer_pressure,
            bullish_score=bullish_score,
            bearish_score=bearish_score,
            neutral_score=neutral_score,
            timestamp=timestamp,
        )
