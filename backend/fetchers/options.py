import time
from datetime import datetime, timezone

import requests

import cache as C
import cache as _cache
import nse_cookie_manager
from core.shared_features import *

from .config import *


def fetch_options_chain(symbol: str, num_expiries: int = 1) -> dict:
    """
    Full NSE option chain → PCR, max pain, ATM IV, OI score, strikes.
    """
    cache_key = f"options_chain:{symbol.upper()}"
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        nse_sym = NSE_INDEX_MAP.get(symbol.upper(), symbol.upper())  # Check map first
        # NSE options API uses a different symbol format sometimes
        nse_opt_sym = symbol.upper()  # default
        if symbol.upper() == "NIFTY":
            nse_opt_sym = "NIFTY"
        elif symbol.upper() == "BANKNIFTY":
            nse_opt_sym = "BANKNIFTY"
        elif symbol.upper() == "FINNIFTY":
            nse_opt_sym = "FINNIFTY"
        elif symbol.upper() == "MIDCPNIFTY":
            nse_opt_sym = "MIDCPNIFTY"

        # Fetch using nse_cookie_manager
        data = nse_cookie_manager.fetch_option_chain_api(nse_opt_sym)

        if not data or "records" not in data:
            raise ValueError(
                f"No option chain data returned from NSE for {nse_opt_sym}"
            )

        records = data["records"]["data"]
        ltp_spot = float(data["records"]["underlyingValue"])
        expiries = data["records"]["expiryDates"]
        expiry = expiries[0] if expiries else None

        # Filter to nearest expiry
        expiry_key = (
            "expiryDates" if records and "expiryDates" in records[0] else "expiryDate"
        )
        rows = [r for r in records if r.get(expiry_key) == expiry]

        ce_oi_total = 0
        pe_oi_total = 0
        strikes_out = []
        pain_map = {}
        atm_strike = None
        atm_ce_iv = None
        atm_pe_iv = None
        min_dist = float("inf")

        for row in rows:
            strike = row.get("strikePrice", 0)
            ce = row.get("CE", {}) or {}
            pe = row.get("PE", {}) or {}
            ce_oi = ce.get("openInterest", 0) or 0
            pe_oi = pe.get("openInterest", 0) or 0

            ce_oi_total += ce_oi
            pe_oi_total += pe_oi
            pain_map[strike] = (ce_oi, pe_oi)

            ce_chg_oi = ce.get("changeinOpenInterest", 0) or 0
            pe_chg_oi = pe.get("changeinOpenInterest", 0) or 0

            strikes_out.append(
                {
                    "strike": strike,
                    "ce_oi": ce_oi,
                    "pe_oi": pe_oi,
                    "ce_chg_oi": ce_chg_oi,
                    "pe_chg_oi": pe_chg_oi,
                    "ce_iv": ce.get("impliedVolatility"),
                    "pe_iv": pe.get("impliedVolatility"),
                    "ce_ltp": ce.get("lastPrice"),
                    "pe_ltp": pe.get("lastPrice"),
                }
            )

            dist = abs(strike - ltp_spot)
            if dist < min_dist:
                min_dist = dist
                atm_strike = strike
                atm_ce_iv = ce.get("impliedVolatility")
                atm_pe_iv = pe.get("impliedVolatility")

        # PCR
        pcr_val = round(pe_oi_total / ce_oi_total, 3) if ce_oi_total > 0 else 1.0
        pcr_signal = (
            "BULLISH" if pcr_val > 1.25 else "BEARISH" if pcr_val < 0.75 else "NEUTRAL"
        )
        pcr_dict = {
            "pcr": pcr_val,
            "signal": pcr_signal,
            "total_ce_oi": ce_oi_total,
            "total_pe_oi": pe_oi_total,
        }

        # Max Pain
        max_pain = None
        min_loss = float("inf")
        for k in pain_map:
            loss = sum(
                max(0, k - s) * c + max(0, s - k) * p for s, (c, p) in pain_map.items()
            )
            if loss < min_loss:
                min_loss = loss
                max_pain = k

        # OI Score: -10 to +10
        total_oi = ce_oi_total + pe_oi_total
        oi_score = (
            round((pe_oi_total - ce_oi_total) / total_oi * 10, 1) if total_oi > 0 else 0
        )

        # ATM IV
        atm_iv = (
            round((atm_ce_iv + atm_pe_iv) / 2, 2) if atm_ce_iv and atm_pe_iv else None
        )

        # OI Signal
        strikes_sorted = sorted(strikes_out, key=lambda x: x["strike"])
        atm_idx = 0
        min_d = float("inf")
        for idx, s in enumerate(strikes_sorted):
            d = abs(s["strike"] - ltp_spot)
            if d < min_d:
                min_d = d
                atm_idx = idx
        # Window of 5 strikes above/below ATM
        start_idx = max(0, atm_idx - 5)
        end_idx = min(len(strikes_sorted), atm_idx + 6)
        window = strikes_sorted[start_idx:end_idx]

        ca = sum(w.get("ce_chg_oi", 0) for w in window)
        pa = sum(w.get("pe_chg_oi", 0) for w in window)
        if pa > ca * 1.5:
            oi_signal = "bullish"
        elif ca > pa * 1.5:
            oi_signal = "bearish"
        else:
            oi_signal = "neutral"

        result = {
            "source": "nse",
            "expiry": expiry,
            "ltp_spot": ltp_spot,
            "atm_strike": atm_strike,
            "pcr": pcr_dict,
            "max_pain": max_pain,
            "atm_iv": atm_iv,
            "atm_ce_iv": atm_ce_iv,
            "atm_pe_iv": atm_pe_iv,
            "ce_oi_total": ce_oi_total,
            "pe_oi_total": pe_oi_total,
            "oi_score": oi_score,
            "oi_signal": oi_signal,
            "strikes": strikes_sorted,
        }
        _cache.put(cache_key, result, 60)  # 60s cache
        return result
    except Exception as e:
        logger.error(f"NSE options fetch failed: {e}")
        return {"source": "nse", "error": str(e)}


