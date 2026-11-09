"""
Unit tests for FraudShield Metrics & Evaluation Module.

Checks:
- Hand-computed worked example from Report Section 10.3:
    Input: N=100,000, TP=160, FN=40, FP=80, TN=99,720
    Expected: Precision=0.667, Recall=0.800, F1=0.727, F2=0.769, FPR=0.080%, MCC=0.730
- Bootstrap Confidence Interval invariants: ci_lower <= median <= ci_upper
- Recall at precision monotonicity
- Expected cost calculation under flat and amount-weighted modes
"""

import math
import numpy as np
import pytest

from src.evaluate import (
    bootstrap_metric_ci,
    calculate_expected_cost,
    compute_confusion_metrics,
    recall_at_precision,
)


def test_hand_computed_worked_example_from_report():
    """
    MATHEMATICAL BENCHMARK:
    Exact verification against the academic report Section 10.3 worked example:
    TP=160, FN=40, FP=80, TN=99,720.
    """
    tp, fn, fp, tn = 160, 40, 80, 99_720

    metrics = compute_confusion_metrics(tp, fn, fp, tn, c_fn=100.0, c_fp=1.0)

    # 1. Accuracy: 99.88%
    assert math.isclose(metrics["accuracy"], 0.9988, abs_tol=1e-4)

    # 2. Precision: 0.667 (160 / 240)
    assert math.isclose(metrics["precision"], 0.6667, abs_tol=1e-3)

    # 3. Recall: 0.800 (160 / 200)
    assert math.isclose(metrics["recall"], 0.8000, abs_tol=1e-4)

    # 4. F1: 0.727
    assert math.isclose(metrics["f1"], 0.7273, abs_tol=1e-3)

    # 5. F2 (recall-weighted beta=2): 0.769
    assert math.isclose(metrics["f2"], 0.7692, abs_tol=1e-3)

    # 6. False-Positive Rate: 0.080%
    assert math.isclose(metrics["fpr"], 0.0008, abs_tol=1e-4)

    # 7. Matthews Correlation Coefficient (MCC): 0.730
    assert math.isclose(metrics["mcc"], 0.7303, abs_tol=1e-3)

    # 8. Expected cost: 40 * 100 + 80 * 1 = 4080
    assert metrics["expected_cost"] == 4080.0


def test_recall_at_precision_monotonicity():
    """Higher precision constraints must yield lower or equal recall."""
    y_true = np.array([0] * 950 + [1] * 50)
    rng = np.random.default_rng(42)
    # Generate realistic probabilities: higher for fraud
    y_prob = np.where(y_true == 1, rng.beta(5, 2, size=len(y_true)), rng.beta(1, 10, size=len(y_true)))

    rec_80 = recall_at_precision(y_true, y_prob, target_precision=0.80)
    rec_90 = recall_at_precision(y_true, y_prob, target_precision=0.90)

    assert rec_80 >= rec_90, f"Recall@P80 ({rec_80}) should be >= Recall@P90 ({rec_90})"


def test_bootstrap_confidence_intervals_bounds():
    """Verify that bootstrap confidence intervals produce ordered bounds."""
    y_true = np.array([0] * 900 + [1] * 100)
    y_prob = np.random.uniform(0.0, 1.0, size=1000)

    ci = bootstrap_metric_ci(y_true, y_prob, metric_name="pr_auc", n_bootstraps=200, seed=42)

    assert 0.0 <= ci["ci_lower"] <= ci["median"] <= ci["ci_upper"] <= 1.0, (
        f"Bootstrap bounds violated: {ci}"
    )


def test_expected_cost_calculation():
    """Verify financial cost calculation in flat and amount-weighted modes."""
    y_true = np.array([1, 1, 0, 0])
    y_prob = np.array([0.9, 0.2, 0.8, 0.1])
    amounts = np.array([500.0, 200.0, 50.0, 20.0])

    # Threshold = 0.5:
    # item 0 (y=1, p=0.9): TP
    # item 1 (y=1, p=0.2): FN -> loss
    # item 2 (y=0, p=0.8): FP -> friction
    # item 3 (y=0, p=0.1): TN

    # Flat cost: C_FN=100, C_FP=1 -> 1 * 100 + 1 * 1 = 101.0
    cost_flat = calculate_expected_cost(y_true, y_prob, threshold=0.5, mode="flat")
    assert cost_flat == 101.0

    # Amount cost: FN amount = 200 + 15 fee = 215. FP cost = 5. Total = 220.0
    cost_amt = calculate_expected_cost(
        y_true, y_prob, threshold=0.5, amounts=amounts, mode="amount_weighted"
    )
    assert cost_amt == 220.0

