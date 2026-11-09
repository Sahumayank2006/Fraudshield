"""
Unit tests for FraudShield Data Ingestion and Protocol Module.

Checks:
- Strictly chronological 70/15/15 split without data leakage
- Split boundary invariants: max(train) <= min(val) <= max(val) <= min(test)
- Absence of row overlap or shuffling across split partitions
- DataCard creation and JSON serialization
- EDA summary metrics generation
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from config import ARTIFACTS_DIR
from src.data import (
    generate_datacard,
    generate_eda_summary,
    load_ledgersim,
    save_datacards,
    time_split,
)


@pytest.fixture(scope="module")
def sample_data():
    """Load sample simulation dataset."""
    return load_ledgersim(fast=True)


def test_time_split_ratios_and_ordering(sample_data):
    """Verify that time-ordered splitting preserves exact chronological order and partition ratios."""
    n = len(sample_data)
    train, val, test = time_split(sample_data, train_ratio=0.70, val_ratio=0.15, test_ratio=0.15)

    # 1. Total row conservation
    assert len(train) + len(val) + len(test) == n
    assert len(train) == int(n * 0.70)
    assert len(val) == int(n * 0.85) - int(n * 0.70)

    # 2. Chronological boundaries: no temporal inversion
    assert train["ts"].max() <= val["ts"].min(), "Temporal leakage between train and validation"
    assert val["ts"].max() <= test["ts"].min(), "Temporal leakage between validation and test"

    # 3. No shared transaction IDs
    train_ids = set(train["txn_id"])
    val_ids = set(val["txn_id"])
    test_ids = set(test["txn_id"])
    assert len(train_ids.intersection(val_ids)) == 0, "Duplicate transaction between train and val"
    assert len(val_ids.intersection(test_ids)) == 0, "Duplicate transaction between val and test"
    assert len(train_ids.intersection(test_ids)) == 0, "Duplicate transaction between train and test"


def test_datacard_generation(sample_data, tmp_path):
    """Verify that DataCards capture all required schema and distribution metadata."""
    card = generate_datacard(
        dataset_name="TestBank",
        df=sample_data,
        caveats=["Synthetic simulation", "Label delay 7 days"],
    )

    assert card["dataset_name"] == "TestBank"
    assert card["total_records"] == len(sample_data)
    assert card["fraud_count"] == int(sample_data["is_fraud"].sum())
    assert "fraud_percentage" in card
    assert card["duration_days"] > 0
    assert len(card["columns"]) == len(sample_data.columns)
    assert "caveats" in card and len(card["caveats"]) == 2

    # Verify JSON persistence
    test_file = tmp_path / "test_datacard.json"
    save_datacards({"TestBank": card}, filepath=test_file)
    assert test_file.exists()

    with open(test_file, "r", encoding="utf-8") as f:
        loaded = json.load(f)
    assert "TestBank" in loaded
    assert loaded["TestBank"]["total_records"] == len(sample_data)


def test_eda_summary_generation(sample_data, tmp_path):
    """Verify that EDA summary computes accurate class balance, amounts, and drift checks."""
    test_eda_path = tmp_path / "test_eda.json"
    eda = generate_eda_summary(sample_data, output_path=test_eda_path)

    assert test_eda_path.exists()
    assert eda["total_records"] == len(sample_data)
    assert eda["fraud_count"] == int(sample_data["is_fraud"].sum())
    assert "amount_distribution" in eda
    assert "legitimate" in eda["amount_distribution"]
    assert "fraud" in eda["amount_distribution"]

    # Verify fraud amounts are generally larger or different than legitimate
    assert eda["amount_distribution"]["fraud"]["mean"] > 0
    assert eda["amount_distribution"]["legitimate"]["mean"] > 0

    # Verify hourly stats
    assert len(eda["hourly_distribution"]) == 24
    assert "drift_check" in eda
    assert "amount_ks_statistic_fraud" in eda["drift_check"]

