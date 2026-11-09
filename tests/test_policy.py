"""
Unit tests for FraudShield Decision Policy & Cost Optimization.

Checks:
- Mathematical guarantee: t1 (review) < t2 (block)
- Cost-optimal threshold beats the default 0.5 threshold on imbalanced fraud data
- Operational three-way decision routing (APPROVE, REVIEW, BLOCK)
- Analyst queue capacity constraint (MAX_REVIEWS_PER_1000)
"""

import numpy as np
import pytest

from src.evaluate import calculate_expected_cost
from src.policy import evaluate_decision, optimize_thresholds


@pytest.fixture
def synthetic_val_data():
    """Create realistic validation data with 0.5% fraud prevalence."""
    rng = np.random.default_rng(42)
    n = 10_000
    n_pos = 50
    y_val = np.array([1] * n_pos + [0] * (n - n_pos))

    # Well-separated probabilities: frauds have higher scores
    p_fraud = rng.beta(6, 2, size=n_pos)
    p_legit = rng.beta(1, 20, size=n - n_pos)
    p_val = np.concatenate([p_fraud, p_legit])

    amounts = rng.lognormal(4.0, 1.0, size=n)

    # Shuffle to simulate random validation set
    perm = rng.permutation(n)
    return y_val[perm], p_val[perm], amounts[perm]


def test_t1_strictly_less_than_t2(synthetic_val_data):
    """Verify that t1 (review) is strictly less than t2 (block)."""
    y_val, p_val, amounts = synthetic_val_data
    policy = optimize_thresholds(y_val, p_val, amounts=amounts, cost_mode="flat")

    assert policy.t1_review < policy.t2_block, (
        f"Threshold invariant violated: t1 ({policy.t1_review}) >= t2 ({policy.t2_block})"
    )


def test_cost_optimal_threshold_beats_default_half(synthetic_val_data):
    """
    Cost Optimization Proof:
    On imbalanced data with asymmetric costs (C_FN=100, C_FP=1),
    the cost-optimal threshold must produce significantly lower total cost than 0.5.
    """
    y_val, p_val, amounts = synthetic_val_data
    policy = optimize_thresholds(y_val, p_val, amounts=amounts, cost_mode="flat")

    cost_at_optimal = calculate_expected_cost(y_val, p_val, threshold=policy.t1_review, mode="flat")
    cost_at_half = calculate_expected_cost(y_val, p_val, threshold=0.5, mode="flat")

    assert cost_at_optimal < cost_at_half, (
        f"Cost at optimal threshold ({cost_at_optimal}) did not beat threshold 0.5 ({cost_at_half})"
    )


def test_decision_routing_states():
    """Verify exact routing into APPROVE, REVIEW, and BLOCK operational buckets."""
    t1, t2 = 0.05, 0.85

    # 1. Low score -> APPROVE
    res_app = evaluate_decision(probability=0.02, t1=t1, t2=t2)
    assert res_app["decision"] == "APPROVE"
    assert res_app["review_required"] is False

    # 2. Medium score -> REVIEW
    res_rev = evaluate_decision(probability=0.25, t1=t1, t2=t2)
    assert res_rev["decision"] == "REVIEW"
    assert res_rev["review_required"] is True

    # 3. High score -> BLOCK
    res_blk = evaluate_decision(probability=0.92, t1=t1, t2=t2)
    assert res_blk["decision"] == "BLOCK"
    assert res_blk["review_required"] is False


def test_analyst_capacity_ceiling(synthetic_val_data):
    """Verify review queue does not exceed the configured capacity per 1,000 transactions."""
    y_val, p_val, amounts = synthetic_val_data
    policy = optimize_thresholds(y_val, p_val, amounts=amounts, cost_mode="amount_weighted")

    # The review queue rate per 1,000 transactions must not exceed max allowed
    assert policy.review_queue_rate <= policy.max_reviews_per_1000 + 0.1

