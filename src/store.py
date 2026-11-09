"""
FraudShield SQLite Repository (src/store.py)
============================================
Persistent storage for analyst cases, decision audits, and live session telemetry.
Maintains relational SQLite tables for case management, audit logs, and
account history retrieval.
"""

from __future__ import annotations

import datetime
import json
import logging
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from config import DATA_DIR

logger = logging.getLogger("fraudshield.store")

DB_PATH = DATA_DIR / "fraudshield.db"


class StorageManager:
    """Manages SQLite database connections and operations for FraudShield."""

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        """Create necessary tables and indices if they do not exist."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # 1. Analyst Cases Queue
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS cases (
                    case_id TEXT PRIMARY KEY,
                    txn_id TEXT UNIQUE NOT NULL,
                    ts REAL NOT NULL,
                    account_id TEXT NOT NULL,
                    merchant_id TEXT NOT NULL,
                    merchant_category TEXT NOT NULL,
                    amount REAL NOT NULL,
                    channel TEXT NOT NULL,
                    device_id TEXT,
                    ip_region TEXT,
                    fraud_probability REAL NOT NULL,
                    anomaly_score REAL NOT NULL,
                    decision TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'OPEN',
                    priority TEXT NOT NULL DEFAULT 'MEDIUM',
                    top_reasons_json TEXT NOT NULL,
                    raw_txn_json TEXT NOT NULL,
                    notes TEXT DEFAULT '',
                    analyst_id TEXT DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_cases_status ON cases(status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_cases_account ON cases(account_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_cases_ts ON cases(ts)")

            # 2. Decision Audit Log (Every scored transaction recorded)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS decision_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    txn_id TEXT NOT NULL,
                    ts REAL NOT NULL,
                    decision TEXT NOT NULL,
                    fraud_probability REAL NOT NULL,
                    anomaly_score REAL NOT NULL,
                    latency_ms REAL NOT NULL,
                    model_version TEXT NOT NULL,
                    feature_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_decision_log_txn ON decision_log(txn_id)")

            # 3. Live Session Telemetry Counters
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS session_telemetry (
                    id INTEGER PRIMARY KEY,
                    streamed_count INTEGER DEFAULT 0,
                    approved_count INTEGER DEFAULT 0,
                    reviewed_count INTEGER DEFAULT 0,
                    blocked_count INTEGER DEFAULT 0,
                    fraud_detected_count INTEGER DEFAULT 0,
                    amount_protected REAL DEFAULT 0.0,
                    total_latency_ms REAL DEFAULT 0.0,
                    recent_latencies_json TEXT DEFAULT '[]'
                )
            """)

            # Ensure row 1 exists in telemetry
            cursor.execute("""
                INSERT OR IGNORE INTO session_telemetry (
                    id, streamed_count, approved_count, reviewed_count, blocked_count,
                    fraud_detected_count, amount_protected, total_latency_ms, recent_latencies_json
                ) VALUES (1, 0, 0, 0, 0, 0, 0.0, 0.0, '[]')
            """)

            conn.commit()
        logger.info("Initialized FraudShield SQLite database at %s", self.db_path)

    # ==========================================================================
    # Case Management
    # ==========================================================================
    def create_case(
        self,
        txn_id: str,
        ts: float,
        account_id: str,
        merchant_id: str,
        merchant_category: str,
        amount: float,
        channel: str,
        fraud_probability: float,
        anomaly_score: float,
        decision: str,
        top_reasons: List[Dict[str, Any]],
        raw_txn: Dict[str, Any],
        device_id: Optional[str] = None,
        ip_region: Optional[str] = None,
        status: str = "OPEN",
    ) -> str:
        """Create a new analyst case for a flagged transaction."""
        now_str = datetime.datetime.now(datetime.timezone.utc).isoformat()
        case_id = f"CASE-{txn_id.replace('TXN_', '')}"

        # Assign priority based on probability and amount
        if fraud_probability >= 0.85 or amount >= 50000.0:
            priority = "CRITICAL"
        elif fraud_probability >= 0.50 or decision == "BLOCK":
            priority = "HIGH"
        else:
            priority = "MEDIUM"

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO cases (
                    case_id, txn_id, ts, account_id, merchant_id, merchant_category,
                    amount, channel, device_id, ip_region, fraud_probability,
                    anomaly_score, decision, status, priority, top_reasons_json,
                    raw_txn_json, notes, analyst_id, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                case_id,
                txn_id,
                float(ts),
                account_id,
                merchant_id,
                merchant_category,
                float(amount),
                channel,
                device_id or raw_txn.get("device_id", "DEV_UNKNOWN"),
                ip_region or raw_txn.get("ip_region", "IN-MH"),
                float(fraud_probability),
                float(anomaly_score),
                decision,
                status,
                priority,
                json.dumps(top_reasons),
                json.dumps(raw_txn),
                "",
                "",
                now_str,
                now_str,
            ))
            conn.commit()

        return case_id

    def list_cases(
        self,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """List cases with optional status/priority filtering and pagination."""
        query = "SELECT * FROM cases"
        params: List[Any] = []
        conditions: List[str] = []

        if status and status.upper() != "ALL":
            conditions.append("status = ?")
            params.append(status.upper())
        if priority and priority.upper() != "ALL":
            conditions.append("priority = ?")
            params.append(priority.upper())

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY ts DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()

        results = []
        for r in rows:
            d = dict(r)
            d["top_reasons"] = json.loads(d.pop("top_reasons_json"))
            d["raw_txn"] = json.loads(d.pop("raw_txn_json"))
            results.append(d)
        return results

    def get_case(self, identifier: str) -> Optional[Dict[str, Any]]:
        """Retrieve full case details by case_id or txn_id."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM cases WHERE case_id = ? OR txn_id = ?",
                (identifier, identifier),
            )
            row = cursor.fetchone()

        if not row:
            return None

        d = dict(row)
        d["top_reasons"] = json.loads(d.pop("top_reasons_json"))
        d["raw_txn"] = json.loads(d.pop("raw_txn_json"))
        return d

    def update_case(
        self,
        case_id: str,
        status: Optional[str] = None,
        notes: Optional[str] = None,
        analyst_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Update case disposition status, notes, or assigned analyst."""
        now_str = datetime.datetime.now(datetime.timezone.utc).isoformat()
        updates = ["updated_at = ?"]
        params: List[Any] = [now_str]

        if status:
            updates.append("status = ?")
            params.append(status.upper())
        if notes is not None:
            updates.append("notes = ?")
            params.append(notes)
        if analyst_id is not None:
            updates.append("analyst_id = ?")
            params.append(analyst_id)

        params.append(case_id)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"UPDATE cases SET {', '.join(updates)} WHERE case_id = ? OR txn_id = ?",
                (*params, case_id),
            )
            conn.commit()

        return self.get_case(case_id)

    def get_account_history(self, account_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Retrieve recent transactions for an account from decision logs and cases."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT case_id, txn_id, ts, amount, merchant_id, channel,
                       fraud_probability, decision, status
                FROM cases
                WHERE account_id = ?
                ORDER BY ts DESC
                LIMIT ?
            """, (account_id, limit))
            rows = cursor.fetchall()

        return [dict(r) for r in rows]

    def find_similar_cases(self, case_id: str, limit: int = 3) -> List[Dict[str, Any]]:
        """Find nearest historical fraud cases sharing similar characteristics."""
        target = self.get_case(case_id)
        if not target:
            return []

        # Find cases sharing same merchant category, channel, or similar amount
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT case_id, txn_id, ts, account_id, merchant_category, amount,
                       channel, fraud_probability, decision, status, notes
                FROM cases
                WHERE case_id != ? AND (status = 'CONFIRMED' OR decision = 'BLOCK')
                ORDER BY ABS(amount - ?) ASC
                LIMIT ?
            """, (target["case_id"], target["amount"], limit))
            rows = cursor.fetchall()

        return [dict(r) for r in rows]

    # ==========================================================================
    # Decision Audit Logging
    # ==========================================================================
    def log_decision(
        self,
        txn_id: str,
        ts: float,
        decision: str,
        fraud_probability: float,
        anomaly_score: float,
        latency_ms: float,
        model_version: str,
        feature_hash: str = "",
    ) -> None:
        """Append an audit record to the permanent decision log."""
        now_str = datetime.datetime.now(datetime.timezone.utc).isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO decision_log (
                    txn_id, ts, decision, fraud_probability, anomaly_score,
                    latency_ms, model_version, feature_hash, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                txn_id,
                float(ts),
                decision,
                float(fraud_probability),
                float(anomaly_score),
                float(latency_ms),
                model_version,
                feature_hash,
                now_str,
            ))
            conn.commit()

    # ==========================================================================
    # Session Telemetry Counters
    # ==========================================================================
    def get_session_stats(self) -> Dict[str, Any]:
        """Fetch real-time aggregate session statistics."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM session_telemetry WHERE id = 1")
            row = cursor.fetchone()

        if not row:
            return {
                "streamed_count": 0,
                "approved_count": 0,
                "reviewed_count": 0,
                "blocked_count": 0,
                "fraud_detected_count": 0,
                "amount_protected": 0.0,
                "avg_latency_ms": 0.0,
                "p95_latency_ms": 0.0,
                "open_cases_count": 0,
            }

        d = dict(row)
        recent_lats = json.loads(d.pop("recent_latencies_json", "[]"))
        total_streamed = max(1, d["streamed_count"])
        avg_lat = d["total_latency_ms"] / total_streamed if d["streamed_count"] > 0 else 0.0
        p95_lat = float(np.percentile(recent_lats, 95)) if recent_lats else 0.0

        # Count open cases
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM cases WHERE status = 'OPEN'")
            open_cases = cursor.fetchone()[0]

        return {
            "streamed_count": d["streamed_count"],
            "approved_count": d["approved_count"],
            "reviewed_count": d["reviewed_count"],
            "blocked_count": d["blocked_count"],
            "fraud_detected_count": d["fraud_detected_count"],
            "amount_protected": round(float(d["amount_protected"]), 2),
            "avg_latency_ms": round(float(avg_lat), 2),
            "p95_latency_ms": round(float(p95_lat), 2),
            "open_cases_count": open_cases,
        }

    def record_transaction_event(
        self,
        decision: str,
        fraud_probability: float,
        amount: float,
        latency_ms: float,
        is_known_fraud: bool = False,
    ) -> None:
        """Update live telemetry counters following a scored transaction."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM session_telemetry WHERE id = 1")
            row = cursor.fetchone()
            if not row:
                return

            d = dict(row)
            streamed = d["streamed_count"] + 1
            approved = d["approved_count"] + (1 if decision == "APPROVE" else 0)
            reviewed = d["reviewed_count"] + (1 if decision == "REVIEW" else 0)
            blocked = d["blocked_count"] + (1 if decision == "BLOCK" else 0)
            fraud_caught = d["fraud_detected_count"] + (1 if (is_known_fraud or decision == "BLOCK") else 0)
            protected = d["amount_protected"] + (amount if decision == "BLOCK" else 0.0)
            total_lat = d["total_latency_ms"] + latency_ms

            # Keep last 200 latencies for p95 calculation
            recent = json.loads(d["recent_latencies_json"])
            recent.append(round(latency_ms, 2))
            if len(recent) > 200:
                recent = recent[-200:]

            cursor.execute("""
                UPDATE session_telemetry SET
                    streamed_count = ?,
                    approved_count = ?,
                    reviewed_count = ?,
                    blocked_count = ?,
                    fraud_detected_count = ?,
                    amount_protected = ?,
                    total_latency_ms = ?,
                    recent_latencies_json = ?
                WHERE id = 1
            """, (
                streamed,
                approved,
                reviewed,
                blocked,
                fraud_caught,
                protected,
                total_lat,
                json.dumps(recent),
            ))
            conn.commit()

    def reset_session_stats(self) -> None:
        """Reset stream counters back to zero for a clean demo session."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE session_telemetry SET
                    streamed_count = 0,
                    approved_count = 0,
                    reviewed_count = 0,
                    blocked_count = 0,
                    fraud_detected_count = 0,
                    amount_protected = 0.0,
                    total_latency_ms = 0.0,
                    recent_latencies_json = '[]'
                WHERE id = 1
            """)
            conn.commit()

    def seed_initial_cases_if_empty(
        self,
        test_df: pd.DataFrame,
        model_bundle: Dict[str, Any],
        explainer: Any,
        count: int = 15,
    ) -> None:
        """Seed initial case queue from high-risk test transactions so desk is pre-populated."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM cases")
            existing = cursor.fetchone()[0]

        if existing >= 5:
            return  # Already populated

        logger.info("Seeding %d initial flagged cases into SQLite...", count)
        model = model_bundle.get("model") or model_bundle.get("champion")
        t1 = model_bundle.get("t1", 0.005)
        t2 = model_bundle.get("t2", 0.059)

        from src.features import extract_features
        # Extract features for sample
        feat_df = extract_features(test_df.iloc[:2000], reset_state=True)
        eval_cols = model_bundle.get("feature_names", list(feat_df.columns))
        probs = model.predict_proba(feat_df[eval_cols])[:, 1]

        # Prioritize frauds or high probabilities
        flagged_indices = np.where(probs >= t1)[0]
        if len(flagged_indices) < count:
            flagged_indices = np.argsort(probs)[-count:]
        else:
            flagged_indices = flagged_indices[:count]

        for idx in flagged_indices:
            row = test_df.iloc[idx].to_dict()
            prob = float(probs[idx])
            dec = "BLOCK" if prob >= t2 else ("REVIEW" if prob >= t1 else "APPROVE")
            if dec == "APPROVE":
                dec = "REVIEW"  # Force flagged for seeded queue

            # Local explanation
            row_feat = feat_df[eval_cols].iloc[idx:idx+1]
            try:
                exp = explainer.explain_instance(row_feat, raw_txn=row, top_k=3)
                reasons = exp["top_reasons"]
                iso_val = float(row_feat.get("iso_score", [0.0])[0]) if "iso_score" in row_feat else 0.5
            except Exception:
                reasons = [{"headline": "Elevated Risk", "description": "High probability signature", "severity": "HIGH", "icon": "alert-circle"}]
                iso_val = 0.5

            self.create_case(
                txn_id=row["txn_id"],
                ts=float(row.get("ts", 0.0)),
                account_id=row["account_id"],
                merchant_id=row["merchant_id"],
                merchant_category=row.get("merchant_category", "retail"),
                amount=float(row["amount"]),
                channel=row.get("channel", "online"),
                fraud_probability=prob,
                anomaly_score=iso_val,
                decision=dec,
                top_reasons=reasons,
                raw_txn=row,
                device_id=row.get("device_id"),
                ip_region=row.get("ip_region"),
            )

        logger.info("Successfully seeded %d cases into database.", count)


# Global singleton instance
storage_manager = StorageManager()

