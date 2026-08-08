"""
Live Multi-Threaded Option Chain Monitor
- Polls NSE every 60 seconds (1-minute bars)
- Detects volume spikes > 500% of 20-day avg
- Computes ΔOI acceleration across entire chain
- Feeds GammaSqueezeEngine and fires signals
"""

import logging
import queue
import threading
import time
from collections import deque
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import numpy as np
import pandas as pd
import pytz

# Corrected import path for active codebase structure
from gamma_squeeze_engine import GammaSqueezeEngine, OptionStrike

# Use the robust cookie-managed NSE fetcher
from nse_cookie_manager import fetch_option_chain_api

logger = logging.getLogger(__name__)
IST = pytz.timezone("Asia/Kolkata")

# ══════════════════════════════════════════════════════════════════
# VOLUME SPIKE DETECTOR  (Strategy Rule #1)
# ══════════════════════════════════════════════════════════════════


class VolumeSpikeDetector:
    """
    Monitors 1-minute bars. Triggers if:
        volume > 500% of 20-day average 1-min volume
        AND bid-ask spread widens simultaneously
    → Institution aggressively executing large order
    """

    THRESHOLD_PCT = 5.0  # 500%

    def __init__(self, symbol: str, window_days: int = 20):
        self.symbol = symbol
        self.window = window_days * 375  # 375 one-min bars per day (NSE)
        self.vol_history: deque = deque(maxlen=self.window)
        self.spread_history: deque = deque(maxlen=100)

    def push(self, volume: float, bid_ask_spread: float) -> dict:
        """Push new 1-min bar data. Returns spike info."""
        self.vol_history.append(volume)
        self.spread_history.append(bid_ask_spread)

        if len(self.vol_history) < 60:  # Need at least 1 hour of data
            return {"is_spike": False, "ratio": 0, "spread_widening": False}

        avg_vol = np.mean(self.vol_history)
        vol_ratio = volume / max(avg_vol, 1)

        # Spread widening: current spread > 150% of recent average
        avg_spread = np.mean(self.spread_history)
        spread_wide = bid_ask_spread > 1.5 * avg_spread

        is_spike = (vol_ratio >= self.THRESHOLD_PCT) and spread_wide

        return {
            "is_spike": is_spike,
            "ratio": round(vol_ratio, 2),
            "vol_current": volume,
            "vol_avg_20d": round(avg_vol, 0),
            "spread_current": bid_ask_spread,
            "spread_avg": round(avg_spread, 4),
            "spread_widening": spread_wide,
            "severity": (
                "EXTREME"
                if vol_ratio >= 10
                else "HIGH"
                if vol_ratio >= 7
                else "MEDIUM"
                if vol_ratio >= 5
                else "LOW"
            ),
        }


# ══════════════════════════════════════════════════════════════════
# ΔOI ACCELERATION TRACKER
# ══════════════════════════════════════════════════════════════════


