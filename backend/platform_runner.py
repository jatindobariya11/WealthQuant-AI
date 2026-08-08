"""
╔══════════════════════════════════════════════════════════════════╗
║  GAMMA SQUEEZE INTELLIGENCE PLATFORM                            ║
║  NSE India — Nifty 50 & Bank Nifty                              ║
║                                                                  ║
║  USAGE:                                                          ║
║    python platform_runner.py --mode live      # Live monitoring ║
║    python platform_runner.py --mode api       # Start FastAPI   ║
║    python platform_runner.py --mode demo      # Demo simulation ║
╚══════════════════════════════════════════════════════════════════╝
"""

import argparse
import logging
import sys
import time
from datetime import datetime

import numpy as np

# ── Configure logging ──────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("GammaPlatform")


# ══════════════════════════════════════════════════════════════════
# DEMO MODE — Synthetic Nifty/Bank Nifty data
# ══════════════════════════════════════════════════════════════════


def run_demo():
    """
    Full demonstration with synthetic option chain data.
    Shows exactly how the engine works end-to-end.
    """
    from gamma_squeeze_engine import GammaSqueezeEngine, OptionStrike
    from signals.breakout_router import BreakoutRouter

    print("\n" + "═" * 65)
    print("   GAMMA SQUEEZE ENGINE — DEMO MODE")
    print("   Simulating NSE Bank Nifty option chain scenario")
    print("═" * 65 + "\n")

    # ── Scenario: BankNifty approaching a 49000 gamma wall ────────
    SPOT = 48650.0
    PREV_SPOT = 48420.0  # Rising price — approaching wall
    SYMBOL = "BANKNIFTY"

    # Simulate option chain: strikes from 46000 to 51000, step 100
    strikes = np.arange(46000, 51500, 100)
    chain = []

    rng = np.random.default_rng(42)  # reproducible

    for K in strikes:
        dist = (K - SPOT) / SPOT

        # Institutional concentration at round numbers
        round_bonus = 3.0 if K % 500 == 0 else (1.5 if K % 200 == 0 else 1.0)

        # Simulate OI: higher near ATM, peaks at 49000 (gamma wall)
        atm_oi = max(0, 100000 * np.exp(-abs(dist) * 12) * round_bonus)
        wall_oi = 80000 * np.exp(-abs(K - 49000) / 150) * 1.8  # 49000 is the wall

        call_oi = (atm_oi + wall_oi * (1 if K >= SPOT else 0.3)) * rng.uniform(0.9, 1.1)
        put_oi = (atm_oi + wall_oi * (1 if K <= SPOT else 0.3)) * rng.uniform(0.9, 1.1)

        # Simulate OI decay (institutions panicking and closing positions)
        # Higher decay near the gamma wall = PANIC signal
        panic_decay = 0.95 if abs(K - 49000) < 200 else 1.0
        call_oi_prev = call_oi / panic_decay
        put_oi_prev = put_oi / panic_decay

        # IV surface: higher for OTM puts (fear skew), normal for calls
        call_iv = 0.15 + 0.02 * max(dist, 0) - 0.01 * min(dist, 0)
        put_iv = 0.17 - 0.015 * max(dist, 0) + 0.04 * max(-dist, 0)  # put skew

        chain.append(
            OptionStrike(
                strike=float(K),
                call_oi=float(call_oi),
                put_oi=float(put_oi),
                call_oi_prev=float(call_oi_prev),
                put_oi_prev=float(put_oi_prev),
                call_iv=float(np.clip(call_iv, 0.10, 0.50)),
                put_iv=float(np.clip(put_iv, 0.10, 0.60)),
                call_volume=float(call_oi * rng.uniform(0.05, 0.15)),
                put_volume=float(put_oi * rng.uniform(0.05, 0.15)),
                call_bid=0,
                call_ask=0,
                put_bid=0,
                put_ask=0,
            )
        )

    # ── Simulate volume spike ─────────────────────────────────────
    VOLUME_1MIN = 8500000  # Current 1-min volume
    AVG_VOLUME_20D = 1400000  # 20-day average → ratio = 6.07x (>500% threshold!)
    BID_ASK_SPREAD = 2.50  # Widened spread (normal is ₹0.50) = institutional activity

    print("📊 Scenario Setup:")
    print(f"   Symbol:         {SYMBOL}")
    print(f"   Spot:           ₹{SPOT:,.2f}")
    print(
        f"   Prev Spot:      ₹{PREV_SPOT:,.2f} (+{(SPOT - PREV_SPOT) / PREV_SPOT * 100:.2f}%)"
    )
    print("   Gamma Wall:     ₹49,000 (high OI concentration)")
    print(f"   Distance:       {(49000 - SPOT) / SPOT * 100:.2f}% to gamma wall")
    print(
        f"   Volume Spike:   {VOLUME_1MIN / AVG_VOLUME_20D:.1f}x avg (threshold: 5.0x)"
    )
    print(f"   Spread:         ₹{BID_ASK_SPREAD} (normal: ₹0.50) → WIDENED")

    # ── Run the engine ─────────────────────────────────────────────
    engine = GammaSqueezeEngine(SYMBOL)

    print("\n⚙️  Running Gamma Squeeze Engine...")
    signal = engine.analyze(
        chain_data=chain,
        spot=SPOT,
        prev_spot=PREV_SPOT,
        expiry_days=0.25,  # 6 hours to expiry (daily option!)
        volume_1min=VOLUME_1MIN,
        avg_volume_20d=AVG_VOLUME_20D,
        bid_ask_spread=BID_ASK_SPREAD,
        normal_spread=0.50,
    )

    # ── Print results ──────────────────────────────────────────────
    summary = engine.get_squeeze_summary()

    print("\n" + "═" * 65)
    print("   GAMMA SQUEEZE ANALYSIS RESULTS")
    print("═" * 65)
    print(f"\n🎯 Signal:         {summary['action']}")
    print("\n📈 Market State:")
    print(f"   Regime:         {summary['regime']}")
    print(f"   Net GEX:        ₹{summary['net_gex_cr']:,.2f} Cr")
    print(f"   Flip Level:     ₹{summary['flip_level']:,.2f}")
    print(f"   Max Pain:       ₹{summary['max_pain']:,.2f}")
    print(f"   Put-Call Ratio: {summary['pcr']}")

    print("\n🔥 Squeeze Metrics:")
    print(f"   IPI Score:      {summary['ipi_score']}/100")
    print(f"   Confidence:     {summary['confidence_pct']}%")
    print(f"   Gamma Wall:     ₹{summary['gamma_wall']:,.2f}")
    print(f"   Distance:       {summary['distance_pct']:.3f}% from spot")
    print(f"   Est. Move:      ₹{summary['est_move']:,.2f}")

    print("\n⚡ Trigger Flags:")
    t = summary["triggers"]
    print(f"   Volume Spike:   {'✅ YES' if t['volume_spike'] else '❌ No'}")
    print(f"   OI Decay:       {'✅ YES' if t['oi_decay'] else '❌ No'}")
    print(f"   Delta Hedge:    {'✅ YES' if t['delta_hedge'] else '❌ No'}")

    print("\n📊 IPI Breakdown:")
    breakdown = summary.get("ipi_breakdown", {})
    for component, score in breakdown.items():
        bar = "█" * int(score)
        print(f"   {component:<28} {score:5.1f}  {bar}")

    # ── Generate trade signal ──────────────────────────────────────
    print("\n" + "═" * 65)
    print("   BREAKOUT ROUTING SIGNAL")
    print("═" * 65)

    available_strikes = sorted(set(o.strike for o in chain))
    router = BreakoutRouter(capital=500000, risk_pct=0.01)

    # Generate all 3 instrument types
    for instr in ["FUTURES", "OPTIONS", "SPREAD"]:
        trade = router.route(signal, "26-Jun-2025", available_strikes, instr)
        print(router.format_signal(trade))

    # ── GEX Profile summary ────────────────────────────────────────
    print("\n" + "═" * 65)
    print("   GEX PROFILE — TOP 10 STRIKES BY GAMMA EXPOSURE")
    print("═" * 65)
    gex_df = engine.gex_calc.compute_gex_profile(chain, SPOT, expiry_days=0.25)
    walls = engine.gex_calc.find_gamma_walls(gex_df, SPOT)

    print(f"\n   Call Wall:    ₹{walls['call_wall']:,.0f}")
    print(f"   Put Wall:     ₹{walls['put_wall']:,.0f}")
    print(f"   GEX Flip:     ₹{walls['flip_level']:,.0f}")
    print(f"   Squeeze Zone: ₹{walls['squeeze_zone']:,.0f}")
    print(f"   GEX Regime:   {walls['gex_regime']}")

    top10 = gex_df.nlargest(10, "net_gex")[
        ["strike", "net_gex", "call_oi", "put_oi", "iv_skew", "doi_net"]
    ]
    print(
        f"\n   {'Strike':>8} {'Net GEX(Cr)':>12} {'Call OI':>10} {'Put OI':>10} {'IV Skew':>8} {'ΔOI':>10}"
    )
    print("   " + "-" * 62)
    for _, row in top10.iterrows():
        marker = " ◄ WALL" if abs(row["strike"] - walls["call_wall"]) < 50 else ""
        print(
            f"   {row['strike']:>8,.0f} {row['net_gex']:>12.2f} {row['call_oi']:>10,.0f} "
            f"{row['put_oi']:>10,.0f} {row['iv_skew']:>8.3f} {row['doi_net']:>10,.0f}{marker}"
        )

    print("\n✅ Demo complete. Connect to NSE API for live data.\n")


