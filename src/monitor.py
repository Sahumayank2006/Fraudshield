"""
FraudShield Monitoring & Operations Engine (src/monitor.py)
===========================================================
Continuous drift tracking, Population Stability Index (PSI), score distribution
monitoring, 7-day label maturation tracking, and champion-challenger retraining
with safe one-click rollback.

Design Constraints:
1. Exact PSI formula using reference decile binning with epsilon clipping ($10^{-6}$).
2. Regulatory status bands: <0.10 (Stable), 0.10-0.25 (Moderate), >=0.25 (Significant).
3. 7-day label maturation window respected: immature transactions are not scored as false positives.
4. Champion-challenger validation gating with atomic filesystem rollback.
"""

from __future__ import annotations

import copy
import datetime
import json
import logging
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import joblib
import numpy as np
import pandas as pd
from scipy import stats

from config import (
    ARTIFACTS_DIR,
    CHAMPION_MODEL_FILE,
    LABEL_MATURITY_SECONDS,
    RANDOM_SEED,
)

logger = logging.getLogger("fraudshield.monitor")

REGISTRY_METADATA_FILE = ARTIFACTS_DIR / "model_registry.json"
ROLLBACK_MODEL_FILE = ARTIFACTS_DIR / "model_rollback.joblib"
DRIFT_MONITOR_FILE = ARTIFACTS_DIR / "drift_monitor.json"


# ==============================================================================
# 1. Population Stability Index (PSI) Calculation
# ==============================================================================
def compute_psi(
    reference: Union[np.ndarray, pd.Series],
    current: Union[np.ndarray, pd.Series],
    n_bins: int = 10,
    epsilon: float = 1e-6,
) -> Dict[str, Any]:
    """
    Compute Population Stability Index (PSI) between a reference baseline distribution
    and a current observed distribution:
        PSI = sum((curr_pct - ref_pct) * ln((curr_pct + eps) / (ref_pct + eps)))

    Bin edges are determined by reference quantiles. Edge bins extend to [-inf, +inf].
    """
    ref_arr = np.asarray(reference, dtype=float)
    curr_arr = np.asarray(current, dtype=float)

    # Clean NaNs and Infs
    ref_clean = ref_arr[np.isfinite(ref_arr)]
    curr_clean = curr_arr[np.isfinite(curr_arr)]

    if len(ref_clean) == 0 or len(curr_clean) == 0:
        return {
            "psi": 0.0,
            "status": "STABLE",
            "bin_edges": [],
            "ref_pct": [],
            "curr_pct": [],
            "ref_counts": [],
            "curr_counts": [],
        }

    # Reference quantiles for bin edges
    quantiles = np.linspace(0.0, 100.0, n_bins + 1)
    bin_edges = np.percentile(ref_clean, quantiles)

    # Deduplicate bin edges in case of zero-inflation or constant values
    unique_edges = np.unique(bin_edges)
    if len(unique_edges) < 2:
        # Distribution is constant
        return {
            "psi": 0.0,
            "status": "STABLE",
            "bin_edges": [float(ref_clean[0]) - 1.0, float(ref_clean[0]) + 1.0],
            "ref_pct": [1.0],
            "curr_pct": [1.0],
            "ref_counts": [len(ref_clean)],
            "curr_counts": [len(curr_clean)],
        }

    # Set outermost edges to -inf and +inf so no values fall outside
    bin_edges_eval = unique_edges.copy()
    bin_edges_eval[0] = -np.inf
    bin_edges_eval[-1] = np.inf

    # Compute histogram counts
    ref_counts, _ = np.histogram(ref_clean, bins=bin_edges_eval)
    curr_counts, _ = np.histogram(curr_clean, bins=bin_edges_eval)

    # Fractions
    ref_pct = ref_counts / len(ref_clean)
    curr_pct = curr_counts / len(curr_clean)

    # PSI summation with epsilon protection
    ref_adj = np.clip(ref_pct, epsilon, 1.0)
    curr_adj = np.clip(curr_pct, epsilon, 1.0)

    psi_contributions = (curr_adj - ref_adj) * np.log(curr_adj / ref_adj)
    psi_total = float(np.sum(psi_contributions))
    psi_total = max(0.0, psi_total)

    # Classification status
    if psi_total < 0.10:
        status = "STABLE"
    elif psi_total < 0.25:
        status = "MODERATE"
    else:
        status = "SIGNIFICANT"

    # Human-readable formatted edges for display
    display_edges = [round(float(e), 4) for e in unique_edges]

    return {
        "psi": round(psi_total, 4),
        "status": status,
        "bin_edges": display_edges,
        "ref_pct": [round(float(p), 4) for p in ref_pct],
        "curr_pct": [round(float(p), 4) for p in curr_pct],
        "ref_counts": [int(c) for c in ref_counts],
        "curr_counts": [int(c) for c in curr_counts],
    }


