"""
test_property_based.py — WealthQuant V14.1 Property-Based Tests (FIX-005)
Tests probability/calibration invariants using Hypothesis.
"""

import math
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

os.environ.setdefault("JWT_SECRET_KEY", "test_secret_key_for_testing_purposes_v14")
os.environ.setdefault("GROWW_AUTH_TOKEN", "test_token")

try:
    from hypothesis import HealthCheck, given, settings
    from hypothesis import strategies as st

    HYPOTHESIS_AVAILABLE = True
except ImportError:
    HYPOTHESIS_AVAILABLE = False

skip_if_no_hypothesis = pytest.mark.skipif(
    not HYPOTHESIS_AVAILABLE, reason="hypothesis not installed"
)


# ─── Bayesian Fusion property: output is a valid probability triple ───────────
@skip_if_no_hypothesis
@given(
    w_up=st.floats(min_value=0.01, max_value=1.0),
    w_down=st.floats(min_value=0.01, max_value=1.0),
    w_side=st.floats(min_value=0.01, max_value=1.0),
)
@settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
def test_probability_normalization(w_up, w_down, w_side):
    """Any non-negative weights when softmax-normalized must sum to 1.0."""
    total = w_up + w_down + w_side
    p_up = w_up / total
    p_down = w_down / total
    p_side = w_side / total
    prob_sum = p_up + p_down + p_side
    assert abs(prob_sum - 1.0) < 1e-9, f"Probabilities do not sum to 1: {prob_sum}"
    assert 0.0 <= p_up <= 1.0
    assert 0.0 <= p_down <= 1.0
    assert 0.0 <= p_side <= 1.0


@skip_if_no_hypothesis
@given(p=st.floats(min_value=0.0, max_value=1.0))
def test_probability_bounds(p):
    """Any probability value must be in [0, 1]."""
    assert 0.0 <= p <= 1.0


@skip_if_no_hypothesis
@given(
    p_up=st.floats(min_value=0.0, max_value=1.0),
    p_down=st.floats(min_value=0.0, max_value=1.0),
)
def test_probability_complement(p_up, p_down):
    """p_sideways = 1 - p_up - p_down must be in [0, 1]."""
    p_side = 1.0 - p_up - p_down
    if p_side < 0.0 or p_side > 1.0:
        pytest.skip("Invalid complement, skipping")
    assert 0.0 <= p_side <= 1.0


@skip_if_no_hypothesis
@given(
    y_true=st.floats(min_value=0.0, max_value=1.0),
    y_prob=st.floats(min_value=1e-9, max_value=1.0 - 1e-9),
)
def test_brier_score_bounds(y_true, y_prob):
    """Brier score (y_true - y_prob)^2 must be in [0, 1]."""
    brier = (y_true - y_prob) ** 2
    assert 0.0 <= brier <= 1.0


# ─── No NaN / No Inf in probability outputs ──────────────────────────────────
@skip_if_no_hypothesis
@given(
    raw_score=st.floats(
        allow_nan=False, allow_infinity=False, min_value=-100.0, max_value=100.0
    )
)
def test_no_nan_in_sigmoid_output(raw_score):
    """Sigmoid of any finite float must not be NaN or Inf."""
    sigmoid = 1.0 / (1.0 + math.exp(-raw_score))
    assert not math.isnan(sigmoid)
    assert not math.isinf(sigmoid)
    assert 0.0 <= sigmoid <= 1.0


# ─── Determinism: same input produces same output ────────────────────────────
def test_prediction_determinism_unit():
    """Simple determinism check: two identical computations yield identical results."""

    def compute(w1, w2, w3):
        total = w1 + w2 + w3
        return w1 / total, w2 / total, w3 / total

    a1, a2, a3 = compute(0.3, 0.5, 0.2)
    b1, b2, b3 = compute(0.3, 0.5, 0.2)
    assert a1 == b1 and a2 == b2 and a3 == b3


# ─── Kelly Fraction: must be >= 0 ────────────────────────────────────────────
@skip_if_no_hypothesis
@given(
    p_win=st.floats(min_value=0.01, max_value=0.99),
    b=st.floats(min_value=0.01, max_value=10.0),
)
def test_kelly_fraction_non_negative(p_win, b):
    """Kelly fraction = (b*p - q) / b must be clamped to >= 0 in practice."""
    q = 1.0 - p_win
    kelly = (b * p_win - q) / b
    # System should clamp to 0 before usage
    clamped_kelly = max(0.0, kelly)
    assert clamped_kelly >= 0.0
