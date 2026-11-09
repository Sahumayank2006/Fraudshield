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
import { Glossary } from "./views/Glossary";
import { PresentModeModal } from "./components/presentation/PresentModeModal";
import { ShortcutsOverlay } from "./components/common/ShortcutsOverlay";
import { WelcomeTour } from "./components/common/WelcomeTour";

export const App: React.FC = () => {
  const [activeScreen, setActiveScreen] = useState<ScreenId>("live");
  const [selectedCaseId, setSelectedCaseId] = useState<string | null>(null);
  const [healthData, setHealthData] = useState<any>(null);
  const [overviewData, setOverviewData] = useState<any>(null);
  const [curvesData, setCurvesData] = useState<any>(null);
  const [attackToast, setAttackToast] = useState<string | null>(null);
  const [presentModeOpen, setPresentModeOpen] = useState<boolean>(false);
  const [shortcutsOpen, setShortcutsOpen] = useState<boolean>(false);
  const gSequenceRef = React.useRef<boolean>(false);

  // Fetch initial telemetry
  useEffect(() => {
    fetchHealth().then(setHealthData).catch(() => {});
    fetchOverview().then(setOverviewData).catch(() => {});
    fetchCurves().then(setCurvesData).catch(() => {});
  }, []);

  const handleTriggerAttackBurst = (typology: string = "card_testing") => {
    triggerAttack(typology, 15).then(() => {
      setAttackToast(`⚡ Scripted attack burst injected: ${typology} (15 micro-transactions)`);
      setTimeout(() => setAttackToast(null), 4000);
    });
  };

  // Global Keyboard Shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) {
        return;
      }

      // Escape closes modals
      if (e.key === "Escape") {
        setPresentModeOpen(false);
        setShortcutsOpen(false);
        return;
      }

      // Help Overlay (?)
      if (e.key === "?") {
        e.preventDefault();
        setShortcutsOpen((prev) => !prev);
        return;
      }

      // Presentation Mode (P)
      if (e.key === "p" || e.key === "P") {
        if (!presentModeOpen) {
          e.preventDefault();
          setPresentModeOpen(true);
        }
        return;
      }

      // Attack Injection (A)
      if (!presentModeOpen && (e.key === "a" || e.key === "A")) {
        e.preventDefault();
        handleTriggerAttackBurst("card_testing");
        return;
      }

      // Play/Pause Stream (Space)
      if (!presentModeOpen && e.code === "Space") {
        e.preventDefault();
        controlStream("pause");
        return;
      }

      // Sequential G Jumps
      if (e.key === "g" || e.key === "G") {
        if (gSequenceRef.current) {
          // G + G -> Glossary
          setActiveScreen("glossary");
          gSequenceRef.current = false;
        } else {
          gSequenceRef.current = true;
          setTimeout(() => {
            gSequenceRef.current = false;
          }, 1500);
        }
        return;
      }

      if (gSequenceRef.current) {
        gSequenceRef.current = false;
        switch (e.key) {
          case "1": setActiveScreen("briefing"); break;
          case "2": setActiveScreen("live"); break;
          case "3": setActiveScreen("case"); break;
          case "4": setActiveScreen("threshold"); break;
          case "5": setActiveScreen("model"); break;
          case "6": setActiveScreen("why"); break;
          case "7": setActiveScreen("drift"); break;
          case "8": setActiveScreen("fairness"); break;
          case "9": setActiveScreen("batch"); break;
          case "0": setActiveScreen("method"); break;
        }
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [activeScreen, presentModeOpen]);

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
      onEnterPresentMode={() => setPresentModeOpen(true)}
      onToggleShortcuts={() => setShortcutsOpen(true)}
      latencyMs={overviewData?.headline?.median_latency_ms || 3.2}
      isStreamLive={true}
      modelVersion={healthData?.model_version || "v1.0-champion"}
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

      {activeScreen === "glossary" && (
        <Glossary />
      )}

      {/* Presentation Mode Fullscreen Tour Overlay */}
      <PresentModeModal
        isOpen={presentModeOpen}
        onClose={() => setPresentModeOpen(false)}
        onNavigateScreen={(scr) => setActiveScreen(scr)}
        onTriggerAttack={handleTriggerAttackBurst}
      />

      {/* Keyboard Shortcuts Overlay */}
      <ShortcutsOverlay
        isOpen={shortcutsOpen}
        onClose={() => setShortcutsOpen(false)}
        onNavigateScreen={(scr) => setActiveScreen(scr)}
        onTriggerAttack={() => handleTriggerAttackBurst("card_testing")}
        onTogglePresentMode={() => setPresentModeOpen((prev) => !prev)}
      />

      {/* First-Run Welcome Popover */}
      <WelcomeTour onStartPresentation={() => setPresentModeOpen(true)} />
    </Layout>
  );
};