def compute_feature_drift_table(
    reference_df: pd.DataFrame,
    current_df: pd.DataFrame,
    feature_cols: List[str],
) -> List[Dict[str, Any]]:
    """
    Compute PSI across all numerical features and sort descending by drift severity.
    """
    table: List[Dict[str, Any]] = []

    for col in feature_cols:
        if col not in reference_df.columns or col not in current_df.columns:
            continue

        ref_series = reference_df[col].dropna()
        curr_series = current_df[col].dropna()

        psi_res = compute_psi(ref_series, curr_series, n_bins=10)

        # Compute summary stats
        ref_mean = float(ref_series.mean()) if len(ref_series) else 0.0
        curr_mean = float(curr_series.mean()) if len(curr_series) else 0.0
        mean_delta = curr_mean - ref_mean

        table.append({
            "feature": col,
            "label": col.replace("_", " ").title(),
            "psi": psi_res["psi"],
            "status": psi_res["status"],
            "ref_mean": round(ref_mean, 4),
            "curr_mean": round(curr_mean, 4),
            "mean_delta": round(mean_delta, 4),
            "bin_edges": psi_res["bin_edges"],
            "ref_pct": psi_res["ref_pct"],
            "curr_pct": psi_res["curr_pct"],
        })

    # Sort descending by PSI
    table.sort(key=lambda x: x["psi"], reverse=True)
    return table


