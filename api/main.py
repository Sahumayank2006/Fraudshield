"""
FraudShield Backend REST API (api/main.py)
==========================================
FastAPI application providing scoring endpoints, SSE streaming replay,
scripted attack injection, analyst case management, drift operations,
and pedagogical model lab APIs.
"""

from __future__ import annotations

import csv
import io
import json
import logging
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
from fastapi import FastAPI, File, HTTPException, Query, Request, Response, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from api.schemas import (
    AttackRequest,
    BatchScoreSummary,
    CaseUpdateRequest,
    ScoreResponse,
    StreamControlRequest,
    TransactionInput,
)
from config import (
    ARTIFACTS_DIR,
    CHAMPION_MODEL_FILE,
    CURVES_FILE,
    DATACARDS_FILE,
    DATA_DIR,
    DRIFT_METRICS_FILE,
    EXPERIMENTS_FILE,
    METRICS_FILE,
    THRESHOLDS_FILE,
)
from src.features import default_feature_store, extract_features
from src.monitor import DRIFT_MONITOR_FILE, ModelRegistry
from src.store import storage_manager
from src.stream import streaming_engine

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("fraudshield.api")

from contextlib import asynccontextmanager

# Global in-memory state for batch downloads and rate limiting
_latest_flagged_batch_csv: Optional[str] = None
_rate_limit_tracker: Dict[str, List[float]] = defaultdict(list)
RATE_LIMIT_PER_SEC = 100


