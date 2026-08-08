# WealthQuant Signal Desk API Specification

The `/api/signal-desk/{symbol}/{interval}` endpoint is a high-performance orchestration layer that merges technical indicators, institutional sentiment, and deep quant analytics.

## Request Specification
- **Method**: `GET`
- **Path Parameters**:
  - `symbol`: e.g., `NIFTY`, `BANKNIFTY`, `RELIANCE.NS`
  - `interval`: `5m`, `15m`, `1h`, `1d`

## Response Architecture (23 Categories)

### 1. Market Pulse & Price
- `price`: Current Last Traded Price (LTP).
- `change_pct`: % change from previous candle.
- `vix`: India VIX value and regime (Market Fear).

### 2. AI Core Signals
- `signal`: Directional bias (BUY_CALL, SELL_PUT, etc.)
- `confidence`: Qualitative strength (HIGH, MEDIUM, LOW).
- `score`: Quantitative score from -10 to 10.

### 3. Institutional Context
- `fii_dii`: Real-time institutional net flows (In Cr).
- `global`: GIFT NIFTY, DXY, and US Market trends.

### 4. Derivatives Desk
- `options_data`:
  - `pcr`: Put-Call Ratio (Sentiment).
  - `max_pain`: Strike price where most options expire worthless.
  - `atm_iv`: At-the-money Implied Volatility.
  - `oi_score`: Weighted Open Interest bias (-10 to 10).

### 5. Quant MTF Engine
- `quant_mtf`:
  - `returns`: Historical performance benchmarking (1w, 1m, 3m, 6m, 1y).
  - `confidence_pct`: Algorithm confidence based on weekly structure alignment.
  - `mtf`: Boolean alignment for Daily and Weekly timeframes.

### 6. News Intelligence
- `news_sentiment`: Real-time AI analysis of news headlines for the specific symbol.

---

## Data Integration Logic
The API follows a multi-sync refresh cycle:
- **Price & Indicators**: 5-second interval.
- **Market Context (VIX/Global)**: 60-second interval.
- **Institutional Flows**: Cached locally to respect NSE rate limits.