# ==============================================================================
# 2. Score Distribution Drift & Kolmogorov-Smirnov Test
# ==============================================================================
def compute_score_drift(
    reference_scores: Union[np.ndarray, List[float]],
    current_scores: Union[np.ndarray, List[float]],
    n_bins: int = 20,
) -> Dict[str, Any]:
    """
    Analyze risk score distribution drift:
    - Score PSI
    - Kolmogorov-Smirnov 2-sample test
    - Score decile shifts
    - Histogram coordinates for then-versus-now visualization
    """
    ref = np.asarray(reference_scores, dtype=float)
    curr = np.asarray(current_scores, dtype=float)

    ref = ref[np.isfinite(ref)]
    curr = curr[np.isfinite(curr)]

    if len(ref) == 0 or len(curr) == 0:
        return {
            "psi": 0.0,
            "status": "STABLE",
            "ks_statistic": 0.0,
            "ks_pvalue": 1.0,
            "ref_mean": 0.0,
            "curr_mean": 0.0,
            "histogram": [],
        }

    # 1. Score PSI using uniform probability bins [0.0 to 1.0]
    fixed_bins = np.linspace(0.0, 1.0, 11)
    ref_counts, _ = np.histogram(ref, bins=fixed_bins)
    curr_counts, _ = np.histogram(curr, bins=fixed_bins)

    ref_pct = np.clip(ref_counts / len(ref), 1e-6, 1.0)
    curr_pct = np.clip(curr_counts / len(curr), 1e-6, 1.0)
    score_psi = float(np.sum((curr_pct - ref_pct) * np.log(curr_pct / ref_pct)))
    score_psi = max(0.0, score_psi)

    # 2. Kolmogorov-Smirnov Test
    ks_res = stats.ks_2samp(ref, curr)
    ks_stat = float(ks_res.statistic)
    ks_pval = float(ks_res.pvalue)

    # 3. Status
    if score_psi < 0.10:
        status = "STABLE"
    elif score_psi < 0.25:
        status = "MODERATE"
    else:
        status = "SIGNIFICANT"

    # 4. Detailed 20-bin histogram coordinates for frontend SVG overlay
    hist_bins = np.linspace(0.0, 1.0, n_bins + 1)
    ref_hist, _ = np.histogram(ref, bins=hist_bins, density=True)
    curr_hist, _ = np.histogram(curr, bins=hist_bins, density=True)

    histogram_data = []
    for i in range(n_bins):
        histogram_data.append({
            "bin_start": round(float(hist_bins[i]), 3),
            "bin_end": round(float(hist_bins[i + 1]), 3),
            "bin_mid": round(float((hist_bins[i] + hist_bins[i + 1]) / 2.0), 3),
            "ref_density": round(float(ref_hist[i]), 4),
            "curr_density": round(float(curr_hist[i]), 4),
        })

    return {
        "psi": round(score_psi, 4),
        "status": status,
        "ks_statistic": round(ks_stat, 4),
        "ks_pvalue": round(ks_pval, 6),
        "ref_mean": round(float(np.mean(ref)), 5),
        "curr_mean": round(float(np.mean(curr)), 5),
        "ref_median": round(float(np.median(ref)), 5),
        "curr_median": round(float(np.median(curr)), 5),
        "ref_p95": round(float(np.percentile(ref, 95)), 5),
        "curr_p95": round(float(np.percentile(curr, 95)), 5),
        "histogram": histogram_data,
    }


