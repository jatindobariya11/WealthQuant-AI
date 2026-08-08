# core/options_pricing.py
"""
WealthQuant V7.1 — Options Pricing Engine
Indian Market Edition: NIFTY / BANKNIFTY / FINNIFTY / MIDCPNIFTY

Implements:
- Black-Scholes-Merton (BSM) for European options (NSE cash-settled)
- Full Greeks: Delta, Gamma, Vega, Theta, Rho, Vanna, Volga, Charm, Color, Speed
- Newton-Raphson + Brent's method IV solver (dual for robustness)
- Forward price model with cost-of-carry (dividend + repo)
- NSE-specific: RBI repo rate as risk-free, daily expiry T computation

NSE F&O Settlement: CASH SETTLED at expiry closing price
Option Type:        EUROPEAN (no early exercise)
Risk-free Rate:     RBI Repo Rate (currently ~6.5%)
Dividend Yield:     NIFTY ~1.2%, BANKNIFTY ~0.8%, FINNIFTY ~1.0%, MIDCPNIFTY ~0.9%

All T (time to expiry) computed in TRADING DAYS / 252,
not calendar days — more accurate for NSE daily expiry options.
"""

import logging
import math
from dataclasses import dataclass
from enum import Enum

from scipy.optimize import brentq
from scipy.stats import norm

logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════════
# CONSTANTS — NSE INDIA
# ══════════════════════════════════════════════════════════════════


class OptionType(Enum):
    CALL = "CE"
    PUT = "PE"


class Underlying(Enum):
    NIFTY = "NIFTY"
    BANKNIFTY = "BANKNIFTY"
    FINNIFTY = "FINNIFTY"
    MIDCPNIFTY = "MIDCPNIFTY"


# NSE lot sizes (as of mid-2025 — update when NSE revises)
LOT_SIZES = {
    "NIFTY": 50,
    "BANKNIFTY": 15,
    "FINNIFTY": 40,
    "MIDCPNIFTY": 75,
}

# Continuous dividend yields (approximate, update periodically)
DIV_YIELDS = {
    "NIFTY": 0.012,  # ~1.2%
    "BANKNIFTY": 0.008,  # ~0.8%
    "FINNIFTY": 0.010,  # ~1.0%
    "MIDCPNIFTY": 0.009,
}

RBI_REPO_RATE = 0.065  # 6.5% — update with each RBI MPC decision
TRADING_DAYS_YEAR = 252  # NSE trading days per year
MIN_IV = 0.001  # Floor to prevent division by zero
MAX_IV = 5.0  # 500% IV ceiling
MIN_T = 1 / (252 * 375)  # 1 minute minimum (daily expiry)


# ══════════════════════════════════════════════════════════════════
# DATA STRUCTURES
# ══════════════════════════════════════════════════════════════════


@dataclass
class OptionContract:
    """Full specification of an NSE option contract."""

    underlying: str  # "NIFTY", "BANKNIFTY" etc.
    option_type: OptionType
    strike: float
    expiry_date: str  # "YYYY-MM-DD"
    spot: float
    iv: float  # Annualized implied volatility (e.g. 0.15 = 15%)
    risk_free: float = RBI_REPO_RATE
    div_yield: float = 0.0  # Will be set from DIV_YIELDS if not provided
    T: float = 0.0  # Time to expiry in years (set by compute_T)
    lot_size: int = 50

    def __post_init__(self):
        if self.div_yield == 0.0:
            self.div_yield = DIV_YIELDS.get(self.underlying, 0.01)
        if self.lot_size == 50:
            self.lot_size = LOT_SIZES.get(self.underlying, 50)


