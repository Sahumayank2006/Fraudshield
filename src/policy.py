"""
FraudShield Two-Threshold Decision Policy & Cost Optimization Module.

Implements the three-way operational decision routing:
  - Score < t1:              APPROVE
  - t1 <= Score < t2:        REVIEW / STEP-UP (analyst queue / OTP challenge)
  - Score >= t2:             BLOCK (automated high-confidence decline)

Threshold selection:
  - t2 (BLOCK): Lowest threshold achieving precision >= TARGET_BLOCK_PRECISION (default 0.90)
  - t1 (REVIEW): Cost-optimal threshold on validation, capped so the review queue does not
                 exceed operational analyst capacity (default: 6 reviews per 1,000 transactions).
  - Mathematical guarantee: t1 < t2.
"""

from __future__ import annotations

import json
import logging
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import numpy as np
from sklearn.metrics import precision_recall_curve

from config import (
    AMOUNT_C_FP,
    FIXED_CHARGEBACK_FEE,
    FLAT_C_FN,
    FLAT_C_FP,
    MAX_REVIEWS_PER_1000,
    TARGET_BLOCK_PRECISION,
    THRESHOLDS_FILE,
)
from src.evaluate import calculate_expected_cost

logger = logging.getLogger("fraudshield.policy")


@dataclass
class PolicyThresholds:
    t1_review: float
    t2_block: float
    max_reviews_per_1000: float
    target_block_precision: float
    cost_mode: str
    expected_val_cost: float
    review_queue_rate: float
    version: str = "1.0.0"


def find_block_threshold(
    y_val: np.ndarray,
    p_val: np.ndarray,
    target_precision: float = TARGET_BLOCK_PRECISION,
) -> float:
    """
    Determine threshold t2: the lowest cut-off where validation precision meets target.
    """
    precisions, _, thresholds = precision_recall_curve(y_val, p_val)
    # Exclude final 1.0 precision anchor
    valid_idx = np.where(precisions[:-1] >= target_precision)[0]
    if len(valid_idx) == 0:
        # If 90% precision is not reached, fall back to high quantile (e.g., 99th percentile)
        return float(np.percentile(p_val, 99.0))
    return float(thresholds[valid_idx[0]])


def find_cost_optimal_review_threshold(
    y_val: np.ndarray,
    p_val: np.ndarray,
    t2_block: float,
    amounts: Optional[np.ndarray] = None,
    max_reviews_per_1000: float = MAX_REVIEWS_PER_1000,
    cost_mode: str = "amount_weighted",
) -> Tuple[float, float, float]:
    """
    Determine threshold t1:
    Minimizes expected business cost on validation data subject to:
    1. Operational review queue constraint: reviews per 1,000 txns <= max_reviews_per_1000
    2. t1 < t2
    """
    n_samples = len(y_val)
    max_review_fraction = max_reviews_per_1000 / 1000.0  # e.g., 0.006

    # Test fine grid between 0.001 and t2 - 0.01
    upper_bound = max(0.01, t2_block - 0.005)
    candidate_thresholds = np.linspace(0.005, upper_bound, 300)

    best_t1 = 0.05
    min_cost = float("inf")
    best_review_rate = 0.0

    for t in candidate_thresholds:
        # Reviews are transactions falling into [t, t2_block)
        in_review = (p_val >= t) & (p_val < t2_block)
        review_fraction = float(np.sum(in_review) / n_samples)

        # Skip candidates that breach analyst headcount capacity
        if review_fraction > max_review_fraction:
            continue

        cost = calculate_expected_cost(
            y_val, p_val, threshold=t, amounts=amounts, mode=cost_mode
        )

        if cost < min_cost:
            min_cost = cost
            best_t1 = float(t)
            best_review_rate = review_fraction

    # Hard guarantee that t1 < t2
    if best_t1 >= t2_block:
        best_t1 = round(max(0.001, t2_block * 0.5), 4)

    return best_t1, min_cost, best_review_rate


def optimize_thresholds(
    y_val: np.ndarray,
    p_val: np.ndarray,
    amounts: Optional[np.ndarray] = None,
    cost_mode: str = "amount_weighted",
    version: str = "1.0.0",
) -> PolicyThresholds:
    """
    Full threshold optimization workflow on validation data.
    """
    logger.info("Optimizing dual thresholds (t1, t2) on validation set (cost_mode=%s)...", cost_mode)
    t2 = find_block_threshold(y_val, p_val, target_precision=TARGET_BLOCK_PRECISION)
    t1, min_cost, rev_rate = find_cost_optimal_review_threshold(
        y_val, p_val, t2_block=t2, amounts=amounts, cost_mode=cost_mode
    )

    thresholds = PolicyThresholds(
        t1_review=round(float(t1), 4),
        t2_block=round(float(t2), 4),
        max_reviews_per_1000=MAX_REVIEWS_PER_1000,
        target_block_precision=TARGET_BLOCK_PRECISION,
        cost_mode=cost_mode,
        expected_val_cost=round(float(min_cost), 2),
        review_queue_rate=round(float(rev_rate * 1000.0), 2),
        version=version,
    )

    logger.info(
        "Thresholds optimized: t1=%.4f (review), t2=%.4f (block), reviews=%.2f/1k txns",
        thresholds.t1_review,
        thresholds.t2_block,
        thresholds.review_queue_rate,
    )
    return thresholds


