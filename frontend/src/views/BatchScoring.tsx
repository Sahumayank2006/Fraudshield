import React, { useState, useRef } from "react";
import {
  uploadBatchCsv,
  BATCH_SAMPLE_CSV_URL,
  BATCH_DOWNLOAD_FLAGGED_URL,
} from "../api/client";
import {
  SignalBlock,
  SignalReview,
  SignalApprove,
  IconDownload,
  IconCheck,
  IconCross,
  IconShieldAlert,
  IconPlay,
} from "../components/common/Icons";

interface FlaggedRow {
  txn_id: string;
  account_id: string;
  amount: number;
  channel: string;
  fraud_probability: number;
  decision: "REVIEW" | "BLOCK";
  reason?: string;
}

interface BatchResult {
  total_transactions: number;
  approved_count: number;
  review_count: number;
  blocked_count: number;
  flagged_rate_pct: number;
  estimated_loss_prevented: number;
  processing_time_ms: number;
  flagged_preview: FlaggedRow[];
}

export const BatchScoring: React.FC = () => {
  const [dragActive, setDragActive] = useState<boolean>(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isProcessing, setIsProcessing] = useState<boolean>(false);
  const [batchResult, setBatchResult] = useState<BatchResult | null>(null);
  const [validationError, setValidationError] = useState<any>(null);
  const [filterDecision, setFilterDecision] = useState<string>("ALL");
  const [searchQuery, setSearchQuery] = useState<string>("");
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFileSelection(e.dataTransfer.files[0]);
    }
  };

  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      handleFileSelection(e.target.files[0]);
    }
  };

  const handleFileSelection = (file: File) => {
    setValidationError(null);
    setBatchResult(null);

    if (!file.name.toLowerCase().endsWith(".csv")) {
      setValidationError({
        message: "Unsupported file type. Please upload a standard comma-separated (.csv) file.",
        filename: file.name,
      });
      setSelectedFile(null);
      return;
    }

    if (file.size > 25 * 1024 * 1024) {
      setValidationError({
        message: "File exceeds 25 MB maximum batch upload payload limit.",
        filename: file.name,
      });
      setSelectedFile(null);
      return;
    }

    setSelectedFile(file);
  };

  const processBatch = async () => {
    if (!selectedFile) return;

    setIsProcessing(true);
    setValidationError(null);

    try {
      const result: BatchResult = await uploadBatchCsv(selectedFile);
      setBatchResult(result);
    } catch (err: any) {
      console.error("Batch scoring failed:", err);
      if (err && err.detail) {
        setValidationError(typeof err.detail === "object" ? err.detail : { message: String(err.detail) });
      } else {
        setValidationError({ message: "An unexpected error occurred during batch inference execution." });
      }
    } finally {
      setIsProcessing(false);
    }
  };

  const resetBatch = () => {
    setSelectedFile(null);
    setBatchResult(null);
    setValidationError(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  const flaggedList = batchResult?.flagged_preview || [];
  const filteredFlagged = flaggedList.filter((row) => {
    const matchesDecision = filterDecision === "ALL" || row.decision === filterDecision;
    const matchesSearch =
      searchQuery.trim() === "" ||
      row.txn_id.toLowerCase().includes(searchQuery.toLowerCase()) ||
      row.account_id.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (row.reason && row.reason.toLowerCase().includes(searchQuery.toLowerCase()));
    return matchesDecision && matchesSearch;
  });

  return (
    <div className="section-container" style={{ paddingBottom: "var(--space-8)" }}>
      {/* Editorial Header */}
      <div style={{ marginBottom: "var(--space-6)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
          <span className="eyebrow" style={{ color: "var(--ink-soft)" }}>§09 Batch Scoring Engine</span>
          <span className="pill" style={{ backgroundColor: "var(--paper-raised)", border: "1px solid var(--rule)" }}>
            High-Throughput Offline Inference
          </span>
        </div>
        <h1 style={{ fontFamily: "var(--font-serif)", fontSize: 28, margin: "4px 0 8px 0", letterSpacing: "-0.01em" }}>
          Batch File Scoring & Schema Verification
        </h1>
        <p style={{ fontSize: 14, color: "var(--ink-soft)", maxWidth: 960, lineHeight: 1.55 }}>
          Process offline transaction ledgers with strict future-leakage-safe feature extraction, isotonic probability
          calibration, and operational dual-threshold routing. Upload any structured CSV or download the pre-generated
          simulator benchmark file to audit high-risk exposures.
        </p>
      </div>

      {/* Upload Zone & Quick Sample Downloader */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "2fr 1fr",
          gap: "var(--space-4)",
          marginBottom: "var(--space-6)",
        }}
      >
        {/* Drag and Drop Box */}
        <div
          onDragEnter={handleDrag}
          onDragOver={handleDrag}
          onDragLeave={handleDrag}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
          style={{
            backgroundColor: dragActive ? "rgba(31, 94, 61, 0.05)" : "var(--paper-raised)",
            border: `2px dashed ${dragActive ? "var(--accent)" : "var(--rule)"}`,
            padding: "28px 24px",
            textAlign: "center",
            cursor: "pointer",
            transition: "all 0.15s ease-in-out",
            position: "relative",
          }}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept=".csv"
            style={{ display: "none" }}
            onChange={handleFileInputChange}
          />
          <div style={{ display: "inline-flex", padding: 10, backgroundColor: "var(--paper)", border: "1px solid var(--rule)", marginBottom: 12 }}>
            <IconDownload size={22} color="var(--ink)" />
          </div>

          <div style={{ fontFamily: "var(--font-serif)", fontSize: 18, color: "var(--ink)", marginBottom: 4 }}>
            {selectedFile ? selectedFile.name : "Drag & Drop Transaction CSV Here"}
          </div>
          <div style={{ fontSize: 12, color: "var(--ink-soft)", maxWidth: 440, margin: "0 auto" }}>
            {selectedFile
              ? `${(selectedFile.size / 1024).toFixed(1)} KB — Ready for high-throughput batch evaluation`
              : "Or click to browse your local filesystem. Required columns: account_id, amount. Optional: txn_id, channel, ts, merchant_id."}
          </div>

          {selectedFile && (
            <div style={{ marginTop: 16, display: "flex", justifyContent: "center", gap: 12 }}>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  processBatch();
                }}
                disabled={isProcessing}
                style={{
                  backgroundColor: "var(--ink)",
                  color: "var(--paper)",
                  border: "none",
                  padding: "8px 18px",
                  fontFamily: "var(--font-mono)",
                  fontSize: 12,
                  fontWeight: 600,
                  cursor: isProcessing ? "not-allowed" : "pointer",
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                }}
              >
                <IconPlay size={12} color="var(--paper)" />
                {isProcessing ? "Executing Model Inference..." : "Run Batch Scoring"}
              </button>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  resetBatch();
                }}
                disabled={isProcessing}
                style={{
                  backgroundColor: "transparent",
                  color: "var(--ink-soft)",
                  border: "1px solid var(--rule)",
                  padding: "8px 14px",
                  fontFamily: "var(--font-mono)",
                  fontSize: 12,
                  cursor: "pointer",
                }}
              >
                Clear
              </button>
            </div>
          )}
        </div>

        {/* Sample Dataset & Format Card */}
        <div style={{ backgroundColor: "var(--paper-raised)", border: "1px solid var(--rule)", padding: "20px", display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
          <div>
            <span className="eyebrow" style={{ color: "var(--ink-faint)" }}>Testing Utility</span>
            <h3 style={{ margin: "4px 0 8px 0", fontSize: 16, fontFamily: "var(--font-serif)" }}>
              Simulator Sample CSV
            </h3>
            <p style={{ fontSize: 12, color: "var(--ink-soft)", lineHeight: 1.5, margin: "0 0 12px 0" }}>
              Download a 60-transaction realistic test ledger generated directly from the LedgerSim simulator with
              clean transactions and structured attack vectors.
            </p>
            <div style={{ fontSize: 11, fontFamily: "var(--font-mono)", color: "var(--ink-faint)", backgroundColor: "var(--paper)", padding: "8px", border: "1px solid var(--rule-light)", marginBottom: 12 }}>
              Columns: account_id, amount, channel, merchant_id, ts, ip_region, device_id
            </div>
          </div>

          <a
            href={BATCH_SAMPLE_CSV_URL}
            download="fraudshield_sample_transactions.csv"
            style={{
              textDecoration: "none",
              backgroundColor: "var(--paper)",
              color: "var(--ink)",
              border: "1px solid var(--ink)",
              padding: "8px 14px",
              fontFamily: "var(--font-mono)",
              fontSize: 12,
              fontWeight: 600,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: 8,
              cursor: "pointer",
            }}
          >
            <IconDownload size={14} color="var(--ink)" />
            Download Sample CSV
          </a>
        </div>
      </div>

      {/* Friendly Validation Error Report Banner */}
      {validationError && (
        <div
          style={{
            backgroundColor: "rgba(184, 51, 42, 0.08)",
            border: "1px solid var(--block)",
            padding: "16px 20px",
            marginBottom: "var(--space-6)",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
            <IconShieldAlert size={16} color="var(--block)" />
            <span style={{ fontFamily: "var(--font-mono)", fontSize: 13, fontWeight: 600, color: "var(--block)" }}>
              CSV Schema Validation Report
            </span>
          </div>
          <div style={{ fontSize: 13, color: "var(--ink)", marginBottom: 8 }}>
            {validationError.message || validationError.error || "Schema verification failed."}
          </div>

          {validationError.required_columns && (
            <div style={{ fontSize: 12, color: "var(--ink-soft)", fontFamily: "var(--font-mono)" }}>
              <div>Mandatory required columns: <strong>{validationError.required_columns.join(", ")}</strong></div>
              {validationError.detected_columns && (
                <div style={{ marginTop: 2 }}>Detected in uploaded file: {validationError.detected_columns.join(", ") || "(none)"}</div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Processing State Indicator */}
      {isProcessing && (
        <div
          style={{
            backgroundColor: "var(--paper-raised)",
            border: "1px solid var(--rule)",
            padding: "32px",
            textAlign: "center",
            marginBottom: "var(--space-6)",
          }}
        >
          <div style={{ fontFamily: "var(--font-serif)", fontSize: 18, marginBottom: 8 }}>
            Computing Batch Feature State & Model Probabilities...
          </div>
          <div style={{ width: 280, height: 6, backgroundColor: "var(--paper)", border: "1px solid var(--rule)", margin: "0 auto 12px auto", overflow: "hidden" }}>
            <div
              style={{
                width: "60%",
                height: "100%",
                backgroundColor: "var(--accent)",
                animation: "pulse 1.5s infinite ease-in-out",
              }}
            />
          </div>
          <div style={{ fontSize: 12, color: "var(--ink-soft)", fontFamily: "var(--font-mono)" }}>
            Running Layer 2 Feature Extraction &rarr; Layer 3 Anomaly Fusion &rarr; Layer 4 Policy
          </div>
        </div>
      )}

      {/* Batch Results KPI Ledger */}
      {batchResult && (
        <div style={{ marginBottom: "var(--space-6)" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
            <div>
              <span className="eyebrow" style={{ color: "var(--ink-faint)" }}>Scoring Telemetry</span>
              <h3 style={{ margin: "2px 0 0 0", fontSize: 18, fontFamily: "var(--font-serif)" }}>
                Batch Evaluation Results Summary
              </h3>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
              <span style={{ fontSize: 12, fontFamily: "var(--font-mono)", color: "var(--ink-soft)" }}>
                Execution Time: <strong>{batchResult.processing_time_ms} ms</strong> (
                {Math.round((batchResult.total_transactions / Math.max(0.001, batchResult.processing_time_ms / 1000))).toLocaleString()} txns/sec)
              </span>
              <a
                href={BATCH_DOWNLOAD_FLAGGED_URL}
                download="fraudshield_flagged_batch.csv"
                style={{
                  textDecoration: "none",
                  backgroundColor: "var(--ink)",
                  color: "var(--paper)",
                  padding: "6px 14px",
                  fontFamily: "var(--font-mono)",
                  fontSize: 12,
                  display: "flex",
                  alignItems: "center",
                  gap: 6,
                }}
              >
                <IconDownload size={12} color="var(--paper)" />
                Download Flagged CSV ({batchResult.review_count + batchResult.blocked_count})
              </a>
            </div>
          </div>

          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(5, 1fr)",
              gap: "var(--space-4)",
            }}
          >
            <div style={{ backgroundColor: "var(--paper-raised)", border: "1px solid var(--rule)", padding: "14px" }}>
              <span className="eyebrow" style={{ color: "var(--ink-faint)" }}>Total Processed</span>
              <div style={{ fontSize: 24, fontFamily: "var(--font-mono)", fontWeight: 600, color: "var(--ink)", marginTop: 2 }}>
                {batchResult.total_transactions.toLocaleString()}
              </div>
              <div style={{ fontSize: 11, color: "var(--ink-soft)", marginTop: 2 }}>100% evaluated</div>
            </div>

            <div style={{ backgroundColor: "var(--paper-raised)", border: "1px solid var(--rule)", padding: "14px" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
                <SignalApprove size={8} />
                <span className="eyebrow" style={{ color: "var(--ink-faint)" }}>Approved (P &lt; t1)</span>
              </div>
              <div style={{ fontSize: 24, fontFamily: "var(--font-mono)", fontWeight: 600, color: "var(--approve)", marginTop: 2 }}>
                {batchResult.approved_count.toLocaleString()}
              </div>
              <div style={{ fontSize: 11, color: "var(--ink-soft)", marginTop: 2 }}>
                {((batchResult.approved_count / batchResult.total_transactions) * 100).toFixed(1)}% of volume
              </div>
            </div>

            <div style={{ backgroundColor: "var(--paper-raised)", border: "1px solid var(--rule)", padding: "14px" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
                <SignalReview size={8} />
                <span className="eyebrow" style={{ color: "var(--ink-faint)" }}>Review (t1 &le; P &lt; t2)</span>
              </div>
              <div style={{ fontSize: 24, fontFamily: "var(--font-mono)", fontWeight: 600, color: "var(--review)", marginTop: 2 }}>
                {batchResult.review_count.toLocaleString()}
              </div>
              <div style={{ fontSize: 11, color: "var(--ink-soft)", marginTop: 2 }}>
                Step-up friction challenge
              </div>
            </div>

            <div style={{ backgroundColor: "var(--paper-raised)", border: "1px solid var(--rule)", padding: "14px" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
                <SignalBlock size={8} />
                <span className="eyebrow" style={{ color: "var(--ink-faint)" }}>Blocked (P &ge; t2)</span>
              </div>
              <div style={{ fontSize: 24, fontFamily: "var(--font-mono)", fontWeight: 600, color: "var(--block)", marginTop: 2 }}>
                {batchResult.blocked_count.toLocaleString()}
              </div>
              <div style={{ fontSize: 11, color: "var(--ink-soft)", marginTop: 2 }}>
                High-confidence prevention
              </div>
            </div>

            <div style={{ backgroundColor: "var(--paper-raised)", border: "1px solid var(--rule)", padding: "14px" }}>
              <span className="eyebrow" style={{ color: "var(--ink-faint)" }}>Prevented Exposure</span>
              <div style={{ fontSize: 20, fontFamily: "var(--font-mono)", fontWeight: 600, color: "var(--ink)", marginTop: 4 }}>
                ₹{batchResult.estimated_loss_prevented.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </div>
              <div style={{ fontSize: 11, color: "var(--ink-soft)", marginTop: 2 }}>
                {batchResult.flagged_rate_pct.toFixed(1)}% Flagged Rate
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Flagged Transactions Ledger Table */}
      {batchResult && (
        <div style={{ backgroundColor: "var(--paper-raised)", border: "1px solid var(--rule)", padding: "20px" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
            <div>
              <span className="eyebrow" style={{ color: "var(--ink-faint)" }}>Exception Dossier</span>
              <h3 style={{ margin: "2px 0 0 0", fontSize: 16, fontFamily: "var(--font-serif)" }}>
                Flagged Transactions Queue ({filteredFlagged.length} of {flaggedList.length})
              </h3>
            </div>

            {/* Filter & Search Bar */}
            <div style={{ display: "flex", gap: 8 }}>
              <input
                type="text"
                placeholder="Search Txn ID, Account, or Reason..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                style={{
                  border: "1px solid var(--rule)",
                  backgroundColor: "var(--paper)",
                  padding: "4px 8px",
                  fontSize: 12,
                  fontFamily: "var(--font-mono)",
                  width: 260,
                }}
              />
              <div style={{ display: "flex", gap: 2, backgroundColor: "var(--paper)", padding: 2, border: "1px solid var(--rule)" }}>
                <button
                  onClick={() => setFilterDecision("ALL")}
                  style={{
                    border: "none",
                    padding: "3px 8px",
                    fontSize: 11,
                    fontFamily: "var(--font-mono)",
                    cursor: "pointer",
                    backgroundColor: filterDecision === "ALL" ? "var(--ink)" : "transparent",
                    color: filterDecision === "ALL" ? "var(--paper)" : "var(--ink-soft)",
                  }}
                >
                  All Flagged
                </button>
                <button
                  onClick={() => setFilterDecision("BLOCK")}
                  style={{
                    border: "none",
                    padding: "3px 8px",
                    fontSize: 11,
                    fontFamily: "var(--font-mono)",
                    cursor: "pointer",
                    backgroundColor: filterDecision === "BLOCK" ? "var(--block)" : "transparent",
                    color: filterDecision === "BLOCK" ? "var(--paper)" : "var(--ink-soft)",
                  }}
                >
                  Blocked Only
                </button>
                <button
                  onClick={() => setFilterDecision("REVIEW")}
                  style={{
                    border: "none",
                    padding: "3px 8px",
                    fontSize: 11,
                    fontFamily: "var(--font-mono)",
                    cursor: "pointer",
                    backgroundColor: filterDecision === "REVIEW" ? "var(--review)" : "transparent",
                    color: filterDecision === "REVIEW" ? "var(--paper)" : "var(--ink-soft)",
                  }}
                >
                  Review Only
                </button>
              </div>
            </div>
          </div>

          {filteredFlagged.length === 0 ? (
            <div style={{ padding: 32, textAlign: "center", color: "var(--ink-soft)", fontFamily: "var(--font-mono)", fontSize: 12 }}>
              {flaggedList.length === 0
                ? "✓ No transactions triggered the review (t1=0.0050) or block (t2=0.0591) thresholds."
                : "No transactions match current filter/search criteria."}
            </div>
          ) : (
            <div style={{ overflowX: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12, fontFamily: "var(--font-mono)" }}>
                <thead>
                  <tr style={{ borderBottom: "1px solid var(--rule)", textAlign: "left", color: "var(--ink-faint)" }}>
                    <th style={{ padding: "8px 6px" }}>TXN ID</th>
                    <th style={{ padding: "8px 6px" }}>ACCOUNT</th>
                    <th style={{ padding: "8px 6px", textAlign: "right" }}>AMOUNT</th>
                    <th style={{ padding: "8px 6px" }}>CHANNEL</th>
                    <th style={{ padding: "8px 6px", textAlign: "right" }}>FRAUD PROB</th>
                    <th style={{ padding: "8px 6px", textAlign: "center" }}>DECISION</th>
                    <th style={{ padding: "8px 6px" }}>PRIMARY RISK DRIVER</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredFlagged.map((row) => (
                    <tr key={row.txn_id} style={{ borderBottom: "1px solid var(--rule-light)" }}>
                      <td style={{ padding: "8px 6px", fontWeight: 600 }}>{row.txn_id}</td>
                      <td style={{ padding: "8px 6px", color: "var(--ink-soft)" }}>{row.account_id}</td>
                      <td style={{ padding: "8px 6px", textAlign: "right", fontWeight: 600 }}>
                        ₹{row.amount.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                      </td>
                      <td style={{ padding: "8px 6px", textTransform: "uppercase", fontSize: 10, color: "var(--ink-faint)" }}>
                        {row.channel}
                      </td>
                      <td style={{ padding: "8px 6px", textAlign: "right", fontWeight: 600, color: row.decision === "BLOCK" ? "var(--block)" : "var(--review)" }}>
                        {(row.fraud_probability * 100).toFixed(2)}%
                      </td>
                      <td style={{ padding: "8px 6px", textAlign: "center" }}>
                        <span
                          className="pill"
                          style={{
                            backgroundColor: row.decision === "BLOCK" ? "rgba(184, 51, 42, 0.1)" : "rgba(196, 122, 34, 0.1)",
                            color: row.decision === "BLOCK" ? "var(--block)" : "var(--review)",
                            fontSize: 10,
                            padding: "2px 8px",
                            display: "inline-flex",
                            alignItems: "center",
                            gap: 4,
                          }}
                        >
                          {row.decision === "BLOCK" ? <SignalBlock size={8} /> : <SignalReview size={8} />}
                          {row.decision}
                        </span>
                      </td>
                      <td style={{ padding: "8px 6px", color: "var(--ink)" }}>
                        {row.reason || "High Statistical Fraud Confidence"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <div style={{ marginTop: 16, display: "flex", justifyContent: "space-between", fontSize: 11, color: "var(--ink-faint)" }}>
            <span>Showing {filteredFlagged.length} flagged transaction records</span>
            <span>Operating Dual Thresholds: Review $t_1 = 0.0050$, Block $t_2 = 0.0591$</span>
          </div>
        </div>
      )}
    </div>
  );
};