# ==============================================================================
# 3. Weekly Performance Tracker (7-Day Label Maturation)
# ==============================================================================
def compute_weekly_performance(
    df: pd.DataFrame,
    probs: np.ndarray,
    preds: np.ndarray,
    label_col: str = "is_fraud",
    time_col: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Cohort transactions into calendar week intervals.
    Enforces 7-day label maturation rule: transactions younger than 7 days from the
    latest recorded timestamp are classified as 'Immature' to avoid false performance alarms.
    """
    if len(df) == 0:
        return []

    eval_df = df.copy()
    eval_df["prob"] = probs
    eval_df["pred"] = preds

    # Auto-detect timestamp column
    if time_col is None:
        if "ts" in eval_df.columns:
            time_col = "ts"
        elif "timestamp" in eval_df.columns:
            time_col = "timestamp"
        elif "time" in eval_df.columns:
            time_col = "time"
        else:
            time_col = "ts"

    if time_col not in eval_df.columns:
        # Fallback to sequential synthetic timestamps
        eval_df[time_col] = np.arange(len(eval_df)) * 60.0

    t_max = float(eval_df[time_col].max())
    t_min = float(eval_df[time_col].min())
    maturation_cutoff = t_max - LABEL_MATURITY_SECONDS

    one_week_secs = 7 * 24 * 3600
    n_weeks = max(1, int(np.ceil((t_max - t_min) / one_week_secs)))

    weekly_results: List[Dict[str, Any]] = []

    for w in range(n_weeks):
        w_start = t_min + w * one_week_secs
        w_end = min(t_max + 1, w_start + one_week_secs)

        mask = (eval_df[time_col] >= w_start) & (eval_df[time_col] < w_end)
        w_slice = eval_df[mask]

        if len(w_slice) == 0:
            continue

        is_mature = bool(w_end <= maturation_cutoff)
        total_tx = len(w_slice)
        fraud_tx = int(w_slice[label_col].sum())
        flagged_tx = int(w_slice["pred"].sum())

        entry: Dict[str, Any] = {
            "week_index": w + 1,
            "week_label": f"Week {w + 1}",
            "start_time": int(w_start),
            "end_time": int(w_end),
            "total_transactions": total_tx,
            "is_mature": is_mature,
            "status": "Mature" if is_mature else "Pending 7d Maturation",
        }

        if is_mature and fraud_tx > 0:
            tp = int(((w_slice["pred"] == 1) & (w_slice[label_col] == 1)).sum())
            fp = int(((w_slice["pred"] == 1) & (w_slice[label_col] == 0)).sum())
            fn = int(((w_slice["pred"] == 0) & (w_slice[label_col] == 1)).sum())

            prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            f1 = 2 * (prec * rec) / (prec + rec) if (prec + rec) > 0 else 0.0

            from sklearn.metrics import precision_recall_curve, auc
            p_curve, r_curve, _ = precision_recall_curve(w_slice[label_col], w_slice["prob"])
            pr_auc = float(auc(r_curve, p_curve))

            entry.update({
                "fraud_count": fraud_tx,
                "fraud_rate": round(fraud_tx / total_tx, 5),
                "flagged_count": flagged_tx,
                "precision": round(prec, 4),
                "recall": round(rec, 4),
                "pr_auc": round(pr_auc, 4),
                "f1": round(f1, 4),
            })
        else:
            entry.update({
                "fraud_count": fraud_tx,
                "fraud_rate": round(fraud_tx / total_tx, 5) if total_tx > 0 else 0.0,
                "flagged_count": flagged_tx,
                "precision": None,
                "recall": None,
                "pr_auc": None,
                "f1": None,
            })

        weekly_results.append(entry)

    return weekly_results


# ==============================================================================
# 4. Drift Health & Retraining Trigger Rules
# ==============================================================================
def evaluate_drift_health(
    feature_psi_table: List[Dict[str, Any]],
    score_drift: Dict[str, Any],
    weekly_perf: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Evaluate system drift health and trigger retraining recommendations:
    Triggers 'RETRAIN_RECOMMENDED' if:
    1. Score distribution PSI >= 0.25 (significant shift in predicted risk).
    2. >= 3 high-impact features demonstrate SIGNIFICANT drift (PSI >= 0.25).
    3. Latest mature weekly Recall drops by >= 15% relative to initial weeks.
    """
    triggers: List[str] = []

    # 1. Score PSI check
    score_psi = score_drift.get("psi", 0.0)
    if score_psi >= 0.25:
        triggers.append(
            f"Risk score PSI reached {score_psi:.3f} (exceeds 0.25 significant drift threshold)."
        )

    # 2. Feature PSI check
    sig_features = [f for f in feature_psi_table if f.get("status") == "SIGNIFICANT"]
    if len(sig_features) >= 3:
        feature_names = [f["feature"] for f in sig_features[:3]]
        triggers.append(
            f"{len(sig_features)} features demonstrate severe drift (top: {', '.join(feature_names)})."
        )

    # 3. Performance decay check
    mature_weeks = [w for w in weekly_perf if w.get("is_mature") and w.get("recall") is not None]
    if len(mature_weeks) >= 2:
        baseline_recall = mature_weeks[0]["recall"]
        latest_recall = mature_weeks[-1]["recall"]
        if baseline_recall > 0 and (latest_recall < baseline_recall * 0.85):
            decay_pct = (1.0 - (latest_recall / baseline_recall)) * 100.0
            triggers.append(
                f"Mature weekly recall degraded by {decay_pct:.1f}% ({baseline_recall:.3f} -> {latest_recall:.3f})."
            )

    alert_state = "RETRAIN_RECOMMENDED" if len(triggers) > 0 else "HEALTHY"

    return {
        "alert_state": alert_state,
        "triggers": triggers,
        "significant_features_count": len(sig_features),
        "score_psi": score_psi,
        "evaluated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "recommended_action": (
            "Initiate challenger retraining pipeline on latest mature window."
            if alert_state == "RETRAIN_RECOMMENDED"
            else "Monitoring active; no retraining required."
        ),
    }