@dataclass
class OptionGreeks:
    """Complete Greeks for an NSE option."""

    # First-order
    delta: float = 0.0  # ∂V/∂S — price sensitivity to spot
    gamma: float = 0.0  # ∂²V/∂S² — delta sensitivity to spot
    vega: float = 0.0  # ∂V/∂σ — price sensitivity to IV (per 1%)
    theta: float = 0.0  # ∂V/∂t — time decay per calendar day
    rho: float = 0.0  # ∂V/∂r — rate sensitivity (per 1%)

    # Second-order (critical for Indian daily expiry options)
    vanna: float = 0.0  # ∂²V/∂S∂σ = ∂delta/∂σ — MM hedging flow
    volga: float = 0.0  # ∂²V/∂σ² — IV curvature / vega convexity
    charm: float = 0.0  # ∂delta/∂t — delta decay per day (key for expiry)
    color: float = 0.0  # ∂gamma/∂t — gamma change over time
    speed: float = 0.0  # ∂gamma/∂S — third order spot sensitivity

    # Position-level (multiplied by lot size)
    delta_rupee: float = 0.0  # Delta in ₹ per lot
    gamma_rupee: float = 0.0  # Gamma in ₹ per lot per 1% spot move
    vega_rupee: float = 0.0  # Vega in ₹ per lot per 1% IV move
    theta_rupee: float = 0.0  # Theta in ₹ per lot per day

    # GEX contribution (for institutional flow analysis)
    gex_contribution: float = 0.0  # Gamma × OI × LotSize × Spot² × 0.01


@dataclass
class PricingResult:
    """Complete pricing output for an option."""

    theoretical_price: float
    intrinsic_value: float
    time_value: float
    greeks: OptionGreeks
    iv_used: float
    T_used: float
    forward_price: float
    moneyness: float  # log(F/K) — log-moneyness
    moneyness_label: str  # "ITM" / "ATM" / "OTM"
    d1: float
    d2: float


# ══════════════════════════════════════════════════════════════════
# BSM PRICING ENGINE
# ══════════════════════════════════════════════════════════════════


