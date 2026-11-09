"""
FraudShield LedgerSim — Synthetic Banking Transaction Simulator.

Generates realistic, seedable, time-ordered payment transactions featuring:
- Account-level behavioral history (lognormal amounts, category preferences, usual devices, home regions)
- Diurnal and weekly seasonality, salary-day bumps, and legitimate anomalies (travel, large purchases)
- Five distinct fraud typologies:
    1. card_testing: Rapid bursts of micro-amounts at new merchants followed by a high-value purchase.
    2. cnp: Card-not-present fraud from new device, mismatched region, luxury/airline categories, and amount spike.
    3. ato: Account takeover with recent password reset, new device/IP, and full-balance drain transfer.
    4. mule_chain: Intermediary accounts receiving rapid inflows followed immediately by quick cash-out.
    5. app: Authorised push payment scam with first-time payee, large sum, unusual hour, and elongated session.
- Concept Drift: Injected in the final 25% of the timeline (altering fraud amounts, times, and category mix).
- Label Maturation Latency: 7-day maturation delay to replicate real-world chargeback reporting lag.
"""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Ensure repository root is on sys.path for direct script execution
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import numpy as np
import pandas as pd

from config import (
    CHANNELS,
    LABEL_MATURITY_SECONDS,
    MERCHANT_CATEGORIES,
    RANDOM_SEED,
    REGIONS,
    SIMULATOR_CONFIG_FAST,
    SIMULATOR_CONFIG_FULL,
)

logger = logging.getLogger("fraudshield.simulator")


@dataclass
class AccountProfile:
    account_id: str
    wealth_tier: str  # 'low', 'medium', 'high', 'affluent'
    base_balance: float
    current_balance: float
    home_region: str
    primary_device: str
    preferred_categories: List[str]
    mean_log_amount: float
    std_log_amount: float
    is_mule: bool = False


@dataclass
class MerchantProfile:
    merchant_id: str
    category: str
    risk_factor: float
    typical_amount: float


