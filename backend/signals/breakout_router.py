"""
Automated Breakout Routing Signal
When IPI triggers → Generates precise entry/exit/SL levels
Supports: Futures, Options (Debit Spread), and Synthetic positions
"""

import logging
from dataclasses import dataclass
from datetime import datetime

# Corrected import path for active codebase structure
from gamma_squeeze_engine import BlackScholesGreeks, GammaSqueezeSignal

logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════════
# TRADE STRUCTURE
# ══════════════════════════════════════════════════════════════════


@dataclass
class TradeSignal:
    signal_id: str
    timestamp: datetime
    symbol: str
    direction: str  # "BUY" / "SELL"
    instrument: str  # "FUTURES" / "CALL" / "PUT" / "SPREAD"
    entry_price: float
    stop_loss: float
    target_1: float  # Conservative target (1:1)
    target_2: float  # Moderate target (1:2)
    target_3: float  # Aggressive target (1:3)
    quantity: int  # Number of lots
    expiry: str
    strike: float | None  # For options
    risk_reward: float
    max_loss_inr: float  # Max loss in ₹
    max_profit_inr: float  # Max profit at target_2
    rationale: str
    urgency: str
    ipi_score: float
    confidence: float


# ══════════════════════════════════════════════════════════════════
# BREAKOUT ROUTER
# ══════════════════════════════════════════════════════════════════


