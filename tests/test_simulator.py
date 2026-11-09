"""
Unit tests for FraudShield LedgerSim Synthetic Banking Generator.

Checks:
- Determinism by seed: identical outputs for identical seeds
- Fraud rate is within the targeted operational window (0.5% to 0.8%)
- All required columns and entity attributes are present and non-null
- All five distinct fraud typologies are generated
- Concept drift segment creates a statistically significant distribution shift (KS test)
"""

import numpy as np
import pandas as pd
import pytest
from scipy import stats

from src.simulator import LedgerSim


@pytest.fixture(scope="module")
def sim_data():
    """Generate a small deterministic simulation dataset for testing."""
    sim = LedgerSim(
        num_transactions=15_000,
        num_days=10,
        num_accounts=1_000,
        num_merchants=100,
        fraud_rate_target=0.0065,
        drift_start_ratio=0.75,
        seed=42,
    )
    return sim.generate()


def test_determinism_by_seed():
    """Verify that identical random seeds produce 100% bit-exact DataFrames."""
    sim1 = LedgerSim(
        num_transactions=2_000,
        num_days=5,
        num_accounts=200,
        num_merchants=50,
        seed=123,
    )
    sim2 = LedgerSim(
        num_transactions=2_000,
        num_days=5,
        num_accounts=200,
        num_merchants=50,
        seed=123,
    )
    df1 = sim1.generate()
    df2 = sim2.generate()

    pd.testing.assert_frame_equal(df1, df2)


def test_fraud_rate_in_range(sim_data):
    """Verify overall fraud rate is within the expected 0.5% - 0.8% window."""
    rate = sim_data["is_fraud"].mean()
    assert 0.0050 <= rate <= 0.0080, f"Fraud rate {rate:.4f} outside [0.005, 0.008]"


def test_required_columns_present(sim_data):
    """Verify all 22 required columns are present with valid non-null records."""
    required_cols = [
        "txn_id",
        "ts",
        "account_id",
        "merchant_id",
        "merchant_category",
        "amount",
        "channel",
        "device_id",
        "device_is_new",
        "ip_region",
        "region_mismatch",
        "hour",
        "is_night",
        "oldbalance",
        "newbalance",
        "dest_account_id",
        "dest_is_new_payee",
        "session_seconds",
        "pwd_reset_last_24h",
        "is_fraud",
        "fraud_type",
        "label_mature_ts",
    ]
    for col in required_cols:
        assert col in sim_data.columns, f"Missing required column: {col}"
        assert sim_data[col].isnull().sum() == 0, f"Column {col} contains null values"


def test_all_five_typologies_present(sim_data):
    """Verify that all five specific fraud typologies are generated."""
    typologies = sim_data[sim_data["is_fraud"] == 1]["fraud_type"].unique()
    expected = {"card_testing", "cnp", "ato", "mule_chain", "app"}
    assert expected.issubset(set(typologies)), f"Missing typologies: {expected - set(typologies)}"


def test_time_strictly_monotonic(sim_data):
    """Verify that transaction timestamps are strictly non-decreasing."""
    assert sim_data["ts"].is_monotonic_increasing, "Timestamps are not strictly non-decreasing"


def test_concept_drift_distribution_shift():
    """Verify that the drift segment in the last 25% of timeline shifts fraud distributions (KS test)."""
    sim = LedgerSim(
        num_transactions=30_000,
        num_days=20,
        num_accounts=2_000,
        num_merchants=200,
        fraud_rate_target=0.010,  # Slightly higher for high-power two-sample test
        drift_start_ratio=0.75,
        seed=999,
    )
    df = sim.generate()

    cutoff = df["ts"].quantile(0.75)
    early_fraud = df[(df["ts"] < cutoff) & (df["is_fraud"] == 1)]
    late_fraud = df[(df["ts"] >= cutoff) & (df["is_fraud"] == 1)]

    assert len(early_fraud) > 50, "Not enough early frauds for statistical test"
    assert len(late_fraud) > 20, "Not enough late frauds for statistical test"

    # Two-sample Kolmogorov-Smirnov test on fraud amount distributions
    res = stats.ks_2samp(early_fraud["amount"], late_fraud["amount"])
    assert res.pvalue < 0.05, f"Drift was not statistically significant on KS test (p={res.pvalue:.4f})"

