"""
Unit Tests for Explainability Engine (tests/test_explain.py)
=============================================================
Tests:
1. Local TreeSHAP instance attribution and margin consistency.
2. Dynamic reason codes formatting with verified numbers (no unresolved template tags).
3. Global SHAP summary ranking, beeswarm points, and causality disclaimer.
"""

import json
import pytest
import numpy as np
import pandas as pd
import joblib

from src.explain import (
    TreeSHAPExplainer,
    format_reason_code,
    generate_global_shap_summary,
    CAUSALITY_CAUTION,
    REASON_CODE_TEMPLATES,
)
from config import ARTIFACTS_DIR


@pytest.fixture(scope="module")
def champion_bundle():
    bundle_path = ARTIFACTS_DIR / "model_champion.joblib"
    if not bundle_path.exists():
        pytest.skip("Champion model bundle does not exist yet. Run train-fast first.")
    return joblib.load(bundle_path)


def test_format_reason_codes_all_templates():
    """Verify every template in REASON_CODE_TEMPLATES formats without unresolved tags."""
    dummy_context = {
        "amount": 25000.0,
        "log_amount": 10.12,
        "amount_zscore_by_account": 4.5,
        "amount_to_balance_ratio": 0.85,
        "drains_account": 1.0,
        "hour": 2.0,
        "is_night": 1.0,
        "time_since_last_txn": 180.0,
        "time_since_account_open": 86400.0 * 5.0,
        "txn_count_1h": 6.0,
        "txn_count_24h": 18.0,
        "txn_count_7d": 45.0,
        "amount_sum_1h": 50000.0,
        "amount_sum_24h": 120000.0,
        "distinct_merchants_24h": 7.0,
        "distinct_devices_7d": 4.0,
        "new_merchant_flag": 1.0,
        "new_payee_flag": 1.0,
        "category_rarity_by_account": 0.95,
        "region_mismatch": 1.0,
        "device_novelty": 1.0,
        "session_anomaly": 1.0,
        "pwd_reset_last_24h": 1.0,
        "errorBalanceOrig": 1200.0,
        "errorBalanceDest": 1200.0,
        "iso_score": -0.65,
        "ae_error": 0.085,
        "merchant_id": "MERCH_ELECTRONICS_01",
        "category": "electronics",
        "region": "US-CA",
    }

    for feature_name in REASON_CODE_TEMPLATES.keys():
        val = dummy_context.get(feature_name, 1.0)
        res = format_reason_code(
            feature=feature_name,
            shap_value=1.25,
            feature_value=val,
            context=dummy_context,
        )

        assert res["feature"] == feature_name
        assert res["severity"] == "HIGH"
        assert res["icon"] is not None
        assert "{" not in res["description"], f"Unresolved bracket in {feature_name}: {res['description']}"
        assert "}" not in res["description"], f"Unresolved bracket in {feature_name}: {res['description']}"
        assert len(res["headline"]) > 0


def test_tree_shap_explainer_local_attribution(champion_bundle):
    """Verify local TreeSHAP calculation: shapes, contributions, and waterfall coordinates."""
    explainer = TreeSHAPExplainer(champion_bundle)
    feature_names = champion_bundle["feature_names"]

    # Create synthetic transaction vector
    dummy_row = pd.DataFrame([np.zeros(len(feature_names))], columns=feature_names)
    dummy_row["log_amount"] = 8.5
    dummy_row["amount_zscore_by_account"] = 3.8
    dummy_row["txn_count_1h"] = 4.0

    raw_txn = {"merchant_id": "MERCH_TEST_01", "channel": "online"}
    res = explainer.explain_instance(dummy_row, raw_txn=raw_txn, top_k=3)

    assert "base_value" in res
    assert "margin_output" in res
    assert "implied_probability" in res
    assert 0.0 <= res["implied_probability"] <= 1.0
    assert "top_reasons" in res
    assert len(res["top_reasons"]) <= 3
    assert len(res["waterfall"]) >= 3
    assert res["causality_caution"] == CAUSALITY_CAUTION

    # Check waterfall starts with base and ends with margin output
    assert res["waterfall"][0]["step"] == "Base Value (Prior)"
    assert res["waterfall"][-1]["step"] == "Model Output Margin"
    assert res["waterfall"][-1]["end_value"] == res["margin_output"]


def test_global_shap_summary_artifact():
    """Verify artifacts/shap_summary.json exists and meets all spec requirements."""
    summary_path = ARTIFACTS_DIR / "shap_summary.json"
    assert summary_path.exists(), "shap_summary.json must exist in artifacts/"

    with open(summary_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert "ranking" in data
    assert len(data["ranking"]) > 0
    assert "beeswarm" in data
    assert len(data["beeswarm"]) > 0
    assert "dependence" in data
    assert len(data["dependence"]) > 0
    assert "causality_caution" in data
    assert data["causality_caution"] == CAUSALITY_CAUTION
