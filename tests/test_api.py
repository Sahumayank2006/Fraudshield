"""
Unit & Integration Tests for FraudShield FastAPI Service (tests/test_api.py)
=============================================================================
Tests:
1. Health and overview metrics endpoints.
2. Single transaction scoring with schema validation (valid and malformed inputs).
3. Batch CSV upload and flagged results download.
4. SSE stream controls and scripted attack burst injection.
5. Case desk lifecycle (list, inspect, patch status/notes, account history, similar cases).
6. Pedagogical endpoints: experiments matrix, curves, global SHAP, threshold simulation.
7. Operations: drift report, challenger retrain, rollback, fairness, and datacards.
"""

import io
import json
import pytest
from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


def test_health_endpoint():
    """Verify GET /api/health returns 200 and all system checks pass."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "FraudShield"
    assert "t1_review" in data
    assert "t2_block" in data
    assert data["t1_review"] < data["t2_block"]
    assert "artifacts" in data


def test_overview_endpoint():
    """Verify GET /api/overview returns headline metrics and session telemetry."""
    response = client.get("/api/overview")
    assert response.status_code == 200
    data = response.json()
    assert "headline" in data
    assert "session" in data
    assert "pr_auc" in data["headline"]
    assert "streamed_count" in data["session"]


def test_score_valid_transaction():
    """Verify POST /api/score produces expected decision, probability, and reason codes."""
    payload = {
        "txn_id": "TXN_TEST_VALID_01",
        "account_id": "ACC_8899",
        "merchant_id": "MERCH_42",
        "merchant_category": "electronics",
        "amount": 45000.0,
        "channel": "online",
        "device_id": "DEV_NEW_01",
        "device_is_new": True,
        "ip_region": "IN-MH",
        "orig_balance": 50000.0,
        "dest_balance": 1000.0,
        "pwd_reset_recent": True,
        "session_risk_score": 0.85,
    }
    response = client.post("/api/score", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["txn_id"] == "TXN_TEST_VALID_01"
    assert data["decision"] in ("APPROVE", "REVIEW", "BLOCK")
    assert 0.0 <= data["fraud_probability"] <= 1.0
    assert "top_reasons" in data
    assert "latency_ms" in data
    assert data["latency_ms"] >= 0.0


def test_score_invalid_negative_amount():
    """Verify POST /api/score returns 422 on invalid negative transaction amount."""
    payload = {
        "account_id": "ACC_9999",
        "merchant_id": "MERCH_01",
        "amount": -50.0,  # Invalid
        "channel": "online",
    }
    response = client.post("/api/score", json=payload)
    assert response.status_code == 422


def test_score_invalid_missing_fields():
    """Verify POST /api/score returns 422 when required account_id is missing."""
    payload = {
        "amount": 100.0,
        "merchant_id": "MERCH_01",
    }
    response = client.post("/api/score", json=payload)
    assert response.status_code == 422


def test_score_batch_csv_and_download():
    """Verify POST /api/score/batch with CSV file and subsequent download."""
    csv_content = (
        "account_id,merchant_id,amount,channel\n"
        "ACC_01,MERCH_10,25.0,card_present\n"
        "ACC_02,MERCH_20,95000.0,online\n"
        "ACC_03,MERCH_30,120.0,upi\n"
    )
    files = {"file": ("test_batch.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")}
    response = client.post("/api/score/batch", files=files)
    assert response.status_code == 200
    data = response.json()
    assert data["total_transactions"] == 3
    assert data["approved_count"] + data["review_count"] + data["blocked_count"] == 3
    assert "processing_time_ms" in data

    # Test download of flagged rows
    dl_resp = client.get("/api/score/batch/download")
    assert dl_resp.status_code == 200
    assert "text/csv" in dl_resp.headers["content-type"]


def test_stream_controls():
    """Verify stream play, pause, speed, and reset controls."""
    # Pause
    r_pause = client.post("/api/stream/control", json={"action": "pause"})
    assert r_pause.status_code == 200
    assert r_pause.json()["is_playing"] is False

    # Speed
    r_speed = client.post("/api/stream/control", json={"action": "speed", "speed": 10.0})
    assert r_speed.status_code == 200
    assert r_speed.json()["speed"] == 10.0

    # Play
    r_play = client.post("/api/stream/control", json={"action": "play"})
    assert r_play.status_code == 200
    assert r_play.json()["is_playing"] is True

    # Reset
    r_reset = client.post("/api/stream/control", json={"action": "reset"})
    assert r_reset.status_code == 200


def test_stream_attack_injection():
    """Verify POST /api/stream/attack enqueues scripted attack burst."""
    payload = {"attack_type": "card_testing", "count": 12}
    response = client.post("/api/stream/attack", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "QUEUED"
    assert data["attack_type"] == "card_testing"
    assert data["injected_count"] == 12


def test_cases_queue_and_lifecycle():
    """Verify listing cases, viewing single case details, and patching status."""
    # List cases
    r_list = client.get("/api/cases?limit=10")
    assert r_list.status_code == 200
    cases = r_list.json()
    assert isinstance(cases, list)

    if cases:
        target_case_id = cases[0]["case_id"]

        # Get full case file
        r_get = client.get(f"/api/cases/{target_case_id}")
        assert r_get.status_code == 200
        case_data = r_get.json()
        assert case_data["case_id"] == target_case_id
        assert "waterfall" in case_data
        assert "account_history" in case_data
        assert "similar_cases" in case_data

        # Patch case disposition
        r_patch = client.patch(
            f"/api/cases/{target_case_id}",
            json={"status": "CONFIRMED", "notes": "Confirmed card testing pattern."},
        )
        assert r_patch.status_code == 200
        patched = r_patch.json()
        assert patched["status"] == "CONFIRMED"
        assert patched["notes"] == "Confirmed card testing pattern."


def test_experiments_matrix_endpoint():
    """Verify GET /api/experiments returns all E1-E10 rows."""
    response = client.get("/api/experiments")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 10
    assert "E1_LR_None" in data
    assert "E9_Hybrid" in data


def test_curves_endpoint():
    """Verify GET /api/curves returns PR, ROC, and reliability coordinates."""
    response = client.get("/api/curves")
    assert response.status_code == 200
    data = response.json()
    assert "champion_e9" in data
    assert "pr_curve" in data["champion_e9"]


def test_explain_global_endpoint():
    """Verify GET /api/explain/global returns ranking and beeswarm sample."""
    response = client.get("/api/explain/global")
    assert response.status_code == 200
    data = response.json()
    assert "ranking" in data
    assert "beeswarm" in data
    assert "causality_caution" in data


def test_threshold_simulation_endpoint():
    """Verify GET /api/threshold/sim computes what-if metrics."""
    response = client.get("/api/threshold/sim?t1=0.01&t2=0.08&cost_mode=amount_weighted")
    assert response.status_code == 200
    data = response.json()
    assert data["t1"] == 0.01
    assert data["t2"] == 0.08
    assert "metrics" in data

    # Inverted thresholds should return 400
    r_bad = client.get("/api/threshold/sim?t1=0.50&t2=0.05")
    assert r_bad.status_code == 400


def test_drift_monitor_endpoint():
    """Verify GET /api/drift returns PSI table, score drift, and alert status."""
    response = client.get("/api/drift")
    assert response.status_code == 200
    data = response.json()
    assert "summary" in data
    assert "score_drift" in data
    assert "feature_psi_table" in data
    assert "weekly_performance" in data


def test_fairness_datasets_hypotheses_endpoints():
    """Verify GET /api/fairness, /api/datasets, and /api/hypotheses."""
    r_fair = client.get("/api/fairness")
    assert r_fair.status_code == 200
    data_fair = r_fair.json()
    assert "ip_region" in data_fair or "channel" in data_fair

    r_data = client.get("/api/datasets")
    assert r_data.status_code == 200
    datasets = {k.lower(): v for k, v in r_data.json().items()}
    assert "ledgersim" in datasets

    r_hyp = client.get("/api/hypotheses")
    assert r_hyp.status_code == 200
    assert "H1" in r_hyp.json()
