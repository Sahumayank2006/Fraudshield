"""
FraudShield Streaming & Attack Engine (src/stream.py)
=====================================================
SSE transaction replay engine with real-time scoring, online state tracking,
speed regulation, and scripted fraud burst injection.

Supported Attack Typologies:
1. card_testing: Rapid micro-authorizations across multiple merchants in <60s.
2. ato (Account Takeover): Credential reset + novel device + high balance drain.
3. mule_chain: Rapid dispersion of recently credited funds across accounts.
"""

from __future__ import annotations

import asyncio
import datetime
import json
import logging
import time
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional

import joblib
import numpy as np
import pandas as pd

from config import ARTIFACTS_DIR, CHAMPION_MODEL_FILE, DATA_DIR, RANDOM_SEED
from src.explain import TreeSHAPExplainer
from src.features import default_feature_store
from src.store import storage_manager

logger = logging.getLogger("fraudshield.stream")


class ReplayStreamEngine:
    """Coordinates held-out transaction replay, attack burst injection, and SSE streaming."""

    def __init__(self):
        self.is_playing: bool = True
        self.speed: float = 2.0  # Transactions per second
        self.current_idx: int = 0
        self.attack_queue: List[Dict[str, Any]] = []

        # Model and explainer artifacts
        self.model_bundle: Optional[Dict[str, Any]] = None
        self.model: Any = None
        self.explainer: Optional[TreeSHAPExplainer] = None
        self.feature_names: List[str] = []
        self.t1: float = 0.005
        self.t2: float = 0.059

        # Test dataset for stream replay
        self.test_records: List[Dict[str, Any]] = []
        self._load_resources()

    def _load_resources(self) -> None:
        """Load champion model bundle, explainer, and held-out test transactions."""
        # 1. Load Champion Model
        if CHAMPION_MODEL_FILE.exists():
            try:
                self.model_bundle = joblib.load(CHAMPION_MODEL_FILE)
                self.model = self.model_bundle.get("model") or self.model_bundle.get("champion")
                self.feature_names = self.model_bundle.get("feature_names", [])
                self.t1 = float(self.model_bundle.get("t1", 0.005))
                self.t2 = float(self.model_bundle.get("t2", 0.059))
                self.explainer = TreeSHAPExplainer(self.model_bundle)
                logger.info("Loaded champion model bundle (version=%s)", self.model_bundle.get("version"))
            except Exception as e:
                logger.error("Error loading model bundle: %s", e)

        # 2. Load Held-Out Test Transactions
        parquet_path = DATA_DIR / "processed" / "ledgersim_fast.parquet"
        if parquet_path.exists():
            try:
                df = pd.read_parquet(parquet_path)
                # Use test partition (final 15%)
                test_start = int(len(df) * 0.85)
                test_df = df.iloc[test_start:].copy()
                self.test_records = test_df.to_dict(orient="records")
                logger.info("Loaded %d held-out test transactions for streaming.", len(self.test_records))
            except Exception as e:
                logger.error("Error loading test transactions: %s", e)

        if not self.test_records:
            # Fallback synthetic generator
            self._create_fallback_records()

    def _create_fallback_records(self, count: int = 500) -> None:
        """Create baseline synthetic records if dataset not pre-generated."""
        base_time = time.time()
        for i in range(count):
            self.test_records.append({
                "txn_id": f"TXN_STREAM_{i:06d}",
                "ts": base_time + i * 30.0,
                "account_id": f"ACC_{1000 + (i % 200)}",
                "merchant_id": f"MERCH_{50 + (i % 50)}",
                "merchant_category": "dining" if i % 4 == 0 else "groceries",
                "amount": round(float(np.random.lognormal(mean=5.5, sigma=1.0)), 2),
                "channel": "online" if i % 2 == 0 else "upi",
                "device_id": f"DEV_{100 + (i % 150)}",
                "device_is_new": bool(i % 17 == 0),
                "ip_region": "IN-MH",
                "is_fraud": 1 if i % 40 == 0 else 0,
            })

    def score_single_transaction(self, raw_txn: Dict[str, Any]) -> Dict[str, Any]:
        """
        Score a single incoming transaction end-to-end:
        - Online stateful feature engineering via FeatureStore
        - Hybrid model inference & calibrated probability
        - Decision routing (APPROVE / REVIEW / BLOCK)
        - TreeSHAP explanation & dynamic reason codes
        - Real inference latency measurement
        """
        t_start = time.perf_counter()

        # 1. Online Feature Extraction
        feat_series = default_feature_store.compute_and_update(raw_txn)
        feat_df = pd.DataFrame([feat_series])

        # 2. Model Inference & Dynamic Anomaly Scoring
        if self.model is not None and self.feature_names:
            if hasattr(self.model, "transform_features"):
                feat_df = self.model.transform_features(feat_df)
            else:
                for missing in set(self.feature_names) - set(feat_df.columns):
                    feat_df[missing] = 0.0

            prob = float(self.model.predict_proba(feat_df[self.feature_names])[:, 1][0])
            iso_val = float(feat_df["iso_score"].iloc[0]) if "iso_score" in feat_df.columns else 0.5
        else:
            prob = 0.02
            iso_val = 0.1

        t_end = time.perf_counter()
        latency_ms = max(0.5, (t_end - t_start) * 1000.0)

        # 3. Decision Routing
        if prob >= self.t2:
            decision = "BLOCK"
        elif prob >= self.t1:
            decision = "REVIEW"
        else:
            decision = "APPROVE"

        # 4. Local Explanation & Dynamic Reason Codes
        top_reasons = []
        waterfall = []
        if self.explainer is not None and (decision != "APPROVE" or prob > 0.05):
            try:
                exp_res = self.explainer.explain_instance(
                    feat_df[self.feature_names],
                    raw_txn=raw_txn,
                    top_k=3,
                )
                top_reasons = exp_res.get("top_reasons", [])
                waterfall = exp_res.get("waterfall", [])
            except Exception as e:
                logger.debug("TreeSHAP explanation fallback: %s", e)

        if not top_reasons and decision != "APPROVE":
            top_reasons = [{
                "feature": "amount",
                "headline": f"Elevated Risk ({decision})",
                "description": f"Predicted fraud probability {prob:.1%} exceeds operational threshold.",
                "shap_value": 0.85,
                "feature_value": float(raw_txn.get("amount", 0.0)),
                "severity": "HIGH" if decision == "BLOCK" else "MEDIUM",
                "icon": "shield-alert",
            }]

        # 5. Audit Logging & Telemetry
        model_ver = self.model_bundle.get("version", "v1.0-champion") if self.model_bundle else "v1.0"
        storage_manager.log_decision(
            txn_id=raw_txn.get("txn_id", "TXN_LIVE"),
            ts=float(raw_txn.get("ts", time.time())),
            decision=decision,
            fraud_probability=prob,
            anomaly_score=iso_val,
            latency_ms=latency_ms,
            model_version=model_ver,
        )

        storage_manager.record_transaction_event(
            decision=decision,
            fraud_probability=prob,
            amount=float(raw_txn.get("amount", 0.0)),
            latency_ms=latency_ms,
            is_known_fraud=bool(raw_txn.get("is_fraud", 0) == 1),
        )

        # Create persistent analyst case if flagged
        if decision in ("REVIEW", "BLOCK"):
            storage_manager.create_case(
                txn_id=raw_txn.get("txn_id", "TXN_LIVE"),
                ts=float(raw_txn.get("ts", time.time())),
                account_id=raw_txn.get("account_id", "ACC_UNKNOWN"),
                merchant_id=raw_txn.get("merchant_id", "MERCH_UNKNOWN"),
                merchant_category=raw_txn.get("merchant_category", "retail"),
                amount=float(raw_txn.get("amount", 0.0)),
                channel=raw_txn.get("channel", "online"),
                fraud_probability=prob,
                anomaly_score=iso_val,
                decision=decision,
                top_reasons=top_reasons,
                raw_txn=raw_txn,
                device_id=raw_txn.get("device_id"),
                ip_region=raw_txn.get("ip_region"),
            )

        return {
            "txn_id": raw_txn.get("txn_id", "TXN_LIVE"),
            "ts": float(raw_txn.get("ts", time.time())),
            "account_id": raw_txn.get("account_id", "ACC_UNKNOWN"),
            "merchant_id": raw_txn.get("merchant_id", "MERCH_UNKNOWN"),
            "merchant_category": raw_txn.get("merchant_category", "retail"),
            "amount": float(raw_txn.get("amount", 0.0)),
            "channel": raw_txn.get("channel", "online"),
            "fraud_probability": round(prob, 4),
            "anomaly_score": round(iso_val, 4),
            "decision": decision,
            "model_version": model_ver,
            "latency_ms": round(latency_ms, 2),
            "top_reasons": top_reasons,
            "waterfall": waterfall,
            "thresholds": {"t1": self.t1, "t2": self.t2},
            "is_attack_burst": bool(raw_txn.get("is_attack_burst", False)),
            "attack_typology": raw_txn.get("attack_typology", None),
        }

    def inject_attack_burst(
        self,
        attack_type: str = "card_testing",
        count: int = 15,
    ) -> Dict[str, Any]:
        """
        Synthesize and enqueue a scripted fraud burst to demonstrate live detection.
        """
        logger.info("Injecting scripted attack burst: %s (N=%d)...", attack_type, count)
        base_time = time.time()
        burst: List[Dict[str, Any]] = []

        if attack_type == "card_testing":
            # 15 rapid micro-transactions across digital merchants in 45s
            test_acc = f"ACC_ATTACK_{np.random.randint(1000, 9999)}"
            test_dev = f"DEV_BOT_{np.random.randint(10, 99)}"
            for i in range(count):
                amt = round(float(np.random.uniform(15.0, 85.0)), 2)
                burst.append({
                    "txn_id": f"TXN_ATK_CT_{int(base_time)}_{i:02d}",
                    "ts": base_time + (i * 2.5),
                    "account_id": test_acc,
                    "merchant_id": f"MERCH_DIGITAL_{10 + (i % 6)}",
                    "merchant_category": "digital_services",
                    "amount": amt,
                    "channel": "online",
                    "device_id": test_dev,
                    "device_is_new": 1,
                    "ip_region": "US-NY",
                    "region_mismatch": 1,
                    "oldbalance": 1500.0,
                    "newbalance": max(0.0, 1500.0 - amt),
                    "orig_balance": 1500.0,
                    "dest_balance": 500.0,
                    "session_seconds": 1.2,
                    "hour": 2,
                    "is_night": 1,
                    "pwd_reset_last_24h": 0,
                    "pwd_reset_recent": False,
                    "session_risk_score": 0.88,
                    "is_fraud": 1,
                    "is_attack_burst": True,
                    "attack_typology": "card_testing",
                })

        elif attack_type == "ato":
            # Account takeover: Credential reset + new device + 94% balance liquidation
            test_acc = f"ACC_VICTIM_{np.random.randint(1000, 9999)}"
            burst.append({
                "txn_id": f"TXN_ATK_ATO_{int(base_time)}_01",
                "ts": base_time,
                "account_id": test_acc,
                "merchant_id": "MERCH_LUXURY_CRYPTO_01",
                "merchant_category": "crypto_exchange",
                "amount": 94500.0,
                "channel": "transfer",
                "device_id": "DEV_UNSEEN_ATTACKER_99",
                "device_is_new": 1,
                "ip_region": "US-NY",
                "region_mismatch": 1,
                "oldbalance": 100000.0,
                "newbalance": 5500.0,
                "orig_balance": 100000.0,
                "dest_balance": 5500.0,
                "session_seconds": 14.0,
                "pwd_reset_last_24h": 1,
                "pwd_reset_recent": True,
                "session_risk_score": 0.95,
                "is_fraud": 1,
                "is_attack_burst": True,
                "attack_typology": "ato",
            })

        elif attack_type == "mule_chain":
            # Mule account pass-through: Rapid consecutive transfers draining credit
            mule_acc = f"ACC_MULE_{np.random.randint(1000, 9999)}"
            for i in range(min(count, 8)):
                amt = round(float(np.random.uniform(45000.0, 78000.0)), 2)
                burst.append({
                    "txn_id": f"TXN_ATK_MULE_{int(base_time)}_{i:02d}",
                    "ts": base_time + (i * 12.0),
                    "account_id": mule_acc,
                    "merchant_id": f"MERCH_TRANSFER_P2P_{i}",
                    "merchant_category": "digital_services",
                    "amount": amt,
                    "channel": "upi" if i % 2 == 0 else "transfer",
                    "device_id": f"DEV_MULE_{i}",
                    "device_is_new": 1,
                    "ip_region": "IN-WB",
                    "region_mismatch": 1,
                    "oldbalance": 80000.0,
                    "newbalance": max(0.0, 80000.0 - amt),
                    "orig_balance": 80000.0,
                    "dest_balance": 100.0,
                    "session_seconds": 22.0,
                    "pwd_reset_last_24h": 0,
                    "pwd_reset_recent": False,
                    "session_risk_score": 0.82,
                    "is_fraud": 1,
                    "is_attack_burst": True,
                    "attack_typology": "mule_chain",
                })

        self.attack_queue.extend(burst)
        return {
            "status": "QUEUED",
            "attack_type": attack_type,
            "injected_count": len(burst),
            "queue_size": len(self.attack_queue),
        }

    async def event_generator(self) -> AsyncGenerator[str, None]:
        """
        Asynchronous Server-Sent Events (SSE) generator.
        Emits:
        - Streamed transaction with real scores & decision
        - Live session aggregate counters
        - Heartbeat when paused
        """
        while True:
            if not self.is_playing:
                # Emit heartbeat keeping SSE connection alive
                yield f": heartbeat {datetime.datetime.now(datetime.timezone.utc).isoformat()}\n\n"
                await asyncio.sleep(0.5)
                continue

            # Prioritize attack transactions if any in queue
            if self.attack_queue:
                raw_txn = self.attack_queue.pop(0)
            else:
                if not self.test_records:
                    await asyncio.sleep(1.0)
                    continue
                raw_txn = self.test_records[self.current_idx]
                self.current_idx = (self.current_idx + 1) % len(self.test_records)

            # Score transaction
            scored = self.score_single_transaction(raw_txn)
            scored["session_stats"] = storage_manager.get_session_stats()

            # Format as valid SSE data packet
            payload = {
                "type": "TRANSACTION",
                "data": scored,
            }
            yield f"data: {json.dumps(payload)}\n\n"

            # Sleep inversely proportional to playback speed
            delay = max(0.02, 1.0 / max(0.5, self.speed))
            await asyncio.sleep(delay)


# Global singleton streaming engine
streaming_engine = ReplayStreamEngine()