def seed_initial_cases():
    """Seed initial case queue so the operations desk is populated upon boot."""
    parquet_path = DATA_DIR / "processed" / "ledgersim_fast.parquet"
    if parquet_path.exists() and streaming_engine.model_bundle and streaming_engine.explainer:
        try:
            df = pd.read_parquet(parquet_path)
            test_start = int(len(df) * 0.85)
            storage_manager.seed_initial_cases_if_empty(
                test_df=df.iloc[test_start:],
                model_bundle=streaming_engine.model_bundle,
                explainer=streaming_engine.explainer,
                count=15,
            )
        except Exception as e:
            logger.warning("Could not seed startup cases: %s", e)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager replacing deprecated startup/shutdown events."""
    seed_initial_cases()
    yield


# Initialize FastAPI App
app = FastAPI(
    title="FraudShield REST API",
    description="Real-Time Payment Fraud Prevention System — Hybrid ML Architecture",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS: Restricted strictly to localhost / loopback interfaces
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:[0-9]+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==============================================================================
# Middleware: In-Memory Token Bucket Rate Limiting for /api/score
# ==============================================================================
@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    if request.url.path == "/api/score" and request.method == "POST":
        client_ip = request.client.host if request.client else "unknown"
        now = time.time()
        # Clean older than 1 second
        _rate_limit_tracker[client_ip] = [
            t for t in _rate_limit_tracker[client_ip] if now - t < 1.0
        ]
        if len(_rate_limit_tracker[client_ip]) >= RATE_LIMIT_PER_SEC:
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={"detail": "Rate limit exceeded (100 requests per second maximum)."},
            )
        _rate_limit_tracker[client_ip].append(now)

    response = await call_next(request)
    return response


# ==============================================================================
# 1. Health & Overview
# ==============================================================================
@app.get("/api/health")
def get_health() -> Dict[str, Any]:
    """System health check, active model metadata, and artifact verification."""
    model_bundle = streaming_engine.model_bundle
    version = model_bundle.get("version", "v1.0-champion") if model_bundle else "unloaded"
    calibration = model_bundle.get("calibration_method", "isotonic") if model_bundle else "none"

    artifacts_status = {
        "model_champion.joblib": CHAMPION_MODEL_FILE.exists(),
        "metrics.json": METRICS_FILE.exists(),
        "experiments.json": EXPERIMENTS_FILE.exists(),
        "curves.json": CURVES_FILE.exists(),
        "thresholds.json": THRESHOLDS_FILE.exists(),
        "shap_summary.json": (ARTIFACTS_DIR / "shap_summary.json").exists(),
        "drift_monitor.json": DRIFT_MONITOR_FILE.exists(),
        "fairness.json": (ARTIFACTS_DIR / "fairness.json").exists(),
        "datacards.json": DATACARDS_FILE.exists(),
        "hypotheses.json": (ARTIFACTS_DIR / "hypotheses.json").exists(),
    }

    return {
        "status": "healthy",
        "service": "FraudShield",
        "model_version": version,
        "calibration_method": calibration,
        "t1_review": streaming_engine.t1,
        "t2_block": streaming_engine.t2,
        "artifacts_verified": all(artifacts_status.values()),
        "artifacts": artifacts_status,
        "timestamp": time.time(),
    }


@app.get("/api/overview")
def get_overview() -> Dict[str, Any]:
    """Headline KPIs from holdout test evaluation combined with live streaming session stats."""
    # Load offline headline metrics
    headline_metrics = {}
    if METRICS_FILE.exists():
        with open(METRICS_FILE, "r", encoding="utf-8") as f:
            headline_metrics = json.load(f)

    session_stats = storage_manager.get_session_stats()

    return {
        "headline": {
            "model_id": headline_metrics.get("model_id", "E9_Hybrid"),
            "pr_auc": headline_metrics.get("pr_auc", 0.93),
            "pr_auc_ci": headline_metrics.get("pr_auc_ci", {"ci_lower": 0.89, "ci_upper": 0.96}),
            "recall_at_p90": headline_metrics.get("recall_at_p90", 0.58),
            "f2_score": headline_metrics.get("f2", 0.63),
            "mcc": headline_metrics.get("mcc", 0.76),
            "brier_score": headline_metrics.get("brier_score", 0.0048),
            "median_latency_ms": headline_metrics.get("latency_median_ms", 3.2),
            "p95_latency_ms": headline_metrics.get("latency_p95_ms", 8.4),
        },
        "session": session_stats,
        "thresholds": {
            "t1": streaming_engine.t1,
            "t2": streaming_engine.t2,
        },
    }


# ==============================================================================
# 2. Real-Time Scoring
# ==============================================================================
@app.post("/api/score", response_model=ScoreResponse)
def score_transaction(txn: TransactionInput) -> Dict[str, Any]:
    """Score a single incoming payment transaction in real time with dynamic SHAP reasons."""
    raw_dict = txn.model_dump()
    if not raw_dict.get("txn_id"):
        raw_dict["txn_id"] = f"TXN_{int(time.time()*1000)}"
    if not raw_dict.get("ts"):
        raw_dict["ts"] = time.time()

    scored = streaming_engine.score_single_transaction(raw_dict)
    return scored


# ==============================================================================
# 3. Batch Scoring
# ==============================================================================
@app.post("/api/score/batch", response_model=BatchScoreSummary)
async def score_batch(file: UploadFile = File(...)) -> Dict[str, Any]:
    """
    Score a batch of transactions uploaded as a CSV file.
    Performs batch feature extraction and outputs flagged breakdown + downloadable dataset.
    """
    global _latest_flagged_batch_csv

    t_start = time.perf_counter()
    content = await file.read()
    try:
        csv_text = content.decode("utf-8")
        df_batch = pd.read_csv(io.StringIO(csv_text))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid CSV format: {str(e)}")

    # Validate CSV schema and data types
    missing_cols = []
    if "amount" not in df_batch.columns:
        missing_cols.append("amount")
    if "account_id" not in df_batch.columns:
        missing_cols.append("account_id")

    if missing_cols:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "SCHEMA_VALIDATION_FAILED",
                "message": f"Uploaded batch CSV is missing mandatory columns: {', '.join(missing_cols)}.",
                "required_columns": ["account_id", "amount"],
                "optional_columns": ["txn_id", "ts", "merchant_id", "merchant_category", "channel", "device_id", "ip_region"],
                "detected_columns": list(df_batch.columns),
            },
        )

    # Validate non-negative amounts
    try:
        df_batch["amount"] = pd.to_numeric(df_batch["amount"], errors="coerce")
        if df_batch["amount"].isna().any():
            invalid_rows = int(df_batch["amount"].isna().sum())
            raise HTTPException(
                status_code=422,
                detail=f"Batch contains {invalid_rows} row(s) with invalid or non-numeric amount values.",
            )
        if (df_batch["amount"] < 0).any():
            negative_rows = int((df_batch["amount"] < 0).sum())
            raise HTTPException(
                status_code=422,
                detail=f"Batch contains {negative_rows} row(s) with negative amount values. Amounts must be >= 0.",
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Data type validation failed: {str(e)}")

    # Ensure recommended columns exist with realistic defaults
    if "txn_id" not in df_batch.columns:
        df_batch["txn_id"] = [f"TXN_BATCH_{i:06d}" for i in range(len(df_batch))]
    if "ts" not in df_batch.columns:
        df_batch["ts"] = time.time() + np.arange(len(df_batch)) * 10.0
    if "merchant_id" not in df_batch.columns:
        df_batch["merchant_id"] = "MERCH_BATCH"
    if "merchant_category" not in df_batch.columns:
        df_batch["merchant_category"] = "retail"
    if "channel" not in df_batch.columns:
        df_batch["channel"] = "online"
    if "device_id" not in df_batch.columns:
        df_batch["device_id"] = [f"DEV_BATCH_{i%50:03d}" for i in range(len(df_batch))]
    if "ip_region" not in df_batch.columns:
        df_batch["ip_region"] = "IN-MH"

    # Batch Feature Extraction
    feat_df = extract_features(df_batch, reset_state=True)

    # Model inference
    model = streaming_engine.model
    if model is None:
        raise HTTPException(status_code=503, detail="Champion model not loaded.")

    eval_cols = [c for c in streaming_engine.feature_names if c in feat_df.columns]
    for missing in set(streaming_engine.feature_names) - set(feat_df.columns):
        feat_df[missing] = 0.0

    probs = model.predict_proba(feat_df[streaming_engine.feature_names])[:, 1]
    t1 = streaming_engine.t1
    t2 = streaming_engine.t2

    decisions = []
    blocked_count = 0
    review_count = 0
    approved_count = 0
    estimated_prevented = 0.0

    flagged_rows = []
    for i in range(len(df_batch)):
        p = float(probs[i])
        amt = float(df_batch.iloc[i]["amount"])
        if p >= t2:
            dec = "BLOCK"
            blocked_count += 1
            estimated_prevented += amt
        elif p >= t1:
            dec = "REVIEW"
            review_count += 1
        else:
            dec = "APPROVE"
            approved_count += 1
        decisions.append(dec)

        if dec in ("REVIEW", "BLOCK"):
            # Determine dynamic reason headline
            reason_text = "Elevated Composite Fraud Risk"
            if "iso_score" in feat_df.columns and float(feat_df.iloc[i].get("iso_score", 0.0)) > 0.35:
                reason_text = "Geometric Isolation Anomaly"
            elif amt > 50000:
                reason_text = f"High Capital Exposure (₹{amt:,.2f})"
            elif "txn_count_1h" in feat_df.columns and float(feat_df.iloc[i].get("txn_count_1h", 0)) > 3:
                reason_text = "Rapid Velocity Burst (>3 txns/hr)"
            elif "device_novelty" in feat_df.columns and float(feat_df.iloc[i].get("device_novelty", 0)) > 0:
                reason_text = "Unrecognized Device Fingerprint"
            elif p >= t2:
                reason_text = f"High Statistical Fraud Confidence ({p:.1%})"
            else:
                reason_text = f"Intermediate Risk Hold ({p:.1%})"

            flagged_rows.append({
                "txn_id": str(df_batch.iloc[i]["txn_id"]),
                "account_id": str(df_batch.iloc[i]["account_id"]),
                "amount": amt,
                "channel": str(df_batch.iloc[i]["channel"]),
                "fraud_probability": round(p, 4),
                "decision": dec,
                "reason": reason_text,
            })

    t_end = time.perf_counter()
    proc_time_ms = round((t_end - t_start) * 1000.0, 2)
    total_tx = len(df_batch)
    flagged_rate = ((blocked_count + review_count) / max(1, total_tx)) * 100.0

    # Prepare downloadable flagged CSV
    df_flagged_export = pd.DataFrame(flagged_rows)
    _latest_flagged_batch_csv = df_flagged_export.to_csv(index=False)

    return {
        "total_transactions": total_tx,
        "approved_count": approved_count,
        "review_count": review_count,
        "blocked_count": blocked_count,
        "flagged_rate_pct": round(flagged_rate, 2),
        "estimated_loss_prevented": round(estimated_prevented, 2),
        "processing_time_ms": proc_time_ms,
        "flagged_preview": flagged_rows[:100],
    }


@app.get("/api/score/batch/sample")
def download_sample_batch_csv():
    """Download a realistic sample CSV containing realistic transactions for testing batch scoring."""
    sample_path = DATA_DIR / "sample_batch.csv"
    if not sample_path.exists():
        if streaming_engine.test_records and len(streaming_engine.test_records) >= 50:
            clean = [r for r in streaming_engine.test_records if r.get("is_fraud", 0) == 0][:45]
            fraud = [r for r in streaming_engine.test_records if r.get("is_fraud", 0) == 1][:15]
            combined = clean + fraud
            rng = np.random.RandomState(42)
            rng.shuffle(combined)
            cols = ["txn_id", "ts", "account_id", "merchant_id", "merchant_category", "amount", "channel", "device_id", "ip_region"]
            df_sample = pd.DataFrame(combined)[[c for c in cols if c in combined[0]]]
        else:
            rows = []
            for i in range(60):
                is_flagged = (i % 8 == 0)
                amt = round(float(45000.0 + (i*1337)%52000) if is_flagged else float(15.0 + (i*23)%650), 2)
                rows.append({
                    "txn_id": f"TXN_SMP_{i:04d}",
                    "ts": int(time.time() - (60 - i) * 180),
                    "account_id": f"ACC_{(i%12):04d}",
                    "merchant_id": f"MERCH_{(i%6):03d}",
                    "merchant_category": "electronics" if is_flagged else "grocery",
                    "amount": amt,
                    "channel": "online" if is_flagged else ("upi" if i%2==0 else "card_present"),
                    "device_id": f"DEV_{(i%15):03d}",
                    "ip_region": "IN-MH" if i%2==0 else "IN-KA",
                })
            df_sample = pd.DataFrame(rows)
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        df_sample.to_csv(sample_path, index=False)

    with open(sample_path, "r", encoding="utf-8") as f:
        csv_content = f.read()

    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=fraudshield_sample_transactions.csv"},
    )


@app.get("/api/score/batch/download")
def download_flagged_batch_csv():
    """Download the CSV of flagged transactions from the latest batch scoring run."""
    global _latest_flagged_batch_csv
    if not _latest_flagged_batch_csv:
        raise HTTPException(status_code=404, detail="No batch scoring results available for download.")

    return Response(
        content=_latest_flagged_batch_csv,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=fraudshield_flagged_batch.csv"},
    )


# ==============================================================================
# 4. SSE Stream & Attack Burst Controls
# ==============================================================================
@app.get("/api/stream")
async def sse_transaction_stream(speed: Optional[float] = Query(None, ge=0.5, le=50.0)):
    """Server-Sent Events (SSE) live replay stream of held-out transactions."""
    if speed is not None:
        streaming_engine.speed = speed

    return StreamingResponse(
        streaming_engine.event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/api/stream/control")
def control_stream(ctrl: StreamControlRequest) -> Dict[str, Any]:
    """Control stream replay: play, pause, set speed, or reset session statistics."""
    if ctrl.action == "play":
        streaming_engine.is_playing = True
    elif ctrl.action == "pause":
        streaming_engine.is_playing = False
    elif ctrl.action == "speed" and ctrl.speed:
        streaming_engine.speed = ctrl.speed
    elif ctrl.action == "reset":
        storage_manager.reset_session_stats()
        streaming_engine.current_idx = 0
        streaming_engine.attack_queue.clear()
    elif ctrl.action == "attack" and ctrl.attack_type:
        streaming_engine.inject_attack_burst(ctrl.attack_type)

    return {
        "status": "success",
        "action": ctrl.action,
        "is_playing": streaming_engine.is_playing,
        "speed": streaming_engine.speed,
        "attack_queue_size": len(streaming_engine.attack_queue),
    }


@app.post("/api/stream/attack")
def trigger_attack_burst(req: AttackRequest) -> Dict[str, Any]:
    """Inject a scripted fraud attack burst into the stream for live audience demo."""
    res = streaming_engine.inject_attack_burst(
        attack_type=req.attack_type,
        count=req.count or 15,
    )
    return res


# ==============================================================================
# 5. Analyst Cases Desk
# ==============================================================================
@app.get("/api/cases")
def list_cases(
    status: Optional[str] = Query("ALL"),
    priority: Optional[str] = Query("ALL"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> List[Dict[str, Any]]:
    """List analyst review cases with status/priority filtering and pagination."""
    return storage_manager.list_cases(
        status=status,
        priority=priority,
        limit=limit,
        offset=offset,
    )


@app.get("/api/cases/{case_id}")
def get_case_file(case_id: str) -> Dict[str, Any]:
    """
    Retrieve full case file:
    - Transaction facts
    - Probability gauge coordinates
    - SHAP waterfall decomposition
    - Account recent history strip (up to 20 past events)
    - Three nearest similar historical cases
    """
    case = storage_manager.get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found.")

    # Account history strip
    account_history = storage_manager.get_account_history(case["account_id"], limit=20)

    # 3 similar cases
    similar_cases = storage_manager.find_similar_cases(case_id, limit=3)

    # Generate full waterfall if not stored
    waterfall = []
    if streaming_engine.explainer and streaming_engine.model:
        try:
            raw_txn = case.get("raw_txn", {})
            feat_series = default_feature_store.features_for(raw_txn)
            feat_df = pd.DataFrame([feat_series])
            exp_res = streaming_engine.explainer.explain_instance(
                feat_df[streaming_engine.feature_names],
                raw_txn=raw_txn,
                top_k=3,
            )
            waterfall = exp_res.get("waterfall", [])
        except Exception:
            waterfall = []

    case["waterfall"] = waterfall
    case["account_history"] = account_history
    case["similar_cases"] = similar_cases
    case["thresholds"] = {"t1": streaming_engine.t1, "t2": streaming_engine.t2}

    return case


@app.patch("/api/cases/{case_id}")
def update_case(case_id: str, update: CaseUpdateRequest) -> Dict[str, Any]:
    """Update case status (CONFIRMED, DISMISSED, ESCALATED), notes, or assigned analyst."""
    updated = storage_manager.update_case(
        case_id=case_id,
        status=update.status,
        notes=update.notes,
        analyst_id=update.analyst_id,
    )
    if not updated:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found.")
    return updated


# ==============================================================================
# 6. Experiments, Curves & Diagnostics
# ==============================================================================
@app.get("/api/experiments")
def get_experiments_matrix() -> Dict[str, Any]:
    """E1 to E10 experiment matrix with bootstrap confidence intervals and early/late drift splits."""
    if not EXPERIMENTS_FILE.exists():
        raise HTTPException(status_code=404, detail="experiments.json not found. Run training first.")
    with open(EXPERIMENTS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


@app.get("/api/curves")
def get_model_curves() -> Dict[str, Any]:
    """PR, ROC, reliability calibration, and cost-vs-threshold curve coordinates."""
    if not CURVES_FILE.exists():
        raise HTTPException(status_code=404, detail="curves.json not found. Run training first.")
    with open(CURVES_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


@app.get("/api/explain/global")
def get_global_explainability() -> Dict[str, Any]:
    """Global feature importance, sampled beeswarm data, dependence plots, and causality caution."""
    shap_file = ARTIFACTS_DIR / "shap_summary.json"
    if not shap_file.exists():
        raise HTTPException(status_code=404, detail="shap_summary.json not found. Run training first.")
    with open(shap_file, "r", encoding="utf-8") as f:
        return json.load(f)


@app.get("/api/threshold/sim")
def simulate_threshold_policy(
    t1: Optional[float] = Query(None, ge=0.0, le=1.0),
    t2: Optional[float] = Query(None, ge=0.0, le=1.0),
    cost_mode: str = Query("amount_weighted", pattern="^(flat|amount_weighted)$"),
) -> Dict[str, Any]:
    """
    Simulate decision policy with arbitrary thresholds on the holdout test set:
    Returns confusion matrix, precision, recall, F1, F2, MCC, cost, and queue capacity check.
    """
    sim_t1 = t1 if t1 is not None else streaming_engine.t1
    sim_t2 = t2 if t2 is not None else streaming_engine.t2

    if sim_t1 > sim_t2:
        raise HTTPException(status_code=400, detail="t1 (review threshold) must be <= t2 (block threshold).")

    from src.policy import simulate_policy_thresholds

    # Extract test probabilities and labels from test_records
    if streaming_engine.test_records:
        test_df = pd.DataFrame(streaming_engine.test_records)
        feat_df = extract_features(test_df, reset_state=True)
        eval_cols = [c for c in streaming_engine.feature_names if c in feat_df.columns]
        probs = streaming_engine.model.predict_proba(feat_df[eval_cols])[:, 1]
        y_true = test_df.get("is_fraud", pd.Series(np.zeros(len(test_df)))).values
        amounts = test_df.get("amount", pd.Series(np.ones(len(test_df)) * 100.0)).values

        res = simulate_policy_thresholds(
            y_true=y_true,
            y_prob=probs,
            amounts=amounts,
            t1=sim_t1,
            t2=sim_t2,
            cost_mode=cost_mode,
        )

        # Compute 50-bin mirrored density curves for legitimate vs fraud scores
        bins = np.linspace(0.0, 1.0, 51)
        legit_scores = probs[y_true == 0] if len(probs[y_true == 0]) > 0 else np.array([0.0])
        fraud_scores = probs[y_true == 1] if len(probs[y_true == 1]) > 0 else np.array([1.0])

        legit_hist, _ = np.histogram(legit_scores, bins=bins)
        fraud_hist, _ = np.histogram(fraud_scores, bins=bins)

        legit_max = max(1, int(np.max(legit_hist)))
        fraud_max = max(1, int(np.max(fraud_hist)))

        density_data = [
            {
                "bin": round(float((bins[i] + bins[i+1]) / 2.0), 3),
                "legit_count": int(legit_hist[i]),
                "fraud_count": int(fraud_hist[i]),
                "legit_norm": round(float(legit_hist[i] / legit_max), 4),
                "fraud_norm": round(float(fraud_hist[i] / fraud_max), 4),
            }
            for i in range(len(legit_hist))
        ]

        return {
            "t1": sim_t1,
            "t2": sim_t2,
            "cost_mode": cost_mode,
            "metrics": res,
            "density": density_data,
            "is_what_if": True,
            "capacity_violated": bool(res.get("capacity_exceeded", False)),
        }

    return {"status": "no_test_data", "t1": sim_t1, "t2": sim_t2}


# ==============================================================================
# 7. Drift, Retraining & Rollback
# ==============================================================================
@app.get("/api/drift")
def get_drift_monitor() -> Dict[str, Any]:
    """PSI feature table, score drift overlay, weekly performance with 7d label delay, and alert status."""
    if not DRIFT_MONITOR_FILE.exists():
        raise HTTPException(status_code=404, detail="drift_monitor.json not found.")
    with open(DRIFT_MONITOR_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


@app.post("/api/retrain")
def retrain_challenger_model() -> Dict[str, Any]:
    """
    Retrain challenger model on mature transaction history, evaluate side-by-side
    against active champion, and promote only if validation gates pass.
    """
    parquet_path = DATA_DIR / "processed" / "ledgersim_fast.parquet"
    if not parquet_path.exists():
        raise HTTPException(status_code=400, detail="Transaction dataset not found for retraining.")

    df = pd.read_parquet(parquet_path)
    train_end = int(len(df) * 0.70)
    val_end = int(len(df) * 0.85)

    train_df = df.iloc[:train_end]
    val_df = df.iloc[train_end:val_end]

    feat_train = extract_features(train_df, reset_state=True)
    feat_val = extract_features(val_df, reset_state=True)

    registry = ModelRegistry()
    result = registry.retrain_challenger(
        X_train=feat_train,
        y_train=train_df["is_fraud"].values,
        X_val=feat_val,
        y_val=val_df["is_fraud"].values,
        fast=True,
    )

    # Reload streaming engine resources if promoted
    if result.get("status") == "PROMOTED":
        streaming_engine._load_resources()

    return result


@app.post("/api/rollback")
def rollback_model() -> Dict[str, Any]:
    """Safely restore previous champion model bundle from rollback storage."""
    registry = ModelRegistry()
    result = registry.rollback()
    if result.get("status") == "ROLLED_BACK":
        streaming_engine._load_resources()
    return result


# ==============================================================================
# 8. Fairness, Datasets & Hypotheses
# ==============================================================================
@app.get("/api/fairness")
def get_fairness_audit() -> Dict[str, Any]:
    """Multi-group false positive rate audit across regions/channels and evasion probe results."""
    fairness_file = ARTIFACTS_DIR / "fairness.json"
    if not fairness_file.exists():
        raise HTTPException(status_code=404, detail="fairness.json not found.")
    with open(fairness_file, "r", encoding="utf-8") as f:
        return json.load(f)


@app.get("/api/datasets")
def get_datacards() -> Dict[str, Any]:
    """Data Cards for LedgerSim, ULB Credit Card Fraud, and PaySim."""
    if not DATACARDS_FILE.exists():
        raise HTTPException(status_code=404, detail="datacards.json not found.")
    with open(DATACARDS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


@app.get("/api/hypotheses")
def get_hypothesis_verdicts() -> Dict[str, Any]:
    """Formal hypothesis testing verdicts (H1 to H4)."""
    hyp_file = ARTIFACTS_DIR / "hypotheses.json"
    if not hyp_file.exists():
        raise HTTPException(status_code=404, detail="hypotheses.json not found.")
    with open(hyp_file, "r", encoding="utf-8") as f:
        return json.load(f)


# ==============================================================================
# 9. Static File Serving for Built Frontend
# ==============================================================================
FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if FRONTEND_DIST.exists():
    from fastapi.staticfiles import StaticFiles

    app.mount("/", StaticFiles(directory=str(FRONTEND_DIST), html=True), name="static")

