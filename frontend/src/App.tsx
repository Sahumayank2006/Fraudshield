import React, { useState, useEffect } from "react";
import { Layout } from "./components/layout/Layout";
import { ScreenId } from "./components/layout/LeftRail";
import { SvgLineChart } from "./components/charts/SvgLineChart";
import { SvgWaterfall } from "./components/charts/SvgWaterfall";
import { fetchHealth, fetchOverview, fetchCurves, triggerAttack, controlStream } from "./api/client";
import { SignalBlock, SignalReview, SignalApprove } from "./components/common/Icons";
import { LiveDesk } from "./views/LiveDesk";
import { CaseFile } from "./views/CaseFile";

export const App: React.FC = () => {
  const [activeScreen, setActiveScreen] = useState<ScreenId>("live");
  const [selectedCaseId, setSelectedCaseId] = useState<string | null>(null);
  const [healthData, setHealthData] = useState<any>(null);
  const [overviewData, setOverviewData] = useState<any>(null);
  const [curvesData, setCurvesData] = useState<any>(null);
  const [attackToast, setAttackToast] = useState<string | null>(null);

  // Fetch initial telemetry
  useEffect(() => {
    fetchHealth().then(setHealthData).catch(() => {});
    fetchOverview().then(setOverviewData).catch(() => {});
    fetchCurves().then(setCurvesData).catch(() => {});
  }, []);

  // Global Keyboard Shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) {
        return;
      }
      if (e.key === "p" || e.key === "P") {
        e.preventDefault();
        alert("Presentation mode shortcut [P] triggered. (Full Present Mode is scheduled for Phase 18)");
      } else if (activeScreen !== "live" && (e.key === "a" || e.key === "A")) {
        e.preventDefault();
        triggerAttack("card_testing", 15).then(() => {
          setAttackToast("⚡ Scripted attack burst injected: card_testing (15 micro-transactions)");
          setTimeout(() => setAttackToast(null), 4000);
        });
      } else if (activeScreen !== "live" && e.code === "Space") {
        e.preventDefault();
        controlStream("pause");
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [activeScreen]);

  // Extract PR curve coordinates for chart primitive preview
  const championPrCurve = curvesData?.champion_e9?.pr_curve || [
    { x: 0.0, y: 1.0 },
    { x: 0.2, y: 0.98 },
    { x: 0.4, y: 0.95 },
    { x: 0.6, y: 0.92 },
    { x: 0.8, y: 0.85 },
    { x: 0.9, y: 0.72 },
    { x: 1.0, y: 0.25 },
  ];

  // Sample TreeSHAP waterfall steps for component test
  const sampleWaterfall = [
    { step: "Base Value (Prior)", delta: -3.85, end_value: -3.85, type: "base" },
    { step: "log_amount", delta: 2.45, start_value: -3.85, end_value: -1.4, type: "positive" },
    { step: "iso_score", delta: 1.82, start_value: -1.4, end_value: 0.42, type: "positive" },
    { step: "txn_count_1h", delta: 1.15, start_value: 0.42, end_value: 1.57, type: "positive" },
    { step: "is_night", delta: 0.65, start_value: 1.57, end_value: 2.22, type: "positive" },
    { step: "time_since_last_txn", delta: -0.45, start_value: 2.22, end_value: 1.77, type: "negative" },
    { step: "Model Output Margin", delta: 0.0, end_value: 1.77, type: "total" },
  ];

  return (
    <Layout
      activeScreen={activeScreen}
      onSelectScreen={setActiveScreen}
      openCasesCount={overviewData?.session?.open_cases_count || 15}
    >
      {/* Scripted Attack Toast Banner (when triggered outside Live Desk) */}
      {attackToast && (
        <div
          style={{
            backgroundColor: "var(--block)",
            color: "var(--paper)",
            padding: "8px 16px",
            fontSize: 12,
            fontFamily: "var(--font-mono)",
            marginBottom: "var(--space-4)",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <span>{attackToast}</span>
          <button
            onClick={() => setAttackToast(null)}
            style={{ background: "none", border: "none", color: "var(--paper)", cursor: "pointer", fontSize: 14 }}
          >
            ×
          </button>
        </div>
      )}

      {/* Screen Router */}
      {activeScreen === "live" && (
        <LiveDesk
          onOpenCaseFile={(caseId) => {
            setSelectedCaseId(caseId);
            setActiveScreen("case");
          }}
        />
      )}

      {activeScreen === "case" && (
        <CaseFile
          initialCaseId={selectedCaseId}
          onSelectCase={(caseId) => setSelectedCaseId(caseId)}
        />
      )}

      {activeScreen === "briefing" && (
        <div>
          {/* Screen Title & Editorial Deck */}
          <div style={{ marginBottom: "var(--space-6)", borderBottom: "1px solid var(--rule)", paddingBottom: "var(--space-4)" }}>
            <div style={{ display: "flex", alignItems: "baseline", gap: "var(--space-3)" }}>
              <span className="eyebrow" style={{ color: "var(--block)" }}>
                §01 Operational Briefing
              </span>
              <span style={{ fontSize: 12, color: "var(--ink-faint)", fontFamily: "var(--font-mono)" }}>
                Active Model: E9 Hybrid Champion
              </span>
            </div>
            <h1 style={{ marginTop: "var(--space-2)" }}>
              The Fraud Desk — Executive & Operations Briefing
            </h1>
            <p style={{ fontSize: 14, color: "var(--ink-soft)", marginTop: "var(--space-2)", maxWidth: 900 }}>
              Production payment protection summary. Evaluates transactions through an unsupervised
              isolation & autoencoder branch fused into class-weighted gradient boosting, calibrated for real-money loss prevention.
            </p>
          </div>

          {/* Decision Signal Encoding Legend */}
          <div
            style={{
              display: "flex",
              gap: "var(--space-6)",
              padding: "var(--space-3) var(--space-4)",
              backgroundColor: "var(--paper-raised)",
              border: "1px solid var(--rule)",
              marginBottom: "var(--space-6)",
              alignItems: "center",
            }}
          >
            <span className="eyebrow">Decision Tiers:</span>
            <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12 }}>
              <SignalBlock size={13} />
              <span style={{ fontWeight: 600, color: "var(--block)" }}>BLOCK</span> (t2 &ge; {healthData?.t2_block?.toFixed(3) || "0.059"})
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12 }}>
              <SignalReview size={13} />
              <span style={{ fontWeight: 600, color: "var(--review)" }}>REVIEW</span> (t1 &ge; {healthData?.t1_review?.toFixed(3) || "0.005"})
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12 }}>
              <SignalApprove size={13} />
              <span style={{ fontWeight: 600, color: "var(--approve)" }}>APPROVE</span> (&lt; t1)
            </div>
          </div>

          {/* Two-Column Asymmetric Layout for Foundation Charts */}
          <div style={{ display: "grid", gridTemplateColumns: "1.1fr 0.9fr", gap: "var(--space-8)" }}>
            {/* Left Column: Hand-Built SVG Line Chart */}
            <div>
              <SvgLineChart
                title="Champion Model Precision-Recall Curve (E9 Hybrid)"
                finding="Maintains 90% precision up to 58.0% recall, outperforming baseline models under concept drift."
                series={[
                  {
                    name: "E9 Hybrid (OOF + Anomaly)",
                    color: "var(--block)",
                    points: championPrCurve.map((pt: any) => ({ x: pt.recall || pt.x, y: pt.precision || pt.y })),
                    strokeWidth: 2.2,
                  },
                ]}
              />
              <div className="marginalia">
                Note: The PR curve reflects honest holdout test performance on the 70/15/15 chronological split. ROC-AUC is
                intentionally superseded as the primary metric because extreme 0.65% class imbalance causes false flattery.
              </div>
            </div>

            {/* Right Column: Hand-Built SVG SHAP Waterfall Chart */}
            <div>
              <SvgWaterfall
                steps={sampleWaterfall}
                title="Local TreeSHAP Waterfall (Sample Transaction)"
                finding="Stepwise attribution demonstrates how high transaction scale and isolation anomaly pushed log-odds past the block threshold."
              />
              <div className="marginalia">
                Causality Caution: SHAP values explain statistical associations learned by the boosted tree ensemble; they do not represent real-world physical causality.
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Other screens placeholder for Phase 10 - 17 */}
      {!["live", "case", "briefing"].includes(activeScreen) && (
        <div style={{ padding: "var(--space-8)", backgroundColor: "var(--paper-raised)", border: "1px solid var(--rule)" }}>
          <span className="eyebrow" style={{ color: "var(--ink-faint)" }}>Phase Pipeline</span>
          <h2 style={{ marginTop: 8 }}>Section §{activeScreen.toUpperCase()}</h2>
          <p style={{ marginTop: 8, fontSize: 14, color: "var(--ink-soft)" }}>
            This screen is scheduled for development in sequential order per the Phase Stop-and-Check protocol.
          </p>
          <button
            onClick={() => setActiveScreen("live")}
            style={{
              marginTop: 16,
              backgroundColor: "var(--ink)",
              color: "var(--paper)",
              border: "none",
              padding: "6px 12px",
              fontFamily: "var(--font-mono)",
              fontSize: 12,
              cursor: "pointer",
            }}
          >
            &larr; Switch to §02 Live Desk
          </button>
        </div>
      )}
    </Layout>
  );
};
