"""
FraudShield Training Pipeline Orchestrator.

Orchestrates:
1. Dataset loading and time-ordered train/val/test splitting (70/15/15)
2. Feature extraction with online/batch parity (zero future leakage)
3. Full experiment matrix execution (E1 through E10):
     E1: Logistic Regression (None)
     E2: Logistic Regression (Balanced)
     E3: Random Forest (Balanced Subsample)
     E4: XGBoost (scale_pos_weight)
     E5: XGBoost + SMOTE (inside training CV pipeline)
     E6: LightGBM (scale_pos_weight)
     E7: Isolation Forest (unsupervised)
     E8: Autoencoder (unsupervised reconstruction error)
     E9: Hybrid Fusion (OOF anomaly scores + XGBoost + calibration)
     E10: Stacked Ensemble (meta-learner on base predictions + calibration)
4. Calibration and two-threshold policy optimization (t1 for review, t2 for block)
5. Single-pass evaluation on untouched test set with 95% bootstrap confidence intervals
6. Early vs late test-period evaluation (drift impact)
7. Segment fairness audit & evasion robustness probe
8. Programmatic verification of Hypotheses H1 to H4
9. Artifact serialization for API serving and UI presentation
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import joblib
import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedKFold

from config import (
    ARTIFACTS_DIR,
    CHAMPION_MODEL_FILE,
    CURVES_FILE,
    DATA_PROCESSED_DIR,
    EXPERIMENTS_FILE,
    FAIRNESS_FILE,
    HYPOTHESES_FILE,
    METRICS_FILE,
    RANDOM_SEED,
    THRESHOLDS_FILE,
)
from src.data import load_ledgersim, time_split
from src.evaluate import (
    evaluate_hypotheses,
    evaluate_model_full,
    generate_curve_data,
    run_evasion_robustness_probe,
    run_fairness_audit,
)
from src.features import FEATURE_COLUMNS, extract_features
from src.imbalance import build_resampling_pipeline, get_scale_pos_weight
from src.models import (
    AutoencoderAnomaly,
    HybridFraudDetector,
    IsolationForestAnomaly,
    StackedFraudEnsemble,
    create_model,
)
from src.policy import optimize_thresholds, save_thresholds

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s [%(name)s]: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("fraudshield.train")


def train_pipeline(fast: bool = True) -> Dict[str, Any]:
    """
    Execute full training pipeline.
    fast=True runs in <3 minutes on laptop CPU for rapid iteration and testing.
    """
    total_start_time = time.time()
    mode_str = "FAST (<3 min rehearsal)" if fast else "FULL (Production)"
    logger.info("=" * 70)
    logger.info("STARTING FRAUDSHIELD TRAINING PIPELINE — %s", mode_str)
    logger.info("=" * 70)

    # --------------------------------------------------------------------------
    # Step 1: Ingest Data & Strict Chronological Split
    # --------------------------------------------------------------------------
    logger.info("Step 1/9: Loading transaction data and applying time-ordered split...")
    df_raw = load_ledgersim(fast=fast)
    train_df, val_df, test_df = time_split(df_raw)

    y_train = train_df["is_fraud"].values
    y_val = val_df["is_fraud"].values
    y_test = test_df["is_fraud"].values

    test_amounts = test_df["amount"].values
    test_timestamps = test_df["ts"].values

    scale_pos = get_scale_pos_weight(y_train)
    logger.info(
        "Training distribution: %d total, %d fraud (scale_pos_weight=%.2f)",
        len(y_train),
        int(np.sum(y_train)),
        scale_pos,
    )

    # --------------------------------------------------------------------------
    # Step 2: Extract Engineered Features (Shared Code Path with Caching)
    # --------------------------------------------------------------------------
    logger.info("Step 2/9: Extracting engineered past-only features (FeatureStore)...")
    feat_cache_file = DATA_PROCESSED_DIR / f"features_{'fast' if fast else 'full'}.parquet"
    if feat_cache_file.exists():
        logger.info("Loading cached engineered feature matrix from %s", feat_cache_file)
        X_all = pd.read_parquet(feat_cache_file)
        n = len(df_raw)
        i1 = int(n * 0.70)
        i2 = int(n * 0.85)
        X_train = X_all.iloc[:i1].copy().reset_index(drop=True)
        X_val = X_all.iloc[i1:i2].copy().reset_index(drop=True)
        X_test = X_all.iloc[i2:].copy().reset_index(drop=True)
    else:
        t_feat_start = time.time()
        X_all = extract_features(df_raw, reset_state=True)
        X_all.to_parquet(feat_cache_file, index=False)
        n = len(df_raw)
        i1 = int(n * 0.70)
        i2 = int(n * 0.85)
        X_train = X_all.iloc[:i1].copy().reset_index(drop=True)
        X_val = X_all.iloc[i1:i2].copy().reset_index(drop=True)
        X_test = X_all.iloc[i2:].copy().reset_index(drop=True)
        logger.info("Feature extraction completed in %.2fs and cached to %s", time.time() - t_feat_start, feat_cache_file)

    experiments_results: Dict[str, Any] = {}
    oof_val_predictions: Dict[str, np.ndarray] = {}
    oof_test_predictions: Dict[str, np.ndarray] = {}

    # Feature columns excluding anomaly score placeholders for base models
    base_cols = [c for c in FEATURE_COLUMNS if c not in ("iso_score", "ae_error")]
    X_train_base = X_train[base_cols]
    X_val_base = X_val[base_cols]
    X_test_base = X_test[base_cols]

    # --------------------------------------------------------------------------
    # Step 3: Run Base Supervised Models (E1 to E6)
    # --------------------------------------------------------------------------
    logger.info("Step 3/9: Executing base supervised experiments (E1 to E6)...")

    # E1: Logistic Regression (None)
    logger.info("--> Experiment E1: Logistic Regression (No class weighting)")
    m_e1 = create_model("E1_LR_None", fast=fast).fit(X_train_base, y_train)
    oof_val_predictions["E1"] = m_e1.predict_proba(X_val_base)[:, 1]
    oof_test_predictions["E1"] = m_e1.predict_proba(X_test_base)[:, 1]
    experiments_results["E1_LR_None"] = evaluate_model_full(
        "E1_LR_None", m_e1, X_test_base, y_test, amounts=test_amounts, timestamps=test_timestamps
    )

    # E2: Logistic Regression (Balanced)
    logger.info("--> Experiment E2: Logistic Regression (Balanced class weights)")
    m_e2 = create_model("E2_LR_Weighted", fast=fast).fit(X_train_base, y_train)
    oof_val_predictions["E2"] = m_e2.predict_proba(X_val_base)[:, 1]
    oof_test_predictions["E2"] = m_e2.predict_proba(X_test_base)[:, 1]
    experiments_results["E2_LR_Weighted"] = evaluate_model_full(
        "E2_LR_Weighted", m_e2, X_test_base, y_test, amounts=test_amounts, timestamps=test_timestamps
    )

    # E3: Random Forest (Balanced Subsample)
    logger.info("--> Experiment E3: Random Forest (Balanced subsample)")
    m_e3 = create_model("E3_RF_Balanced", fast=fast).fit(X_train_base, y_train)
    oof_val_predictions["E3"] = m_e3.predict_proba(X_val_base)[:, 1]
    oof_test_predictions["E3"] = m_e3.predict_proba(X_test_base)[:, 1]
    experiments_results["E3_RF_Balanced"] = evaluate_model_full(
        "E3_RF_Balanced", m_e3, X_test_base, y_test, amounts=test_amounts, timestamps=test_timestamps
    )

    # E4: XGBoost (scale_pos_weight)
    logger.info("--> Experiment E4: XGBoost (scale_pos_weight)")
    m_e4 = create_model("E4_XGBoost", scale_pos_weight=scale_pos, fast=fast)
    m_e4.fit(
        X_train_base,
        y_train,
        eval_set=[(X_val_base, y_val)],
        verbose=False,
    )
    oof_val_predictions["E4"] = m_e4.predict_proba(X_val_base)[:, 1]
    oof_test_predictions["E4"] = m_e4.predict_proba(X_test_base)[:, 1]
    experiments_results["E4_XGBoost"] = evaluate_model_full(
        "E4_XGBoost", m_e4, X_test_base, y_test, amounts=test_amounts, timestamps=test_timestamps
    )

    # E5: XGBoost + SMOTE (Pipeline inside training fold)
    logger.info("--> Experiment E5: XGBoost + SMOTE (Resampling inside pipeline)")
    raw_xgb = create_model("E5_XGBoost_SMOTE", scale_pos_weight=1.0, fast=fast)
    pipe_e5 = build_resampling_pipeline(raw_xgb, resampler_name="smote", sampling_strategy=0.20)
    pipe_e5.fit(X_train_base, y_train)
    oof_val_predictions["E5"] = pipe_e5.predict_proba(X_val_base)[:, 1]
    oof_test_predictions["E5"] = pipe_e5.predict_proba(X_test_base)[:, 1]
    experiments_results["E5_XGBoost_SMOTE"] = evaluate_model_full(
        "E5_XGBoost_SMOTE", pipe_e5, X_test_base, y_test, amounts=test_amounts, timestamps=test_timestamps
    )

    # E6: LightGBM (Class Weighted)
    logger.info("--> Experiment E6: LightGBM (scale_pos_weight)")
    m_e6 = create_model("E6_LightGBM", scale_pos_weight=scale_pos, fast=fast)
    m_e6.fit(X_train_base, y_train)
    oof_val_predictions["E6"] = m_e6.predict_proba(X_val_base)[:, 1]
    oof_test_predictions["E6"] = m_e6.predict_proba(X_test_base)[:, 1]
    experiments_results["E6_LightGBM"] = evaluate_model_full(
        "E6_LightGBM", m_e6, X_test_base, y_test, amounts=test_amounts, timestamps=test_timestamps
    )

    # --------------------------------------------------------------------------
    # Step 4: Run Unsupervised Anomaly Detectors (E7 & E8)
    # --------------------------------------------------------------------------
    logger.info("Step 4/9: Executing unsupervised anomaly models (E7 & E8)...")
    legit_train_mask = (y_train == 0)

    # E7: Isolation Forest
    logger.info("--> Experiment E7: Isolation Forest (Trained on legitimate rows only)")
    m_e7 = IsolationForestAnomaly(n_estimators=100 if fast else 300).fit(X_train_base.values[legit_train_mask])
    experiments_results["E7_IsolationForest"] = evaluate_model_full(
        "E7_IsolationForest", m_e7, X_test_base.values, y_test, amounts=test_amounts, timestamps=test_timestamps
    )

    # E8: Deep Autoencoder
    logger.info("--> Experiment E8: Deep Autoencoder (Reconstruction error)")
    m_e8 = AutoencoderAnomaly(epochs=15 if fast else 35).fit(X_train_base.values[legit_train_mask])
    experiments_results["E8_Autoencoder"] = evaluate_model_full(
        "E8_Autoencoder", m_e8, X_test_base.values, y_test, amounts=test_amounts, timestamps=test_timestamps
    )

    # --------------------------------------------------------------------------
    # Step 5: Run Hybrid Fusion with Out-of-Fold Anomaly Scoring (E9)
    # --------------------------------------------------------------------------
    logger.info("Step 5/9: Training Headline Hybrid Model E9 (Anomaly branch + XGBoost + Calibration)...")
    m_e9 = HybridFraudDetector(
        scale_pos_weight=scale_pos,
        n_folds=3 if fast else 5,
        fast=fast,
        random_state=RANDOM_SEED,
    )
    m_e9.fit(X_train, y_train, X_val, y_val)

    # --------------------------------------------------------------------------
    # Step 6: Optimize Dual-Threshold Decision Policy (t1 review, t2 block)
    # --------------------------------------------------------------------------
    logger.info("Step 6/9: Optimizing decision policy thresholds (t1, t2) on validation set...")
    val_probs = m_e9.predict_proba(X_val)[:, 1]
    val_amounts = val_df["amount"].values

    policy_thresholds = optimize_thresholds(
        y_val=y_val,
        p_val=val_probs,
        amounts=val_amounts,
        cost_mode="amount_weighted",
        version="1.0.0",
    )
    save_thresholds(policy_thresholds)

    # Evaluate E9 on untouched test set at its optimized threshold
    experiments_results["E9_Hybrid"] = evaluate_model_full(
        "E9_Hybrid",
        m_e9,
        X_test,
        y_test,
        threshold=policy_thresholds.t1_review,
        amounts=test_amounts,
        timestamps=test_timestamps,
    )

    # --------------------------------------------------------------------------
    # Step 7: Run Stacked Ensemble (E10)
    # --------------------------------------------------------------------------
    logger.info("Step 7/9: Executing Stacked Ensemble E10...")
    # Assemble base model predictions matrix on validation and test
    val_meta_X = np.column_stack([
        oof_val_predictions["E2"],
        oof_val_predictions["E3"],
        oof_val_predictions["E4"],
        oof_val_predictions["E6"],
    ])
    test_meta_X = np.column_stack([
        oof_test_predictions["E2"],
        oof_test_predictions["E3"],
        oof_test_predictions["E4"],
        oof_test_predictions["E6"],
    ])

    m_e10 = StackedFraudEnsemble()
    m_e10.fit(val_meta_X, y_val, val_meta_X, y_val)
    experiments_results["E10_Stacked"] = evaluate_model_full(
        "E10_Stacked",
        m_e10,
        test_meta_X,
        y_test,
        threshold=policy_thresholds.t1_review,
        amounts=test_amounts,
        timestamps=test_timestamps,
    )

    # --------------------------------------------------------------------------
    # Step 8: Generate Curves, Fairness Audit, Evasion Probe & Hypotheses
    # --------------------------------------------------------------------------
    logger.info("Step 8/9: Computing curves, fairness audit, evasion probe, and hypothesis tests...")
    test_probs_e9 = m_e9.predict_proba(X_test)[:, 1]

    # Generate visual curve coordinates for front-end SVG
    curves_data = {
        "champion_e9": generate_curve_data(y_test, test_probs_e9, amounts=test_amounts),
        "baseline_e4": generate_curve_data(y_test, oof_test_predictions["E4"], amounts=test_amounts),
        "baseline_lr": generate_curve_data(y_test, oof_test_predictions["E2"], amounts=test_amounts),
    }

    # Multi-group Fairness Audit
    fairness_audit = run_fairness_audit(
        df=test_df,
        y_prob=test_probs_e9,
        threshold=policy_thresholds.t1_review,
        group_cols=["ip_region", "channel"],
    )

    # Adversarial Evasion Robustness Probe (-30% fraud amounts)
    evasion_results = run_evasion_robustness_probe(
        model=m_e9,
        feature_store_cls=None,
        test_df=test_df,
        threshold=policy_thresholds.t1_review,
        amount_reduction_pct=0.30,
    )
    fairness_audit["evasion_probe"] = evasion_results

    # Scientific Hypothesis Verification Engine (H1 to H4)
    hypotheses_verdicts = evaluate_hypotheses(experiments_results)

    # Champion headline KPIs
    champion_kpi = experiments_results["E9_Hybrid"].copy()
    champion_kpi["model_version"] = "1.0.0"
    champion_kpi["t1_review"] = policy_thresholds.t1_review
    champion_kpi["t2_block"] = policy_thresholds.t2_block
    champion_kpi["training_duration_seconds"] = round(time.time() - total_start_time, 2)
    champion_kpi["fast_mode"] = fast

    # --------------------------------------------------------------------------
    # Step 9: Serialize All Deliverables & Model Bundle
    # --------------------------------------------------------------------------
    logger.info("Step 9/9: Saving model bundle and all verification artifacts...")
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

    # Save Champion Model Bundle
    model_bundle = {
        "model": m_e9,
        "feature_names": m_e9.feature_names,
        "t1": policy_thresholds.t1_review,
        "t2": policy_thresholds.t2_block,
        "version": "1.0.0",
        "calibration_method": m_e9.calibration_method,
        "brier_score": m_e9.brier_score_val,
        "trained_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    joblib.dump(model_bundle, CHAMPION_MODEL_FILE)
    logger.info("Saved champion model bundle to %s", CHAMPION_MODEL_FILE)

    # Save JSON artifacts
    with open(EXPERIMENTS_FILE, "w", encoding="utf-8") as f:
        json.dump(experiments_results, f, indent=2)
    logger.info("Saved experiments matrix to %s", EXPERIMENTS_FILE)

    with open(CURVES_FILE, "w", encoding="utf-8") as f:
        json.dump(curves_data, f, indent=2)
    logger.info("Saved curve coordinates to %s", CURVES_FILE)

    with open(METRICS_FILE, "w", encoding="utf-8") as f:
        json.dump(champion_kpi, f, indent=2)
    logger.info("Saved headline metrics to %s", METRICS_FILE)

    with open(FAIRNESS_FILE, "w", encoding="utf-8") as f:
        json.dump(fairness_audit, f, indent=2)
    logger.info("Saved fairness audit to %s", FAIRNESS_FILE)

    with open(HYPOTHESES_FILE, "w", encoding="utf-8") as f:
        json.dump(hypotheses_verdicts, f, indent=2)
    logger.info("Saved hypothesis verification verdicts to %s", HYPOTHESES_FILE)

    elapsed_total = time.time() - total_start_time
    logger.info("=" * 70)
    logger.info("TRAINING PIPELINE COMPLETE in %.2f seconds (%.2f minutes)", elapsed_total, elapsed_total / 60.0)
    logger.info("Champion Model (E9 Hybrid): PR-AUC = %.4f | Recall@P90 = %.4f", champion_kpi["pr_auc"], champion_kpi["recall_at_p90"])
    logger.info("Optimal Policy: t1=%.4f (review), t2=%.4f (block)", policy_thresholds.t1_review, policy_thresholds.t2_block)
    logger.info("=" * 70)

    return champion_kpi


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="FraudShield Training Orchestrator")
    parser.add_argument("--fast", action="store_true", default=False, help="Run fast training for testing (<3 min)")
    args = parser.parse_args()

    train_pipeline(fast=args.fast)