class BSMEngine:
    """
    Black-Scholes-Merton pricing engine adapted for NSE India.

    Key NSE adaptations:
    1. Uses RBI Repo Rate as risk-free (not US T-bill)
    2. Continuous dividend yield model (not discrete)
    3. Trading-day T computation (252-day year, not 365)
    4. Daily expiry support (min T = 1 minute)
    5. Full second-order Greeks for dealer hedging analysis
    """

    @staticmethod
    def _d1(S: float, K: float, T: float, r: float, q: float, sigma: float) -> float:
        """d1 parameter of BSM formula."""
        if T <= 0 or sigma <= MIN_IV or S <= 0 or K <= 0:
            return 0.0
        return (math.log(S / K) + (r - q + 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))

    @staticmethod
    def _d2(d1: float, sigma: float, T: float) -> float:
        """d2 = d1 - σ√T"""
        return d1 - sigma * math.sqrt(T)

    @staticmethod
    def _forward(S: float, r: float, q: float, T: float) -> float:
        """Forward price: F = S × e^((r-q)T)"""
        return S * math.exp((r - q) * T)

    @classmethod
    def price(
        cls,
        S: float,
        K: float,
        T: float,
        r: float,
        q: float,
        sigma: float,
        option_type: OptionType,
    ) -> tuple[float, float, float]:
        """
        BSM option price with dividend yield.

        Returns: (theoretical_price, d1, d2)
        """
        if T <= MIN_T:
            # At expiry: return intrinsic value only
            if option_type == OptionType.CALL:
                return max(S - K, 0.0), 0.0, 0.0
            else:
                return max(K - S, 0.0), 0.0, 0.0

        d1 = cls._d1(S, K, T, r, q, sigma)
        d2 = cls._d2(d1, sigma, T)

        df = math.exp(-r * T)  # discount factor
        dfq = math.exp(-q * T)  # dividend discount factor

        if option_type == OptionType.CALL:
            price = S * dfq * norm.cdf(d1) - K * df * norm.cdf(d2)
        else:
            price = K * df * norm.cdf(-d2) - S * dfq * norm.cdf(-d1)

        return max(price, 0.0), d1, d2

    @classmethod
    def compute_all_greeks(
        cls,
        S: float,
        K: float,
        T: float,
        r: float,
        q: float,
        sigma: float,
        option_type: OptionType,
        lot_size: int = 50,
        oi: float = 0.0,
    ) -> OptionGreeks:
        """
        Compute complete Greek set including second-order.
        All position Greeks multiplied by lot_size.
        """
        g = OptionGreeks()
        if T <= MIN_T or sigma <= MIN_IV:
            return g

        d1 = cls._d1(S, K, T, r, q, sigma)
        d2 = cls._d2(d1, sigma, T)

        nd1 = norm.cdf(d1)
        nd2 = norm.cdf(d2)
        nd1_ = norm.pdf(d1)  # standard normal PDF at d1
        nd2_ = norm.pdf(d2)

        df = math.exp(-r * T)
        dfq = math.exp(-q * T)
        sqrtT = math.sqrt(T)

        # ── First-order Greeks ────────────────────────────────────

        # Delta
        if option_type == OptionType.CALL:
            g.delta = dfq * nd1
        else:
            g.delta = dfq * (nd1 - 1.0)

        # Gamma (same for calls and puts — put-call parity)
        g.gamma = dfq * nd1_ / (S * sigma * sqrtT)

        # Vega (per 1% IV move = divide by 100)
        g.vega = S * dfq * nd1_ * sqrtT / 100.0

        # Theta (per calendar day — NSE options decay calendar-day)
        term1 = -(S * dfq * nd1_ * sigma) / (2 * sqrtT)
        if option_type == OptionType.CALL:
            term2 = -r * K * df * nd2
            term3 = q * S * dfq * nd1
            g.theta = (term1 + term2 + term3) / 365.0
        else:
            term2 = r * K * df * norm.cdf(-d2)
            term3 = -q * S * dfq * norm.cdf(-d1)
            g.theta = (term1 + term2 + term3) / 365.0

        # Rho (per 1% rate move)
        if option_type == OptionType.CALL:
            g.rho = K * T * df * nd2 / 100.0
        else:
            g.rho = -K * T * df * norm.cdf(-d2) / 100.0

        # ── Second-order Greeks ───────────────────────────────────

        # Vanna = ∂delta/∂σ = ∂vega/∂S
        # Critical for understanding MM delta-hedge flow when IV changes
        g.vanna = -dfq * nd1_ * d2 / sigma

        # Volga = ∂vega/∂σ (vega convexity)
        # High volga = option benefits from IV moves in both directions
        g.volga = S * dfq * nd1_ * sqrtT * d1 * d2 / sigma

        # Charm = ∂delta/∂t (delta decay per day)
        # CRITICAL for NSE daily expiry — delta changes rapidly near expiry
        if option_type == OptionType.CALL:
            g.charm = (
                -dfq
                * (
                    nd1_
                    * (2 * (r - q) * T - d2 * sigma * sqrtT)
                    / (2 * T * sigma * sqrtT)
                    - q * nd1
                )
                / 365.0
            )
        else:
            g.charm = (
                -dfq
                * (
                    nd1_
                    * (2 * (r - q) * T - d2 * sigma * sqrtT)
                    / (2 * T * sigma * sqrtT)
                    + q * norm.cdf(-d1)
                )
                / 365.0
            )

        # Color = ∂gamma/∂t (gamma decay per day)
        g.color = (
            -dfq
            * nd1_
            / (2 * S * T * sigma * sqrtT)
            * (
                2 * q * T
                + 1
                + d1 * (2 * (r - q) * T - d2 * sigma * sqrtT) / (sigma * sqrtT)
            )
            / 365.0
        )

        # Speed = ∂gamma/∂S (third-order, for large move scenarios)
        g.speed = -g.gamma / S * (d1 / (sigma * sqrtT) + 1)

        # ── Position Greeks (per lot) ────────────────────────────
        g.delta_rupee = g.delta * lot_size * S
        g.gamma_rupee = g.gamma * lot_size * S * S * 0.01  # per 1% spot
        g.vega_rupee = g.vega * lot_size
        g.theta_rupee = g.theta * lot_size

        # GEX contribution (dealer perspective — short options)
        # GEX = Gamma × OI × LotSize × S² × 0.01 (in ₹ crores)
        if oi > 0:
            g.gex_contribution = g.gamma * oi * lot_size * S**2 * 0.01 / 1e7

        return g

    @classmethod
    def full_pricing(cls, contract: OptionContract, oi: float = 0.0) -> PricingResult:
        """
        Complete pricing: price + all Greeks + metadata.
        Use this as the single entry point for WealthQuant.
        """
        S = contract.spot
        K = contract.strike
        T = contract.T
        r = contract.risk_free
        q = contract.div_yield
        sigma = max(contract.iv, MIN_IV)
        otype = contract.option_type

        theoretical_price, d1, d2 = cls.price(S, K, T, r, q, sigma, otype)
        greeks = cls.compute_all_greeks(
            S, K, T, r, q, sigma, otype, contract.lot_size, oi
        )

        # Intrinsic and time value
        if otype == OptionType.CALL:
            intrinsic = max(S - K, 0.0)
        else:
            intrinsic = max(K - S, 0.0)
        time_value = max(theoretical_price - intrinsic, 0.0)

        # Forward price
        forward = cls._forward(S, r, q, T)

        # Log-moneyness
        moneyness = math.log(forward / K) if K > 0 else 0.0
        if moneyness > 0.01:
            moneyness_label = "ITM" if otype == OptionType.CALL else "OTM"
        elif moneyness < -0.01:
            moneyness_label = "OTM" if otype == OptionType.CALL else "ITM"
        else:
            moneyness_label = "ATM"

        return PricingResult(
            theoretical_price=round(theoretical_price, 4),
            intrinsic_value=round(intrinsic, 4),
            time_value=round(time_value, 4),
            greeks=greeks,
            iv_used=sigma,
            T_used=T,
            forward_price=round(forward, 2),
            moneyness=round(moneyness, 6),
            moneyness_label=moneyness_label,
            d1=round(d1, 6),
            d2=round(d2, 6),
        )


