"""
FraudShield Feature Engineering & Feature Store Module.

Provides:
- Strict past-only rolling and behavioural features (zero future leakage)
- FeatureStore: In-memory stateful entity store for real-time online serving
- Full batch-and-online feature parity guarantee via a single shared code path
- Features:
    Amount: log_amount, amount_zscore_by_account, amount_to_balance_ratio, drains_account
    Time: hour, is_night, time_since_last_txn, time_since_account_open
    Velocity: txn_count_1h, txn_count_24h, txn_count_7d, amount_sum_1h, amount_sum_24h,
              distinct_merchants_24h, distinct_devices_7d, new_merchant_flag, new_payee_flag
    Behaviour: category_rarity_by_account, region_mismatch, device_novelty, session_anomaly,
               pwd_reset_last_24h
    Balance: errorBalanceOrig, errorBalanceDest
    Anomaly: iso_score, ae_error (injected by anomaly models)
"""

from __future__ import annotations

import collections
import logging
import math
import sys
from collections import defaultdict, deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import numpy as np
import pandas as pd

logger = logging.getLogger("fraudshield.features")

# Time window constants in seconds
WINDOW_1H = 3_600.0
WINDOW_24H = 86_400.0
WINDOW_7D = 604_800.0

# Base feature column order for model training & scoring
FEATURE_COLUMNS = [
    # Amount
    "log_amount",
    "amount_zscore_by_account",
    "amount_to_balance_ratio",
    "drains_account",
    # Time
    "hour",
    "is_night",
    "time_since_last_txn",
    "time_since_account_open",
    # Velocity
    "txn_count_1h",
    "txn_count_24h",
    "txn_count_7d",
    "amount_sum_1h",
    "amount_sum_24h",
    "distinct_merchants_24h",
    "distinct_devices_7d",
    "new_merchant_flag",
    "new_payee_flag",
    # Behaviour
    "category_rarity_by_account",
    "region_mismatch",
    "device_novelty",
    "session_anomaly",
    "pwd_reset_last_24h",
    # Balance
    "errorBalanceOrig",
    "errorBalanceDest",
    # Anomaly scores (populated by unsupervised branch)
    "iso_score",
    "ae_error",
]


@dataclass
class AccountHistory:
    first_seen_ts: float = 0.0
    last_seen_ts: float = 0.0
    total_txns: int = 0
    sum_amounts: float = 0.0
    sum_sq_amounts: float = 0.0
    home_region: str = ""
    seen_merchants: Set[str] = field(default_factory=set)
    seen_payees: Set[str] = field(default_factory=set)
    seen_devices: Set[str] = field(default_factory=set)
    category_counts: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    # Rolling deque of (ts, amount, merchant_id, device_id)
    history_deque: deque = field(default_factory=deque)