class BreakoutRouter:
    """
    Converts GammaSqueezeSignal → Actionable TradeSignal
    with precise entry, SL, and targets.
    """

    # NSE lot sizes
    LOT_SIZES = {"NIFTY": 50, "BANKNIFTY": 15, "FINNIFTY": 40}

    # Risk per trade (₹)
    DEFAULT_RISK_INR = 5000

    def __init__(self, capital: float = 500000, risk_pct: float = 0.01):
        """
        capital:  Total trading capital in ₹
        risk_pct: Max risk per trade as fraction of capital
        """
        self.capital = capital
        self.risk_pct = risk_pct
        self.risk_inr = capital * risk_pct

    def route(
        self,
        squeeze_signal: GammaSqueezeSignal,
        current_expiry: str,
        available_strikes: list[float],
        instrument_preference: str = "FUTURES",  # or "OPTIONS" or "SPREAD"
    ) -> TradeSignal:
        """Generate trade signal from gamma squeeze signal."""

        sym = squeeze_signal.symbol
        spot = squeeze_signal.spot_price
        direction = squeeze_signal.direction
        wall = squeeze_signal.gamma_wall_strike
        flip = squeeze_signal.flip_level
        atr_proxy = squeeze_signal.estimated_move * 0.5  # use est_move as ATR proxy

        if instrument_preference == "FUTURES":
            return self._futures_signal(squeeze_signal, current_expiry, atr_proxy)
        elif instrument_preference == "OPTIONS":
            return self._options_signal(
                squeeze_signal, current_expiry, available_strikes, atr_proxy
            )
        else:
            return self._spread_signal(
                squeeze_signal, current_expiry, available_strikes, atr_proxy
            )

    # ── Futures Signal ────────────────────────────────────────────
    def _futures_signal(
        self,
        sig: GammaSqueezeSignal,
        expiry: str,
        atr: float,
    ) -> TradeSignal:
        spot = sig.spot_price
        wall = sig.gamma_wall_strike
        flip = sig.flip_level

        if sig.direction == "UP":
            # BUY futures
            entry = spot + atr * 0.1  # Small buffer above current price
            sl = max(sig.max_pain - atr, flip - atr)  # Below flip/max-pain
            sl = min(sl, entry - atr)  # Ensure meaningful SL

            # Targets: gamma wall is T2, beyond is T3
            t1 = entry + (entry - sl)  # 1:1
            t2 = sig.gamma_wall_strike  # Natural target = wall
            t3 = wall + (wall - spot) * 0.5  # Overshoot

            direction = "BUY"
        else:
            # SELL futures
            entry = spot - atr * 0.1
            sl = min(sig.max_pain + atr, flip + atr)
            sl = max(sl, entry + atr)

            t1 = entry - (sl - entry)
            t2 = sig.gamma_wall_strike
            t3 = wall - (spot - wall) * 0.5

            direction = "SELL"

        lot_size = self.LOT_SIZES.get(sig.symbol, 50)
        sl_points = abs(entry - sl)
        qty = max(1, int(self.risk_inr / (sl_points * lot_size)))

        return TradeSignal(
            signal_id=f"{sig.symbol}_FUT_{datetime.now().strftime('%H%M%S')}",
            timestamp=sig.timestamp,
            symbol=sig.symbol,
            direction=direction,
            instrument="FUTURES",
            entry_price=round(entry, 2),
            stop_loss=round(sl, 2),
            target_1=round(t1, 2),
            target_2=round(t2, 2),
            target_3=round(t3, 2),
            quantity=qty,
            expiry=expiry,
            strike=None,
            risk_reward=round(abs(t2 - entry) / abs(entry - sl), 2),
            max_loss_inr=round(sl_points * lot_size * qty, 0),
            max_profit_inr=round(abs(t2 - entry) * lot_size * qty, 0),
            rationale=(
                f"Gamma Squeeze {sig.direction}: IPI={sig.ipi_score:.0f}, "
                f"GEX Wall at {sig.gamma_wall_strike:,.0f}, "
                f"Confidence={sig.confidence * 100:.0f}%"
            ),
            urgency=sig.urgency,
            ipi_score=sig.ipi_score,
            confidence=sig.confidence,
        )

    # ── Options Signal (ATM Call/Put) ─────────────────────────────
    def _options_signal(
        self,
        sig: GammaSqueezeSignal,
        expiry: str,
        available_strikes: list[float],
        atr: float,
    ) -> TradeSignal:
        spot = sig.spot_price

        # Find ATM strike (closest to spot)
        atm_strike = min(available_strikes, key=lambda k: abs(k - spot))

        # Slightly OTM for directional bet (cheaper, higher leverage)
        if sig.direction == "UP":
            step = (
                available_strikes[1] - available_strikes[0]
                if len(available_strikes) > 1
                else 50
            )
            strike = min(available_strikes, key=lambda k: abs(k - (spot + step)))
            option = "CALL"
            bs_delta = BlackScholesGreeks.delta(
                spot,
                strike,
                max(sig.distance_pct / 100 / 365, 1e-6),
                0.065,
                0.15,
                "call",
            )
        else:
            step = (
                available_strikes[1] - available_strikes[0]
                if len(available_strikes) > 1
                else 50
            )
            strike = min(available_strikes, key=lambda k: abs(k - (spot - step)))
            option = "PUT"
            bs_delta = BlackScholesGreeks.delta(
                spot,
                strike,
                max(sig.distance_pct / 100 / 365, 1e-6),
                0.065,
                0.15,
                "put",
            )

        # For daily expiry options: entry ≈ option premium (approximate)
        # In production: fetch live bid/ask from chain
        approx_premium = max(atr * abs(bs_delta), 10)

        entry_prem = approx_premium
        sl_prem = entry_prem * 0.5  # 50% of premium as stop loss
        t1_prem = entry_prem * 1.5
        t2_prem = entry_prem * 2.5  # Target when at gamma wall
        t3_prem = entry_prem * 4.0  # Overshoot

        lot_size = self.LOT_SIZES.get(sig.symbol, 50)
        qty = max(1, int(self.risk_inr / (sl_prem * lot_size)))

        return TradeSignal(
            signal_id=f"{sig.symbol}_{option}_{int(strike)}_{datetime.now().strftime('%H%M%S')}",
            timestamp=sig.timestamp,
            symbol=sig.symbol,
            direction="BUY",
            instrument=option,
            entry_price=round(entry_prem, 2),
            stop_loss=round(sl_prem, 2),
            target_1=round(t1_prem, 2),
            target_2=round(t2_prem, 2),
            target_3=round(t3_prem, 2),
            quantity=qty,
            expiry=expiry,
            strike=strike,
            risk_reward=round(t2_prem / sl_prem, 2),
            max_loss_inr=round(sl_prem * lot_size * qty, 0),
            max_profit_inr=round(t2_prem * lot_size * qty, 0),
            rationale=(
                f"Gamma Squeeze {sig.direction}: Buy {option} {int(strike)}, "
                f"IPI={sig.ipi_score:.0f}, Wall={sig.gamma_wall_strike:,.0f}"
            ),
            urgency=sig.urgency,
            ipi_score=sig.ipi_score,
            confidence=sig.confidence,
        )

    # ── Debit Spread Signal (defined risk) ────────────────────────
    def _spread_signal(
        self,
        sig: GammaSqueezeSignal,
        expiry: str,
        available_strikes: list[float],
        atr: float,
    ) -> TradeSignal:
        """
        Bull Call Spread or Bear Put Spread — defined max loss.
        Better for high-IV environments (like near gamma squeezes).
        """
        spot = sig.spot_price
        step = (
            available_strikes[1] - available_strikes[0]
            if len(available_strikes) > 1
            else 50
        )

        if sig.direction == "UP":
            buy_strike = min(available_strikes, key=lambda k: abs(k - spot))
            sell_strike = buy_strike + 2 * step  # spread width = 2 steps
            instrument = "BULL_CALL_SPREAD"
            t2 = sell_strike  # max profit at sell strike
        else:
            buy_strike = min(available_strikes, key=lambda k: abs(k - spot))
            sell_strike = buy_strike - 2 * step
            instrument = "BEAR_PUT_SPREAD"
            t2 = sell_strike

        # Net debit ≈ ATM IV-based approximation
        net_debit = atr * 0.3
        max_profit = 2 * step - net_debit
        lot_size = self.LOT_SIZES.get(sig.symbol, 50)
        qty = max(1, int(self.risk_inr / (net_debit * lot_size)))

        return TradeSignal(
            signal_id=f"{sig.symbol}_{instrument}_{datetime.now().strftime('%H%M%S')}",
            timestamp=sig.timestamp,
            symbol=sig.symbol,
            direction="BUY",
            instrument=instrument,
            entry_price=round(net_debit, 2),
            stop_loss=0,  # Defined risk: max loss = debit
            target_1=round(net_debit + max_profit * 0.4, 2),
            target_2=round(net_debit + max_profit * 0.7, 2),
            target_3=round(net_debit + max_profit, 2),
            quantity=qty,
            expiry=expiry,
            strike=buy_strike,
            risk_reward=round(max_profit / net_debit, 2),
            max_loss_inr=round(net_debit * lot_size * qty, 0),
            max_profit_inr=round(max_profit * lot_size * qty, 0),
            rationale=(
                f"Defined-risk spread: Buy {int(buy_strike)}, Sell {int(sell_strike)}, "
                f"Net debit ₹{net_debit:.0f}, IPI={sig.ipi_score:.0f}"
            ),
            urgency=sig.urgency,
            ipi_score=sig.ipi_score,
            confidence=sig.confidence,
        )

    def format_signal(self, trade: TradeSignal) -> str:
        """Pretty-print trade signal."""
        return f"""
╔═══════════════════════════════════════════════════════╗
║  🎯 TRADE SIGNAL — {trade.symbol} {trade.instrument:<20}  ║
╠═══════════════════════════════════════════════════════╣
║  Direction:  {trade.direction:<10}  Urgency: {trade.urgency:<12}  ║
║  Entry:      ₹{trade.entry_price:>10,.2f}                        ║
║  Stop Loss:  ₹{trade.stop_loss:>10,.2f}                          ║
║  Target 1:   ₹{trade.target_1:>10,.2f}  (1:1 R:R)               ║
║  Target 2:   ₹{trade.target_2:>10,.2f}  ← GAMMA WALL            ║
║  Target 3:   ₹{trade.target_3:>10,.2f}  (overshoot)             ║
║  Quantity:   {trade.quantity} lot(s)                             ║
║  Max Loss:   ₹{trade.max_loss_inr:>10,.0f}                       ║
║  Max Profit: ₹{trade.max_profit_inr:>10,.0f} (at T2)            ║
║  R:R Ratio:  {trade.risk_reward:.2f}                              ║
║  IPI Score:  {trade.ipi_score:.1f}/100   Confidence: {trade.confidence * 100:.0f}%  ║
╠═══════════════════════════════════════════════════════╣
║  {trade.rationale[:53]:<53}  ║
╚═══════════════════════════════════════════════════════╝"""
