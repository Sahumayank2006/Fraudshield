import React, { useState, useEffect } from "react";
import { Layout } from "./components/layout/Layout";
import { ScreenId } from "./components/layout/LeftRail";
import { SvgLineChart } from "./components/charts/SvgLineChart";
import { SvgWaterfall } from "./components/charts/SvgWaterfall";
import { fetchHealth, fetchOverview, fetchCurves, triggerAttack, controlStream } from "./api/client";
import { SignalBlock, SignalReview, SignalApprove } from "./components/common/Icons";
import { LiveDesk } from "./views/LiveDesk";
import { CaseFile } from "./views/CaseFile";
import { Briefing } from "./views/Briefing";
import { ThresholdLab } from "./views/ThresholdLab";
import { ModelLab } from "./views/ModelLab";
import { WhyExplain } from "./views/WhyExplain";
import { DriftOperations } from "./views/DriftOperations";
import { FairnessRisk } from "./views/FairnessRisk";
import { BatchScoring } from "./views/BatchScoring";
import { Methodology } from "./views/Methodology";

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
        <Briefing onNavigateScreen={(screen) => setActiveScreen(screen as ScreenId)} />
      )}

      {activeScreen === "threshold" && (
        <ThresholdLab />
      )}

      {activeScreen === "model" && (
        <ModelLab />
      )}

      {activeScreen === "why" && (
        <WhyExplain />
      )}

      {activeScreen === "drift" && (
        <DriftOperations />
      )}

      {activeScreen === "fairness" && (
        <FairnessRisk />
      )}

      {activeScreen === "batch" && (
        <BatchScoring />
      )}

      {activeScreen === "method" && (
        <Methodology />
      )}

      {/* Other screens placeholder for Phase 17 */}
      {!["live", "case", "briefing", "threshold", "model", "why", "drift", "fairness", "batch", "method"].includes(activeScreen) && (
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
