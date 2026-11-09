"""
FraudShield Data Pipeline Module.

Handles:
- Loading and caching of primary LedgerSim transactions
- Optional auto-detected loading and feature extraction for ULB CreditCard and PaySim datasets
- Strict time-ordered splitting (70% train / 15% val / 15% test) without data leakage
- Data Card generation capturing provenance, schema, and empirical distributions
- Comprehensive Exploratory Data Analysis (EDA) artifact generation saved to JSON
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import numpy as np
import pandas as pd
from scipy import stats

from config import (
    ARTIFACTS_DIR,
    DATA_PROCESSED_DIR,
    DATA_RAW_DIR,
    DATACARDS_FILE,
    EDA_FILE,
    LABEL_MATURITY_SECONDS,
    RANDOM_SEED,
    TEST_RATIO,
    TRAIN_RATIO,
    VAL_RATIO,
)
from src.simulator import LedgerSim, generate_ledgersim_dataset

logger = logging.getLogger("fraudshield.data")


def load_ledgersim(fast: bool = True, force_regenerate: bool = False) -> pd.DataFrame:
    """
    Load LedgerSim transactions from processed cache if available, or generate anew.
    """
    mode_str = "fast" if fast else "full"
    cache_path = DATA_PROCESSED_DIR / f"ledgersim_{mode_str}.parquet"

    if cache_path.exists() and not force_regenerate:
        logger.info("Loading cached LedgerSim dataset from %s", cache_path)
        df = pd.read_parquet(cache_path)
    else:
        logger.info("Generating fresh LedgerSim dataset (fast=%s)...", fast)
        df = generate_ledgersim_dataset(fast=fast, output_path=str(cache_path))

    return df


def load_ulb(raw_path: Optional[str] = None) -> Optional[pd.DataFrame]:
    """
    Auto-detect and load the ULB Credit Card Fraud dataset (Kaggle).
    Returns None if the raw file is not present.
    """
    path = Path(raw_path) if raw_path else (DATA_RAW_DIR / "creditcard.csv")
    if not path.exists():
        logger.info("ULB dataset not found at %s. Skipping.", path)
        return None

    logger.info("Loading ULB Credit Card dataset from %s...", path)
    df = pd.read_csv(path)
    # Ensure strictly sorted by Time
    df = df.sort_values("Time").reset_index(drop=True)
    df["ts"] = df["Time"].astype(np.float64)
    df["hour"] = ((df["Time"] // 3600) % 24).astype(np.int32)
    df["is_night"] = np.isin(df["hour"], [0, 1, 2, 3, 4, 5]).astype(np.int32)
    df["log_amount"] = np.log1p(df["Amount"].clip(lower=0.0)).astype(np.float32)
    df["is_fraud"] = df["Class"].astype(np.int32)
    return df


def load_paysim(
    raw_path: Optional[str] = None, max_legitimate_sample: Optional[int] = 300_000
) -> Optional[pd.DataFrame]:
    """
    Auto-detect and load PaySim mobile money dataset (Kaggle).
    Engineers balance-error features and conditionally subsamples legitimate records
    to prevent RAM exhaustion while preserving 100% of fraudulent rows.
    """
    path = Path(raw_path) if raw_path else (DATA_RAW_DIR / "paysim.csv")
    if not path.exists():
        logger.info("PaySim dataset not found at %s. Skipping.", path)
        return None

    logger.info("Loading PaySim dataset from %s...", path)
    df = pd.read_csv(path)

    # Convert step (1 step = 1 hour) to simulated timestamp in seconds
    df["ts"] = (df["step"] * 3600.0).astype(np.float64)
    df = df.sort_values("ts").reset_index(drop=True)

    # Engineer PaySim domain balance features
    df["errorBalanceOrig"] = (df["newbalanceOrig"] + df["amount"] - df["oldbalanceOrg"]).astype(np.float32)
    df["errorBalanceDest"] = (df["oldbalanceDest"] + df["amount"] - df["newbalanceDest"]).astype(np.float32)
    df["drains_account"] = (np.abs(df["amount"] - df["oldbalanceOrg"]) < 0.01).astype(np.int32)
    df["is_fraud"] = df["isFraud"].astype(np.int32)

    if max_legitimate_sample and len(df) > max_legitimate_sample:
        logger.info("Subsampling PaySim: retaining 100%% frauds, sampling legitimate to %d rows", max_legitimate_sample)
        frauds = df[df["is_fraud"] == 1]
        legit = df[df["is_fraud"] == 0]
        # Stratified by step/time
        sampled_legit = legit.sample(n=max_legitimate_sample, random_state=RANDOM_SEED)
        df = pd.concat([frauds, sampled_legit]).sort_values("ts").reset_index(drop=True)

    return df


def time_split(
    df: pd.DataFrame,
    train_ratio: float = TRAIN_RATIO,
    val_ratio: float = VAL_RATIO,
    test_ratio: float = TEST_RATIO,
    time_col: str = "ts",
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Strictly chronological time-ordered split without random shuffling.
    Enforces that:
        max(train[time_col]) <= min(val[time_col]) <= max(val[time_col]) <= min(test[time_col])
    """
    if not np.isclose(train_ratio + val_ratio + test_ratio, 1.0):
        raise ValueError(f"Split ratios must sum to 1.0 (got {train_ratio + val_ratio + test_ratio})")

    # Verify sort order
    if not df[time_col].is_monotonic_increasing:
        logger.warning("DataFrame was not monotonic on %s; sorting strictly by time.", time_col)
        df = df.sort_values(time_col).reset_index(drop=True)

    n = len(df)
    i1 = int(n * train_ratio)
    i2 = int(n * (train_ratio + val_ratio))

    train = df.iloc[:i1].copy().reset_index(drop=True)
    val = df.iloc[i1:i2].copy().reset_index(drop=True)
    test = df.iloc[i2:].copy().reset_index(drop=True)

    logger.info(
        "Time-split completed: Train=%d (%.3f%% fraud), Val=%d (%.3f%% fraud), Test=%d (%.3f%% fraud)",
        len(train),
        train["is_fraud"].mean() * 100 if "is_fraud" in train else 0.0,
        len(val),
        val["is_fraud"].mean() * 100 if "is_fraud" in val else 0.0,
        len(test),
        test["is_fraud"].mean() * 100 if "is_fraud" in test else 0.0,
    )

    return train, val, test


