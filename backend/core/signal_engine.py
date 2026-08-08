from prediction_engine import analyze_global_intermarket_bias


def compute_unified_signal(data: dict) -> dict:
    """
    ══════════════════════════════════════════════════════════════
    MOMENTUM SPIKE ENGINE v3 — 70-Point Trade Activation Model
    ══════════════════════════════════════════════════════════════
    Core philosophy: Score ONLY what we can reliably measure.
    Missing data (OI, News) → neutral/pass, never penalise.
    EXECUTE fires at 70/100 with 2-of-4 momentum triggers.
    """
    mo = data.get("market_overview", {})
    quant = data.get("quant_mtf", {})
    opts = data.get("options", {})
    vix = data.get("vix") or {}
    fii = data.get("fii_dii") or {}
    glb = data.get("global") or {}
    news = data.get("news_sentiment") or {}
    ltp = data.get("ltp", 0) or 0

    rsi = mo.get("rsi")
    macd = mo.get("macd")
    macd_sig = mo.get("macd_signal")

    # Global Intermarket Bias Analysis
    intermarket = analyze_global_intermarket_bias(glb)
    sentiment_index = intermarket.get("sentiment_index", 50.0)
    evaluated_count = intermarket.get("evaluated_count", 0)
    stoch_k = mo.get("stoch_k")
    stoch_d = mo.get("stoch_d")
    candle_str = str(mo.get("candle", "")).upper()
    ema9 = mo.get("ema9", ltp) or ltp
    ema21 = mo.get("ema21", ltp) or ltp
    ema50 = mo.get("ema50", ltp) or ltp

    vol_data = mo.get("volume") or {}
    current_vol = vol_data.get("current", 0) or 0
    vol_ratio = (
        vol_data.get("ratio")
        if (isinstance(vol_data, dict) and current_vol > 0)
        else 0.0
    )

    pcr = opts.get("pcr") if isinstance(opts, dict) else None
    oi_score = opts.get("oi_score") if isinstance(opts, dict) else None

    conf_pct = quant.get("confidence_pct")
    mtf = quant.get("mtf", {})
    mtf_bull = mtf.get("daily_bullish", False)
    mtf_bear = not mtf_bull if mtf else False

    vix_val = vix.get("value")
    sp_chg = (glb.get("sp500") or {}).get("chg_pct")
    nq_chg = (glb.get("nasdaq") or {}).get("chg_pct")
    news_sc = news.get("score") if isinstance(news, dict) else None

    fii_missing = (not fii) or (fii.get("fii_net") is None) or ("error" in fii)
    if fii_missing:
        fii_net = None
    else:
        try:
            fii_net = float(
                str(fii.get("fii_net", 0))
                .replace(",", "")
                .replace(" ", "")
                .replace("−", "-")
            )
        except Exception:
            fii_net = 0.0

    mo_ltp = (
        mo.get("ltp") or ltp
    )  # MUST use the OHLC candle close for mathematical alignment with EMA
    bull_trend = mo_ltp > ema50 and ema9 > ema21
    bear_trend = mo_ltp < ema50 and ema9 < ema21

    # ── Step 1: Directional Bias ──────────────────────────────
    bias_score = 0
    if bull_trend:
        bias_score += 2
    elif bear_trend:
        bias_score -= 2

    if rsi is not None:
        if rsi > 60:
            bias_score += 2
        elif rsi < 40:
            bias_score -= 2

    if macd is not None and macd_sig is not None:
        if macd > macd_sig:
            bias_score += 2
        elif macd < macd_sig:
            bias_score -= 2

    # Set proposed direction directly from live indicators for maximum responsiveness
    if bias_score >= 2:
        proposed_direction = "BUY CALL"
        is_buy = True
    elif bias_score <= -2:
        proposed_direction = "BUY PUT"
        is_buy = False
    else:
        # Ambiguous — use EMA trend as tiebreaker
        is_buy = bull_trend if (bull_trend or bear_trend) else True
        proposed_direction = "BUY CALL" if is_buy else "BUY PUT"

    macd_confirms = (
        macd is not None
        and macd_sig is not None
        and (macd > macd_sig if is_buy else macd < macd_sig)
    )

    # Calculate dynamic intermarket alignment
    global_met = False
    if evaluated_count > 0:
        if is_buy:
            global_met = sentiment_index >= 50.0
        else:
            global_met = sentiment_index <= 50.0

    # ── Step 2: Momentum Spike Scoring (100-point scale) ──────
    # CORE indicators (70 pts) — always have data from yfinance
    # BONUS indicators (30 pts) — missing data = auto-pass (neutral)
    checks = [
        # ── CORE MOMENTUM (70 pts) ──
        {
            "key": "trend_aligned",
            "label": "Trend aligned (EMA stack)",
            "met": bull_trend if is_buy else bear_trend,
            "weight": 15,
            "tier": "core",
            "missing": mo.get("ema9") is None
            or mo.get("ema21") is None
            or mo.get("ema50") is None,
        },
        {
            "key": "macd_confirms",
            "label": "MACD confirms direction",
            "met": macd_confirms,
            "weight": 15,
            "tier": "core",
            "missing": macd is None or macd_sig is None,
        },
        {
            "key": "rsi_momentum",
            "label": "RSI momentum zone",
            "met": rsi is not None and ((rsi >= 45) if is_buy else (rsi <= 55)),
            "weight": 12,
            "tier": "core",
            "missing": rsi is None,
        },
        {
            "key": "volume_confirms",
            "label": "Volume above average",
            "met": vol_ratio > 0.8,
            "weight": 12,
            "tier": "core",
            "missing": current_vol == 0 or vol_ratio == 0.0,
        },
        {
            "key": "stochrsi_confirms",
            "label": "StochRSI confirms",
            "met": stoch_k is not None
            and stoch_d is not None
            and ((stoch_k > stoch_d) if is_buy else (stoch_k < stoch_d)),
            "weight": 8,
            "tier": "core",
            "missing": stoch_k is None or stoch_d is None,
        },
        {
            "key": "quant_mtf_confirms",
            "label": "Quant MTF confirms",
            "met": conf_pct is not None
            and ((conf_pct > 20) if is_buy else (conf_pct < -20)),
            "weight": 8,
            "tier": "core",
            "missing": conf_pct is None,
        },
        # ── BONUS / SECONDARY (30 pts) — missing data gives 0 points AND is excluded from total_weight ──
        {
            "key": "vix_acceptable",
            "label": "VIX acceptable",
            "met": False if vix_val is None else vix_val < 22,
            "weight": 5,
            "tier": "bonus",
            "missing": vix_val is None,
        },
        {
            "key": "global_supports",
            "label": "Global supports",
            "met": global_met,
            "weight": 5,
            "tier": "bonus",
            "missing": evaluated_count == 0,
        },
        {
            "key": "fii_aligned",
            "label": "FII flow aligned",
            "met": False
            if fii_net is None
            else (abs(fii_net) <= 100 or (fii_net > 0 if is_buy else fii_net < 0)),
            "weight": 5,
            "tier": "bonus",
            "missing": fii_net is None,
        },
        {
            "key": "oi_aligned",
            "label": "Option OI aligned",
            "met": False
            if oi_score is None
            else (oi_score > 3.0 if is_buy else oi_score < -3.0),
            "weight": 5,
            "tier": "bonus",
            "missing": oi_score is None,
        },
        {
            "key": "news_supports",
            "label": "News supports",
            "met": False
            if news_sc is None
            else (news_sc >= 0 if is_buy else news_sc <= 0),
            "weight": 5,
            "tier": "bonus",
            "missing": news_sc is None,
        },
        {
            "key": "candle_confirms",
            "label": "Candle confirms",
            "met": ("BULL" in candle_str or "HAMMER" in candle_str)
            if is_buy
            else ("BEAR" in candle_str or "SHOOTING_STAR" in candle_str),
            "weight": 5,
            "tier": "bonus",
            "missing": not candle_str or candle_str == "NONE",
        },
    ]

    total_score = sum(c["weight"] for c in checks if c["met"])
    # If a check is missing (bonus triggers for FAST), we exclude its weight to prevent artificially
    # deflating the score, so the score strictly reflects the evaluated indicators.
    total_weight = sum(c["weight"] for c in checks if not c.get("missing", False))
    readiness = round((total_score / total_weight) * 100, 1) if total_weight > 0 else 0

    # ── Step 3: Momentum Trigger Count (need 2 of 4) ─────────
    momentum_triggers = {
        "MACD crossover": macd_confirms,
        "Volume spike": vol_ratio >= 1.2,  # relaxed from 1.5
        "EMA trend": bull_trend if is_buy else bear_trend,
        "RSI momentum": rsi is not None and ((rsi > 50) if is_buy else (rsi < 50)),
    }
    active_triggers = [k for k, v in momentum_triggers.items() if v]
    missing_triggers = [k for k, v in momentum_triggers.items() if not v]
    trigger_count = len(active_triggers)

    next_trigger = (
        " + ".join(missing_triggers) if missing_triggers else "All triggers active"
    )
    estimated_move = (
        "Potential bullish breakout" if is_buy else "Potential bearish breakdown"
    )

    # ── Step 4: State Machine (Momentum Spike Model) ──────────
    state = "NO TRADE"
    allow_trade = False

    # SETUP BUILDING: score ≥ 35 and at least 1 momentum trigger
    if readiness >= 35 and trigger_count >= 1:
        state = "SETUP BUILDING"

    # READY: score ≥ 55 and at least 2 momentum triggers
    if readiness >= 55 and trigger_count >= 2:
        state = "READY"

    # EXECUTE: score ≥ 70 and at least 2 momentum triggers
    if readiness >= 70 and trigger_count >= 2:
        state = "EXECUTE"
        allow_trade = True

    pct = readiness
    reasons = missing_triggers

    if state == "EXECUTE":
        final_decision = proposed_direction
        urgency = "NOW" if readiness >= 80 else "SOON"
    elif state == "READY":
        final_decision = proposed_direction
        urgency = "WAIT"
    else:
        final_decision = "NO TRADE"
        urgency = "AVOID"

    # ── Step 5: Entry/Exit Calculation ────────────────────────
    atr = mo.get("atr", ltp * 0.005) or ltp * 0.005
    entry = round(ltp, 2)

    if allow_trade and final_decision == "BUY CALL":
        stop_loss = round(entry - atr * 1.5, 2)
        target1 = round(entry + atr * 2.0, 2)
        target2 = round(entry + atr * 3.0, 2)
    elif allow_trade and final_decision == "BUY PUT":
        stop_loss = round(entry + atr * 1.5, 2)
        target1 = round(entry - atr * 2.0, 2)
        target2 = round(entry - atr * 3.0, 2)
    else:
        stop_loss = None
        target1 = None
        target2 = None

    risk = round(abs(entry - stop_loss), 2) if stop_loss else 0
    reward = round(abs(target1 - entry), 2) if target1 else 0
    rr = round(reward / risk, 2) if risk > 0 else 0

    return {
        "engine_output": {
            "score": pct,
            "decision": final_decision,
            "reason": reasons,
            "allow_trade": allow_trade,
            "state": state,
            "readiness": readiness,
            "next_trigger": next_trigger,
            "estimated_move": estimated_move,
            "trigger_count": trigger_count,
            "active_triggers": active_triggers,
        },
        "signal": {
            "signal": final_decision,
            "score": pct,
            "confidence": {
                "label": "HIGH" if pct >= 80 else "MEDIUM" if pct >= 65 else "LOW",
                "score": pct,
            },
            "urgency": urgency,
            "entry": entry if allow_trade else None,
            "stop_loss": stop_loss,
            "target1": target1,
            "target2": target2,
            "risk": risk,
            "reward": reward,
            "rr_ratio": rr,
            "breakdown": {
                "Direction": proposed_direction,
                "Bias": bias_score,
                "Triggers": f"{trigger_count}/4",
                "Core": total_score,
            },
        },
        "quality": {
            "score": total_score,
            "max_score": total_weight,
            "pct": pct,
            "grade": "Strong Signal"
            if pct >= 85
            else "Good Trade"
            if pct >= 70
            else "Building"
            if pct >= 55
            else "Weak",
            "label": "Strong Signal"
            if pct >= 85
            else "Good Trade"
            if pct >= 70
            else "Building"
            if pct >= 55
            else "Weak",
            "conditions": checks,
        },
        "intermarket": intermarket,
    }