def fetch_options_chain_safe(symbol="NIFTY", max_retries=3):
    """FIX #5,#21 — with retry loop, fresh session each time."""
    cache_key = f"options_chain:{symbol}"
    hit = C.get(cache_key)
    if hit is not None:
        return hit

    unavailable_key = f"options_chain_unavailable:{symbol}"
    if C.get(unavailable_key):
        raise ValueError(
            "NSE options chain recently failed / unavailable (cached to prevent uvicorn timeout)"
        )

    import nse_cookie_manager

    last_err = None
    for attempt in range(max_retries):
        try:
            d = nse_cookie_manager.fetch_option_chain_api(symbol)
            C.put(cache_key, d, C.TTL_OPTIONS)
            return d
        except (
            TimeoutError,
            ConnectionError,
            requests.exceptions.RequestException,
            OSError,
        ) as e:
            last_err = e
            print(
                f"[NSE Retry] {symbol} attempt {attempt + 1}/{max_retries} failed: {e}"
            )
            if attempt < max_retries - 1:
                time.sleep(1.5**attempt)  # Exponential backoff
        except Exception as e:
            # For 400 validation failures or other unhandled errors, don't retry.
            last_err = e
            break

    C.put(unavailable_key, True, 120)
    raise ValueError(
        f"Failed to fetch option chain after {max_retries} retries: {last_err}"
    )


def get_nse_options_summary(symbol="NIFTY"):
    """
    Fetches option chain and returns a 'live and clear' summary including PCR and ATM IV.
    """
    try:
        data = fetch_options_chain_safe(symbol)
        recs = data.get("records", {})
        filt = data.get("filtered", {})

        # 1. PCR Calculation (Near Expiry)
        total_ce_oi = filt.get("CE", {}).get("totOI", 0)
        total_pe_oi = filt.get("PE", {}).get("totOI", 0)
        pcr = round(total_pe_oi / total_ce_oi, 2) if total_ce_oi > 0 else 1.0

        # 2. ATM Determination
        ltp = recs.get("underlyingValue", 0)
        strike_prices = recs.get("strikePrices", [])
        atm_strike = (
            min(strike_prices, key=lambda x: abs(x - ltp)) if strike_prices else None
        )

        # 3. ATM IV (from filtered data - nearest expiry)
        atm_iv = None
        if atm_strike:
            # FIX-003 Validation: Legal Strike Increments
            if atm_strike % 50 != 0 and symbol == "NIFTY":
                print(
                    f"[Options] Validation Error: ATM strike {atm_strike} is not a valid 50-increment for NIFTY"
                )
                return {
                    "status": "degraded",
                    "reason": "Invalid strike increment",
                    "symbol": symbol,
                }

            for d in filt.get("data", []):
                if d.get("strikePrice") == atm_strike:
                    # Preference: Avg of CE/PE IV if available
                    ce_iv = d.get("CE", {}).get("impliedVolatility", 0)
                    pe_iv = d.get("PE", {}).get("impliedVolatility", 0)
                    if ce_iv > 0 and pe_iv > 0:
                        atm_iv = round((ce_iv + pe_iv) / 2, 2)
                    else:
                        atm_iv = ce_iv or pe_iv or None
                    break

        # FIX-003 Validation: Payload freshness
        option_ts_str = recs.get("timestamp")
        if option_ts_str:
            try:
                opt_time = datetime.strptime(option_ts_str, "%d-%b-%Y %H:%M:%S")
                # Timezone naive from NSE, assume IST. Compare with current IST
                from pipeline.scheduler import _now_ist

                now_ist = _now_ist().replace(tzinfo=None)
                if (now_ist - opt_time).total_seconds() > 900:  # 15 minutes stale
                    print(
                        f"[Options] Validation Error: Stale payload from {option_ts_str}"
                    )
                    return {
                        "status": "degraded",
                        "reason": "Stale option chain payload",
                        "symbol": symbol,
                    }
            except Exception as e:
                print(f"[Options] Timestamp parse error: {e}")

        expiries = recs.get("expiryDates", [])
        return {
            "symbol": symbol,
            "ltp": ltp,
            "pcr": pcr,
            "atm_iv": atm_iv,
            "atm_strike": atm_strike,
            "expiry": expiries[0] if expiries else None,
            "bias": "BULLISH" if pcr > 1.2 else "BEARISH" if pcr < 0.8 else "NEUTRAL",
            "status": "ok",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        print(f"[Options] Summary failed: {e}")
        return {"status": "error", "reason": str(e), "symbol": symbol}
