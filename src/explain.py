"""
FraudShield Explainability Engine (src/explain.py)
==================================================
Provides exact TreeSHAP feature attribution, dynamic plain-English reason codes,
waterfall decomposition, and global explainability artifacts (beeswarm, dependence,
permutation importance cross-check).

Design Constraints:
1. Native XGBoost `pred_contribs=True` for exact TreeSHAP ($O(TLD^2)$), zero external shap dependency required.
2. Dynamic reason codes embed verified feature values and business context (no unresolved placeholders).
3. Explicit causality caution attached to all attribution summaries.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd
import xgboost as xgb

from config import ARTIFACTS_DIR, RANDOM_SEED

logger = logging.getLogger("fraudshield.explain")

# Explicit causality disclaimer required by specifications
CAUSALITY_CAUTION = (
    "SHAP values explain which model inputs drove this specific prediction score; "
    "they reflect statistical associations learned by the tree ensemble and do NOT "
    "prove real-world causality."
)


# ==============================================================================
# 1. Dynamic Reason Code Templates (Matched to FEATURE_COLUMNS)
# ==============================================================================
REASON_CODE_TEMPLATES: Dict[str, Dict[str, str]] = {
    "log_amount": {
        "headline": "Elevated Capital Scale",
        "template": "Log transaction scale indicates significant capital exposure (₹{amount:,.2f}).",
        "icon": "trending-up",
    },
    "amount_zscore_by_account": {
        "headline": "Extreme Account Deviation",
        "template": "Amount deviates by {amount_zscore_by_account:+.1f} standard deviations from account norms.",
        "icon": "activity",
    },
    "amount_to_balance_ratio": {
        "headline": "Severe Balance Depletion",
        "template": "Transfer consumes {balance_drain_pct:.1f}% of total available account balance.",
        "icon": "percent",
    },
    "drains_account": {
        "headline": "Account Drain Event",
        "template": "Transaction nearly or completely liquidates available liquid account reserves.",
        "icon": "alert-triangle",
    },
    "hour": {
        "headline": "Off-Peak Night Window",
        "template": "Transaction initiated at {hour:02.0f}:00 during low-activity off-peak night hours.",
        "icon": "moon",
    },
    "is_night": {
        "headline": "Late Night Activity",
        "template": "Out-of-cycle transfer initiated during late night clearing window (00:00 - 05:00).",
        "icon": "moon",
    },
    "time_since_last_txn": {
        "headline": "Rapid Consecutive Transfer",
        "template": "Only {mins_since_prev:.1f} minutes elapsed since the preceding transaction on this account.",
        "icon": "fast-forward",
    },
    "time_since_account_open": {
        "headline": "New Account Exposure",
        "template": "Transaction conducted on newly opened account ({days_since_open:.1f} days old).",
        "icon": "user-plus",
    },
    "txn_count_1h": {
        "headline": "Elevated Hourly Velocity",
        "template": "{txn_count_1h:.0f} transactions completed in the past 60 minutes.",
        "icon": "clock",
    },
    "txn_count_24h": {
        "headline": "Surge in Daily Transactions",
        "template": "Unusual 24-hour volume: {txn_count_24h:.0f} transactions logged against this account.",
        "icon": "repeat",
    },
    "txn_count_7d": {
        "headline": "7-Day Volume Acceleration",
        "template": "Sustained weekly activity surge: {txn_count_7d:.0f} transactions in the past 7 days.",
        "icon": "calendar",
    },
    "amount_sum_1h": {
        "headline": "Heavy 1-Hour Outbound Drain",
        "template": "Rapid capital movement: ₹{amount_sum_1h:,.2f} transferred within a single hour.",
        "icon": "arrow-up-right",
    },
    "amount_sum_24h": {
        "headline": "Large 24-Hour Aggregate Outflow",
        "template": "Cumulative 24-hour spend reached ₹{amount_sum_24h:,.2f}, exceeding regular baseline.",
        "icon": "credit-card",
    },
    "distinct_merchants_24h": {
        "headline": "Rapid Multi-Merchant Dispersion",
        "template": "Card presented across {distinct_merchants_24h:.0f} different merchants in 24 hours.",
        "icon": "shopping-bag",
    },
    "distinct_devices_7d": {
        "headline": "Multiple Device Fingerprints",
        "template": "{distinct_devices_7d:.0f} distinct device fingerprints detected operating this account within 7 days.",
        "icon": "smartphone",
    },
    "new_merchant_flag": {
        "headline": "Unseen Merchant Beneficiary",
        "template": "First transaction observed at merchant '{merchant_id}' for this account.",
        "icon": "user-x",
    },
    "new_payee_flag": {
        "headline": "Unverified Beneficiary",
        "template": "Funds transferred to a newly linked or unverified counterparty account.",
        "icon": "user-check",
    },
    "category_rarity_by_account": {
        "headline": "Uncharacteristic Spend Category",
        "template": "Spending in merchant category '{category}' diverges from account's historical distribution.",
        "icon": "tag",
    },
    "region_mismatch": {
        "headline": "Geographic Region Mismatch",
        "template": "Transaction originated from region '{region}' which differs from the account's home billing state.",
        "icon": "map-pin",
    },
    "device_novelty": {
        "headline": "Unrecognized Device Fingerprint",
        "template": "Payment attempted from a previously unseen hardware fingerprint.",
        "icon": "shield-alert",
    },
    "session_anomaly": {
        "headline": "Anomalous Web/App Session",
        "template": "Session telemetry indicates suspicious client interaction or proxy routing.",
        "icon": "globe",
    },
    "pwd_reset_last_24h": {
        "headline": "Post-Password-Reset Outflow",
        "template": "High-velocity outflow executed within hours of an account credential reset.",
        "icon": "key",
    },
    "errorBalanceOrig": {
        "headline": "Originator Balance Discrepancy",
        "template": "Accounting anomaly: debited amount does not balance with observed sender ledger.",
        "icon": "alert-circle",
    },
    "errorBalanceDest": {
        "headline": "Recipient Balance Discrepancy",
        "template": "Accounting anomaly: credited amount does not balance with observed receiver ledger.",
        "icon": "alert-circle",
    },
    "iso_score": {
        "headline": "Isolation Forest Anomaly",
        "template": "Unsupervised Isolation Forest isolated this transaction as structurally atypical (anomaly score: {iso_score:.3f}).",
        "icon": "compass",
    },
    "ae_error": {
        "headline": "Autoencoder Reconstruction Divergence",
        "template": "Deep Autoencoder reconstruction error ({ae_error:.4f}) indicates structural deviation from normal payment profiles.",
        "icon": "cpu",
    },
}


def format_reason_code(
    feature: str,
    shap_value: float,
    feature_value: float,
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Format a dynamic, plain-English reason code from a feature attribution.
    Embeds real verified numbers with fallbacks.
    """
    ctx = dict(context or {})
    ctx[feature] = feature_value

    # Derived context calculations
    if "amount" not in ctx:
        ctx["amount"] = float(np.expm1(ctx.get("log_amount", feature_value))) if "log" in feature else float(feature_value)
    if "balance_drain_pct" not in ctx:
        ratio = ctx.get("amount_to_balance_ratio", feature_value)
        ctx["balance_drain_pct"] = max(0.0, float(ratio) * 100.0)
    if "mins_since_prev" not in ctx:
        secs = ctx.get("time_since_last_txn", feature_value)
        ctx["mins_since_prev"] = max(0.0, float(secs) / 60.0)
    if "days_since_open" not in ctx:
        secs = ctx.get("time_since_account_open", feature_value)
        ctx["days_since_open"] = max(0.0, float(secs) / 86400.0)
    if "merchant_id" not in ctx:
        ctx["merchant_id"] = "Unknown"
    if "category" not in ctx:
        ctx["category"] = "retail"
    if "region" not in ctx:
        ctx["region"] = "Remote"

    template_cfg = REASON_CODE_TEMPLATES.get(feature)

    if template_cfg:
        headline = template_cfg["headline"]
        icon = template_cfg["icon"]
        try:
            description = template_cfg["template"].format(**ctx)
        except Exception:
            description = f"{headline}: feature value {feature_value:.2f} contributed to fraud score."
    else:
        clean_name = feature.replace("_", " ").title()
        headline = f"Unusual {clean_name}"
        icon = "info"
        description = f"{clean_name} ({feature_value:.2f}) contributed +{shap_value:.3f} toward the fraud risk assessment."

    # Severity classification based on attribution strength
    if shap_value >= 1.0:
        severity = "HIGH"
    elif shap_value >= 0.35:
        severity = "MEDIUM"
    else:
        severity = "LOW"

    return {
        "feature": feature,
        "headline": headline,
        "description": description,
        "shap_value": round(float(shap_value), 4),
        "feature_value": round(float(feature_value), 4),
        "severity": severity,
        "icon": icon,
    }


