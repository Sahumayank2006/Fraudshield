"""
Unit Tests for Monitoring & Operations Engine (tests/test_monitor.py)
=====================================================================
Tests:
1. Population Stability Index (PSI) mathematical properties and thresholds.
2. Score distribution drift and Kolmogorov-Smirnov test.
3. 7-day label maturation rule for weekly cohorts.
4. Drift health evaluation and retraining alert triggers.
5. Champion-challenger registry, gate verification, and safe rollback.
"""

import json
import shutil
import pytest
import numpy as np
import pandas as pd

from src.monitor import (
    compute_psi,
    compute_score_drift,
    compute_weekly_performance,
    evaluate_drift_health,
    ModelRegistry,
    DRIFT_MONITOR_FILE,
)
from config import ARTIFACTS_DIR


def test_compute_psi_identical_distributions():
    """Verify PSI between identical distributions is near zero and classified as STABLE."""
    np.random.seed(42)
    ref = np.random.normal(loc=100.0, scale=15.0, size=5000)
    curr = np.random.normal(loc=100.0, scale=15.0, size=5000)

    res = compute_psi(ref, curr, n_bins=10)

    assert res["psi"] < 0.05, f"PSI for identical distribution too high: {res['psi']}"
    assert res["status"] == "STABLE"
    assert len(res["bin_edges"]) >= 2
    assert len(res["ref_pct"]) == len(res["curr_pct"])


def test_compute_psi_severely_shifted_distributions():
    """Verify PSI detects significant population shift (PSI >= 0.25)."""
    np.random.seed(42)
    ref = np.random.normal(loc=50.0, scale=10.0, size=5000)
    curr = np.random.normal(loc=75.0, scale=10.0, size=5000)  # 2.5 std dev shift

    res = compute_psi(ref, curr, n_bins=10)

    assert res["psi"] >= 0.25, f"Expected SIGNIFICANT drift, got PSI={res['psi']}"
    assert res["status"] == "SIGNIFICANT"


def test_score_drift_and_ks_test():
    """Verify score distribution drift computation, KS statistic, and 20-bin histogram."""
    np.random.seed(42)
    ref_scores = np.random.beta(0.5, 20.0, size=3000)  # Highly skewed low risk scores
    curr_scores = np.random.beta(1.5, 10.0, size=3000)  # Upward shift in risk

    drift_res = compute_score_drift(ref_scores, curr_scores, n_bins=20)

    assert drift_res["psi"] > 0.0
    assert drift_res["ks_statistic"] > 0.0
    assert drift_res["ks_pvalue"] < 0.01
    assert len(drift_res["histogram"]) == 20
    assert "ref_density" in drift_res["histogram"][0]
    assert "curr_density" in drift_res["histogram"][0]


def test_weekly_performance_7day_maturation():
    """Verify transactions within 7 days of t_max are marked immature."""
    day_secs = 86400
    n_days = 21
    # 21 days of transactions
    timestamps = np.linspace(0, n_days * day_secs, 2100)
    df = pd.DataFrame({
        "ts": timestamps,
        "is_fraud": np.random.binomial(1, 0.05, size=len(timestamps)),
    })
    probs = np.random.uniform(0.0, 1.0, size=len(timestamps))
    preds = (probs > 0.5).astype(int)

    weekly = compute_weekly_performance(df, probs, preds, time_col="ts")

    assert len(weekly) >= 3
    # Earlier weeks should be mature
    assert weekly[0]["is_mature"] is True
    assert weekly[0]["status"] == "Mature"
    # Final week (within last 7 days of 21-day period) must be immature
    assert weekly[-1]["is_mature"] is False
    assert weekly[-1]["status"] == "Pending 7d Maturation"


def test_evaluate_drift_health_alert_trigger():
    """Verify alert triggers when score PSI exceeds 0.25 threshold."""
    feature_table = [
        {"feature": "amount", "status": "STABLE", "psi": 0.02},
        {"feature": "velocity", "status": "STABLE", "psi": 0.04},
    ]
    # Normal health
    normal_score = {"psi": 0.03, "status": "STABLE"}
    normal_health = evaluate_drift_health(feature_table, normal_score, [])
    assert normal_health["alert_state"] == "HEALTHY"
    assert len(normal_health["triggers"]) == 0

    # Drifting score triggers alert
    drifting_score = {"psi": 0.28, "status": "SIGNIFICANT"}
    alert_health = evaluate_drift_health(feature_table, drifting_score, [])
    assert alert_health["alert_state"] == "RETRAIN_RECOMMENDED"
    assert len(alert_health["triggers"]) >= 1


def test_model_registry_and_rollback_workflow(tmp_path):
    """Verify ModelRegistry handles metadata, champion backups, and atomic rollback."""
    champ_file = tmp_path / "model_champion.joblib"
    roll_file = tmp_path / "model_rollback.joblib"
    meta_file = tmp_path / "model_registry.json"

    # Seed mock champion file
    import joblib
    joblib.dump({"version": "v1.0-champion", "data": "initial"}, champ_file)

    registry = ModelRegistry(
        champion_path=champ_file,
        rollback_path=roll_file,
        metadata_path=meta_file,
    )

    meta = registry.get_metadata()
    assert meta["active_version"] == "v1.0-champion"
    assert meta["has_rollback"] is False

    # Simulate rollback when no rollback file exists -> should return error
    res_fail = registry.rollback()
    assert res_fail["status"] == "ERROR"

    # Simulate backing up v1.0 and promoting v2.0
    shutil.copy2(champ_file, roll_file)
    joblib.dump({"version": "v2.0-challenger", "data": "updated"}, champ_file)
    meta["active_version"] = "v2.0-challenger"
    meta["rollback_version"] = "v1.0-champion"
    registry.save_metadata(meta)

    # Roll back
    res_rollback = registry.rollback()
    assert res_rollback["status"] == "ROLLED_BACK"
    assert res_rollback["active_version"] == "v1.0-champion"

    # Verify champ_file restored
    restored_bundle = joblib.load(champ_file)
    assert restored_bundle["version"] == "v1.0-champion"


def test_baseline_drift_monitor_artifact():
    """Verify artifacts/drift_monitor.json exists and contains all required sections."""
    assert DRIFT_MONITOR_FILE.exists(), "drift_monitor.json must exist in artifacts/"

    with open(DRIFT_MONITOR_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert "summary" in data
    assert "score_drift" in data
    assert "feature_psi_table" in data
    assert "weekly_performance" in data
    assert "model_registry" in data
    assert len(data["feature_psi_table"]) > 0