class FeatureStore:
    """
    Stateful entity-level feature store maintaining online state for accounts.
    Guarantees that single-transaction scoring computes identical feature vectors
    to offline batch feature generation.
    """

    def __init__(self) -> None:
        self.accounts: Dict[str, AccountHistory] = {}
        # Global session statistics for normalizing session durations
        self._session_count: int = 0
        self._session_sum: float = 0.0
        self._session_sum_sq: float = 0.0

    def reset(self) -> None:
        """Clear all entity states."""
        self.accounts.clear()
        self._session_count = 0
        self._session_sum = 0.0
        self._session_sum_sq = 0.0

    def _prune_history(self, history: AccountHistory, current_ts: float) -> None:
        """Remove events older than 7 days from the account rolling deque."""
        cutoff = current_ts - WINDOW_7D
        d = history.history_deque
        while d and d[0][0] < cutoff:
            d.popleft()

    def features_for(self, txn: Dict[str, Any]) -> Dict[str, float]:
        """
        Compute features for a single transaction using ONLY past state.
        Does NOT update the internal state (pure read-only view).
        """
        acc_id = str(txn.get("account_id", ""))
        ts = float(txn.get("ts", 0.0))
        amount = float(txn.get("amount", 0.0))
        hour = int(txn.get("hour", int((ts // 3600) % 24)))
        is_night = int(txn.get("is_night", 1 if hour in (0, 1, 2, 3, 4, 5) else 0))
        old_bal = float(txn.get("oldbalance", 0.0))
        new_bal = float(txn.get("newbalance", max(0.0, old_bal - amount)))
        merch_id = str(txn.get("merchant_id", ""))
        category = str(txn.get("merchant_category", ""))
        dev_id = str(txn.get("device_id", ""))
        dev_is_new = int(txn.get("device_is_new", 0))
        reg_mismatch = int(txn.get("region_mismatch", 0))
        dest_acc = str(txn.get("dest_account_id", ""))
        dest_is_new = int(txn.get("dest_is_new_payee", 0))
        sess_sec = float(txn.get("session_seconds", 120.0))
        pwd_reset = int(txn.get("pwd_reset_last_24h", 0))

        # Retrieve existing account history
        acc = self.accounts.get(acc_id)

        # 1. Amount Features
        log_amount = float(math.log1p(max(0.0, amount)))
        amount_to_balance = float(amount / (old_bal + 1.0))
        drains_acc = 1.0 if (abs(amount - old_bal) < 0.01 or (old_bal > 0 and amount >= 0.95 * old_bal)) else 0.0

        if acc is not None and acc.total_txns >= 2:
            mean = acc.sum_amounts / acc.total_txns
            variance = max(0.0, (acc.sum_sq_amounts / acc.total_txns) - (mean * mean))
            std = math.sqrt(variance)
            std_effective = max(std, 1.0)
            raw_z = (amount - mean) / std_effective
            amount_zscore = float(max(-50.0, min(50.0, raw_z)))
        else:
            amount_zscore = 0.0

        # 2. Time Features
        if acc is not None and acc.total_txns > 0:
            time_since_last = float(ts - acc.last_seen_ts)
            time_since_open = float(ts - acc.first_seen_ts)
        else:
            time_since_last = float(WINDOW_7D * 4.0)  # ~28 days default for brand new accounts
            time_since_open = 0.0

        # 3. Velocity Features (Rolling counts, sums, and distinct entities)
        count_1h = 0
        count_24h = 0
        count_7d = 0
        sum_1h = 0.0
        sum_24h = 0.0
        merchants_24h: Set[str] = set()
        devices_7d: Set[str] = set()

        if acc is not None:
            cutoff_1h = ts - WINDOW_1H
            cutoff_24h = ts - WINDOW_24H
            cutoff_7d = ts - WINDOW_7D

            # Iterate backwards in time: newest transactions first.
            # Stop immediately when an event is older than 7 days!
            for past_ts, past_amt, past_merch, past_dev in reversed(acc.history_deque):
                if past_ts < cutoff_7d:
                    break
                count_7d += 1
                devices_7d.add(past_dev)
                if past_ts >= cutoff_24h:
                    count_24h += 1
                    sum_24h += past_amt
                    merchants_24h.add(past_merch)
                    if past_ts >= cutoff_1h:
                        count_1h += 1
                        sum_1h += past_amt

            new_merch_flag = 1.0 if (merch_id and merch_id not in acc.seen_merchants) else 0.0
            new_payee_flag = (
                1.0
                if (dest_acc and dest_acc not in acc.seen_payees)
                else float(dest_is_new)
            )
            device_novel = (
                1.0
                if (dev_is_new == 1 or (dev_id and dev_id not in acc.seen_devices))
                else 0.0
            )

            # Behavioural Category Rarity
            cat_count = acc.category_counts.get(category, 0)
            cat_rarity = float(1.0 - (cat_count / max(1, acc.total_txns)))
        else:
            new_merch_flag = 1.0
            new_payee_flag = float(dest_is_new)
            device_novel = 1.0 if (dev_is_new == 1 or dev_id != "") else 0.0
            cat_rarity = 0.5

        # 4. Behaviour & Session Anomaly
        log_sess = math.log1p(max(0.0, sess_sec))
        if self._session_count >= 10:
            s_mean = self._session_sum / self._session_count
            s_var = max(0.0, (self._session_sum_sq / self._session_count) - (s_mean * s_mean))
            s_std = math.sqrt(s_var)
            session_z = float((sess_sec - s_mean) / (s_std + 1e-4))
        else:
            session_z = 0.0

        # 5. Balance Accounting Features
        err_orig = float(txn.get("errorBalanceOrig", new_bal + amount - old_bal))
        err_dest = float(txn.get("errorBalanceDest", 0.0))

        # 6. Default Anomaly Scores
        iso_score = float(txn.get("iso_score", 0.0))
        ae_error = float(txn.get("ae_error", 0.0))

        features = {
            "log_amount": round(log_amount, 5),
            "amount_zscore_by_account": round(amount_zscore, 5),
            "amount_to_balance_ratio": round(min(100.0, amount_to_balance), 5),
            "drains_account": float(drains_acc),
            "hour": float(hour),
            "is_night": float(is_night),
            "time_since_last_txn": round(time_since_last, 2),
            "time_since_account_open": round(time_since_open, 2),
            "txn_count_1h": float(count_1h),
            "txn_count_24h": float(count_24h),
            "txn_count_7d": float(count_7d),
            "amount_sum_1h": round(sum_1h, 2),
            "amount_sum_24h": round(sum_24h, 2),
            "distinct_merchants_24h": float(len(merchants_24h)),
            "distinct_devices_7d": float(len(devices_7d)),
            "new_merchant_flag": float(new_merch_flag),
            "new_payee_flag": float(new_payee_flag),
            "category_rarity_by_account": round(cat_rarity, 5),
            "region_mismatch": float(reg_mismatch),
            "device_novelty": float(device_novel),
            "session_anomaly": round(session_z, 5),
            "pwd_reset_last_24h": float(pwd_reset),
            "errorBalanceOrig": round(err_orig, 2),
            "errorBalanceDest": round(err_dest, 2),
            "iso_score": iso_score,
            "ae_error": ae_error,
        }

        return features

    def update(self, txn: Dict[str, Any]) -> None:
        """
        Commit a transaction into the historical state.
        Must be called AFTER computing features for this transaction to avoid leakage.
        """
        acc_id = str(txn.get("account_id", ""))
        ts = float(txn.get("ts", 0.0))
        amount = float(txn.get("amount", 0.0))
        merch_id = str(txn.get("merchant_id", ""))
        category = str(txn.get("merchant_category", ""))
        dev_id = str(txn.get("device_id", ""))
        dest_acc = str(txn.get("dest_account_id", ""))
        sess_sec = float(txn.get("session_seconds", 120.0))
        reg = str(txn.get("ip_region", ""))

        if acc_id not in self.accounts:
            self.accounts[acc_id] = AccountHistory(
                first_seen_ts=ts,
                last_seen_ts=ts,
                total_txns=0,
                sum_amounts=0.0,
                sum_sq_amounts=0.0,
                home_region=reg,
            )

        acc = self.accounts[acc_id]
        acc.last_seen_ts = ts
        acc.total_txns += 1
        acc.sum_amounts += amount
        acc.sum_sq_amounts += amount * amount

        if merch_id:
            acc.seen_merchants.add(merch_id)
        if dest_acc:
            acc.seen_payees.add(dest_acc)
        if dev_id:
            acc.seen_devices.add(dev_id)
        if category:
            acc.category_counts[category] += 1

        # Append to rolling history and prune old events (>7 days)
        acc.history_deque.append((ts, amount, merch_id, dev_id))
        self._prune_history(acc, ts)

        # Update global session stats
        self._session_count += 1
        self._session_sum += sess_sec
        self._session_sum_sq += sess_sec * sess_sec

    def compute_and_update(self, txn: Dict[str, Any]) -> Dict[str, float]:
        """
        Atomic operation: calculate features using strictly past history,
        then commit the current event into the state store.
        """
        feat = self.features_for(txn)
        self.update(txn)
        return feat

    def compute_batch(
        self,
        df: pd.DataFrame,
        time_col: str = "ts",
        reset_state: bool = True,
    ) -> pd.DataFrame:
        """
        Compute features for an entire chronological DataFrame row-by-row.
        Guarantees exact parity with online serving.
        """
        if reset_state:
            self.reset()

        if not df[time_col].is_monotonic_increasing:
            logger.warning("compute_batch received unsorted DataFrame. Sorting by %s.", time_col)
            df = df.sort_values(time_col).reset_index(drop=True)

        rows = df.to_dict(orient="records")
        computed_features: List[Dict[str, float]] = []

        for row in rows:
            feat = self.compute_and_update(row)
            computed_features.append(feat)

        feat_df = pd.DataFrame(computed_features, columns=FEATURE_COLUMNS)
        return feat_df


# Global singleton instance for convenient access across modules
default_feature_store = FeatureStore()


def extract_features(
    df: pd.DataFrame,
    feature_store: Optional[FeatureStore] = None,
    reset_state: bool = True,
) -> pd.DataFrame:
    """
    Primary API function to extract engineered feature matrix from a transaction DataFrame.
    Shared by training, validation, testing, and batch processing.
    """
    store = feature_store or default_feature_store
    return store.compute_batch(df, reset_state=reset_state)


if __name__ == "__main__":
    from src.data import load_ledgersim

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    df_raw = load_ledgersim(fast=True)
    logger.info("Extracting features from sample of 5,000 transactions...")
    sample_df = df_raw.iloc[:5_000].copy()

    store = FeatureStore()
    feat_df = store.compute_batch(sample_df)
    print("Features extracted successfully! Shape:", feat_df.shape)
    print("Feature columns:", list(feat_df.columns))
    print("\nSummary statistics of first 5 features:")
    print(feat_df[FEATURE_COLUMNS[:5]].describe().round(3))