# ══════════════════════════════════════════════════════════════════
# LIVE MODE
# ══════════════════════════════════════════════════════════════════


def run_live(symbols=["NIFTY", "BANKNIFTY"], alert_ipi=65.0):
    from signals.live_chain_monitor import LiveGammaMonitor

    def on_signal(signal_data):
        print(
            f"\n🔔 [{datetime.now().strftime('%H:%M:%S')}] SIGNAL — {signal_data['symbol']}"
        )
        print(f"   {signal_data['action']}")
        print(
            f"   IPI={signal_data['ipi_score']} | Confidence={signal_data['confidence_pct']}%"
        )

    monitor = LiveGammaMonitor(
        symbols=symbols,
        signal_callback=on_signal,
        alert_threshold=alert_ipi,
    )
    print(f"Starting live monitor for {symbols}...")
    print("Press Ctrl+C to stop.\n")
    monitor.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        monitor.stop()
        print("\nMonitor stopped.")


# ══════════════════════════════════════════════════════════════════
# API MODE
# ══════════════════════════════════════════════════════════════════


def run_api():
    import uvicorn

    print("Starting Gamma Squeeze API on http://0.0.0.0:8000")
    print("Docs: http://localhost:8000/docs\n")
    uvicorn.run("api.server:app", host="0.0.0.0", port=8000, reload=False)


# ══════════════════════════════════════════════════════════════════
# ENTRY POINT
# ══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Gamma Squeeze Intelligence Platform")
    parser.add_argument("--mode", choices=["live", "api", "demo"], default="demo")
    parser.add_argument("--symbols", nargs="+", default=["NIFTY", "BANKNIFTY"])
    parser.add_argument("--alert-ipi", type=float, default=65.0)
    args = parser.parse_args()

    if args.mode == "demo":
        run_demo()
    elif args.mode == "live":
        run_live(args.symbols, args.alert_ipi)
    elif args.mode == "api":
        run_api()
