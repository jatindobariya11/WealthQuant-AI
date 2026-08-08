from datetime import datetime

import database as DB


async def analyze_fii_trends():
    """
    Analyzes FII/DII data across multiple timeframes to provide a bias/prediction.
    Timeframes: 1d (Short), 5d (Weekly), 22d (Monthly), 66d (Quarterly)
    """
    # Fetch enough history for quarterly analysis (66 trading days)
    history = await DB.get_fii_history_async(limit=70)
    if not history:
        return {"status": "error", "reason": "No data available"}

    # Sort history by date descending for easiest relative indexing
    # id is autoincrement, so higher id = more recent
    rev_hist = history[::-1]

    current = rev_hist[0]

    def get_bias(net_value):
        return (
            "BULLISH"
            if net_value > 500
            else "BEARISH"
            if net_value < -500
            else "NEUTRAL"
        )

    def get_stats(days):
        subset = rev_hist[:days]
        if not subset:
            return None
        fii_sum = sum(r["fii_net"] for r in subset)
        dii_sum = sum(r["dii_net"] for r in subset)
        return {
            "fii_net": round(fii_sum, 2),
            "dii_net": round(dii_sum, 2),
            "combined": round(fii_sum + dii_sum, 2),
            "fii_avg": round(fii_sum / len(subset), 2),
            "fii_bias": get_bias(
                fii_sum / len(subset) * 5 if days > 1 else fii_sum
            ),  # Normalize for comparison
            "count": len(subset),
        }

    analysis = {
        "1d": get_stats(1),
        "5d": get_stats(5),
        "22d": get_stats(22),
        "66d": get_stats(66),
    }

    # Master Prediction Logic
    score = 0
    weights = {"1d": 1, "5d": 2, "22d": 3, "66d": 4}

    for tf, weight in weights.items():
        stats = analysis.get(tf)
        if stats:
            if stats["fii_net"] > 0:
                score += weight
            else:
                score -= weight

            # Additional bonus if DIIs are also supporting
            if stats["dii_net"] > 0 and stats["fii_net"] > 0:
                score += weight * 0.5
            elif stats["dii_net"] < 0 and stats["fii_net"] < 0:
                score -= weight * 0.5

    max_score = sum(weights.values()) * 1.5
    confidence = round(abs(score) / max_score, 2)

    prediction = (
        "STRONG BULLISH"
        if score > 7
        else "BULLISH"
        if score > 3
        else "STRONG BEARISH"
        if score < -7
        else "BEARISH"
        if score < -3
        else "NEUTRAL"
    )

    return {
        "symbol": "FII_DII_FLOWS",
        "date": current["date"],
        "timestamp": datetime.now().isoformat(),
        "prediction": prediction,
        "confidence": confidence,
        "score": score,
        "analysis": analysis,
        "note": "Prediction based on institutional flow alignment across timeframes.",
    }


def analyze_global_intermarket_bias(global_data: dict) -> dict:
    """
    Computes a Global Intermarket Sentiment Index (0% to 100%) based on 11 key macroeconomic drivers
    for Indian equities (NIFTY/BANKNIFTY).
    Macro drivers:
      - Positive bias for Indian Equities: Dow Jones, S&P 500, Nasdaq, Nikkei, Hang Seng, KOSPI, DAX, FTSE 100 having positive returns.
      - Negative bias for Indian Equities: Brent Crude, USD/INR, Spot Gold having positive returns.
    """
    data = global_data.get("global") or global_data
    if not isinstance(data, dict):
        return {
            "status": "error",
            "reason": "Invalid or missing global market data structure.",
            "sentiment_index": 50.0,
            "prediction": "NEUTRAL",
            "confidence": 0.0,
        }

    # Map target keys in the global_data payload to their direction multiplier for Indian Equities.
    # Multiplier: 1 means price up is BULLISH for Rupee/Indian Equities.
    # Multiplier: -1 means price up is BEARISH for Rupee/Indian Equities (Crude, Gold, USD/INR).
    macro_mapping = {
        "dow_jones": 1,
        "sp500": 1,
        "nasdaq": 1,
        "nikkei": 1,
        "hang_seng": 1,
        "kospi": 1,
        "dax": 1,
        "ftse": 1,
        "brent_crude": -1,
        "usd_inr": -1,
        "gold": -1,
    }

    evaluated = {}
    supporting_count = 0
    evaluated_count = 0

    for key, multiplier in macro_mapping.items():
        val = data.get(key)
        if isinstance(val, dict) and val.get("chg_pct") is not None:
            chg_pct = float(val["chg_pct"])
            evaluated_count += 1
            # Check if this driver supports Indian equities
            # If multiplier is 1 (equities): supporting if chg_pct > 0
            # If multiplier is -1 (oil/gold/usd): supporting if chg_pct < 0 (lower is better)
            is_supporting = (chg_pct * multiplier) > 0
            evaluated[key] = {
                "chg_pct": chg_pct,
                "bias": "BULLISH" if is_supporting else "BEARISH",
                "value": val.get("value"),
            }
            if is_supporting:
                supporting_count += 1
        else:
            evaluated[key] = {"chg_pct": None, "bias": "NEUTRAL", "value": None}

    if evaluated_count == 0:
        return {
            "status": "partial_data",
            "sentiment_index": 50.0,
            "prediction": "NEUTRAL",
            "confidence": 0.0,
            "evaluated_count": 0,
            "details": evaluated,
            "note": "No valid global intermarket drivers could be evaluated.",
        }

    sentiment_index = round((supporting_count / evaluated_count) * 100, 1)

    # Classification
    if sentiment_index >= 80:
        prediction = "STRONG BULLISH"
    elif sentiment_index >= 55:
        prediction = "BULLISH"
    elif sentiment_index >= 45:
        prediction = "NEUTRAL"
    elif sentiment_index >= 20:
        prediction = "BEARISH"
    else:
        prediction = "STRONG BEARISH"

    confidence = round(abs(sentiment_index - 50.0) / 50.0, 2)

    return {
        "status": "ok",
        "sentiment_index": sentiment_index,
        "prediction": prediction,
        "confidence": confidence,
        "evaluated_count": evaluated_count,
        "supporting_count": supporting_count,
        "details": evaluated,
        "note": f"Evaluated {evaluated_count}/11 drivers. {supporting_count} are supporting Indian equities.",
    }


if __name__ == "__main__":
    import json

    print("FII trends:")
    print(json.dumps(analyze_fii_trends(), indent=2))
    print("\nGlobal Intermarket Bias sample:")
    sample = {
        "global": {
            "dow_jones": {"value": 39000, "chg_pct": 0.5},
            "brent_crude": {"value": 83.5, "chg_pct": -1.2},
            "gold": {"value": 2300, "chg_pct": 0.1},
        }
    }
    print(json.dumps(analyze_global_intermarket_bias(sample), indent=2))