# ==============================================================================
# 2. TreeSHAP Explainer
# ==============================================================================
class TreeSHAPExplainer:
    """
    Exact TreeSHAP attribution explainer using XGBoost's native `pred_contribs=True`.
    Seamlessly supports both standalone XGBoost models and HybridFraudDetector models.
    """

    def __init__(self, model_bundle: Union[Dict[str, Any], Any]):
        if isinstance(model_bundle, dict):
            self.model = model_bundle.get("model") or model_bundle.get("champion")
            self.feature_names = model_bundle.get("feature_names", [])
        else:
            self.model = model_bundle
            self.feature_names = getattr(model_bundle, "feature_names", [])

        # Extract underlying XGBoost booster
        if hasattr(self.model, "xgb"):
            self.booster = self.model.xgb.get_booster()
            self.extended_names = getattr(self.model, "feature_names", self.feature_names)
        elif hasattr(self.model, "get_booster"):
            self.booster = self.model.get_booster()
            self.extended_names = self.feature_names
        elif hasattr(self.model, "named_steps") and "classifier" in self.model.named_steps:
            self.booster = self.model.named_steps["classifier"].get_booster()
            self.extended_names = self.feature_names
        else:
            raise ValueError(f"Unable to extract XGBoost booster from model of type {type(self.model)}")

    def explain_instance(
        self,
        X_df: pd.DataFrame,
        raw_txn: Optional[Dict[str, Any]] = None,
        top_k: int = 3,
    ) -> Dict[str, Any]:
        """
        Produce a full local SHAP explanation for a single transaction or batch row:
        - Exact SHAP contributions for every feature
        - Waterfall coordinates for SVG visualization
        - Top K plain-English reason codes with dynamic verified values
        """
        # Ensure row is DataFrame
        if isinstance(X_df, pd.Series):
            X_df = X_df.to_frame().T
        elif isinstance(X_df, dict):
            X_df = pd.DataFrame([X_df])

        # If hybrid model, apply feature transformations (iso_score, ae_error)
        if hasattr(self.model, "transform_features"):
            X_eval = self.model.transform_features(X_df)
        else:
            X_eval = X_df[self.extended_names].copy()

        dmat = xgb.DMatrix(X_eval[self.extended_names], feature_names=self.extended_names)
        # Booster returns (n_samples, n_features + 1) where last column is bias
        contribs = self.booster.predict(dmat, pred_contribs=True)[0]

        bias_shap = float(contribs[-1])
        feature_shap = contribs[:-1]

        # Extract context for string formatting
        context: Dict[str, Any] = {}
        if raw_txn:
            context.update(raw_txn)
        for col in X_eval.columns:
            context[col] = X_eval.iloc[0][col]

        # Build contribution list
        contributions: List[Dict[str, Any]] = []
        for i, col in enumerate(self.extended_names):
            val = float(X_eval.iloc[0][col])
            shap_v = float(feature_shap[i])
            contributions.append({
                "feature": col,
                "value": round(val, 4),
                "shap_value": round(shap_v, 4),
                "direction": "positive" if shap_v > 0 else "negative",
            })

        # Sort all contributions by absolute attribution magnitude
        contributions.sort(key=lambda x: abs(x["shap_value"]), reverse=True)

        # Filter positive contributors that push risk up
        positive_contributors = [c for c in contributions if c["shap_value"] > 0]
        positive_contributors.sort(key=lambda x: x["shap_value"], reverse=True)

        # Generate top K plain-English reason codes
        top_reasons: List[Dict[str, Any]] = []
        for item in positive_contributors[:top_k]:
            code = format_reason_code(
                feature=item["feature"],
                shap_value=item["shap_value"],
                feature_value=item["value"],
                context=context,
            )
            top_reasons.append(code)

        # Total margin output
        total_margin = bias_shap + float(np.sum(feature_shap))
        # Logistic sigmoid probability
        implied_prob = 1.0 / (1.0 + np.exp(-total_margin))

        # Waterfall step coordinates (Base -> cumulative sum of top features -> Final)
        waterfall_steps = []
        running_total = bias_shap
        waterfall_steps.append({
            "step": "Base Value (Prior)",
            "delta": round(bias_shap, 4),
            "end_value": round(running_total, 4),
            "type": "base",
        })

        # Include top 8 most influential features in waterfall
        for item in contributions[:8]:
            prev_total = running_total
            running_total += item["shap_value"]
            waterfall_steps.append({
                "step": item["feature"],
                "delta": round(item["shap_value"], 4),
                "start_value": round(prev_total, 4),
                "end_value": round(running_total, 4),
                "type": "positive" if item["shap_value"] > 0 else "negative",
            })

        waterfall_steps.append({
            "step": "Model Output Margin",
            "delta": 0.0,
            "end_value": round(total_margin, 4),
            "type": "total",
        })

        return {
            "base_value": round(bias_shap, 4),
            "margin_output": round(total_margin, 4),
            "implied_probability": round(implied_prob, 5),
            "contributions": contributions,
            "top_reasons": top_reasons,
            "waterfall": waterfall_steps,
            "causality_caution": CAUSALITY_CAUTION,
        }