# ══════════════════════════════════════════════════════════════════
# IMPLIED VOLATILITY SOLVER
# ══════════════════════════════════════════════════════════════════


class IVSolver:
    """
    Dual-method IV solver: Newton-Raphson → Brent's fallback.

    Newton-Raphson: fast (3-5 iterations for typical NSE options)
    Brent's method: robust fallback when NR diverges (deep ITM/OTM,
                    near-expiry options with very low time value)

    NSE-specific tuning:
    - Initial guess uses Brenner-Subrahmanyam approximation
    - Handles near-zero time-value options gracefully
    - Minimum time value threshold before flagging as unreliable
    """

    NR_MAX_ITER = 100
    NR_TOLERANCE = 1e-8
    BRENT_XTOL = 1e-10
    MIN_VEGA_FLOOR = 1e-12  # below this vega, NR is unstable

    @staticmethod
    def _brenner_subrahmanyam_guess(S: float, K: float, T: float) -> float:
        """
        Brenner-Subrahmanyam (1988) closed-form IV approximation.
        Good initial guess that reduces NR iterations.
        σ ≈ √(2π/T) × (C/S) where C is ATM call price.
        For general strikes: σ ≈ (2/√T) × |ln(S/K)|^0.5 (modified)
        """
        if T <= 0:
            return 0.3
        # Corrado-Miller approximation (more accurate for OTM)
        try:
            x = math.log(S / K)
            return abs(x) / math.sqrt(T) * math.sqrt(2 / math.pi)
        except Exception:
            return 0.3  # safe fallback

    @classmethod
    def newton_raphson(
        cls,
        market_price: float,
        S: float,
        K: float,
        T: float,
        r: float,
        q: float,
        option_type: OptionType,
        initial_sigma: float | None = None,
    ) -> tuple[float, int, bool]:
        """
        Newton-Raphson IV solver.
        Returns: (iv, iterations, converged)
        """
        if T <= MIN_T or market_price <= 0:
            return 0.0, 0, False

        sigma = initial_sigma or cls._brenner_subrahmanyam_guess(S, K, T)
        sigma = max(MIN_IV, min(sigma, MAX_IV))

        for i in range(cls.NR_MAX_ITER):
            price, d1, d2 = BSMEngine.price(S, K, T, r, q, sigma, option_type)
            diff = price - market_price

            if abs(diff) < cls.NR_TOLERANCE:
                return sigma, i + 1, True

            # Vega = ∂price/∂σ (the derivative we divide by)
            vega = S * math.exp(-q * T) * norm.pdf(d1) * math.sqrt(T)

            if abs(vega) < cls.MIN_VEGA_FLOOR:
                break  # NR unstable — fall through to Brent's

            sigma_new = sigma - diff / vega
            sigma_new = max(MIN_IV, min(sigma_new, MAX_IV))

            if abs(sigma_new - sigma) < cls.NR_TOLERANCE:
                return sigma_new, i + 1, True

            sigma = sigma_new

        return sigma, cls.NR_MAX_ITER, False

    @classmethod
    def brentq_solver(
        cls,
        market_price: float,
        S: float,
        K: float,
        T: float,
        r: float,
        q: float,
        option_type: OptionType,
    ) -> tuple[float, bool]:
        """
        Brent's method fallback — guaranteed convergence on [MIN_IV, MAX_IV].
        Slower than NR but robust for corner cases.
        """

        def objective(sigma: float) -> float:
            price, _, _ = BSMEngine.price(S, K, T, r, q, sigma, option_type)
            return price - market_price

        try:
            # Check bracket validity
            low_price, _, _ = BSMEngine.price(S, K, T, r, q, MIN_IV, option_type)
            high_price, _, _ = BSMEngine.price(S, K, T, r, q, MAX_IV, option_type)

            if market_price < low_price:
                return MIN_IV, False  # price below BSM minimum
            if market_price > high_price:
                return MAX_IV, False  # price above BSM maximum

            iv = brentq(objective, MIN_IV, MAX_IV, xtol=cls.BRENT_XTOL)
            return iv, True
        except Exception as e:
            logger.debug(f"Brent's method failed: {e}")
            return 0.0, False

    @classmethod
    def solve(
        cls,
        market_price: float,
        S: float,
        K: float,
        T: float,
        r: float,
        q: float,
        option_type: OptionType,
    ) -> dict:
        """
        Master IV solver: NR first, Brent's fallback.
        Returns full diagnostic dict for WealthQuant health reporting.
        """
        # Step 1: Newton-Raphson
        iv_nr, iters, converged = cls.newton_raphson(
            market_price, S, K, T, r, q, option_type
        )

        if converged:
            return {
                "iv": round(iv_nr, 8),
                "method": "Newton-Raphson",
                "iters": iters,
                "converged": True,
                "reliable": True,
            }

        # Step 2: Brent's fallback
        iv_brent, brent_ok = cls.brentq_solver(market_price, S, K, T, r, q, option_type)

        if brent_ok:
            return {
                "iv": round(iv_brent, 8),
                "method": "Brent",
                "iters": iters,  # NR iterations before giving up
                "converged": True,
                "reliable": T > 1 / 365,  # flag unreliable for <1 day
            }

        # Both methods failed
        logger.warning(
            f"IV solve failed: price={market_price:.4f}, "
            f"S={S:.2f}, K={K:.2f}, T={T:.6f}"
        )
        return {
            "iv": 0.0,
            "method": "FAILED",
            "iters": iters,
            "converged": False,
            "reliable": False,
        }
