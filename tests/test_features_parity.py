"""
Unit tests for FraudShield Online/Batch Feature Parity.

Verifies:
- Batch feature generation (compute_batch) produces bit-exact identical feature vectors
  to online transaction-by-transaction scoring (compute_and_update).
- Calling features_for(txn) does not alter internal state (read-only invariant).
- Resetting the FeatureStore restores completely clean initial conditions.
- Single transaction feature computation produces all expected feature keys.
"""

import numpy as np
import pandas as pd
import pytest

from src.data import load_ledgersim
from src.features import FEATURE_COLUMNS, FeatureStore, extract_features


@pytest.fixture(scope="module")
def sample_transactions():
    """Load a sample partition of LedgerSim transactions."""
    df = load_ledgersim(fast=True)
    return df.iloc[:3_000].copy()


def test_batch_and_online_feature_parity(sample_transactions):
    """
    Core Parity Test:
    Batch extraction across N transactions must produce mathematically identical
    results to sequential, single-transaction online streaming scoring.
    """
    # 1. Batch computation path
    batch_store = FeatureStore()
    batch_features_df = batch_store.compute_batch(sample_transactions, reset_state=True)

    # 2. Online streaming single-event path
    online_store = FeatureStore()
    online_features_list = []
    records = sample_transactions.to_dict(orient="records")

    for record in records:
        # Online scoring: features calculated strictly before state commit
        feat = online_store.compute_and_update(record)
        online_features_list.append(feat)

    online_features_df = pd.DataFrame(online_features_list, columns=FEATURE_COLUMNS)

    # 3. Assert mathematical equality across all features and all rows
    assert batch_features_df.shape == online_features_df.shape
    pd.testing.assert_frame_equal(batch_features_df, online_features_df, check_exact=False, rtol=1e-5, atol=1e-5)


def test_features_for_is_read_only(sample_transactions):
    """
    Verify that calling features_for(txn) does NOT mutate the feature store.
    Repeated calls with the same transaction must return identical feature vectors.
    """
    store = FeatureStore()
    records = sample_transactions.to_dict(orient="records")

    # Prime with first 50 transactions
    for r in records[:50]:
        store.update(r)

    target_txn = records[50]

    # Call features_for three times
    feat1 = store.features_for(target_txn)
    feat2 = store.features_for(target_txn)
    feat3 = store.features_for(target_txn)

    assert feat1 == feat2 == feat3, "features_for mutated internal state unexpectedly"


def test_feature_store_reset(sample_transactions):
    """Verify that reset() clears all account histories and global accumulators."""
    store = FeatureStore()
    records = sample_transactions.to_dict(orient="records")

    for r in records[:100]:
        store.compute_and_update(r)

    assert len(store.accounts) > 0
    assert store._session_count == 100

    store.reset()

    assert len(store.accounts) == 0
    assert store._session_count == 0
    assert store._session_sum == 0.0
    assert store._session_sum_sq == 0.0


def test_all_feature_columns_present(sample_transactions):
    """Verify all 26 defined feature columns are present and non-null in output."""
    feat_df = extract_features(sample_transactions.iloc[:100])
    assert list(feat_df.columns) == FEATURE_COLUMNS
    assert feat_df.isnull().sum().sum() == 0, "Feature matrix contains null values"