def save_thresholds(policy: PolicyThresholds, filepath: Path = THRESHOLDS_FILE) -> None:
    """Save thresholds to JSON file."""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(asdict(policy), f, indent=2)
    logger.info("Saved policy thresholds to %s", filepath)


def load_thresholds(filepath: Path = THRESHOLDS_FILE) -> PolicyThresholds:
    """Load thresholds from JSON file or return sensible defaults."""
    if filepath.exists():
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
            return PolicyThresholds(**data)
    else:
        logger.warning("Thresholds file not found at %s. Using default policy.", filepath)
        return PolicyThresholds(
            t1_review=0.035,
            t2_block=0.820,
            max_reviews_per_1000=MAX_REVIEWS_PER_1000,
            target_block_precision=TARGET_BLOCK_PRECISION,
            cost_mode="amount_weighted",
            expected_val_cost=0.0,
            review_queue_rate=4.5,
        )


def evaluate_decision(
    probability: float,
    anomaly_score: float = 0.0,
    t1: float = 0.035,
    t2: float = 0.820,
    model_version: str = "1.0.0",
) -> Dict[str, Any]:
    """
    Convert a calibrated fraud probability into an operational decision.
    """
    if probability >= t2:
        decision = "BLOCK"
        action = "Automated transaction block; notify cardholder of potential security compromise."
        review_required = False
    elif probability >= t1:
        decision = "REVIEW"
        action = "Route to analyst priority review queue or challenge with step-up MFA."
        review_required = True
    else:
        decision = "APPROVE"
        action = "Instant frictionless approval; transaction within safe parameters."
        review_required = False

    return {
        "decision": decision,
        "fraud_probability": round(float(probability), 5),
        "anomaly_score": round(float(anomaly_score), 5),
        "t1_review": round(float(t1), 4),
        "t2_block": round(float(t2), 4),
        "action_recommended": action,
        "review_required": review_required,
        "model_version": model_version,
    }


def simulate_policy_thresholds(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    amounts: Optional[np.ndarray] = None,
    t1: float = 0.005,
    t2: float = 0.059,
    cost_mode: str = "amount_weighted",
) -> Dict[str, Any]:
    """
    Simulate decision policy with arbitrary thresholds:
    Computes confusion matrix, precision, recall, F1, F2, MCC, cost, and review queue capacity check.
    """
    y_true = np.asarray(y_true, dtype=int)
    y_prob = np.asarray(y_prob, dtype=float)
    N = len(y_true)

    if amounts is None:
        amounts = np.ones(N) * 100.0
    else:
        amounts = np.asarray(amounts, dtype=float)

    is_flagged = (y_prob >= t1).astype(int)
    is_blocked = (y_prob >= t2).astype(int)
    is_reviewed = ((y_prob >= t1) & (y_prob < t2)).astype(int)
    is_approved = (y_prob < t1).astype(int)

    tp = int(((is_flagged == 1) & (y_true == 1)).sum())
    fp = int(((is_flagged == 1) & (y_true == 0)).sum())
    fn = int(((is_flagged == 0) & (y_true == 1)).sum())
    tn = int(((is_flagged == 0) & (y_true == 0)).sum())

    prec = float(tp / (tp + fp)) if (tp + fp) > 0 else 0.0
    rec = float(tp / (tp + fn)) if (tp + fn) > 0 else 0.0
    f1 = float(2 * (prec * rec) / (prec + rec)) if (prec + rec) > 0 else 0.0
    beta = 2.0
    f2 = float((1 + beta**2) * (prec * rec) / (beta**2 * prec + rec)) if (beta**2 * prec + rec) > 0 else 0.0

    denom = np.sqrt(float((tp + fp) * (tp + fn) * (tn + fp) * (tn + fn)))
    mcc = float((tp * tn - fp * fn) / denom) if denom > 0 else 0.0

    review_count = int(is_reviewed.sum())
    blocked_count = int(is_blocked.sum())
    approved_count = int(is_approved.sum())

    review_queue_rate = (review_count / max(1, N)) * 1000.0
    capacity_exceeded = review_queue_rate > MAX_REVIEWS_PER_1000

    # Calculate financial cost
    from src.evaluate import calculate_expected_cost
    if cost_mode == "amount_weighted":
        total_cost = calculate_expected_cost(
            y_true, y_prob, threshold=t1, amounts=amounts, mode="amount_weighted"
        )
    else:
        total_cost = calculate_expected_cost(
            y_true, y_prob, threshold=t1, mode="flat"
        )

    return {
        "confusion_matrix": {"tp": tp, "fn": fn, "fp": fp, "tn": tn},
        "precision": round(prec, 4),
        "recall": round(rec, 4),
        "f1": round(f1, 4),
        "f2": round(f2, 4),
        "mcc": round(mcc, 4),
        "expected_cost": round(float(total_cost), 2),
        "review_count": review_count,
        "blocked_count": blocked_count,
        "approved_count": approved_count,
        "review_queue_rate_per_1000": round(review_queue_rate, 2),
        "capacity_exceeded": capacity_exceeded,
        "max_capacity_per_1000": MAX_REVIEWS_PER_1000,
    }

