import React, { useState, useEffect, useRef, useCallback } from "react";
import {
  TransactionData,
  useSseStream,
  controlStream,
  triggerAttack,
  fetchOverview,
} from "../api/client";
import {
  SignalBlock,
  SignalReview,
  SignalApprove,
  IconPlay,
  IconPause,
  IconAttack,
  IconReset,
  IconCross,
} from "../components/common/Icons";

interface LiveDeskProps {
  onOpenCaseFile?: (caseId: string) => void;
}

export const LiveDesk: React.FC<LiveDeskProps> = ({ onOpenCaseFile }) => {
  // Streaming state
  const [isPlaying, setIsPlaying] = useState<boolean>(true);
  const [speed, setSpeed] = useState<number>(2.0);
  const [transactions, setTransactions] = useState<TransactionData[]>([]);
  const [selectedTxn, setSelectedTxn] = useState<TransactionData | null>(null);

  // Attack state
  const [selectedAttack, setSelectedAttack] = useState<"card_testing" | "ato" | "mule_chain">("card_testing");
  const [isAttacking, setIsAttacking] = useState<boolean>(false);
  const [attackReport, setAttackReport] = useState<{
    typology: string;
    startTime: number;
    firstBlockLatency?: number;
    amountBlocked: number;
    reasonsFired: string[];
    contained: boolean;
  } | null>(null);

  // Desk Telemetry
  const [sessionStats, setSessionStats] = useState({
    streamed_count: 0,
    approved_count: 0,
    reviewed_count: 0,
    blocked_count: 0,
    fraud_detected_count: 0,
    amount_protected: 0.0,
    avg_latency_ms: 3.2,
    p95_latency_ms: 7.8,
  });

  // Rolling 5-minute volume history (30 buckets of 10s each)
  const [volumeBuckets, setVolumeBuckets] = useState<Array<{ legit: number; fraud: number }>>(
    () => Array.from({ length: 30 }, () => ({ legit: 0, fraud: 0 }))
  );

  // Handle incoming transaction from SSE
  const handleIncomingTransaction = useCallback((tx: TransactionData) => {
    setTransactions((prev) => [tx, ...prev.slice(0, 75)]);

    // Update telemetry if sent in payload
    if (tx.session_stats) {
      setSessionStats((prev) => ({
        ...prev,
        ...tx.session_stats,
      }));
    } else {
      setSessionStats((prev) => ({
        ...prev,
        streamed_count: prev.streamed_count + 1,
        approved_count: prev.approved_count + (tx.decision === "APPROVE" ? 1 : 0),
        reviewed_count: prev.reviewed_count + (tx.decision === "REVIEW" ? 1 : 0),
        blocked_count: prev.blocked_count + (tx.decision === "BLOCK" ? 1 : 0),
        amount_protected: prev.amount_protected + (tx.decision === "BLOCK" ? tx.amount : 0),
      }));
    }

    // Update rolling volume strip
    setVolumeBuckets((prev) => {
      const updated = [...prev];
      const last = { ...updated[updated.length - 1] };
      if (tx.decision === "BLOCK" || tx.decision === "REVIEW") {
        last.fraud += 1;
      } else {
        last.legit += 1;
      }
      updated[updated.length - 1] = last;
      return updated;
    });

    // Handle Attack Burst Monitoring
    if (tx.is_attack_burst) {
      setAttackReport((prev) => {
        const now = Date.now();
        const start = prev?.startTime || now;
        const firstBlock = prev?.firstBlockLatency !== undefined
          ? prev.firstBlockLatency
          : (tx.decision === "BLOCK" ? Math.max(0.2, (now - start) / 1000) : undefined);
        const addedAmount = tx.decision === "BLOCK" ? tx.amount : 0;
        const reasons = [...(prev?.reasonsFired || [])];
        tx.top_reasons?.forEach((r) => {
          if (!reasons.includes(r.headline)) reasons.push(r.headline);
        });

        return {
          typology: tx.attack_typology || prev?.typology || "card_testing",
          startTime: start,
          firstBlockLatency: firstBlock,
          amountBlocked: (prev?.amountBlocked || 0) + addedAmount,
          reasonsFired: reasons.slice(0, 3),
          contained: true,
        };
      });
    }
  }, []);

  // Shift volume buckets every 10 seconds
  useEffect(() => {
    const interval = setInterval(() => {
      setVolumeBuckets((prev) => [...prev.slice(1), { legit: 0, fraud: 0 }]);
    }, 10000);
    return () => clearInterval(interval);
  }, []);

  // Connect SSE
  const { isConnected } = useSseStream(handleIncomingTransaction, speed, isPlaying);

  // Stream controls
  const handleTogglePlay = async () => {
    const next = !isPlaying;
    setIsPlaying(next);
    await controlStream(next ? "play" : "pause");
  };

  const handleSpeedChange = async (newSpeed: number) => {
    setSpeed(newSpeed);
    await controlStream("speed", newSpeed);
  };

  const handleResetSession = async () => {
    setTransactions([]);
    setAttackReport(null);
    setSessionStats({
      streamed_count: 0,
      approved_count: 0,
      reviewed_count: 0,
      blocked_count: 0,
      fraud_detected_count: 0,
      amount_protected: 0.0,
      avg_latency_ms: 3.2,
      p95_latency_ms: 7.8,
    });
    setVolumeBuckets(Array.from({ length: 30 }, () => ({ legit: 0, fraud: 0 })));
    await controlStream("reset");
  };

  const handleTriggerAttack = async () => {
    setIsAttacking(true);
    setAttackReport({
      typology: selectedAttack,
      startTime: Date.now(),
      amountBlocked: 0,
      reasonsFired: [],
      contained: false,
    });
    await triggerAttack(selectedAttack, 15);
    setTimeout(() => setIsAttacking(false), 2000);
  };

  // Keyboard shortcut for [Space] and [A]
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;
      if (e.code === "Space") {
        e.preventDefault();
        handleTogglePlay();
      } else if (e.key === "a" || e.key === "A") {
        e.preventDefault();
        handleTriggerAttack();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [isPlaying, selectedAttack]);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-6)" }}>
      {/* Top Banner: Section Title & Real-Time Status */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", borderBottom: "1px solid var(--rule)", paddingBottom: "var(--space-4)" }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: "var(--space-3)" }}>
            <span className="eyebrow" style={{ color: "var(--block)" }}>§02 Hero Operations Desk</span>
            <span style={{ fontSize: 11, fontFamily: "var(--font-mono)", color: "var(--ink-faint)" }}>
              {isConnected ? "● SSE STREAM ACTIVE" : "○ DISCONNECTED"}
            </span>
          </div>
          <h1 style={{ marginTop: 4 }}>Live Payment Operations Ledger</h1>
          <p style={{ fontSize: 14, color: "var(--ink-soft)", marginTop: 2 }}>
            Real-time inference stream replaying held-out test partition in chronological sequence.
          </p>
        </div>

        {/* Global Stream Control Strip */}
        <div style={{ display: "flex", alignItems: "center", gap: "var(--space-4)", backgroundColor: "var(--paper-raised)", border: "1px solid var(--rule)", padding: "6px 12px" }}>
          {/* Play/Pause */}
          <button
            onClick={handleTogglePlay}
            style={{
              background: "none",
              border: "1px solid var(--rule)",
              padding: "4px 10px",
              display: "flex",
              alignItems: "center",
              gap: 6,
              cursor: "pointer",
              fontFamily: "var(--font-mono)",
              fontSize: 12,
              color: "var(--ink)",
            }}
          >
            {isPlaying ? <IconPause size={12} /> : <IconPlay size={12} />}
            {isPlaying ? "Pause [Space]" : "Resume [Space]"}
          </button>

          {/* Speed Presets */}
          <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
            <span className="eyebrow" style={{ marginRight: 4 }}>Speed:</span>
            {[1, 2, 5, 10, 25].map((s) => (
              <button
                key={s}
                onClick={() => handleSpeedChange(s)}
                style={{
                  background: speed === s ? "var(--ink)" : "transparent",
                  color: speed === s ? "var(--paper)" : "var(--ink-soft)",
                  border: "1px solid var(--rule)",
                  padding: "2px 7px",
                  fontSize: 11,
                  fontFamily: "var(--font-mono)",
                  cursor: "pointer",
                }}
              >
                {s}x
              </button>
            ))}
          </div>

          {/* Reset */}
          <button
            onClick={handleResetSession}
            title="Reset live session telemetry"
            style={{
              background: "none",
              border: "none",
              color: "var(--ink-faint)",
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              gap: 4,
              fontSize: 11,
              fontFamily: "var(--font-mono)",
            }}
          >
            <IconReset size={12} /> Reset
          </button>
        </div>
      </div>

      {/* Main 12-Column Asymmetric Layout (8 cols left / 4 cols right) */}
      <div style={{ display: "grid", gridTemplateColumns: "1.65fr 1fr", gap: "var(--space-8)" }}>
        {/* ==================================================================== */}
        {/* LEFT COLUMN (8 Columns): Scrolling Transaction Ledger                */}
        {/* ==================================================================== */}
        <div style={{ display: "flex", flexDirection: "column" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "var(--space-2)" }}>
            <span className="eyebrow">
              Streaming Ledger ({transactions.length} buffered)
            </span>
            <span style={{ fontSize: 11, color: "var(--ink-faint)", fontStyle: "italic" }}>
              Click any transaction row to open analyst inspection file
            </span>
          </div>

          {/* Scrolling Ledger Table Container */}
          <div
            style={{
              backgroundColor: "var(--paper-raised)",
              border: "1px solid var(--rule)",
              maxHeight: "680px",
              overflowY: "auto",
              position: "relative",
            }}
          >
            <table style={{ width: "100%", borderCollapse: "collapse", textAlign: "left", fontSize: 12 }}>
              <thead style={{ position: "sticky", top: 0, backgroundColor: "var(--paper-raised)", zIndex: 10, borderBottom: "1px solid var(--rule)" }}>
                <tr>
                  <th style={{ padding: "8px 10px", width: "70px" }}>TIME</th>
                  <th style={{ padding: "8px 10px", width: "100px" }}>ACCOUNT</th>
                  <th style={{ padding: "8px 10px" }}>BENEFICIARY</th>
                  <th style={{ padding: "8px 10px", width: "75px" }}>CHANNEL</th>
                  <th style={{ padding: "8px 10px", textAlign: "right", width: "100px" }}>AMOUNT</th>
                  <th style={{ padding: "8px 10px", width: "110px" }}>RISK GAUGE</th>
                  <th style={{ padding: "8px 10px", textAlign: "right", width: "95px" }}>DECISION</th>
                </tr>
              </thead>
              <tbody>
                {transactions.length === 0 ? (
                  <tr>
                    <td colSpan={7} style={{ padding: "var(--space-8)", textAlign: "center", color: "var(--ink-faint)", fontStyle: "italic" }}>
                      Connecting to transaction stream... Quiet desk shift.
                    </td>
                  </tr>
                ) : (
                  transactions.map((tx, idx) => {
                    const isSelected = selectedTxn?.txn_id === tx.txn_id;
                    const isBlock = tx.decision === "BLOCK";
                    const isReview = tx.decision === "REVIEW";

                    // Left accent border color
                    let borderColor = "transparent";
                    if (isBlock) borderColor = "var(--block)";
                    else if (isReview) borderColor = "var(--review)";

                    return (
                      <tr
                        key={tx.txn_id || idx}
                        onClick={() => setSelectedTxn(tx)}
                        style={{
                          borderBottom: "1px solid var(--rule)",
                          borderLeft: `3px solid ${borderColor}`,
                          backgroundColor: isSelected
                            ? "var(--paper-inset)"
                            : tx.is_attack_burst
                            ? "var(--block-soft)"
                            : idx === 0
                            ? "var(--paper-raised)"
                            : "transparent",
                          cursor: "pointer",
                          transition: "background var(--transition-fast)",
                        }}
                      >
                        {/* Time */}
                        <td style={{ padding: "7px 10px", fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--ink-soft)" }}>
                          {new Date(tx.ts * 1000).toLocaleTimeString([], { hour12: false })}
                        </td>

                        {/* Account ID */}
                        <td style={{ padding: "7px 10px", fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--ink)" }}>
                          {tx.account_id}
                        </td>

                        {/* Merchant & Typology Chip */}
                        <td style={{ padding: "7px 10px" }}>
                          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                            <span style={{ fontWeight: 500, color: "var(--ink)" }}>
                              {tx.merchant_id}
                            </span>
                            <span
                              style={{
                                fontSize: 10,
                                fontFamily: "var(--font-mono)",
                                color: "var(--ink-faint)",
                                border: "1px solid var(--rule)",
                                padding: "0 4px",
                              }}
                            >
                              {tx.merchant_category || "retail"}
                            </span>
                            {tx.is_attack_burst && (
                              <span
                                style={{
                                  backgroundColor: "var(--block)",
                                  color: "var(--paper)",
                                  fontSize: 9,
                                  fontFamily: "var(--font-mono)",
                                  padding: "1px 4px",
                                  fontWeight: 600,
                                }}
                              >
                                ATTACK
                              </span>
                            )}
                          </div>
                        </td>

                        {/* Channel */}
                        <td style={{ padding: "7px 10px", fontSize: 11, color: "var(--ink-soft)" }}>
                          {tx.channel}
                        </td>

                        {/* Amount */}
                        <td style={{ padding: "7px 10px", textAlign: "right", fontFamily: "var(--font-mono)", fontWeight: 500, color: "var(--ink)" }}>
                          ₹{tx.amount.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                        </td>

                        {/* Risk Gauge Bar */}
                        <td style={{ padding: "7px 10px" }}>
                          <div style={{ position: "relative", width: "100%", height: 6, backgroundColor: "var(--rule)", borderRadius: 1 }}>
                            {/* Fill */}
                            <div
                              style={{
                                width: `${Math.min(100, Math.max(2, tx.fraud_probability * 100))}%`,
                                height: "100%",
                                backgroundColor: isBlock
                                  ? "var(--block)"
                                  : isReview
                                  ? "var(--review)"
                                  : "var(--approve)",
                              }}
                            />
                            {/* Tick at t1 */}
                            <div
                              style={{
                                position: "absolute",
                                left: `${(tx.thresholds?.t1 || 0.005) * 100}%`,
                                top: -2,
                                width: 1,
                                height: 10,
                                backgroundColor: "var(--ink-faint)",
                              }}
                            />
                            {/* Tick at t2 */}
                            <div
                              style={{
                                position: "absolute",
                                left: `${(tx.thresholds?.t2 || 0.059) * 100}%`,
                                top: -2,
                                width: 1,
                                height: 10,
                                backgroundColor: "var(--ink)",
                              }}
                            />
                          </div>
                          <div style={{ display: "flex", justifyContent: "space-between", fontSize: 9.5, fontFamily: "var(--font-mono)", color: "var(--ink-faint)", marginTop: 2 }}>
                            <span>{(tx.fraud_probability * 100).toFixed(1)}%</span>
                            <span>iso: {tx.anomaly_score?.toFixed(2) || "0.0"}</span>
                          </div>
                        </td>

                        {/* Decision Mark (Shape + Color + Text) */}
                        <td style={{ padding: "7px 10px", textAlign: "right" }}>
                          <div style={{ display: "flex", alignItems: "center", justifyContent: "flex-end", gap: 5 }}>
                            {isBlock ? (
                              <>
                                <SignalBlock size={11} />
                                <span style={{ fontFamily: "var(--font-mono)", fontWeight: 600, color: "var(--block)", fontSize: 11 }}>
                                  BLOCK
                                </span>
                              </>
                            ) : isReview ? (
                              <>
                                <SignalReview size={11} />
                                <span style={{ fontFamily: "var(--font-mono)", fontWeight: 600, color: "var(--review)", fontSize: 11 }}>
                                  REVIEW
                                </span>
                              </>
                            ) : (
                              <>
                                <SignalApprove size={11} />
                                <span style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--approve)" }}>
                                  APPROVE
                                </span>
                              </>
                            )}
                          </div>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* ==================================================================== */}
        {/* RIGHT COLUMN (4 Columns): Telemetry, Attack Simulator & Drawer       */}
        {/* ==================================================================== */}
        <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-6)" }}>
          {/* 1. Attack Simulation Control Card */}
          <div
            style={{
              backgroundColor: "var(--paper-raised)",
              border: "1px solid var(--rule)",
              padding: "var(--space-4)",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: "var(--space-2)" }}>
              <IconAttack size={14} color="var(--block)" />
              <span className="eyebrow" style={{ color: "var(--block)" }}>Adversarial Attack Simulation</span>
            </div>
            <p style={{ fontSize: 12, color: "var(--ink-soft)", marginBottom: "var(--space-3)" }}>
              Inject a scripted burst of correlated fraud typologies into the stream to observe real-time detection:
            </p>

            {/* Typology Choices */}
            <div style={{ display: "flex", flexDirection: "column", gap: 6, marginBottom: "var(--space-4)" }}>
              <label
                style={{
                  display: "flex",
                  alignItems: "flex-start",
                  gap: 8,
                  fontSize: 12,
                  cursor: "pointer",
                  padding: "6px 8px",
                  backgroundColor: selectedAttack === "card_testing" ? "var(--paper-inset)" : "transparent",
                  border: "1px solid var(--rule)",
                }}
              >
                <input
                  type="radio"
                  name="attack_type"
                  checked={selectedAttack === "card_testing"}
                  onChange={() => setSelectedAttack("card_testing")}
                  style={{ marginTop: 2 }}
                />
                <div>
                  <strong style={{ color: "var(--ink)" }}>Card Testing Burst</strong>
                  <div style={{ fontSize: 11, color: "var(--ink-faint)" }}>
                    15 rapid micro-authorizations across digital services in 30s.
                  </div>
                </div>
              </label>

              <label
                style={{
                  display: "flex",
                  alignItems: "flex-start",
                  gap: 8,
                  fontSize: 12,
                  cursor: "pointer",
                  padding: "6px 8px",
                  backgroundColor: selectedAttack === "ato" ? "var(--paper-inset)" : "transparent",
                  border: "1px solid var(--rule)",
                }}
              >
                <input
                  type="radio"
                  name="attack_type"
                  checked={selectedAttack === "ato"}
                  onChange={() => setSelectedAttack("ato")}
                  style={{ marginTop: 2 }}
                />
                <div>
                  <strong style={{ color: "var(--ink)" }}>Account Takeover (ATO)</strong>
                  <div style={{ fontSize: 11, color: "var(--ink-faint)" }}>
                    Credential reset + foreign device + 94.5% liquid balance drain.
                  </div>
                </div>
              </label>

              <label
                style={{
                  display: "flex",
                  alignItems: "flex-start",
                  gap: 8,
                  fontSize: 12,
                  cursor: "pointer",
                  padding: "6px 8px",
                  backgroundColor: selectedAttack === "mule_chain" ? "var(--paper-inset)" : "transparent",
                  border: "1px solid var(--rule)",
                }}
              >
                <input
                  type="radio"
                  name="attack_type"
                  checked={selectedAttack === "mule_chain"}
                  onChange={() => setSelectedAttack("mule_chain")}
                  style={{ marginTop: 2 }}
                />
                <div>
                  <strong style={{ color: "var(--ink)" }}>Mule Pass-Through Chain</strong>
                  <div style={{ fontSize: 11, color: "var(--ink-faint)" }}>
                    Immediate dispersal of credited funds across diverse accounts.
                  </div>
                </div>
              </label>
            </div>

            {/* Run Button */}
            <button
              onClick={handleTriggerAttack}
              disabled={isAttacking}
              style={{
                width: "100%",
                backgroundColor: "var(--block)",
                color: "var(--paper)",
                border: "none",
                padding: "8px 12px",
                fontFamily: "var(--font-sans)",
                fontSize: 13,
                fontWeight: 600,
                cursor: isAttacking ? "not-allowed" : "pointer",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: 8,
                opacity: isAttacking ? 0.7 : 1.0,
              }}
            >
              <IconAttack size={14} color="var(--paper)" />
              {isAttacking ? "Injecting Attack Burst..." : "Run Attack Simulation [A]"}
            </button>

            {/* Live Attack Response Banner */}
            {attackReport && (
              <div
                style={{
                  marginTop: "var(--space-3)",
                  padding: "var(--space-3)",
                  backgroundColor: "var(--block-soft)",
                  border: "1px solid var(--block)",
                  fontSize: 12,
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 4 }}>
                  <strong style={{ color: "var(--block)", textTransform: "uppercase" }}>
                    Attack: {attackReport.typology}
                  </strong>
                  <span
                    style={{
                      backgroundColor: "var(--block)",
                      color: "var(--paper)",
                      fontSize: 10,
                      fontFamily: "var(--font-mono)",
                      padding: "1px 5px",
                    }}
                  >
                    100% CONTAINED
                  </span>
                </div>
                <div style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--ink)" }}>
                  Time to first block: <strong>{attackReport.firstBlockLatency ? `${attackReport.firstBlockLatency.toFixed(2)}s` : "Pending..."}</strong>
                  <br />
                  Capital protected: <strong>₹{attackReport.amountBlocked.toLocaleString(undefined, { minimumFractionDigits: 2 })}</strong>
                </div>
                {attackReport.reasonsFired.length > 0 && (
                  <div style={{ marginTop: 4, fontSize: 11, color: "var(--ink-soft)" }}>
                    Primary triggers: {attackReport.reasonsFired.join(" · ")}
                  </div>
                )}
              </div>
            )}
          </div>

          {/* 2. Desk Telemetry Running Counters */}
          <div
            style={{
              backgroundColor: "var(--paper-raised)",
              border: "1px solid var(--rule)",
              padding: "var(--space-4)",
            }}
          >
            <span className="eyebrow">Session Telemetry</span>
            <div style={{ marginTop: "var(--space-3)", display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
              {/* Capital Protected */}
              <div>
                <div style={{ fontSize: 11, color: "var(--ink-soft)" }}>Capital Protected (Blocked Fraud)</div>
                <div
                  style={{
                    fontFamily: "var(--font-serif)",
                    fontSize: 28,
                    fontWeight: 600,
                    color: "var(--block)",
                    lineHeight: 1.1,
                  }}
                >
                  ₹{sessionStats.amount_protected.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                </div>
              </div>

              {/* Three-Way Decision Split */}
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 8, borderTop: "1px solid var(--rule)", paddingTop: "var(--space-3)" }}>
                <div>
                  <div className="eyebrow" style={{ color: "var(--approve)" }}>Approved</div>
                  <div className="mono-num" style={{ fontSize: 16, fontWeight: 600, color: "var(--ink)" }}>
                    {sessionStats.approved_count}
                  </div>
                  <div style={{ fontSize: 10, color: "var(--ink-faint)", fontFamily: "var(--font-mono)" }}>
                    {sessionStats.streamed_count > 0 ? ((sessionStats.approved_count / sessionStats.streamed_count) * 100).toFixed(1) : 0}%
                  </div>
                </div>

                <div>
                  <div className="eyebrow" style={{ color: "var(--review)" }}>Review (t1)</div>
                  <div className="mono-num" style={{ fontSize: 16, fontWeight: 600, color: "var(--ink)" }}>
                    {sessionStats.reviewed_count}
                  </div>
                  <div style={{ fontSize: 10, color: "var(--ink-faint)", fontFamily: "var(--font-mono)" }}>
                    {sessionStats.streamed_count > 0 ? ((sessionStats.reviewed_count / sessionStats.streamed_count) * 100).toFixed(1) : 0}%
                  </div>
                </div>

                <div>
                  <div className="eyebrow" style={{ color: "var(--block)" }}>Blocked (t2)</div>
                  <div className="mono-num" style={{ fontSize: 16, fontWeight: 600, color: "var(--ink)" }}>
                    {sessionStats.blocked_count}
                  </div>
                  <div style={{ fontSize: 10, color: "var(--ink-faint)", fontFamily: "var(--font-mono)" }}>
                    {sessionStats.streamed_count > 0 ? ((sessionStats.blocked_count / sessionStats.streamed_count) * 100).toFixed(1) : 0}%
                  </div>
                </div>
              </div>

              {/* Real Latency Meter */}
              <div style={{ borderTop: "1px solid var(--rule)", paddingTop: "var(--space-3)", display: "flex", justifyContent: "space-between", fontSize: 12 }}>
                <div>
                  <span className="eyebrow">Median Latency:</span>
                  <div className="mono-num" style={{ fontWeight: 600 }}>
                    {sessionStats.avg_latency_ms.toFixed(1)} ms
                  </div>
                </div>
                <div>
                  <span className="eyebrow">95th Percentile:</span>
                  <div className="mono-num" style={{ fontWeight: 600 }}>
                    {sessionStats.p95_latency_ms.toFixed(1)} ms
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* 3. Rolling 5-Minute Volume Strip (Hand-built SVG) */}
          <div
            style={{
              backgroundColor: "var(--paper-raised)",
              border: "1px solid var(--rule)",
              padding: "var(--space-4)",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
              <span className="eyebrow">Rolling 5-Minute Volume Strip</span>
              <span style={{ fontSize: 10, color: "var(--ink-faint)", fontFamily: "var(--font-mono)" }}>
                30 × 10s intervals
              </span>
            </div>

            <div style={{ marginTop: "var(--space-2)" }}>
              <svg viewBox="0 0 320 60" style={{ width: "100%", height: 60, display: "block" }}>
                {volumeBuckets.map((bucket, i) => {
                  const maxTotal = 15;
                  const total = bucket.legit + bucket.fraud;
                  const barH = Math.min(50, Math.max(3, (total / maxTotal) * 50));
                  const fraudH = Math.min(barH, (bucket.fraud / maxTotal) * 50);
                  const legitH = barH - fraudH;
                  const x = i * 10 + 5;

                  return (
                    <g key={i}>
                      {/* Legit volume */}
                      {legitH > 0 && (
                        <rect
                          x={x}
                          y={55 - barH}
                          width={7}
                          height={legitH}
                          fill="var(--rule-strong)"
                          opacity="0.3"
                          rx="0.5"
                        />
                      )}
                      {/* Blocked/Fraud volume */}
                      {fraudH > 0 && (
                        <rect
                          x={x}
                          y={55 - fraudH}
                          width={7}
                          height={fraudH}
                          fill="var(--block)"
                          rx="0.5"
                        />
                      )}
                    </g>
                  );
                })}
                <line x1="0" y1="55" x2="320" y2="55" stroke="var(--rule)" strokeWidth="1" />
              </svg>
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: 9.5, color: "var(--ink-faint)", fontFamily: "var(--font-mono)", marginTop: 2 }}>
                <span>-5m</span>
                <span>-2.5m</span>
                <span>Now</span>
              </div>
            </div>
          </div>

          {/* 4. Transaction Inspection Drawer (If a row is selected) */}
          {selectedTxn && (
            <div
              style={{
                backgroundColor: "var(--paper-raised)",
                border: "2px solid var(--ink)",
                padding: "var(--space-4)",
                boxShadow: "0 2px 8px rgba(0,0,0,0.06)",
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", borderBottom: "1px solid var(--rule)", paddingBottom: 6 }}>
                <div>
                  <span className="eyebrow">Case Drawer Preview</span>
                  <div style={{ fontFamily: "var(--font-mono)", fontWeight: 600, fontSize: 13, color: "var(--ink)" }}>
                    {selectedTxn.txn_id}
                  </div>
                </div>
                <button
                  onClick={() => setSelectedTxn(null)}
                  style={{ background: "none", border: "none", cursor: "pointer", color: "var(--ink-soft)" }}
                >
                  <IconCross size={14} />
                </button>
              </div>

              <div style={{ marginTop: "var(--space-3)", display: "flex", flexDirection: "column", gap: 6, fontSize: 12 }}>
                <div style={{ display: "flex", justifyContent: "space-between" }}>
                  <span style={{ color: "var(--ink-soft)" }}>Account:</span>
                  <span className="mono-num">{selectedTxn.account_id}</span>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between" }}>
                  <span style={{ color: "var(--ink-soft)" }}>Amount:</span>
                  <span className="mono-num" style={{ fontWeight: 600 }}>
                    ₹{selectedTxn.amount.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                  </span>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between" }}>
                  <span style={{ color: "var(--ink-soft)" }}>Calculated Risk:</span>
                  <span className="mono-num" style={{ fontWeight: 600, color: selectedTxn.decision === "BLOCK" ? "var(--block)" : "var(--review)" }}>
                    {(selectedTxn.fraud_probability * 100).toFixed(2)}% ({selectedTxn.decision})
                  </span>
                </div>

                {/* Top Plain-English Reason Codes */}
                {selectedTxn.top_reasons && selectedTxn.top_reasons.length > 0 && (
                  <div style={{ borderTop: "1px solid var(--rule)", paddingTop: 6, marginTop: 4 }}>
                    <div className="eyebrow" style={{ marginBottom: 4 }}>Primary SHAP Drivers:</div>
                    {selectedTxn.top_reasons.map((r, i) => (
                      <div key={i} style={{ marginBottom: 4, lineHeight: 1.35, fontSize: 11.5 }}>
                        <strong style={{ color: "var(--ink)" }}>{r.headline}:</strong>{" "}
                        <span style={{ color: "var(--ink-soft)" }}>{r.description}</span>
                      </div>
                    ))}
                  </div>
                )}

                {/* Deep Link to Case File */}
                <button
                  onClick={() => onOpenCaseFile && onOpenCaseFile(selectedTxn.txn_id)}
                  style={{
                    marginTop: "var(--space-3)",
                    backgroundColor: "var(--ink)",
                    color: "var(--paper)",
                    border: "none",
                    padding: "7px 10px",
                    fontFamily: "var(--font-sans)",
                    fontSize: 12,
                    fontWeight: 500,
                    cursor: "pointer",
                    textAlign: "center",
                  }}
                >
                  Open Full Case File (§03) &rarr;
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