# ==============================================================================
# 5. Model Registry, Challenger Retrain & Safe Rollback
# ==============================================================================
class ModelRegistry:
    """
    Manages active champion and challenger models, validation gate evaluation,
    atomic model promotion, and one-click rollback.
    """

    def __init__(
        self,
        champion_path: Path = CHAMPION_MODEL_FILE,
        rollback_path: Path = ROLLBACK_MODEL_FILE,
        metadata_path: Path = REGISTRY_METADATA_FILE,
    ):
        self.champion_path = Path(champion_path)
        self.rollback_path = Path(rollback_path)
        self.metadata_path = Path(metadata_path)
        self._ensure_metadata_file()

    def _ensure_metadata_file(self) -> None:
        if not self.metadata_path.exists():
            default_meta = {
                "active_version": "v1.0-champion",
                "active_trained_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "has_rollback": self.rollback_path.exists(),
                "rollback_version": None,
                "latest_comparison": None,
                "history": [],
            }
            self.metadata_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.metadata_path, "w", encoding="utf-8") as f:
                json.dump(default_meta, f, indent=2)

    def get_metadata(self) -> Dict[str, Any]:
        self._ensure_metadata_file()
        with open(self.metadata_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
        meta["has_rollback"] = self.rollback_path.exists()
        return meta

    def save_metadata(self, meta: Dict[str, Any]) -> None:
        self.metadata_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.metadata_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)

    def load_champion(self) -> Dict[str, Any]:
        if not self.champion_path.exists():
            raise FileNotFoundError(f"Champion model not found at {self.champion_path}")
        return joblib.load(self.champion_path)

    def retrain_challenger(
        self,
        X_train: pd.DataFrame,
        y_train: np.ndarray,
        X_val: pd.DataFrame,
        y_val: np.ndarray,
        fast: bool = True,
    ) -> Dict[str, Any]:
        """
        Retrain a challenger model, evaluate side-by-side against active champion on
        the validation set, apply strict promotion gates, and promote if superior.
        """
        logger.info("Retraining Challenger model (fast=%s, N_train=%d)...", fast, len(X_train))

        # 1. Load active champion
        champion_bundle = self.load_champion()
        champion_model = champion_bundle.get("model") or champion_bundle.get("champion")

        # 2. Evaluate active champion baseline on validation
        from src.evaluate import evaluate_model
        champ_metrics = evaluate_model(
            champion_model,
            X_val,
            y_val,
            model_id="Champion_Active",
            compute_ci=False,
        )

        # 3. Train Challenger Model (E9 Hybrid Architecture)
        from src.models import HybridFraudDetector
        challenger_model = HybridFraudDetector(
            scale_pos_weight=float(len(y_train) - y_train.sum()) / max(1, y_train.sum()),
            fast=fast,
            random_state=RANDOM_SEED + 99,
        )
        challenger_model.fit(X_train, y_train, X_val, y_val)

        # 4. Evaluate Challenger on validation
        challenger_metrics = evaluate_model(
            challenger_model,
            X_val,
            y_val,
            model_id="Challenger_Candidate",
            compute_ci=False,
        )

        # 5. Side-by-Side Validation Promotion Gate
        # Gate Criteria:
        # a) PR-AUC must be at least within 1% of champion or higher
        # b) Expected Cost must not exceed champion by >5%
        # c) Inference latency must remain under 25ms
        pr_diff = challenger_metrics["pr_auc"] - champ_metrics["pr_auc"]
        cost_diff = challenger_metrics["expected_cost_flat"] - champ_metrics["expected_cost_flat"]
        latency_ok = challenger_metrics["latency_p95_ms"] <= 25.0

        gate_pr_pass = pr_diff >= -0.010
        gate_cost_pass = cost_diff <= 0.05 * champ_metrics["expected_cost_flat"]
        gate_passed = gate_pr_pass and gate_cost_pass and latency_ok

        meta = self.get_metadata()
        timestamp_str = datetime.datetime.now(datetime.timezone.utc).isoformat()
        new_version = f"v{len(meta.get('history', [])) + 2}.0-challenger"

        comparison = {
            "evaluated_at": timestamp_str,
            "gate_passed": gate_passed,
            "criteria": {
                "pr_auc_rule": {
                    "passed": bool(gate_pr_pass),
                    "champion": champ_metrics["pr_auc"],
                    "challenger": challenger_metrics["pr_auc"],
                    "delta": round(pr_diff, 4),
                },
                "expected_cost_rule": {
                    "passed": bool(gate_cost_pass),
                    "champion": champ_metrics["expected_cost_flat"],
                    "challenger": challenger_metrics["expected_cost_flat"],
                    "delta": round(cost_diff, 2),
                },
                "latency_rule": {
                    "passed": bool(latency_ok),
                    "latency_p95_ms": challenger_metrics["latency_p95_ms"],
                    "limit_ms": 25.0,
                },
            },
            "champion_summary": {
                "pr_auc": champ_metrics["pr_auc"],
                "recall_at_p90": champ_metrics["recall_at_p90"],
                "cost": champ_metrics["expected_cost_flat"],
                "mcc": champ_metrics["mcc"],
            },
            "challenger_summary": {
                "pr_auc": challenger_metrics["pr_auc"],
                "recall_at_p90": challenger_metrics["recall_at_p90"],
                "cost": challenger_metrics["expected_cost_flat"],
                "mcc": challenger_metrics["mcc"],
            },
        }

        if gate_passed:
            logger.info("Promotion Gate PASSED. Backing up active champion and promoting challenger...")
            # Backup current champion
            if self.champion_path.exists():
                shutil.copy2(self.champion_path, self.rollback_path)

            # Save new challenger bundle
            challenger_bundle = {
                "model": challenger_model,
                "feature_names": champion_bundle.get("feature_names", list(X_train.columns)),
                "t1": champion_bundle.get("t1", 0.005),
                "t2": champion_bundle.get("t2", 0.059),
                "version": new_version,
                "calibration_method": getattr(challenger_model, "calibration_method", "isotonic"),
                "brier_score": getattr(challenger_model, "brier_score_val", 0.0),
                "trained_at": timestamp_str,
            }
            joblib.dump(challenger_bundle, self.champion_path)

            meta["rollback_version"] = meta["active_version"]
            meta["active_version"] = new_version
            meta["active_trained_at"] = timestamp_str
            meta["has_rollback"] = True
            meta["latest_comparison"] = comparison
            meta["history"].append({
                "action": "PROMOTED",
                "version": new_version,
                "timestamp": timestamp_str,
                "pr_auc": challenger_metrics["pr_auc"],
            })
            self.save_metadata(meta)

            return {
                "status": "PROMOTED",
                "version": new_version,
                "gate_passed": True,
                "comparison": comparison,
            }
        else:
            logger.warning("Promotion Gate FAILED. Challenger candidate rejected; active champion retained.")
            meta["latest_comparison"] = comparison
            meta["history"].append({
                "action": "REJECTED",
                "version": f"{new_version}-rejected",
                "timestamp": timestamp_str,
                "reasons": [
                    k for k, v in comparison["criteria"].items() if not v.get("passed", True)
                ],
            })
            self.save_metadata(meta)

            return {
                "status": "REJECTED",
                "gate_passed": False,
                "comparison": comparison,
            }

    def rollback(self) -> Dict[str, Any]:
        """
        Safely restore the previous champion model bundle from rollback storage.
        """
        if not self.rollback_path.exists():
            return {
                "status": "ERROR",
                "message": "No rollback artifact found on disk.",
            }

        meta = self.get_metadata()
        current_active = meta.get("active_version", "unknown")
        rollback_target = meta.get("rollback_version", "v1.0-champion-restored")

        logger.info("Executing safe rollback from %s back to %s...", current_active, rollback_target)

        # Atomic copy rollback file to champion file
        shutil.copy2(self.rollback_path, self.champion_path)

        timestamp_str = datetime.datetime.now(datetime.timezone.utc).isoformat()
        meta["active_version"] = rollback_target
        meta["active_trained_at"] = timestamp_str
        meta["history"].append({
            "action": "ROLLED_BACK",
            "from_version": current_active,
            "to_version": rollback_target,
            "timestamp": timestamp_str,
        })
        self.save_metadata(meta)

        return {
            "status": "ROLLED_BACK",
            "active_version": rollback_target,
            "message": f"Successfully restored model {rollback_target}.",
        }


