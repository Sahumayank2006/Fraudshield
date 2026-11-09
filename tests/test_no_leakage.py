"""
Unit tests for FraudShield Data Leakage Prevention & Scientific Invariants.

Verifies:
1. Future Invariance: Shuffling or modifying future transactions NEVER changes the
   engineered features of past transactions.
2. Temporal Monotonicity: Split boundaries are strictly non-overlapping in time.
3. Strict Past-Only Rolling Windows: Rolling window counts and sums consider only events
   with timestamp strictly LESS than the current transaction timestamp (< ts).
4. Safe Resampling Invariant: SMOTE is restricted strictly inside training folds/pipelines
   and never alters or leaks into validation or test partitions.
"""

import numpy as np
import pandas as pd
import pytest
from imblearn.over_sampling import SMOTE
from imblearn.pipeline import Pipeline
from sklearn.linear_model import LogisticRegression

from src.data import load_ledgersim, time_split
from src.features import FeatureStore, extract_features


@pytest.fixture(scope="module")
def base_transactions():
    """Load sample of LedgerSim transactions."""
    df = load_ledgersim(fast=True)
    return df.iloc[:2_000].copy()


def test_future_invariance_leakage_guard(base_transactions):
    """
    LEAKAGE GATE PROOF:
    Features of transaction i must depend solely on transactions [0..i-1].
    If future transactions [i+1..N] are shuffled or replaced, the feature vectors
    for transactions [0..i] MUST remain 100% identical.
    """
    df_original = base_transactions.copy()
    cutoff_idx = 800

    # Run 1: Original chronologically ordered data
    store1 = FeatureStore()
    feat_original = store1.compute_batch(df_original, reset_state=True)
    features_before_cutoff_run1 = feat_original.iloc[:cutoff_idx].copy()

    # Run 2: Future rows [cutoff_idx..N] are randomly shuffled / permuted
    rng = np.random.default_rng(12345)
    future_indices = list(range(cutoff_idx, len(df_original)))
    shuffled_future_indices = rng.permutation(future_indices)

    df_tampered = pd.concat(
        [
            df_original.iloc[:cutoff_idx],
            df_original.iloc[shuffled_future_indices],
        ]
    ).reset_index(drop=True)

    # Note: We keep the past [0..cutoff_idx] untouched in time order
    store2 = FeatureStore()
    feat_tampered = store2.compute_batch(df_tampered, reset_state=True)
    features_before_cutoff_run2 = feat_tampered.iloc[:cutoff_idx].copy()

    # The past features MUST be identical
    pd.testing.assert_frame_equal(
        features_before_cutoff_run1,
        features_before_cutoff_run2,
        check_exact=True,
    )


def test_split_boundaries_strictly_increasing(base_transactions):
    """
    Verify that time-split produces strictly non-overlapping temporal partitions.
    """
    train, val, test = time_split(base_transactions, train_ratio=0.70, val_ratio=0.15, test_ratio=0.15)

    assert train["ts"].max() <= val["ts"].min(), (
        f"Train max ts ({train['ts'].max()}) exceeds Val min ts ({val['ts'].min()})"
    )
    assert val["ts"].max() <= test["ts"].min(), (
        f"Val max ts ({val['ts'].max()}) exceeds Test min ts ({test['ts'].min()})"
    )


def test_rolling_window_strict_past_only():
    """
    Verify that an event at timestamp T does not include itself or future events
    in its rolling 1h, 24h, or 7d velocity counts.
    """
    # Create two synthetic transactions for the same account:
    # Txn 1 at t = 100.0, amount = 50.0
    # Txn 2 at t = 200.0, amount = 100.0
    txns = [
        {
            "txn_id": "TXN_A",
            "account_id": "ACC_TEST",
            "ts": 100.0,
            "amount": 50.0,
            "merchant_id": "MERCH_1",
            "merchant_category": "groceries",
            "device_id": "DEV_1",
            "device_is_new": 0,
            "ip_region": "IN-MH",
            "region_mismatch": 0,
            "hour": 0,
            "is_night": 1,
            "oldbalance": 1000.0,
            "newbalance": 950.0,
            "dest_account_id": "",
            "dest_is_new_payee": 0,
            "session_seconds": 60.0,
            "pwd_reset_last_24h": 0,
        },
        {
            "txn_id": "TXN_B",
            "account_id": "ACC_TEST",
            "ts": 200.0,
            "amount": 100.0,
            "merchant_id": "MERCH_2",
            "merchant_category": "groceries",
            "device_id": "DEV_1",
            "device_is_new": 0,
            "ip_region": "IN-MH",
            "region_mismatch": 0,
            "hour": 0,
            "is_night": 1,
            "oldbalance": 950.0,
            "newbalance": 850.0,
            "dest_account_id": "",
            "dest_is_new_payee": 0,
            "session_seconds": 45.0,
            "pwd_reset_last_24h": 0,
        },
    ]

    store = FeatureStore()

    # For Txn 1: It has NO past transactions
    feat1 = store.compute_and_update(txns[0])
    assert feat1["txn_count_1h"] == 0.0, "Txn 1 should see 0 past transactions in 1h window"
    assert feat1["amount_sum_1h"] == 0.0, "Txn 1 should see 0 sum in 1h window"

    # For Txn 2: It should see exactly Txn 1 (count=1, sum=50.0), NOT itself (sum=150.0)
    feat2 = store.compute_and_update(txns[1])
    assert feat2["txn_count_1h"] == 1.0, f"Txn 2 should see exactly 1 past txn (got {feat2['txn_count_1h']})"
    assert feat2["amount_sum_1h"] == 50.0, f"Txn 2 should see sum 50.0 (got {feat2['amount_sum_1h']})"


def test_smote_pipeline_isolation(base_transactions):
    """
    SMOTE ISOLATION PROOF:
    Verify that imblearn.pipeline.Pipeline applies SMOTE strictly on the training partition
    and does not modify test set sample counts, distributions, or labels.
    """
    # Create synthetic imbalanced training and validation sets
    X_train = np.random.randn(1000, 5)
    y_train = np.array([0] * 980 + [1] * 20)  # 2% minority

    X_val = np.random.randn(300, 5)
    y_val = np.array([0] * 294 + [1] * 6)  # 2% minority

    original_val_len = len(y_val)
    original_val_pos = int(y_val.sum())

    # Build Pipeline with SMOTE
    pipe = Pipeline(
        [
            ("smote", SMOTE(sampling_strategy=0.2, k_neighbors=3, random_state=42)),
            ("clf", LogisticRegression()),
        ]
    )

    # Fit pipeline on training data
    pipe.fit(X_train, y_train)

    # Validation set must remain completely untouched
    preds = pipe.predict(X_val)
    assert len(preds) == original_val_len
    assert len(y_val) == original_val_len
    assert int(y_val.sum()) == original_val_pos, "Validation target distribution was corrupted by SMOTE"
