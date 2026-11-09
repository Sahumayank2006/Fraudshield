import React, { useState, useEffect, useCallback } from "react";
import {
  fetchCases,
  fetchCase,
  updateCase,
  TransactionData,
} from "../api/client";
import {
  SignalBlock,
  SignalReview,
  SignalApprove,
  IconCheck,
  IconCross,
  IconShieldAlert,
  IconChevronLeft,
  IconChevronRight,
  IconHistory,
  IconFileText,
} from "../components/common/Icons";
import { SvgWaterfall, WaterfallStep } from "../components/charts/SvgWaterfall";

interface CaseFileProps {
  initialCaseId?: string | null;
  onSelectCase?: (caseId: string) => void;
}

export const CaseFile: React.FC<CaseFileProps> = ({ initialCaseId, onSelectCase }) => {
  // Case queue state
  const [caseList, setCaseList] = useState<any[]>([]);
  const [statusFilter, setStatusFilter] = useState<string>("ALL");
  const [activeCaseId, setActiveCaseId] = useState<string | null>(initialCaseId || null);
  const [caseData, setCaseData] = useState<any | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isSaving, setIsSaving] = useState<boolean>(false);
  const [actionFeedback, setActionFeedback] = useState<string | null>(null);

  // Form notes state
  const [analystNotes, setAnalystNotes] = useState<string>("");

  // Load cases list
  const loadCaseQueue = useCallback(async () => {
    try {
      const cases = await fetchCases(statusFilter, 50);
      setCaseList(cases);
      if (cases.length > 0) {
        // If current activeCaseId is not in list or not set, select the first
        const exists = cases.some((c: any) => c.case_id === activeCaseId);
        if (!exists || !activeCaseId) {
          setActiveCaseId(cases[0].case_id);
        }
      }
    } catch (err) {
      console.error("Failed to load case queue:", err);
    }
  }, [statusFilter, activeCaseId]);

  useEffect(() => {
    loadCaseQueue();
  }, [loadCaseQueue]);

  // If initialCaseId changes from parent
  useEffect(() => {
    if (initialCaseId) {
      setActiveCaseId(initialCaseId);
    }
  }, [initialCaseId]);

  // Load detailed case file
  const loadActiveCase = useCallback(async (id: string) => {
    setIsLoading(true);
    try {
      const data = await fetchCase(id);
      setCaseData(data);
      setAnalystNotes(data.notes || "");
    } catch (err) {
      console.error("Failed to load case details for", id, err);
      setCaseData(null);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (activeCaseId) {
      loadActiveCase(activeCaseId);
      if (onSelectCase) onSelectCase(activeCaseId);
    }
  }, [activeCaseId, loadActiveCase, onSelectCase]);

  // Queue navigation
  const currentIndex = caseList.findIndex((c) => c.case_id === activeCaseId);
  const hasPrev = currentIndex > 0;
  const hasNext = currentIndex >= 0 && currentIndex < caseList.length - 1;

  const handlePrevCase = () => {
    if (hasPrev) {
      setActiveCaseId(caseList[currentIndex - 1].case_id);
    }
  };

  const handleNextCase = () => {
    if (hasNext) {
      setActiveCaseId(caseList[currentIndex + 1].case_id);
    }
  };

  // Disposition Actions
  const handleDisposition = async (newStatus: "CONFIRMED" | "DISMISSED" | "ESCALATED") => {
    if (!activeCaseId) return;
    setIsSaving(true);
    try {
      await updateCase(activeCaseId, newStatus, analystNotes);
      setActionFeedback(`Case ${activeCaseId} successfully updated to [${newStatus}].`);
      setTimeout(() => setActionFeedback(null), 4000);

      // Reload case details and queue
      await loadActiveCase(activeCaseId);
      const updatedList = await fetchCases(statusFilter, 50);
      setCaseList(updatedList);

      // Auto-advance if next case exists
      if (hasNext && newStatus !== "ESCALATED") {
        setTimeout(() => {
          setActiveCaseId(caseList[currentIndex + 1].case_id);
        }, 1200);
      }
    } catch (err) {
      console.error("Failed to update case disposition:", err);
      setActionFeedback("Error saving case disposition.");
    } finally {
      setIsSaving(false);
    }
  };

  const handleSaveNotesOnly = async () => {
    if (!activeCaseId) return;
    setIsSaving(true);
    try {
      await updateCase(activeCaseId, undefined, analystNotes);
      setActionFeedback("Notes saved to database.");
      setTimeout(() => setActionFeedback(null), 3000);
      await loadActiveCase(activeCaseId);
    } catch (err) {
      console.error("Failed to save notes:", err);
      setActionFeedback("Error saving notes.");
    } finally {
      setIsSaving(false);
    }
  };

  // Keyboard navigation shortcuts [J] next, [K] prev
  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;
      if (e.key === "j" || e.key === "J") {
        e.preventDefault();
        handleNextCase();
      } else if (e.key === "k" || e.key === "K") {
        e.preventDefault();
        handlePrevCase();
      }
    };
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [currentIndex, caseList]);

  // Render Dual-Threshold Score Gauge
  const renderDualThresholdGauge = () => {
    if (!caseData) return null;
    const p = caseData.fraud_probability;
    const t1 = caseData.thresholds?.t1 ?? 0.005;
    const t2 = caseData.thresholds?.t2 ?? 0.059;

    // Standard error approx for 95% CI
    const se = Math.sqrt((p * (1 - p)) / 250);
    const ciLow = Math.max(0.0, p - 1.96 * se);
    const ciHigh = Math.min(1.0, p + 1.96 * se);

    // Coordinate mapping (0 to 1 -> 0% to 100%)
    const pct = (val: number) => `${Math.min(100, Math.max(0, val * 100)).toFixed(1)}%`;

    return (
      <div style={{ backgroundColor: "var(--paper-raised)", border: "1px solid var(--rule)", padding: "var(--space-4)" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 8 }}>
          <span className="eyebrow">Dual-Threshold Decision Gauge</span>
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            {caseData.decision === "BLOCK" && <SignalBlock size={13} />}
            {caseData.decision === "REVIEW" && <SignalReview size={13} />}
            {caseData.decision === "APPROVE" && <SignalApprove size={13} />}
            <span
              style={{
                fontFamily: "var(--font-mono)",
                fontWeight: 600,
                fontSize: 13,
                color:
                  caseData.decision === "BLOCK"
                    ? "var(--block)"
                    : caseData.decision === "REVIEW"
                    ? "var(--review)"
                    : "var(--approve)",
              }}
            >
              {caseData.decision}
            </span>
          </div>
        </div>

        {/* Visual Gauge Bar */}
        <div style={{ position: "relative", height: 26, backgroundColor: "var(--paper)", border: "1px solid var(--rule)", marginTop: 12, marginBottom: 28 }}>
          {/* Green / Approve Zone */}
          <div
            style={{
              position: "absolute",
              left: 0,
              top: 0,
              bottom: 0,
              width: pct(t1),
              backgroundColor: "rgba(45, 106, 79, 0.15)",
              borderRight: "1px dashed var(--approve)",
            }}
          />
          {/* Amber / Review Zone */}
          <div
            style={{
              position: "absolute",
              left: pct(t1),
              top: 0,
              bottom: 0,
              width: `${((t2 - t1) * 100).toFixed(1)}%`,
              backgroundColor: "rgba(180, 83, 9, 0.18)",
              borderRight: "1px dashed var(--block)",
            }}
          />
          {/* Crimson / Block Zone */}
          <div
            style={{
              position: "absolute",
              left: pct(t2),
              top: 0,
              bottom: 0,
              right: 0,
              backgroundColor: "rgba(158, 42, 43, 0.20)",
            }}
          />

          {/* t1 Marker Tick */}
          <div style={{ position: "absolute", left: pct(t1), top: -18, transform: "translateX(-50%)", fontSize: 10, fontFamily: "var(--font-mono)", color: "var(--review)" }}>
            t₁={t1.toFixed(3)}
          </div>

          {/* t2 Marker Tick */}
          <div style={{ position: "absolute", left: pct(t2), top: -18, transform: "translateX(-50%)", fontSize: 10, fontFamily: "var(--font-mono)", color: "var(--block)" }}>
            t₂={t2.toFixed(3)}
          </div>

          {/* 95% Confidence Interval Span */}
          <div
            style={{
              position: "absolute",
              left: pct(ciLow),
              width: `${Math.max(1, (ciHigh - ciLow) * 100).toFixed(1)}%`,
              top: 10,
              height: 6,
              backgroundColor: caseData.decision === "BLOCK" ? "var(--block)" : "var(--review)",
              opacity: 0.35,
            }}
          />

          {/* Needle Pointer */}
          <div
            style={{
              position: "absolute",
              left: pct(p),
              top: -3,
              bottom: -3,
              width: 3,
              backgroundColor: caseData.decision === "BLOCK" ? "var(--block)" : "var(--review)",
              transform: "translateX(-50%)",
              zIndex: 3,
            }}
          />

          {/* Needle Value Callout */}
          <div
            style={{
              position: "absolute",
              left: pct(p),
              bottom: -22,
              transform: "translateX(-50%)",
              fontSize: 11,
              fontFamily: "var(--font-mono)",
              fontWeight: 600,
              color: caseData.decision === "BLOCK" ? "var(--block)" : "var(--ink)",
              whiteSpace: "nowrap",
            }}
          >
            p={(p * 100).toFixed(2)}%
          </div>
        </div>

        {/* Legend & Stats */}
        <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, color: "var(--ink-soft)", fontFamily: "var(--font-mono)", marginTop: 6 }}>
          <span>95% CI: [{(ciLow * 100).toFixed(2)}%, {(ciHigh * 100).toFixed(2)}%]</span>
          <span>Anomaly Score: {(caseData.anomaly_score * 100).toFixed(1)}%</span>
        </div>
      </div>
    );
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-6)" }}>
      {/* Top Strip: Queue Header & Case Navigation */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          borderBottom: "1px solid var(--rule)",
          paddingBottom: "var(--space-4)",
        }}
      >
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: "var(--space-3)" }}>
            <span className="eyebrow" style={{ color: "var(--review)" }}>§03 Case File</span>
            <span style={{ fontSize: 11, fontFamily: "var(--font-mono)", color: "var(--ink-faint)" }}>
              QUEUE: {caseList.length > 0 ? `${currentIndex + 1} of ${caseList.length}` : "0"} CASES
            </span>
          </div>
          <h1 style={{ marginTop: 4 }}>
            Case Dossier: {activeCaseId || "Loading..."}
          </h1>
        </div>

        {/* Status Filter & Queue Paging Controls */}
        <div style={{ display: "flex", alignItems: "center", gap: "var(--space-3)" }}>
          {/* Status Filter Tabs */}
          <div style={{ display: "flex", border: "1px solid var(--rule)", backgroundColor: "var(--paper-raised)" }}>
            {["ALL", "OPEN", "CONFIRMED", "DISMISSED", "ESCALATED"].map((st) => (
              <button
                key={st}
                onClick={() => setStatusFilter(st)}
                style={{
                  padding: "4px 8px",
                  fontSize: 11,
                  fontFamily: "var(--font-mono)",
                  border: "none",
                  borderRight: "1px solid var(--rule)",
                  background: statusFilter === st ? "var(--ink)" : "none",
                  color: statusFilter === st ? "var(--paper)" : "var(--ink-soft)",
                  cursor: "pointer",
                }}
              >
                {st}
              </button>
            ))}
          </div>

          {/* Prev / Next Keyboard Navigation */}
          <div style={{ display: "flex", gap: 4 }}>
            <button
              onClick={handlePrevCase}
              disabled={!hasPrev}
              style={{
                padding: "5px 9px",
                border: "1px solid var(--rule)",
                background: "var(--paper-raised)",
                cursor: hasPrev ? "pointer" : "not-allowed",
                opacity: hasPrev ? 1 : 0.4,
                color: "var(--ink)",
              }}
              title="Previous Case [K]"
            >
              <IconChevronLeft size={12} />
            </button>
            <button
              onClick={handleNextCase}
              disabled={!hasNext}
              style={{
                padding: "5px 9px",
                border: "1px solid var(--rule)",
                background: "var(--paper-raised)",
                cursor: hasNext ? "pointer" : "not-allowed",
                opacity: hasNext ? 1 : 0.4,
                color: "var(--ink)",
              }}
              title="Next Case [J]"
            >
              <IconChevronRight size={12} />
            </button>
          </div>
        </div>
      </div>

      {/* Action Feedback Banner */}
      {actionFeedback && (
        <div
          style={{
            backgroundColor: "var(--paper-raised)",
            border: "1px solid var(--ink)",
            padding: "8px 16px",
            fontSize: 12,
            fontFamily: "var(--font-mono)",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <span>{actionFeedback}</span>
          <button
            onClick={() => setActionFeedback(null)}
            style={{ background: "none", border: "none", cursor: "pointer", fontSize: 13, color: "var(--ink)" }}
          >
            ×
          </button>
        </div>
      )}

      {/* Main Two-Column Layout */}
      <div style={{ display: "grid", gridTemplateColumns: "0.9fr 1.1fr", gap: "var(--space-6)" }}>
        {/* ==================================================================== */}
        {/* LEFT COLUMN: Dual-Threshold Gauge, Fact Ledger, Analyst Action Bar  */}
        {/* ==================================================================== */}
        <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-6)" }}>
          {/* Dual-Threshold Gauge */}
          {renderDualThresholdGauge()}

          {/* Transaction Fact Dossier */}
          {caseData && (
            <div style={{ backgroundColor: "var(--paper-raised)", border: "1px solid var(--rule)", padding: "var(--space-5)" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", borderBottom: "1px solid var(--rule)", paddingBottom: 8, marginBottom: 12 }}>
                <span className="eyebrow">Transaction Fact Dossier</span>
                <span style={{ fontSize: 11, fontFamily: "var(--font-mono)", color: "var(--ink-faint)" }}>
                  TXN: {caseData.txn_id}
                </span>
              </div>

              {/* Form Ledger Table */}
              <div style={{ display: "flex", flexDirection: "column", gap: 10, fontSize: 12.5 }}>
                {/* Amount */}
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
                  <span style={{ color: "var(--ink-soft)" }}>Transaction Amount:</span>
                  <span className="mono-num" style={{ fontSize: 16, fontWeight: 700, color: "var(--ink)" }}>
                    ₹{caseData.amount.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                  </span>
                </div>

                {/* Account ID & Balance */}
                <div style={{ display: "flex", justifyContent: "space-between" }}>
                  <span style={{ color: "var(--ink-soft)" }}>Origin Account:</span>
                  <span className="mono-num" style={{ fontWeight: 600 }}>{caseData.account_id}</span>
                </div>
                {caseData.raw_txn?.oldbalance !== undefined && (
                  <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11.5, color: "var(--ink-soft)" }}>
                    <span>Account Balance:</span>
                    <span className="mono-num">
                      ₹{caseData.raw_txn.oldbalance?.toLocaleString()} &rarr; ₹{caseData.raw_txn.newbalance?.toLocaleString()}
                      {caseData.raw_txn.amount >= 0.95 * caseData.raw_txn.oldbalance && (
                        <span style={{ color: "var(--block)", marginLeft: 6, fontWeight: 600 }}>⚠️ DRAINS 95%+</span>
                      )}
                    </span>
                  </div>
                )}

                {/* Counterparty / Destination */}
                <div style={{ display: "flex", justifyContent: "space-between" }}>
                  <span style={{ color: "var(--ink-soft)" }}>Beneficiary / Merchant:</span>
                  <span className="mono-num">{caseData.merchant_id} ({caseData.merchant_category})</span>
                </div>

                {/* Channel & Region */}
                <div style={{ display: "flex", justifyContent: "space-between" }}>
                  <span style={{ color: "var(--ink-soft)" }}>Channel & State:</span>
                  <span>
                    <strong style={{ textTransform: "uppercase" }}>{caseData.channel}</strong> | {caseData.ip_region || "IN-MH"}
                    {caseData.raw_txn?.region_mismatch === 1 && (
                      <span style={{ color: "var(--block)", marginLeft: 6, fontSize: 11, fontWeight: 600 }}>⚠️ MISMATCH</span>
                    )}
                  </span>
                </div>

                {/* Device */}
                <div style={{ display: "flex", justifyContent: "space-between" }}>
                  <span style={{ color: "var(--ink-soft)" }}>Device Fingerprint:</span>
                  <span className="mono-num">
                    {caseData.device_id || "DEV_WEB"}
                    {caseData.raw_txn?.device_is_new === 1 && (
                      <span style={{ color: "var(--review)", marginLeft: 6, fontSize: 11, fontWeight: 600 }}>⚠️ NEW DEVICE</span>
                    )}
                  </span>
                </div>

                {/* Velocity Features Divider */}
                <div style={{ borderTop: "1px solid var(--rule)", paddingTop: 8, marginTop: 4 }}>
                  <div className="eyebrow" style={{ marginBottom: 6 }}>Online Feature Vectors</div>
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 6, fontSize: 11.5 }}>
                    <div>
                      <span style={{ color: "var(--ink-soft)" }}>1-Hour Volume:</span>{" "}
                      <span className="mono-num">₹{(caseData.raw_txn?.amount_sum_1h || caseData.amount)?.toLocaleString()}</span>
                    </div>
                    <div>
                      <span style={{ color: "var(--ink-soft)" }}>1-Hour Txns:</span>{" "}
                      <span className="mono-num">{caseData.raw_txn?.txn_count_1h || 1}</span>
                    </div>
                    <div>
                      <span style={{ color: "var(--ink-soft)" }}>24-Hour Txns:</span>{" "}
                      <span className="mono-num">{caseData.raw_txn?.txn_count_24h || 1}</span>
                    </div>
                    <div>
                      <span style={{ color: "var(--ink-soft)" }}>7-Day Txns:</span>{" "}
                      <span className="mono-num">{caseData.raw_txn?.txn_count_7d || 3}</span>
                    </div>
                  </div>
                </div>

                {/* Anomaly Sub-Model Scores */}
                <div style={{ borderTop: "1px solid var(--rule)", paddingTop: 8, marginTop: 4 }}>
                  <div className="eyebrow" style={{ marginBottom: 6 }}>Unsupervised Branch Anomaly Scores</div>
                  <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11.5 }}>
                    <div>
                      <span style={{ color: "var(--ink-soft)" }}>Isolation Forest:</span>{" "}
                      <span className="mono-num" style={{ fontWeight: 600 }}>
                        {((caseData.raw_txn?.iso_score ?? caseData.anomaly_score ?? 0.5) * 100).toFixed(1)}%
                      </span>
                    </div>
                    <div>
                      <span style={{ color: "var(--ink-soft)" }}>Autoencoder Loss:</span>{" "}
                      <span className="mono-num" style={{ fontWeight: 600 }}>
                        {((caseData.raw_txn?.ae_error ?? 0.42) * 100).toFixed(1)}%
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Analyst Action Bar & Disposition Persistence */}
          {caseData && (
            <div style={{ backgroundColor: "var(--paper-raised)", border: "1px solid var(--rule)", padding: "var(--space-5)" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
                <span className="eyebrow">Analyst Disposition Action</span>
                <span
                  style={{
                    fontSize: 11,
                    fontFamily: "var(--font-mono)",
                    fontWeight: 600,
                    padding: "2px 6px",
                    border: "1px solid var(--rule)",
                    backgroundColor:
                      caseData.status === "CONFIRMED"
                        ? "rgba(158, 42, 43, 0.15)"
                        : caseData.status === "DISMISSED"
                        ? "rgba(45, 106, 79, 0.15)"
                        : "var(--paper)",
                    color:
                      caseData.status === "CONFIRMED"
                        ? "var(--block)"
                        : caseData.status === "DISMISSED"
                        ? "var(--approve)"
                        : "var(--ink)",
                  }}
                >
                  STATUS: {caseData.status}
                </span>
              </div>

              {/* Action Buttons */}
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "var(--space-2)", marginBottom: 12 }}>
                {/* Confirm Fraud */}
                <button
                  onClick={() => handleDisposition("CONFIRMED")}
                  disabled={isSaving}
                  style={{
                    backgroundColor: "var(--block)",
                    color: "var(--paper)",
                    border: "none",
                    padding: "8px 6px",
                    fontFamily: "var(--font-sans)",
                    fontSize: 11.5,
                    fontWeight: 600,
                    cursor: isSaving ? "wait" : "pointer",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    gap: 4,
                  }}
                >
                  <IconCheck size={12} color="var(--paper)" />
                  Confirm Fraud
                </button>

                {/* Dismiss FP */}
                <button
                  onClick={() => handleDisposition("DISMISSED")}
                  disabled={isSaving}
                  style={{
                    backgroundColor: "var(--approve)",
                    color: "var(--paper)",
                    border: "none",
                    padding: "8px 6px",
                    fontFamily: "var(--font-sans)",
                    fontSize: 11.5,
                    fontWeight: 600,
                    cursor: isSaving ? "wait" : "pointer",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    gap: 4,
                  }}
                >
                  <IconCross size={12} color="var(--paper)" />
                  Dismiss (FP)
                </button>

                {/* Escalate */}
                <button
                  onClick={() => handleDisposition("ESCALATED")}
                  disabled={isSaving}
                  style={{
                    backgroundColor: "var(--review)",
                    color: "var(--paper)",
                    border: "none",
                    padding: "8px 6px",
                    fontFamily: "var(--font-sans)",
                    fontSize: 11.5,
                    fontWeight: 600,
                    cursor: isSaving ? "wait" : "pointer",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    gap: 4,
                  }}
                >
                  <IconShieldAlert size={12} color="var(--paper)" />
                  Escalate Tier 2
                </button>
              </div>

              {/* Analyst Notes Textarea */}
              <div style={{ marginTop: 8 }}>
                <label className="eyebrow" style={{ display: "block", marginBottom: 4 }}>
                  Investigation Notes (SQLite Audit Log):
                </label>
                <textarea
                  value={analystNotes}
                  onChange={(e) => setAnalystNotes(e.target.value)}
                  placeholder="Record investigation findings, customer contact verification, or typology notes..."
                  rows={3}
                  style={{
                    width: "100%",
                    padding: 8,
                    fontFamily: "var(--font-sans)",
                    fontSize: 12,
                    border: "1px solid var(--rule)",
                    backgroundColor: "var(--paper)",
                    color: "var(--ink)",
                    resize: "vertical",
                  }}
                />
                <button
                  onClick={handleSaveNotesOnly}
                  disabled={isSaving}
                  style={{
                    marginTop: 6,
                    padding: "5px 12px",
                    fontFamily: "var(--font-mono)",
                    fontSize: 11,
                    border: "1px solid var(--rule)",
                    background: "var(--paper)",
                    color: "var(--ink)",
                    cursor: "pointer",
                  }}
                >
                  Save Notes Only
                </button>
              </div>
            </div>
          )}
        </div>

        {/* ==================================================================== */}
        {/* RIGHT COLUMN: TreeSHAP Waterfall, Reason Codes, History, Similar     */}
        {/* ==================================================================== */}
        <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-6)" }}>
          {/* Local TreeSHAP Waterfall */}
          <div style={{ backgroundColor: "var(--paper-raised)", border: "1px solid var(--rule)", padding: "var(--space-5)" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 8 }}>
              <span className="eyebrow">Local TreeSHAP Attribution Waterfall</span>
              <span style={{ fontSize: 11, fontFamily: "var(--font-mono)", color: "var(--ink-faint)" }}>
                Log-Odds Space &rarr; Logistic Sigmoid Output
              </span>
            </div>

            {caseData?.waterfall && caseData.waterfall.length > 0 ? (
              <SvgWaterfall
                steps={caseData.waterfall}
                width={560}
                height={260}
                title="Exact Marginal Contribution to Fraud Risk"
                finding="Stepwise attribution shows how transaction scale, isolation anomaly, and velocity nudged prediction past the threshold."
              />
            ) : (
              <div style={{ padding: "var(--space-6)", textAlign: "center", color: "var(--ink-soft)", fontSize: 13 }}>
                Calculating SHAP attribution waterfall coordinates...
              </div>
            )}

            <div className="marginalia" style={{ marginTop: 8 }}>
              Causality Caution: SHAP values explain statistical associations learned by the boosted tree ensemble; they do not represent real-world physical causality.
            </div>
          </div>

          {/* Dynamic Plain-English Reason Codes */}
          <div style={{ backgroundColor: "var(--paper-raised)", border: "1px solid var(--rule)", padding: "var(--space-5)" }}>
            <div className="eyebrow" style={{ marginBottom: 10 }}>Primary Plain-English Decision Drivers</div>
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              {caseData?.top_reasons && caseData.top_reasons.length > 0 ? (
                caseData.top_reasons.map((r: any, idx: number) => (
                  <div
                    key={idx}
                    style={{
                      padding: "8px 12px",
                      backgroundColor: "var(--paper)",
                      border: "1px solid var(--rule)",
                      display: "flex",
                      flexDirection: "column",
                      gap: 3,
                    }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                      <strong style={{ fontSize: 12.5, color: "var(--ink)" }}>{r.headline}</strong>
                      <span
                        style={{
                          fontSize: 10,
                          fontFamily: "var(--font-mono)",
                          padding: "1px 5px",
                          backgroundColor: r.severity === "HIGH" ? "rgba(158, 42, 43, 0.15)" : "rgba(180, 83, 9, 0.15)",
                          color: r.severity === "HIGH" ? "var(--block)" : "var(--review)",
                          fontWeight: 600,
                        }}
                      >
                        {r.severity || "HIGH"}
                      </span>
                    </div>
                    <p style={{ fontSize: 12, color: "var(--ink-soft)", margin: 0, lineHeight: 1.4 }}>
                      {r.description}
                    </p>
                  </div>
                ))
              ) : (
                <div style={{ fontSize: 12, color: "var(--ink-soft)" }}>No high-severity drivers flagged for this transaction.</div>
              )}
            </div>
          </div>

          {/* Account History Timeline Strip (Last 20 Events) */}
          <div style={{ backgroundColor: "var(--paper-raised)", border: "1px solid var(--rule)", padding: "var(--space-5)" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 10 }}>
              <span className="eyebrow">Account Event History (Chronological)</span>
              <span style={{ fontSize: 11, fontFamily: "var(--font-mono)", color: "var(--ink-faint)" }}>
                {caseData?.account_history?.length || 0} Recent Events
              </span>
            </div>

            {caseData?.account_history && caseData.account_history.length > 0 ? (
              <div style={{ display: "flex", flexDirection: "column", gap: 6, maxHeight: 180, overflowY: "auto" }}>
                {caseData.account_history.map((evt: any, idx: number) => (
                  <div
                    key={idx}
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                      fontSize: 11.5,
                      padding: "4px 8px",
                      backgroundColor: evt.txn_id === caseData.txn_id ? "var(--paper)" : "transparent",
                      border: evt.txn_id === caseData.txn_id ? "1px solid var(--ink)" : "none",
                      borderBottom: "1px solid var(--rule)",
                    }}
                  >
                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <span className="mono-num" style={{ color: "var(--ink-faint)", width: 65 }}>
                        {new Date(evt.ts * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                      </span>
                      <span className="mono-num" style={{ fontWeight: 600 }}>{evt.txn_id}</span>
                      <span style={{ color: "var(--ink-soft)" }}>{evt.merchant_id} ({evt.channel})</span>
                    </div>
                    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                      <span className="mono-num">₹{evt.amount.toLocaleString(undefined, { minimumFractionDigits: 2 })}</span>
                      <span
                        style={{
                          fontSize: 10,
                          fontWeight: 600,
                          fontFamily: "var(--font-mono)",
                          color:
                            evt.decision === "BLOCK"
                              ? "var(--block)"
                              : evt.decision === "REVIEW"
                              ? "var(--review)"
                              : "var(--approve)",
                        }}
                      >
                        {evt.decision}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div style={{ fontSize: 12, color: "var(--ink-soft)" }}>
                This is the first observed transaction for account {caseData?.account_id}.
              </div>
            )}
          </div>

          {/* Similar Historical Fraud Cases (Proximity Neighbors) */}
          <div style={{ backgroundColor: "var(--paper-raised)", border: "1px solid var(--rule)", padding: "var(--space-5)" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 10 }}>
              <span className="eyebrow">Nearest Similar Historical Cases</span>
              <span style={{ fontSize: 11, fontFamily: "var(--font-mono)", color: "var(--ink-faint)" }}>
                Cosine Feature Proximity Match
              </span>
            </div>

            {caseData?.similar_cases && caseData.similar_cases.length > 0 ? (
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "var(--space-3)" }}>
                {caseData.similar_cases.map((sim: any, idx: number) => (
                  <div
                    key={idx}
                    style={{
                      padding: 8,
                      backgroundColor: "var(--paper)",
                      border: "1px solid var(--rule)",
                      display: "flex",
                      flexDirection: "column",
                      gap: 4,
                      fontSize: 11,
                    }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between" }}>
                      <span className="mono-num" style={{ fontWeight: 600 }}>{sim.case_id}</span>
                      <span style={{ color: "var(--block)", fontWeight: 600 }}>{(sim.fraud_probability * 100).toFixed(0)}%</span>
                    </div>
                    <div style={{ color: "var(--ink-soft)" }}>
                      ₹{sim.amount.toLocaleString()} ({sim.merchant_category})
                    </div>
                    <div style={{ display: "flex", justifyContent: "space-between", marginTop: 2 }}>
                      <span style={{ textTransform: "uppercase", fontSize: 10 }}>{sim.channel}</span>
                      <span style={{ fontWeight: 600, color: "var(--block)" }}>{sim.status}</span>
                    </div>
                    <button
                      onClick={() => setActiveCaseId(sim.case_id)}
                      style={{
                        marginTop: 4,
                        border: "1px solid var(--rule)",
                        background: "none",
                        padding: "3px 6px",
                        fontSize: 10,
                        fontFamily: "var(--font-mono)",
                        cursor: "pointer",
                        color: "var(--ink)",
                      }}
                    >
                      Inspect Case &rarr;
                    </button>
                  </div>
                ))}
              </div>
            ) : (
              <div style={{ fontSize: 12, color: "var(--ink-soft)" }}>No past confirmed fraud cases matched this feature profile.</div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