def generate_datacard(
    dataset_name: str,
    df: pd.DataFrame,
    target_col: str = "is_fraud",
    time_col: str = "ts",
    caveats: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Generate structured DataCard metadata for an ingested dataset.
    """
    total_rows = len(df)
    fraud_count = int(df[target_col].sum()) if target_col in df else 0
    fraud_rate = float(fraud_count / total_rows) if total_rows > 0 else 0.0

    min_ts = float(df[time_col].min()) if time_col in df else 0.0
    max_ts = float(df[time_col].max()) if time_col in df else 0.0
    duration_days = round((max_ts - min_ts) / 86400.0, 2)

    col_summaries = []
    for col in df.columns:
        dtype_str = str(df[col].dtype)
        null_count = int(df[col].isnull().sum())
        col_summaries.append({"name": col, "dtype": dtype_str, "null_count": null_count})

    card = {
        "dataset_name": dataset_name,
        "total_records": total_rows,
        "fraud_count": fraud_count,
        "legitimate_count": total_rows - fraud_count,
        "fraud_rate": round(fraud_rate, 6),
        "fraud_percentage": f"{fraud_rate * 100:.3f}%",
        "duration_days": duration_days,
        "time_col": time_col,
        "target_col": target_col,
        "columns_count": len(df.columns),
        "columns": col_summaries,
        "memory_mb": round(df.memory_usage(deep=True).sum() / (1024 * 1024), 2),
        "caveats": caveats or [],
    }

    return card


def save_datacards(cards: Dict[str, Any], filepath: Path = DATACARDS_FILE) -> None:
    """Save dictionary of data cards to JSON artifact."""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(cards, f, indent=2)
    logger.info("Saved data cards to %s", filepath)


def generate_eda_summary(df: pd.DataFrame, output_path: Path = EDA_FILE) -> Dict[str, Any]:
    """
    Perform rigorous Exploratory Data Analysis (EDA) on the primary dataset and
    export structured statistics (class balance, distributions, hourly rates,
    typology counts, drift checks via Kolmogorov-Smirnov test and PSI).
    """
    logger.info("Generating EDA summary artifact...")
    total_rows = len(df)
    fraud_mask = df["is_fraud"] == 1
    legit_mask = df["is_fraud"] == 0

    fraud_count = int(fraud_mask.sum())
    legit_count = int(legit_mask.sum())
    fraud_rate = float(fraud_count / total_rows)

    # 1. Amount distributions by class
    def get_stats(series: pd.Series) -> Dict[str, float]:
        desc = series.describe(percentiles=[0.05, 0.25, 0.50, 0.75, 0.95, 0.99])
        return {
            "mean": round(float(desc["mean"]), 2),
            "std": round(float(desc["std"]), 2),
            "min": round(float(desc["min"]), 2),
            "p5": round(float(desc["5%"]), 2),
            "p25": round(float(desc["25%"]), 2),
            "median": round(float(desc["50%"]), 2),
            "p75": round(float(desc["75%"]), 2),
            "p95": round(float(desc["95%"]), 2),
            "p99": round(float(desc["99%"]), 2),
            "max": round(float(desc["max"]), 2),
        }

    amount_legit = get_stats(df.loc[legit_mask, "amount"])
    amount_fraud = get_stats(df.loc[fraud_mask, "amount"])

    # 2. Hourly breakdown
    hour_stats = []
    for h in range(24):
        h_df = df[df["hour"] == h]
        h_total = len(h_df)
        h_fraud = int(h_df["is_fraud"].sum())
        h_rate = float(h_fraud / h_total) if h_total > 0 else 0.0
        hour_stats.append({
            "hour": h,
            "total": h_total,
            "fraud": h_fraud,
            "fraud_rate": round(h_rate, 5),
        })

    # 3. Channel breakdown
    channel_stats = []
    if "channel" in df:
        for ch, group in df.groupby("channel"):
            c_tot = len(group)
            c_frd = int(group["is_fraud"].sum())
            c_rate = float(c_frd / c_tot) if c_tot > 0 else 0.0
            channel_stats.append({
                "channel": ch,
                "total": c_tot,
                "fraud": c_frd,
                "fraud_rate": round(c_rate, 5),
            })

    # 4. Fraud typologies
    typology_counts = {}
    if "fraud_type" in df:
        typology_counts = df["fraud_type"].value_counts().to_dict()

    # 5. Concept Drift check: compare first 75% vs last 25% of timeline
    cutoff_ts = df["ts"].quantile(0.75)
    early_df = df[df["ts"] < cutoff_ts]
    late_df = df[df["ts"] >= cutoff_ts]

    early_fraud = early_df[early_df["is_fraud"] == 1]
    late_fraud = late_df[late_df["is_fraud"] == 1]

    # Kolmogorov-Smirnov test on Amount (both overall and fraud subset)
    ks_stat_all, ks_pval_all = stats.ks_2samp(early_df["amount"], late_df["amount"])
    ks_stat_frd, ks_pval_frd = stats.ks_2samp(early_fraud["amount"], late_fraud["amount"])

    # PSI calculation helper
    def calculate_psi(ref: np.ndarray, cur: np.ndarray, num_bins: int = 10) -> float:
        quantiles = np.linspace(0, 1, num_bins + 1)
        edges = np.percentile(ref, quantiles * 100)
        edges[0] = -np.inf
        edges[-1] = np.inf
        edges = np.unique(edges)

        p, _ = np.histogram(ref, bins=edges)
        q, _ = np.histogram(cur, bins=edges)

        p_ratio = p / len(ref)
        q_ratio = q / len(cur)

        # Clip epsilons
        p_ratio = np.clip(p_ratio, 1e-6, None)
        q_ratio = np.clip(q_ratio, 1e-6, None)

        return float(np.sum((p_ratio - q_ratio) * np.log(p_ratio / q_ratio)))

    psi_amount = calculate_psi(early_df["amount"].values, late_df["amount"].values)
    psi_fraud_amount = calculate_psi(early_fraud["amount"].values, late_fraud["amount"].values)

    eda_summary = {
        "dataset_name": "LedgerSim",
        "total_records": total_rows,
        "fraud_count": fraud_count,
        "legitimate_count": legit_count,
        "fraud_rate": round(fraud_rate, 6),
        "amount_distribution": {
            "legitimate": amount_legit,
            "fraud": amount_fraud,
        },
        "hourly_distribution": hour_stats,
        "channel_distribution": channel_stats,
        "typology_counts": typology_counts,
        "drift_check": {
            "early_cutoff_timestamp": float(cutoff_ts),
            "early_records": len(early_df),
            "late_records": len(late_df),
            "early_frauds": len(early_fraud),
            "late_frauds": len(late_fraud),
            "amount_ks_statistic_overall": round(float(ks_stat_all), 4),
            "amount_ks_pvalue_overall": float(ks_pval_all),
            "amount_ks_statistic_fraud": round(float(ks_stat_frd), 4),
            "amount_ks_pvalue_fraud": float(ks_pval_frd),
            "amount_psi_overall": round(psi_amount, 4),
            "amount_psi_fraud": round(psi_fraud_amount, 4),
            "fraud_rate_early": round(float(early_df["is_fraud"].mean()), 5),
            "fraud_rate_late": round(float(late_df["is_fraud"].mean()), 5),
            "has_statistically_significant_drift": bool(ks_pval_frd < 0.05 or psi_fraud_amount > 0.05),
        },
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(eda_summary, f, indent=2)

    logger.info("EDA summary written successfully to %s", output_path)
    return eda_summary


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    df_sim = load_ledgersim(fast=True)
    eda = generate_eda_summary(df_sim)
    card = generate_datacard("LedgerSim", df_sim)
    save_datacards({"LedgerSim": card})
    print("EDA and DataCard generation successful!")
    print(f"Drift check PSI: {eda['drift_check']['amount_psi']}")