class DeltaOITracker:
    """
    Tracks Change in Open Interest over time per strike.
    Computes ΔOI acceleration = second derivative of OI.

    Rapid OI decay at ATM strikes = Institutions PANIC-CLOSING positions
    This is the most reliable pre-squeeze signal.
    """

    def __init__(self, lookback: int = 5):
        """lookback: number of snapshots to compute acceleration (5 = 5 min)"""
        self.lookback = lookback
        # strike → deque of OI values
        self.call_oi_history: dict[float, deque] = {}
        self.put_oi_history: dict[float, deque] = {}
        self.timestamps: deque = deque(maxlen=lookback + 1)

    def update(self, chain_snapshot: list[dict]):
        """
        Push a full chain snapshot.
        chain_snapshot: list of {strike, call_oi, put_oi}
        """
        self.timestamps.append(datetime.now(IST))

        for item in chain_snapshot:
            k = item["strike"]
            if k not in self.call_oi_history:
                self.call_oi_history[k] = deque(maxlen=self.lookback + 1)
                self.put_oi_history[k] = deque(maxlen=self.lookback + 1)
            self.call_oi_history[k].append(item.get("call_oi", 0))
            self.put_oi_history[k].append(item.get("put_oi", 0))

    def get_oi_with_delta(self, spot: float) -> list[OptionStrike]:
        """
        Returns OptionStrike objects with prev_oi populated
        from the lookback window.
        """
        result = []
        all_strikes = sorted(set(self.call_oi_history.keys()))

        # Filter to ±10% of spot for efficiency
        relevant = [k for k in all_strikes if abs(k - spot) / spot <= 0.10]

        for k in relevant:
            call_hist = list(self.call_oi_history.get(k, [0, 0]))
            put_hist = list(self.put_oi_history.get(k, [0, 0]))

            call_now = call_hist[-1] if call_hist else 0
            call_prev = call_hist[0] if len(call_hist) > 1 else call_now
            put_now = put_hist[-1] if put_hist else 0
            put_prev = put_hist[0] if len(put_hist) > 1 else put_now

            result.append(
                OptionStrike(
                    strike=k,
                    call_oi=call_now,
                    put_oi=put_now,
                    call_oi_prev=call_prev,
                    put_oi_prev=put_prev,
                    call_iv=0.15,  # Will be updated from live chain
                    put_iv=0.15,
                    call_volume=0,
                    put_volume=0,
                    call_bid=0,
                    call_ask=0,
                    put_bid=0,
                    put_ask=0,
                )
            )
        return result

    def get_acceleration_matrix(self) -> pd.DataFrame:
        """
        Full ΔOI Acceleration Matrix (the multi-threaded matrix from the strategy).
        Returns DataFrame: strikes × time, values = ΔOI per minute
        """
        rows = []
        for k in sorted(self.call_oi_history.keys()):
            call_hist = list(self.call_oi_history[k])
            put_hist = list(self.put_oi_history[k])
            if len(call_hist) < 2:
                continue
            # ΔOI per snapshot
            call_deltas = np.diff(call_hist)
            put_deltas = np.diff(put_hist)
            rows.append(
                {
                    "strike": k,
                    "call_doi_latest": call_deltas[-1] if len(call_deltas) else 0,
                    "put_doi_latest": put_deltas[-1] if len(put_deltas) else 0,
                    "call_doi_accel": call_deltas[-1] - call_deltas[-2]
                    if len(call_deltas) >= 2
                    else 0,
                    "put_doi_accel": put_deltas[-1] - put_deltas[-2]
                    if len(put_deltas) >= 2
                    else 0,
                    "call_oi_now": call_hist[-1],
                    "put_oi_now": put_hist[-1],
                }
            )
        return pd.DataFrame(rows)


# ══════════════════════════════════════════════════════════════════
# NSE CHAIN FETCHER
# ══════════════════════════════════════════════════════════════════


class NSEChainFetcher:
    """
    Fetches live option chain data from NSE India.
    Uses the robust nse_cookie_manager (curl_cffi + Selenium Akamai bypass)
    so the Gamma Squeeze panel always gets live data.
    """

    def __init__(self):
        logger.info("NSEChainFetcher initialized (using nse_cookie_manager)")

    def fetch_chain(self, symbol: str = "NIFTY") -> dict:
        """
        Returns option chain JSON via cookie-managed NSE session.
        Automatically refreshes Akamai cookies on expiry.
        Returns the v3 API format: {"filtered": {"data": [...], "underlyingValue": ...}}
        """
        try:
            data = fetch_option_chain_api(symbol.upper())
            if data:
                logger.info(f"NSE chain fetched for {symbol} via cookie manager")
            return data
        except Exception as e:
            logger.error(f"NSE fetch error for {symbol}: {e}")
            return {}

    def parse_chain(self, raw: dict, expiry: str | None = None) -> tuple:
        """
        Parses the NSE v3 API response into (spot, expiry, List[OptionStrike]).
        NSE v3: spot/expiry metadata lives in 'records', chain rows in 'filtered'.
        Falls back to legacy format where all data is in 'records'.
        Uses nearest expiry if not specified.
        """
        if not raw:
            return 0.0, "", []

        # ── spot + expiry metadata always lives in 'records' ────────
        records = raw.get("records", {})
        spot = float(records.get("underlyingValue", 0.0))
        expiries = records.get("expiryDates", [])
        expiry = expiry or (expiries[0] if expiries else "")

        # ── chain data: use 'filtered' (v3) or fall back to 'records' ──
        # 'filtered' is pre-filtered for first expiry — no expiryDate per row
        if "filtered" in raw:
            chain = raw["filtered"].get("data", [])
            expiry_filter = None  # all rows already belong to this expiry
        else:
            chain = records.get("data", [])
            expiry_filter = expiry

        expiry = expiry or (expiries[0] if expiries else "")
        strikes_map: dict[float, dict] = {}

        for item in chain:
            # For filtered (v3): no expiryDate per row, all rows belong to expiry.
            # For legacy records: filter by expiry explicitly.
            if expiry_filter is not None:
                if item.get("expiryDate") != expiry_filter:
                    continue
            k = float(item.get("strikePrice", 0))
            if k == 0:
                continue
            ce = item.get("CE", {})
            pe = item.get("PE", {})
            strikes_map[k] = {
                "call_oi": float(ce.get("openInterest", 0) or 0),
                "put_oi": float(pe.get("openInterest", 0) or 0),
                "call_iv": float(ce.get("impliedVolatility", 0) or 0) / 100,
                "put_iv": float(pe.get("impliedVolatility", 0) or 0) / 100,
                "call_volume": float(ce.get("totalTradedVolume", 0) or 0),
                "put_volume": float(pe.get("totalTradedVolume", 0) or 0),
                "call_bid": float(ce.get("bidprice", 0) or 0),
                "call_ask": float(ce.get("askPrice", 0) or 0),
                "put_bid": float(pe.get("bidprice", 0) or 0),
                "put_ask": float(pe.get("askPrice", 0) or 0),
            }

        options = []
        for k, v in sorted(strikes_map.items()):
            options.append(
                OptionStrike(
                    strike=k,
                    call_oi=v["call_oi"],
                    put_oi=v["put_oi"],
                    call_oi_prev=v["call_oi"],
                    put_oi_prev=v["put_oi"],  # will be overwritten by tracker
                    call_iv=v["call_iv"],
                    put_iv=v["put_iv"],
                    call_volume=v["call_volume"],
                    put_volume=v["put_volume"],
                    call_bid=v["call_bid"],
                    call_ask=v["call_ask"],
                    put_bid=v["put_bid"],
                    put_ask=v["put_ask"],
                )
            )

        return spot, expiry, options


