"""
WealthQuant V7.1 — Unit Test Suite for Options Pricing Engine
Tests BSM pricing, 10 Greeks, dual IV solver, position Rupee-Greeks, and edge cases.
"""

import math
import unittest

from core.options_pricing import (
    RBI_REPO_RATE,
    BSMEngine,
    IVSolver,
    OptionContract,
    OptionType,
)


class TestBSMEngine(unittest.TestCase):
    def setUp(self):
        self.S = 24000.0
        self.K = 24000.0
        self.T = 30.0 / 252.0  # 30 trading days
        self.r = RBI_REPO_RATE  # 0.065
        self.q = 0.012  # NIFTY dividend yield
        self.sigma = 0.15  # 15% IV

    def test_call_put_pricing_benchmark(self):
        call_price, d1, d2 = BSMEngine.price(
            self.S, self.K, self.T, self.r, self.q, self.sigma, OptionType.CALL
        )
        put_price, _, _ = BSMEngine.price(
            self.S, self.K, self.T, self.r, self.q, self.sigma, OptionType.PUT
        )

        self.assertGreater(call_price, 0.0)
        self.assertGreater(put_price, 0.0)
        # Call should be higher than put when r > q for ATM option
        self.assertGreater(call_price, put_price)

    def test_put_call_parity(self):
        call_price, _, _ = BSMEngine.price(
            self.S, self.K, self.T, self.r, self.q, self.sigma, OptionType.CALL
        )
        put_price, _, _ = BSMEngine.price(
            self.S, self.K, self.T, self.r, self.q, self.sigma, OptionType.PUT
        )

        forward = BSMEngine._forward(self.S, self.r, self.q, self.T)
        lhs = call_price - put_price
        rhs = (forward - self.K) * math.exp(-self.r * self.T)

        self.assertAlmostEqual(lhs, rhs, places=4)

    def test_first_order_greeks_finite_difference(self):
        greeks = BSMEngine.compute_all_greeks(
            self.S, self.K, self.T, self.r, self.q, self.sigma, OptionType.CALL
        )

        # 1. Delta via numerical derivative
        dS = 0.1
        p_up, _, _ = BSMEngine.price(
            self.S + dS, self.K, self.T, self.r, self.q, self.sigma, OptionType.CALL
        )
        p_dn, _, _ = BSMEngine.price(
            self.S - dS, self.K, self.T, self.r, self.q, self.sigma, OptionType.CALL
        )
        num_delta = (p_up - p_dn) / (2 * dS)
        self.assertAlmostEqual(greeks.delta, num_delta, places=3)

        # 2. Gamma via 2nd numerical derivative
        p_mid, _, _ = BSMEngine.price(
            self.S, self.K, self.T, self.r, self.q, self.sigma, OptionType.CALL
        )
        num_gamma = (p_up - 2 * p_mid + p_dn) / (dS**2)
        self.assertAlmostEqual(greeks.gamma, num_gamma, places=4)

        # 3. Vega via numerical derivative (per 1% IV)
        dVol = 0.0001
        p_vup, _, _ = BSMEngine.price(
            self.S, self.K, self.T, self.r, self.q, self.sigma + dVol, OptionType.CALL
        )
        p_vdn, _, _ = BSMEngine.price(
            self.S, self.K, self.T, self.r, self.q, self.sigma - dVol, OptionType.CALL
        )
        num_vega = (p_vup - p_vdn) / (2 * dVol * 100.0)
        self.assertAlmostEqual(greeks.vega, num_vega, places=3)

    def test_position_rupee_greeks(self):
        contract = OptionContract(
            underlying="NIFTY",
            option_type=OptionType.CALL,
            strike=24000.0,
            expiry_date="2026-08-20",
            spot=24000.0,
            iv=0.15,
            T=30.0 / 252.0,
            lot_size=50,
        )
        res = BSMEngine.full_pricing(contract, oi=100000.0)

        self.assertGreater(res.greeks.delta_rupee, 0.0)
        self.assertGreater(res.greeks.gamma_rupee, 0.0)
        self.assertGreater(res.greeks.vega_rupee, 0.0)
        self.assertLess(res.greeks.theta_rupee, 0.0)
        self.assertGreater(res.greeks.gex_contribution, 0.0)

    def test_expiry_boundary_condition(self):
        price, d1, d2 = BSMEngine.price(
            self.S,
            self.K,
            T=1e-7,
            r=self.r,
            q=self.q,
            sigma=self.sigma,
            option_type=OptionType.CALL,
        )
        self.assertEqual(price, max(self.S - self.K, 0.0))


class TestIVSolver(unittest.TestCase):
    def setUp(self):
        self.S = 24000.0
        self.K = 24000.0
        self.T = 20.0 / 252.0
        self.r = RBI_REPO_RATE
        self.q = 0.012
        self.target_iv = 0.18

    def test_newton_raphson_convergence(self):
        market_price, _, _ = BSMEngine.price(
            self.S, self.K, self.T, self.r, self.q, self.target_iv, OptionType.CALL
        )
        iv, iters, converged = IVSolver.newton_raphson(
            market_price, self.S, self.K, self.T, self.r, self.q, OptionType.CALL
        )

        self.assertTrue(converged)
        self.assertLessEqual(iters, 10)
        self.assertAlmostEqual(iv, self.target_iv, places=5)

    def test_brent_fallback_on_deep_itm(self):
        K_itm = 18000.0
        market_price, _, _ = BSMEngine.price(
            self.S, K_itm, self.T, self.r, self.q, self.target_iv, OptionType.CALL
        )
        iv, brent_ok = IVSolver.brentq_solver(
            market_price, self.S, K_itm, self.T, self.r, self.q, OptionType.CALL
        )

        self.assertTrue(brent_ok)
        self.assertAlmostEqual(iv, self.target_iv, places=4)

    def test_master_solver_diagnostics(self):
        market_price, _, _ = BSMEngine.price(
            self.S, self.K, self.T, self.r, self.q, self.target_iv, OptionType.PUT
        )
        diag = IVSolver.solve(
            market_price, self.S, self.K, self.T, self.r, self.q, OptionType.PUT
        )

        self.assertTrue(diag["converged"])
        self.assertTrue(diag["reliable"])
        self.assertAlmostEqual(diag["iv"], self.target_iv, places=5)


if __name__ == "__main__":
    unittest.main()