class LedgerSim:
    """
    High-performance synthetic bank transaction generator with account-level
    state tracking, fraud injection, and concept drift.
    """

    def __init__(
        self,
        num_transactions: int = 120_000,
        num_days: int = 30,
        num_accounts: int = 8_000,
        num_merchants: int = 600,
        fraud_rate_target: float = 0.0065,
        drift_start_ratio: float = 0.75,
        seed: int = RANDOM_SEED,
    ):
        self.num_transactions = num_transactions
        self.num_days = num_days
        self.num_accounts = num_accounts
        self.num_merchants = num_merchants
        self.fraud_rate_target = fraud_rate_target
        self.drift_start_ratio = drift_start_ratio
        self.seed = seed

        self.rng = np.random.default_rng(self.seed)
        self.total_seconds = self.num_days * 86_400
        self.drift_start_sec = self.total_seconds * self.drift_start_ratio

        self.accounts: Dict[str, AccountProfile] = {}
        self.merchants: Dict[str, MerchantProfile] = {}
        self._init_entities()

    def _init_entities(self) -> None:
        """Initialize bank accounts and merchant ecosystem."""
        tiers = ["low", "medium", "high", "affluent"]
        tier_probs = [0.45, 0.35, 0.15, 0.05]
        tier_balance_range = {
            "low": (300.0, 2_500.0),
            "medium": (2_000.0, 12_000.0),
            "high": (10_000.0, 50_000.0),
            "affluent": (40_000.0, 250_000.0),
        }
        tier_log_amounts = {
            "low": (2.8, 0.7),
            "medium": (3.6, 0.8),
            "high": (4.5, 0.9),
            "affluent": (5.2, 1.1),
        }

        # Create Accounts
        for i in range(self.num_accounts):
            acc_id = f"ACC_{i:06d}"
            tier = self.rng.choice(tiers, p=tier_probs)
            b_min, b_max = tier_balance_range[tier]
            init_balance = float(self.rng.uniform(b_min, b_max))
            region = self.rng.choice(REGIONS)
            dev_id = f"DEV_{self.rng.integers(100_000, 999_999)}"
            pref_cats = list(self.rng.choice(MERCHANT_CATEGORIES, size=4, replace=False))
            mean_la, std_la = tier_log_amounts[tier]

            # Mark 0.8% of accounts as potential money mules
            is_mule = bool(self.rng.random() < 0.008)

            self.accounts[acc_id] = AccountProfile(
                account_id=acc_id,
                wealth_tier=tier,
                base_balance=init_balance,
                current_balance=init_balance,
                home_region=region,
                primary_device=dev_id,
                preferred_categories=pref_cats,
                mean_log_amount=mean_la,
                std_log_amount=std_la,
                is_mule=is_mule,
            )

        # Create Merchants
        for j in range(self.num_merchants):
            m_id = f"MERCH_{j:05d}"
            cat = self.rng.choice(MERCHANT_CATEGORIES)
            risk = float(self.rng.beta(1.5, 8.0))
            if cat in ("crypto_exchange", "luxury_goods", "travel_airline"):
                risk = min(1.0, risk + 0.35)

            typ_amount = float(self.rng.lognormal(3.8, 0.9))
            self.merchants[m_id] = MerchantProfile(
                merchant_id=m_id, category=cat, risk_factor=risk, typical_amount=typ_amount
            )

    def generate(self) -> pd.DataFrame:
        """
        Generate time-ordered transaction dataset with realistic distributions,
        injected fraud typologies, concept drift, and label maturation timestamps.
        """
        logger.info(
            "Generating %d transactions over %d simulated days (seed=%d)...",
            self.num_transactions,
            self.num_days,
            self.seed,
        )

        # 1. Generate strictly increasing timestamps with non-homogeneous Poisson process
        # Daily diurnal cycle + salary-day boosts (1st, 15th, 30th)
        raw_intervals = self.rng.exponential(
            scale=self.total_seconds / (self.num_transactions * 1.05),
            size=int(self.num_transactions * 1.15),
        )
        candidate_ts = np.cumsum(raw_intervals)
        candidate_ts = candidate_ts[candidate_ts < self.total_seconds]

        # Diurnal probability filter: night (00:00 - 06:00) has lower traffic (~15% of day)
        hours = ((candidate_ts // 3600) % 24).astype(int)
        day_of_month = ((candidate_ts // 86400) % 30) + 1
        
        # Diurnal acceptance weight: peak at 13h and 19h, trough at 03h
        diurnal_weight = 0.20 + 0.80 * (0.5 + 0.5 * np.sin((hours - 8) * np.pi / 12)) ** 2
        # Salary boost on day 1, 15, 30
        salary_weight = np.where(np.isin(day_of_month, [1, 15, 30]), 1.35, 1.0)
        acceptance_prob = np.clip(diurnal_weight * salary_weight, 0.05, 1.0)

        accepted_mask = self.rng.random(len(candidate_ts)) < acceptance_prob
        selected_ts = candidate_ts[accepted_mask][: self.num_transactions]

        # If slightly short due to filtering, pad with linearly interpolated stamps
        if len(selected_ts) < self.num_transactions:
            extra_needed = self.num_transactions - len(selected_ts)
            last_ts = selected_ts[-1] if len(selected_ts) > 0 else 0.0
            remaining = np.linspace(last_ts + 1.0, self.total_seconds - 1.0, extra_needed)
            selected_ts = np.sort(np.concatenate([selected_ts, remaining]))

        timestamps = np.round(selected_ts, 2)
        n = len(timestamps)

        # 2. Pick primary accounts and baseline attributes
        account_keys = list(self.accounts.keys())
        merchant_keys = list(self.merchants.keys())

        # Heavy hitters: Pareto distribution on account activity
        acc_indices = self.rng.choice(
            len(account_keys),
            size=n,
            p=self._get_pareto_probabilities(len(account_keys), alpha=1.35),
        )
        chosen_acc_ids = [account_keys[i] for i in acc_indices]

        merch_indices = self.rng.choice(
            len(merchant_keys),
            size=n,
            p=self._get_pareto_probabilities(len(merchant_keys), alpha=1.2),
        )
        chosen_merch_ids = [merchant_keys[j] for j in merch_indices]

        # 3. Determine Fraud Assignments & Typologies
        num_frauds_target = int(n * self.fraud_rate_target)
        # Select target fraud indices (some clustered, some isolated)
        fraud_candidate_indices = np.sort(
            self.rng.choice(n, size=num_frauds_target, replace=False)
        )
        is_fraud_arr = np.zeros(n, dtype=np.int32)
        is_fraud_arr[fraud_candidate_indices] = 1

        fraud_type_arr = ["none"] * n

        # 4. Generate Core Transaction Attributes (Pre-sample vectorized distributions for speed)
        txn_ids = [f"TXN_{i:08d}" for i in range(n)]
        amounts = np.zeros(n, dtype=np.float32)
        
        # Pre-sample channels, session durations, and random numbers in bulk
        pre_channels = self.rng.choice(CHANNELS, size=n, p=[0.40, 0.32, 0.22, 0.06])
        pre_sessions = np.round(np.clip(self.rng.exponential(scale=180.0, size=n), 10.0, 1800.0), 1).astype(np.float32)
        pre_rand_floats = self.rng.random((n, 6))  # 6 columns of random floats for decisions

        device_ids = [""] * n
        device_is_new_arr = np.zeros(n, dtype=np.int32)
        ip_regions = [""] * n
        region_mismatch_arr = np.zeros(n, dtype=np.int32)
        dest_account_ids = [""] * n
        dest_is_new_payee_arr = np.zeros(n, dtype=np.int32)
        session_seconds_arr = pre_sessions.copy()
        pwd_reset_arr = np.zeros(n, dtype=np.int32)
        old_balances = np.zeros(n, dtype=np.float32)
        new_balances = np.zeros(n, dtype=np.float32)
        categories = [""] * n
        channels = list(pre_channels)

        # Account-level state tracking
        account_seen_merchants: Dict[str, set] = {acc: set() for acc in account_keys}
        account_seen_payees: Dict[str, set] = {acc: set() for acc in account_keys}
        account_last_pwd_reset: Dict[str, float] = {acc: -1.0e9 for acc in account_keys}
        account_balances: Dict[str, float] = {
            acc: prof.base_balance for acc, prof in self.accounts.items()
        }

        # Typology mix distributions: Baseline vs Drift Period
        typologies_baseline = ["card_testing", "cnp", "ato", "mule_chain", "app"]
        probs_baseline = [0.25, 0.30, 0.20, 0.15, 0.10]

        typologies_drift = ["card_testing", "cnp", "ato", "mule_chain", "app"]
        # Concept drift shifts mix toward ATO and APP, with novel low-amount stealth attacks
        probs_drift = [0.10, 0.15, 0.35, 0.15, 0.25]

        # Process each transaction sequentially to maintain stateful ground truth
        for idx in range(n):
            ts = timestamps[idx]
            acc_id = chosen_acc_ids[idx]
            acc_prof = self.accounts[acc_id]
            is_drifting = ts >= self.drift_start_sec
            is_fraud = bool(is_fraud_arr[idx] == 1)
            r = pre_rand_floats[idx]

            # Determine fraud typology if fraudulent
            if is_fraud:
                p_dist = probs_drift if is_drifting else probs_baseline
                ftype = self.rng.choice(typologies_baseline, p=p_dist)
                fraud_type_arr[idx] = ftype
            else:
                ftype = "none"

            # -------------------------------------------------------------
            # CASE A: LEGITIMATE BEHAVIOUR
            # -------------------------------------------------------------
            if not is_fraud:
                # Normal lognormal amount around account profile
                base_amt = float(
                    np.exp(acc_prof.mean_log_amount + acc_prof.std_log_amount * (r[0] * 3.0 - 1.5))
                )
                # Occasional legitimate spike (travel / large purchase: 1.2% chance)
                if r[1] < 0.012:
                    base_amt *= (4.0 + r[2] * 5.0)
                amounts[idx] = round(max(1.0, base_amt), 2)

                # Merchant and Category
                if r[3] < 0.75:
                    categories[idx] = acc_prof.preferred_categories[int(r[4] * len(acc_prof.preferred_categories))]
                else:
                    categories[idx] = self.merchants[chosen_merch_ids[idx]].category

                # Device
                if r[4] < 0.94:
                    device_ids[idx] = acc_prof.primary_device
                    device_is_new_arr[idx] = 0
                else:
                    device_ids[idx] = f"DEV_{int(100000 + r[5] * 899999)}"
                    device_is_new_arr[idx] = 1

                # Region
                if r[5] < 0.96:
                    ip_regions[idx] = acc_prof.home_region
                    region_mismatch_arr[idx] = 0
                else:
                    # Legitimate travel
                    travel_region = REGIONS[(REGIONS.index(acc_prof.home_region) + 1) % len(REGIONS)]
                    ip_regions[idx] = travel_region
                    region_mismatch_arr[idx] = 1

                # Payee for transfers/UPI
                if channels[idx] in ("transfer", "upi"):
                    seen = account_seen_payees[acc_id]
                    if len(seen) > 0 and r[2] < 0.70:
                        dest_acc = next(iter(seen))
                        dest_is_new_payee_arr[idx] = 0
                    else:
                        dest_acc = account_keys[int(r[1] * len(account_keys))]
                        dest_is_new_payee_arr[idx] = 1
                        seen.add(dest_acc)
                    dest_account_ids[idx] = dest_acc

                # Password reset is very rare legitimately (~0.05%)
                if r[0] < 0.0005:
                    account_last_pwd_reset[acc_id] = ts
                    pwd_reset_arr[idx] = 1
                else:
                    time_since_reset = ts - account_last_pwd_reset[acc_id]
                    pwd_reset_arr[idx] = 1 if time_since_reset < 86_400 else 0

            # -------------------------------------------------------------
            # CASE B: FRAUDULENT BEHAVIOUR (BY TYPOLOGY)
            # -------------------------------------------------------------
            else:
                if ftype == "card_testing":
                    # Typology 1: Card Testing
                    # Burst of tiny amounts (e.g., $1 - $5), new merchant, online/UPI
                    channels[idx] = self.rng.choice(["online", "upi"], p=[0.75, 0.25])
                    categories[idx] = self.rng.choice(
                        ["digital_services", "utilities", "groceries"]
                    )
                    if not is_drifting:
                        amounts[idx] = round(float(self.rng.uniform(0.99, 4.99)), 2)
                    else:
                        # Drift: card testing tests slightly higher random sums
                        amounts[idx] = round(float(self.rng.uniform(3.50, 9.99)), 2)

                    device_ids[idx] = f"DEV_BOT_{self.rng.integers(10_000, 99_999)}"
                    device_is_new_arr[idx] = 1
                    ip_regions[idx] = acc_prof.home_region
                    region_mismatch_arr[idx] = 0
                    session_seconds_arr[idx] = round(
                        float(self.rng.uniform(2.0, 15.0)), 1
                    )
                    pwd_reset_arr[idx] = 0

                elif ftype == "cnp":
                    # Typology 2: Card Not Present
                    # High amount spike, new device, region mismatch, luxury or electronics
                    channels[idx] = "online"
                    categories[idx] = (
                        "crypto_exchange"
                        if is_drifting
                        else self.rng.choice(["luxury_goods", "electronics", "travel_airline"])
                    )
                    mean_spike = (
                        acc_prof.mean_log_amount + 2.8
                        if not is_drifting
                        else acc_prof.mean_log_amount + 1.8
                    )
                    amounts[idx] = round(
                        float(np.exp(self.rng.normal(mean_spike, 0.4))), 2
                    )

                    device_ids[idx] = f"DEV_FRAUD_{self.rng.integers(10_000, 99_999)}"
                    device_is_new_arr[idx] = 1
                    foreign_region = self.rng.choice(
                        [r for r in REGIONS if r != acc_prof.home_region]
                    )
                    ip_regions[idx] = foreign_region
                    region_mismatch_arr[idx] = 1
                    session_seconds_arr[idx] = round(
                        float(self.rng.uniform(40.0, 240.0)), 1
                    )
                    pwd_reset_arr[idx] = 0

                elif ftype == f"ato":
                    # Typology 3: Account Takeover
                    # Password reset within 24h, new device + IP, full balance drain transfer
                    channels[idx] = "transfer"
                    categories[idx] = "transfer"
                    account_last_pwd_reset[acc_id] = ts - self.rng.uniform(300.0, 3600.0)
                    pwd_reset_arr[idx] = 1
                    device_ids[idx] = f"DEV_ATO_{self.rng.integers(10_000, 99_999)}"
                    device_is_new_arr[idx] = 1
                    ip_regions[idx] = self.rng.choice(
                        [r for r in REGIONS if r != acc_prof.home_region]
                    )
                    region_mismatch_arr[idx] = 1

                    # Drain 85% - 99% of available balance
                    curr_bal = account_balances[acc_id]
                    drain_pct = self.rng.uniform(0.85, 0.99)
                    amounts[idx] = round(max(50.0, curr_bal * drain_pct), 2)

                    dest_acc = self.rng.choice(account_keys)
                    dest_account_ids[idx] = dest_acc
                    dest_is_new_payee_arr[idx] = 1
                    account_seen_payees[acc_id].add(dest_acc)
                    session_seconds_arr[idx] = round(
                        float(self.rng.uniform(120.0, 600.0)), 1
                    )

                elif ftype == "mule_chain":
                    # Typology 4: Mule / Cash-out chain
                    # In-flow / rapid cash out through new accounts
                    channels[idx] = self.rng.choice(["transfer", "upi"])
                    categories[idx] = "transfer"
                    amounts[idx] = round(float(self.rng.uniform(1_500.0, 15_000.0)), 2)
                    device_ids[idx] = acc_prof.primary_device
                    device_is_new_arr[idx] = 0
                    ip_regions[idx] = acc_prof.home_region
                    region_mismatch_arr[idx] = 0

                    dest_acc = self.rng.choice(account_keys)
                    dest_account_ids[idx] = dest_acc
                    dest_is_new_payee_arr[idx] = 1
                    account_seen_payees[acc_id].add(dest_acc)
                    session_seconds_arr[idx] = round(
                        float(self.rng.uniform(30.0, 180.0)), 1
                    )
                    pwd_reset_arr[idx] = 0

                elif ftype == "app":
                    # Typology 5: Authorised Push Payment (Scam)
                    # Victim transfers large sum to first-time payee, long session (on phone call)
                    channels[idx] = self.rng.choice(["transfer", "upi"])
                    categories[idx] = "transfer"
                    amounts[idx] = round(
                        float(self.rng.uniform(2_000.0, 25_000.0)), 2
                    )
                    # Customer's genuine device & region
                    device_ids[idx] = acc_prof.primary_device
                    device_is_new_arr[idx] = 0
                    ip_regions[idx] = acc_prof.home_region
                    region_mismatch_arr[idx] = 0

                    dest_acc = self.rng.choice(account_keys)
                    dest_account_ids[idx] = dest_acc
                    dest_is_new_payee_arr[idx] = 1
                    account_seen_payees[acc_id].add(dest_acc)
                    # Long session: victim coerced on call
                    session_seconds_arr[idx] = round(
                        float(self.rng.uniform(1_200.0, 4_500.0)), 1
                    )
                    pwd_reset_arr[idx] = 0

            # Balance Accounting
            old_bal = account_balances[acc_id]
            # Top-up if balance would go deeply negative
            if old_bal < amounts[idx]:
                old_bal += round(float(amounts[idx] * self.rng.uniform(1.2, 2.5)), 2)

            new_bal = max(0.0, round(old_bal - amounts[idx], 2))
            old_balances[idx] = old_bal
            new_balances[idx] = new_bal
            account_balances[acc_id] = new_bal

        # Build DataFrame
        df = pd.DataFrame(
            {
                "txn_id": txn_ids,
                "ts": timestamps,
                "account_id": chosen_acc_ids,
                "merchant_id": chosen_merch_ids,
                "merchant_category": categories,
                "amount": amounts,
                "channel": channels,
                "device_id": device_ids,
                "device_is_new": device_is_new_arr,
                "ip_region": ip_regions,
                "region_mismatch": region_mismatch_arr,
                "hour": ((timestamps // 3600) % 24).astype(np.int32),
                "is_night": np.isin(((timestamps // 3600) % 24).astype(int), [0, 1, 2, 3, 4, 5]).astype(np.int32),
                "oldbalance": old_balances,
                "newbalance": new_balances,
                "dest_account_id": dest_account_ids,
                "dest_is_new_payee": dest_is_new_payee_arr,
                "session_seconds": session_seconds_arr,
                "pwd_reset_last_24h": pwd_reset_arr,
                "is_fraud": is_fraud_arr,
                "fraud_type": fraud_type_arr,
            }
        )

        # Label maturity timestamp: labels are mature exactly 7 days after the transaction
        df["label_mature_ts"] = df["ts"] + LABEL_MATURITY_SECONDS

        actual_fraud_rate = df["is_fraud"].mean()
        logger.info(
            "LedgerSim generation complete: %d rows, %d frauds (%.3f%% rate).",
            len(df),
            df["is_fraud"].sum(),
            actual_fraud_rate * 100,
        )

        return df

    def _get_pareto_probabilities(self, size: int, alpha: float = 1.3) -> np.ndarray:
        """Generate normalized Pareto power-law probabilities for entity frequencies."""
        ranks = np.arange(1, size + 1, dtype=np.float64)
        weights = 1.0 / (ranks**alpha)
        return weights / np.sum(weights)


def generate_ledgersim_dataset(
    fast: bool = True, output_path: Optional[str] = None
) -> pd.DataFrame:
    """Convenience helper to generate and optionally save the LedgerSim dataset."""
    cfg = SIMULATOR_CONFIG_FAST if fast else SIMULATOR_CONFIG_FULL
    sim = LedgerSim(
        num_transactions=cfg["num_transactions"],
        num_days=cfg["num_days"],
        num_accounts=cfg["num_accounts"],
        num_merchants=cfg["num_merchants"],
        fraud_rate_target=cfg["fraud_rate_target"],
        drift_start_ratio=cfg["drift_start_ratio"],
        seed=cfg["seed"],
    )
    df = sim.generate()

    if output_path is not None:
        p = Path(output_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        if p.suffix == ".parquet":
            df.to_parquet(p, index=False)
        else:
            df.to_csv(p, index=False)
        logger.info("Saved LedgerSim dataset to %s", p)

    return df


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    df_sample = generate_ledgersim_dataset(fast=True)
    print("Sample generation success:")
    print(df_sample.info())
    print(df_sample.head(3))
    print("\nFraud Breakdown:")
    print(df_sample["fraud_type"].value_counts())
