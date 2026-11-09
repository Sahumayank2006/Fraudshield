"""
FraudShield API Schemas (api/schemas.py)
========================================
Pydantic schemas for request validation, score outputs, batch summaries,
and stream control parameters.
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field, field_validator


# ==============================================================================
# Transaction Input & Scoring
# ==============================================================================
class TransactionInput(BaseModel):
    """Raw transaction fields required for real-time scoring."""

    txn_id: Optional[str] = Field(None, description="Unique transaction ID. Auto-generated if omitted.")
    ts: Optional[float] = Field(None, description="Transaction timestamp in epoch seconds.")
    account_id: str = Field(..., min_length=1, description="Originating account ID.")
    merchant_id: str = Field(..., min_length=1, description="Target merchant identifier.")
    merchant_category: str = Field("retail", description="Merchant category classification.")
    amount: float = Field(..., gt=0.0, description="Transaction amount in currency units.")
    channel: Literal["card_present", "online", "upi", "transfer"] = Field(
        "online", description="Payment initiation channel."
    )
    device_id: Optional[str] = Field(None, description="Hardware device fingerprint.")
    device_is_new: Optional[bool] = Field(False, description="Whether device is newly observed for this account.")
    ip_region: Optional[str] = Field("IN-MH", description="Geographic IP state/region code.")
    orig_balance: Optional[float] = Field(15000.0, ge=0.0, description="Available balance prior to transfer.")
    dest_balance: Optional[float] = Field(5000.0, ge=0.0, description="Recipient balance prior to transfer.")
    pwd_reset_recent: Optional[bool] = Field(False, description="Whether account credentials were reset recently.")
    session_risk_score: Optional[float] = Field(0.05, ge=0.0, le=1.0, description="Client session anomaly score.")

    @field_validator("amount")
    @classmethod
    def validate_positive_amount(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("Transaction amount must be strictly positive.")
        return v


class ReasonCodeOutput(BaseModel):
    feature: str
    headline: str
    description: str
    shap_value: float
    feature_value: float
    severity: Literal["HIGH", "MEDIUM", "LOW"]
    icon: str


class ScoreResponse(BaseModel):
    """Structured response for real-time inference."""

    txn_id: str
    decision: Literal["APPROVE", "REVIEW", "BLOCK"]
    fraud_probability: float = Field(..., ge=0.0, le=1.0)
    anomaly_score: float
    model_version: str
    latency_ms: float
    top_reasons: List[ReasonCodeOutput]
    thresholds: Dict[str, float]
    waterfall: Optional[List[Dict[str, Any]]] = None
    account_id: str
    amount: float


# ==============================================================================
# Batch Processing
# ==============================================================================
class BatchScoreSummary(BaseModel):
    total_transactions: int
    approved_count: int
    review_count: int
    blocked_count: int
    flagged_rate_pct: float
    estimated_loss_prevented: float
    processing_time_ms: float
    flagged_preview: List[Dict[str, Any]]


# ==============================================================================
# Stream Control & Attack Injection
# ==============================================================================
class StreamControlRequest(BaseModel):
    action: Literal["play", "pause", "speed", "reset", "attack"]
    speed: Optional[float] = Field(None, ge=0.5, le=50.0, description="Replay speed multiplier (0.5x to 50x).")
    attack_type: Optional[Literal["card_testing", "ato", "mule_chain"]] = None


class AttackRequest(BaseModel):
    attack_type: Literal["card_testing", "ato", "mule_chain"] = Field(
        ..., description="Specific fraud typology attack burst to synthesize."
    )
    count: Optional[int] = Field(15, ge=5, le=50, description="Number of burst transactions.")


# ==============================================================================
# Case Disposition
# ==============================================================================
class CaseUpdateRequest(BaseModel):
    status: Optional[Literal["OPEN", "CONFIRMED", "DISMISSED", "ESCALATED"]] = None
    notes: Optional[str] = None
    analyst_id: Optional[str] = None


# ==============================================================================
# Threshold Simulation
# ==============================================================================
class ThresholdSimQuery(BaseModel):
    t1: Optional[float] = Field(None, ge=0.0, le=1.0)
    t2: Optional[float] = Field(None, ge=0.0, le=1.0)
    cost_mode: Optional[Literal["flat", "amount_weighted"]] = "amount_weighted"