# ══════════════════════════════════════════════════════════════════
# LIVE MONITOR — MAIN ORCHESTRATOR
# ══════════════════════════════════════════════════════════════════


class LiveGammaMonitor:
    """
    Multi-threaded live monitor.
    Thread 1: Chain fetcher (every 60s)
    Thread 2: Volume spike detector (every 1-min bar)
    Thread 3: Signal processor & alert dispatcher
    """

    def __init__(
        self,
        symbols: list[str] = ["NIFTY", "BANKNIFTY"],
        signal_callback: Callable | None = None,
        alert_threshold: float = 60.0,  # IPI score to fire alert
    ):
        self.symbols = symbols
        self.signal_callback = signal_callback or self._default_callback
        self.alert_threshold = alert_threshold
        self.running = False
        self.signal_queue: queue.Queue = queue.Queue()
        self.executor = ThreadPoolExecutor(max_workers=len(symbols) * 2)

        # Per-symbol components
        self.engines: dict[str, GammaSqueezeEngine] = {}
        self.fetchers: dict[str, NSEChainFetcher] = {}
        self.trackers: dict[str, DeltaOITracker] = {}
        self.vol_dets: dict[str, VolumeSpikeDetector] = {}
        self.prev_spots: dict[str, float] = {}

        for sym in symbols:
            self.engines[sym] = GammaSqueezeEngine(sym)
            self.fetchers[sym] = NSEChainFetcher()
            self.trackers[sym] = DeltaOITracker(lookback=5)
            self.vol_dets[sym] = VolumeSpikeDetector(sym)
            self.prev_spots[sym] = 0.0

    def start(self):
        """Start all monitoring threads."""
        self.running = True
        logger.info(f"Starting Live Gamma Monitor for: {self.symbols}")

        # One watcher thread per symbol
        for sym in self.symbols:
            t = threading.Thread(
                target=self._watch_symbol,
                args=(sym,),
                daemon=True,
                name=f"GammaWatch-{sym}",
            )
            t.start()

        # Signal dispatcher thread
        dispatcher = threading.Thread(
            target=self._dispatch_signals, daemon=True, name="SignalDispatcher"
        )
        dispatcher.start()

        logger.info("Monitor threads started")

    def stop(self):
        self.running = False
        logger.info("Monitor stopped")

    def _watch_symbol(self, symbol: str):
        """Per-symbol monitoring loop (runs every 60 seconds)."""
        POLL_INTERVAL = 60  # 1-minute bars

        while self.running:
            try:
                loop_start = time.time()
                self._process_symbol(symbol)
                elapsed = time.time() - loop_start
                sleep_time = max(POLL_INTERVAL - elapsed, 5)
                time.sleep(sleep_time)
            except Exception as e:
                logger.error(f"Error watching {symbol}: {e}", exc_info=True)
                time.sleep(30)

    def _process_symbol(self, symbol: str):
        """Full 1-minute processing cycle for one symbol."""
        fetcher = self.fetchers[symbol]
        tracker = self.trackers[symbol]
        vol_det = self.vol_dets[symbol]
        engine = self.engines[symbol]

        # 1. Fetch live chain
        raw_chain = fetcher.fetch_chain(symbol)
        if not raw_chain:
            logger.warning(f"No chain data for {symbol}")
            return

        spot, expiry, options = fetcher.parse_chain(raw_chain)
        if spot == 0 or not options:
            return

        # 2. Push to ΔOI tracker
        snapshot = [
            {"strike": o.strike, "call_oi": o.call_oi, "put_oi": o.put_oi}
            for o in options
        ]
        tracker.update(snapshot)

        # 3. Get options with historical delta
        options_with_delta = tracker.get_oi_with_delta(spot)

        # Merge live IVs back in
        iv_map = {o.strike: (o.call_iv, o.put_iv) for o in options}
        for opt in options_with_delta:
            if opt.strike in iv_map:
                opt.call_iv, opt.put_iv = iv_map[opt.strike]

        # 4. Approximate volume from total chain volume change
        total_vol_now = sum(o.call_volume + o.put_volume for o in options)
        spread_now = self._estimate_futures_spread(raw_chain, spot)

        vol_spike_info = vol_det.push(total_vol_now, spread_now)

        # 5. Compute expiry in days (daily options!)
        expiry_days = self._days_to_expiry(expiry)

        # 6. Run gamma squeeze engine
        prev_spot = self.prev_spots.get(symbol, spot)
        signal = engine.analyze(
            chain_data=options_with_delta,
            spot=spot,
            prev_spot=prev_spot,
            expiry_days=max(expiry_days, 1 / 1440),  # min 1 minute
            volume_1min=total_vol_now,
            avg_volume_20d=max(
                np.mean(list(vol_det.vol_history)) if vol_det.vol_history else 1, 1
            ),
            bid_ask_spread=spread_now,
        )
        self.prev_spots[symbol] = spot

        # 7. Attach volume spike info
        signal.trigger_volume_spike = vol_spike_info["is_spike"]

        # 8. Get acceleration matrix for logging
        accel_matrix = tracker.get_acceleration_matrix()
        logger.info(
            f"[{symbol}] spot={spot:,.0f} | IPI={signal.ipi_score:.1f} | "
            f"wall={signal.gamma_wall_strike:,.0f} | dir={signal.direction} | "
            f"urgency={signal.urgency} | vol_ratio={vol_spike_info['ratio']:.1f}x"
        )

        # 9. Fire to queue if significant
        if signal.ipi_score >= self.alert_threshold or signal.urgency in [
            "IMMEDIATE",
            "ALERT",
        ]:
            summary = engine.get_squeeze_summary()
            summary["vol_spike_info"] = vol_spike_info
            summary["accel_matrix"] = (
                accel_matrix.to_dict("records") if len(accel_matrix) > 0 else []
            )
            self.signal_queue.put(summary)

    def _dispatch_signals(self):
        """Pulls from signal queue and calls the callback."""
        while self.running:
            try:
                signal = self.signal_queue.get(timeout=5)
                self.signal_callback(signal)
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Signal dispatch error: {e}")

    def _days_to_expiry(self, expiry_str: str) -> float:
        """Parse NSE expiry string to days remaining."""
        try:
            fmt = "%d-%b-%Y"
            exp_dt = datetime.strptime(expiry_str, fmt)
            now = datetime.now()
            # NSE options expire at 15:30 IST
            exp_dt = exp_dt.replace(hour=15, minute=30)
            diff = (exp_dt - now).total_seconds() / 86400
            return max(diff, 1 / 1440)
        except Exception:
            return 1.0

    def _estimate_futures_spread(self, raw_chain: dict, spot: float) -> float:
        """Estimate futures bid-ask spread as proxy for market stress."""
        # In real deployment: read from live futures feed
        # Here: use ATM option spread as proxy
        records = raw_chain.get("records", {}).get("data", [])
        for item in records:
            if abs(float(item.get("strikePrice", 0)) - spot) < spot * 0.005:
                ce = item.get("CE", {})
                if ce.get("bidprice") and ce.get("askPrice"):
                    return float(ce["askPrice"]) - float(ce["bidprice"])
        return 0.5  # default

    def _default_callback(self, signal: dict):
        """Default: log to console."""
        print("\n" + "═" * 60)
        print(f"🔥 GAMMA SQUEEZE SIGNAL — {signal.get('symbol')}")
        print(f"   Action:     {signal.get('action')}")
        print(f"   IPI Score:  {signal.get('ipi_score')}/100")
        print(f"   Direction:  {signal.get('direction')}")
        print(f"   Wall:       {signal.get('gamma_wall'):,}")
        print(f"   Confidence: {signal.get('confidence_pct')}%")
        print(f"   Regime:     {signal.get('regime')}")
        print(f"   PCR:        {signal.get('pcr')}")
        print(f"   Max Pain:   {signal.get('max_pain'):,}")
        print("═" * 60)