# ==============================================================================
# 3. Global Explainability Summary Generator
# ==============================================================================
def generate_global_shap_summary(
    model: Any,
    X_sample: pd.DataFrame,
    y_sample: Optional[pd.Series] = None,
    feature_names: Optional[List[str]] = None,
    max_samples: int = 2000,
    output_path: Optional[Union[str, Path]] = None,
) -> Dict[str, Any]:
    """
    Generate global feature importance, sampled beeswarm data, dependence plots,
    and permutation importance cross-check coordinates.
    Saves results to artifacts/shap_summary.json.
    """
    logger.info("Computing global SHAP feature attributions on sample (N=%d)...", min(len(X_sample), max_samples))

    if len(X_sample) > max_samples:
        np.random.seed(RANDOM_SEED)
        sample_indices = np.random.choice(len(X_sample), size=max_samples, replace=False)
        X_sub = X_sample.iloc[sample_indices].copy()
        y_sub = y_sample.iloc[sample_indices].copy() if y_sample is not None else None
    else:
        X_sub = X_sample.copy()
        y_sub = y_sample.copy() if y_sample is not None else None

    # Handle hybrid feature transformation
    if hasattr(model, "transform_features"):
        X_ext = model.transform_features(X_sub)
        eval_features = model.feature_names
        booster = model.xgb.get_booster()
    elif hasattr(model, "xgb"):
        eval_features = model.feature_names
        booster = model.xgb.get_booster()
        X_ext = X_sub[eval_features]
    elif hasattr(model, "get_booster"):
        eval_features = feature_names or list(X_sub.columns)
        booster = model.get_booster()
        X_ext = X_sub[eval_features]
    else:
        raise ValueError("Unsupported model for TreeSHAP extraction")

    dmat = xgb.DMatrix(X_ext[eval_features], feature_names=eval_features)
    # Contribs shape: (n_samples, n_features + 1)
    raw_contribs = booster.predict(dmat, pred_contribs=True)
    shap_matrix = raw_contribs[:, :-1]
    bias_margin = float(np.mean(raw_contribs[:, -1]))

    # 1. Mean Absolute SHAP Ranking
    mean_abs_shap = np.mean(np.abs(shap_matrix), axis=0)
    sorted_idx = np.argsort(mean_abs_shap)[::-1]

    feature_ranking = []
    for rank, idx in enumerate(sorted_idx, 1):
        feature_name = eval_features[idx]
        feature_ranking.append({
            "rank": rank,
            "feature": feature_name,
            "mean_abs_shap": round(float(mean_abs_shap[idx]), 5),
            "label": feature_name.replace("_", " ").title(),
        })

    # 2. Beeswarm Plot Coordinates (Sampled to 2,000 points per top 12 features)
    top_12_indices = sorted_idx[:12]
    beeswarm_data = []

    for idx in top_12_indices:
        feat_name = eval_features[idx]
        feat_vals = X_ext[feat_name].values
        shap_vals = shap_matrix[:, idx]

        # Min-max normalize feature value to [0, 1] for colour mapping (blue=low, red=high)
        val_min = float(np.percentile(feat_vals, 1))
        val_max = float(np.percentile(feat_vals, 99))
        denom = val_max - val_min if val_max > val_min else 1.0
        norm_vals = np.clip((feat_vals - val_min) / denom, 0.0, 1.0)

        # Sample up to 300 points per feature for crisp, responsive SVG rendering
        n_pts = min(len(feat_vals), 300)
        sample_pts = np.linspace(0, len(feat_vals) - 1, n_pts, dtype=int)

        for pt_idx in sample_pts:
            beeswarm_data.append({
                "feature": feat_name,
                "value": round(float(feat_vals[pt_idx]), 4),
                "shap": round(float(shap_vals[pt_idx]), 4),
                "norm_value": round(float(norm_vals[pt_idx]), 3),
            })

    # 3. Dependence Plot Data (Top 6 features)
    top_6_indices = sorted_idx[:6]
    dependence_data = {}

    for idx in top_6_indices:
        feat_name = eval_features[idx]
        feat_vals = X_ext[feat_name].values
        shap_vals = shap_matrix[:, idx]

        # Sort points by feature value for line / scatter plotting
        order = np.argsort(feat_vals)
        n_dep = min(len(feat_vals), 200)
        dep_indices = np.linspace(0, len(feat_vals) - 1, n_dep, dtype=int)
        dep_order = order[dep_indices]

        dependence_data[feat_name] = [
            {
                "x": round(float(feat_vals[k]), 4),
                "y": round(float(shap_vals[k]), 4),
            }
            for k in dep_order
        ]

    # 4. Permutation Importance Cross-Check on sample
    permutation_importance_summary = []
    if y_sub is not None and len(y_sub) > 0:
        logger.info("Computing permutation importance cross-check...")
        from sklearn.metrics import roc_auc_score

        # Baseline evaluation
        base_preds = booster.predict(dmat)
        try:
            base_auc = roc_auc_score(y_sub, base_preds)
        except Exception:
            base_auc = 0.5

        # Check top 10 features
        for idx in sorted_idx[:10]:
            feat = eval_features[idx]
            # Copy and shuffle feature
            X_perm = X_ext[eval_features].copy()
            X_perm[feat] = np.random.permutation(X_perm[feat].values)
            dmat_perm = xgb.DMatrix(X_perm, feature_names=eval_features)
            perm_preds = booster.predict(dmat_perm)
            try:
                perm_auc = roc_auc_score(y_sub, perm_preds)
                score_drop = max(0.0, float(base_auc - perm_auc))
            except Exception:
                score_drop = 0.0

            permutation_importance_summary.append({
                "feature": feat,
                "score_drop": round(score_drop, 5),
                "baseline_auc": round(float(base_auc), 4),
            })

    summary = {
        "n_samples": int(len(X_sub)),
        "base_margin": round(bias_margin, 4),
        "ranking": feature_ranking,
        "beeswarm": beeswarm_data,
        "dependence": dependence_data,
        "permutation_importance": permutation_importance_summary,
        "causality_caution": CAUSALITY_CAUTION,
    }

    if output_path is None:
        output_path = ARTIFACTS_DIR / "shap_summary.json"
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    logger.info("Saved global SHAP summary to %s", output_path)
    return summary