# ==============================================================================
# 6. Baseline Drift Monitor Generator
# ==============================================================================
def generate_baseline_drift_report(
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    feature_cols: List[str],
    champion_bundle: Optional[Dict[str, Any]] = None,
    output_path: Optional[Union[str, Path]] = None,
) -> Dict[str, Any]:
    """
    Generate initial baseline drift monitoring report comparing training distribution
    with the test partition (which contains the concept drift segment in the last 25%).
    Saves results to artifacts/drift_monitor.json.
    """
    logger.info("Computing baseline drift report (Train N=%d vs Test N=%d)...", len(train_df), len(test_df))

    # 1. Feature PSI Table
    feature_psi_table = compute_feature_drift_table(train_df, test_df, feature_cols)

    # 2. Score Drift
    if champion_bundle is None and CHAMPION_MODEL_FILE.exists():
        champion_bundle = joblib.load(CHAMPION_MODEL_FILE)

    if champion_bundle is not None:
        model = champion_bundle.get("model") or champion_bundle.get("champion")
        ref_sample = train_df[feature_cols].iloc[:2000]
        test_sample = test_df[feature_cols].iloc[:2000]

        ref_probs = model.predict_proba(ref_sample)[:, 1]
        test_probs = model.predict_proba(test_sample)[:, 1]

        score_drift = compute_score_drift(ref_probs, test_probs)

        # 3. Weekly performance
        test_preds = (test_probs >= champion_bundle.get("t2", 0.059)).astype(int)
        weekly_perf = compute_weekly_performance(test_df.iloc[:2000], test_probs, test_preds)
    else:
        score_drift = {
            "psi": 0.0,
            "status": "STABLE",
            "ks_statistic": 0.0,
            "ks_pvalue": 1.0,
            "ref_mean": 0.0,
            "curr_mean": 0.0,
            "histogram": [],
        }
        weekly_perf = []

    # 4. Drift Health & Alerts
    drift_health = evaluate_drift_health(feature_psi_table, score_drift, weekly_perf)

    # 5. Model Registry status
    registry = ModelRegistry()
    registry_meta = registry.get_metadata()

    report = {
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "summary": {
            "overall_health": drift_health["alert_state"],
            "score_psi": score_drift.get("psi", 0.0),
            "score_drift_status": score_drift.get("status", "STABLE"),
            "features_monitored": len(feature_psi_table),
            "significant_drifting_features": drift_health["significant_features_count"],
            "triggers": drift_health["triggers"],
            "recommended_action": drift_health["recommended_action"],
        },
        "score_drift": score_drift,
        "feature_psi_table": feature_psi_table,
        "weekly_performance": weekly_perf,
        "model_registry": registry_meta,
    }

    if output_path is None:
        output_path = DRIFT_MONITOR_FILE
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    logger.info("Saved baseline drift report to %s", output_path)
    return report
