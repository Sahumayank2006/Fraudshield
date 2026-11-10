import React, { useEffect } from "react";
import { ScreenId } from "../layout/LeftRail";
import {
  SignalBlock,
  SignalReview,
  SignalApprove,
  IconCross,
  IconPlay,
  IconAttack,
} from "../common/Icons";

export interface TourStep {
  stepIndex: number;
  totalSteps: number;
  section: string;
  title: string;
  duration: string;
  screenId: ScreenId;
  talkTrack: string[];
  keyHighlight: string;
  triggerAction?: "attack";
}

const TOUR_STEPS: TourStep[] = [
  {
    stepIndex: 1,
    totalSteps: 7,
    section: "§01 Executive Briefing",
    title: "The Financial Fraud Crisis & Production Architecture",
    duration: "0:00 – 1:00",
    screenId: "briefing",
    talkTrack: [
      "Welcome the committee. State the core problem: in production financial rails, fraud is rare (<1% prevalence), highly asymmetric in cost, and exhibits continuous adversarial concept drift.",
      "Highlight the headline results: FraudShield's hybrid model delivers a PR-AUC of 0.930 (95% CI [0.892, 0.959]), a Recall@P90 of 58.0%, and a 96.8% reduction in expected financial fraud losses relative to traditional rule-based baselines.",
      "Point to the Precision-Recall curve comparison: single-layer trees and logistic baselines collapse under high-precision operational constraints, while FraudShield maintains superior sensitivity.",
    ],
    keyHighlight: "PR-AUC 0.930 &bull; 96.8% Cost Reduction &bull; Zero Rule Leakage",
  },
  {
    stepIndex: 2,
    totalSteps: 7,
    section: "§02 Live Desk",
    title: "Real-Time Ingestion, Latency, & Two-Threshold Decisions",
    duration: "1:00 – 2:00",
    screenId: "live",
    talkTrack: [
      "Point to the live transaction ledger streaming via Server-Sent Events (SSE). Emphasize that every row represents real-time feature extraction via in-memory FeatureStore deques.",
      "Showcase inference speed: median scoring latency is measured live at ~3.2 ms (p95 < 10 ms), well within Visa/Mastercard 50 ms SLA windows.",
      "Explain the two-threshold policy: Green (P < t1) approved instantly; Amber (t1 <= P < t2) queued for human review with step-up 2FA; Crimson (P >= t2) blocked automatically with verified >= 90% precision.",
    ],
    keyHighlight: "Sub-5ms Inference &bull; Triple-Encoded Accessibility &bull; Rolling 5-Min Histogram",
  },
  {
    stepIndex: 3,
    totalSteps: 7,
    section: "§02 Attack Simulation",
    title: "Adversarial Burst Containment Telemetry",
    duration: "2:00 – 2:45",
    screenId: "live",
    triggerAction: "attack",
    talkTrack: [
      "Demonstrate live defense against active fraud syndicates by injecting a scripted attack burst (Card Testing, Account Takeover, or Mule Chain).",
      "Show the containment banner: Observe how the online rolling velocity features detect the rapid burst, driving probabilities above t2 within sub-second intervals.",
      "Highlight containment telemetry: Time-to-first-block (< 100 ms) and cumulative financial capital saved (INR exposure protected).",
    ],
    keyHighlight: "Instant Card Testing & ATO Mitigation &bull; Live Telemetry Banner",
  },
  {
    stepIndex: 4,
    totalSteps: 7,
    section: "§03 Case File",
    title: "Explainable AI: Exact TreeSHAP & Reason Codes",
    duration: "2:45 – 3:45",
    screenId: "case",
    talkTrack: [
      "Switch to an analyst case dossier. Emphasize that black-box decisions violate regulatory principles (RBI, DPDP, Federal Reserve SR 11-7).",
      "Walk through the hand-built SVG TreeSHAP waterfall: Decomposes log-odds margin into exact additive feature contributions (O(TLD^2) complexity, zero sampling approximation error).",
      "Explain dynamic plain-English reason codes: Each mathematical Shapley value is translated into contextual statements (e.g., 'Log transaction scale indicates significant capital exposure').",
      "Showcase persistent analyst disposition actions: Confirm Fraud, Dismiss FP, or Escalate, persisting atomically to SQLite.",
    ],
    keyHighlight: "Exact Polynomial TreeSHAP &bull; Plain-English Reasons &bull; SQLite Persistence",
  },
  {
    stepIndex: 5,
    totalSteps: 7,
    section: "§04 Threshold Lab",
    title: "Cost-Optimal Operational Policy & Human Capacity",
    duration: "3:45 – 4:30",
    screenId: "threshold",
    talkTrack: [
      "Demonstrate why default machine learning thresholding (P = 0.50) is economically catastrophic in rare-event fraud.",
      "Show the mirrored score density plot: Drag t1 and t2 handles live to see the 2x2 confusion matrix and financial cost recalculate instantaneously.",
      "Highlight the Human Review Queue Capacity Ceiling: Operational review rate is bounded at <= 6.0 reviews per 1,000 transactions to prevent human analyst burnout.",
      "Click 'Snap to Optimal Policy' to demonstrate automated restoration of minimum-cost operating parameters (t1 = 0.0050, t2 = 0.0591).",
    ],
    keyHighlight: "Mirrored Density Curves &bull; Amount-Weighted Loss Model &bull; Capacity Ceiling",
  },
  {
    stepIndex: 6,
    totalSteps: 7,
    section: "§05 Model Lab",
    title: "Systematic E1–E10 Matrix, ROC Flattery, & Calibration",
    duration: "4:30 – 5:15",
    screenId: "model",
    talkTrack: [
      "Present the complete E1 to E10 systematic experiment matrix with 95% bootstrap confidence intervals, demonstrating empirical rigour.",
      "Deliver the critical pedagogical insight (ROC vs PR flattery): In 0.65% fraud prevalence, an algorithm generating 200 false positives per 1,000 txns still boasts 0.999 ROC-AUC despite abysmal 30% precision.",
      "Showcase isotonic probability calibration (reducing Brier loss to 0.0048) and the early vs late holdout split demonstrating resilience against concept drift.",
    ],
    keyHighlight: "E1–E10 Rigour &bull; Pedagogical ROC Flattery Callout &bull; Isotonic Calibration",
  },
  {
    stepIndex: 7,
    totalSteps: 7,
    section: "§07 Drift & Operations",
    title: "Surveillance, 7-Day Maturation Embargo, & Challenger Rollback",
    duration: "5:15 – 6:00",
    screenId: "drift",
    talkTrack: [
      "Conclude with production operations and governance: continuous decile Population Stability Index (PSI) tracking across all 26 feature vectors.",
      "Explain the mandatory 7-Day Ground Truth Maturation Delay: Chargebacks require time to clear. Unflagged recent transactions cannot be presumed innocent without introducing severe false precision.",
      "Demonstrate Champion-Challenger governance: Click 'Train Challenger Model' to execute real background retraining, side-by-side gate validation, and one-click atomic rollback.",
    ],
    keyHighlight: "Decile PSI Surveillance &bull; 7-Day Maturation Embargo &bull; Atomic Rollback",
  },
];

interface PresentModeModalProps {
  isOpen: boolean;
  onClose: () => void;
  onNavigateScreen: (screenId: ScreenId) => void;
  onTriggerAttack?: (typology: string) => void;
}

export const PresentModeModal: React.FC<PresentModeModalProps> = ({
  isOpen,
  onClose,
  onNavigateScreen,
  onTriggerAttack,
}) => {
  const [currentStepIndex, setCurrentStepIndex] = React.useState<number>(0);

  const step = TOUR_STEPS[currentStepIndex];

  // Synchronize background screen with tour step
  useEffect(() => {
    if (isOpen && step) {
      onNavigateScreen(step.screenId);
      if (step.triggerAction === "attack" && onTriggerAttack) {
        onTriggerAttack("card_testing");
      }
    }
  }, [isOpen, currentStepIndex]);

  // Keyboard navigation inside presentation mode
  useEffect(() => {
    if (!isOpen) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
      } else if (e.key === "ArrowRight" || e.code === "Space") {
        e.preventDefault();
        setCurrentStepIndex((prev) => Math.min(TOUR_STEPS.length - 1, prev + 1));
      } else if (e.key === "ArrowLeft") {
        e.preventDefault();
        setCurrentStepIndex((prev) => Math.max(0, prev - 1));
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const handleNext = () => {
    if (currentStepIndex < TOUR_STEPS.length - 1) {
      setCurrentStepIndex(currentStepIndex + 1);
    } else {
      onClose();
    }
  };

  const handlePrev = () => {
    if (currentStepIndex > 0) {
      setCurrentStepIndex(currentStepIndex - 1);
    }
  };

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 9999,
        backgroundColor: "rgba(18, 17, 14, 0.78)",
        backdropFilter: "blur(4px)",
        display: "flex",
        alignItems: "flex-end",
        justifyContent: "center",
        padding: "0 var(--space-6) var(--space-6) var(--space-6)",
      }}
    >
      <div
        style={{
          width: "100%",
          maxWidth: 980,
          backgroundColor: "var(--paper-raised)",
          border: "2px solid var(--ink)",
          boxShadow: "0 16px 40px rgba(0, 0, 0, 0.35)",
          padding: "24px 28px",
          display: "flex",
          flexDirection: "column",
          gap: 16,
          position: "relative",
        }}
      >
        {/* Top Header Bar */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", borderBottom: "1px solid var(--rule)", paddingBottom: 12 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <span
              className="pill"
              style={{
                backgroundColor: "var(--ink)",
                color: "var(--paper)",
                fontFamily: "var(--font-mono)",
                fontSize: 11,
                padding: "3px 8px",
              }}
            >
              PRESENTATION MODE [P]
            </span>
            <span style={{ fontSize: 12, fontFamily: "var(--font-mono)", color: "var(--ink-soft)" }}>
              Step {step.stepIndex} of {step.totalSteps} &bull; {step.duration}
            </span>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ fontSize: 11, fontFamily: "var(--font-mono)", color: "var(--ink-faint)" }}>
              Arrows [← / →] step &bull; Space advance &bull; [Esc] exit
            </span>
            <button
              onClick={onClose}
              style={{
                background: "none",
                border: "none",
                color: "var(--ink)",
                cursor: "pointer",
                padding: 4,
                display: "flex",
                alignItems: "center",
              }}
              title="Exit Present Mode (Esc)"
            >
              <IconCross size={16} />
            </button>
          </div>
        </div>

        {/* Slide Title & Section */}
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span className="eyebrow" style={{ color: "var(--accent)" }}>{step.section}</span>
            <span className="pill" style={{ backgroundColor: "var(--paper)", border: "1px solid var(--rule-light)", fontSize: 10 }}>
              {step.keyHighlight}
            </span>
          </div>
          <h2 style={{ fontFamily: "var(--font-serif)", fontSize: 24, margin: "6px 0 0 0", letterSpacing: "-0.01em", color: "var(--ink)" }}>
            {step.title}
          </h2>
        </div>

        {/* Talk-Track Narrative Bullets (What to say to the faculty) */}
        <div style={{ backgroundColor: "var(--paper)", border: "1px solid var(--rule-light)", padding: "16px 20px" }}>
          <div style={{ fontSize: 11, fontFamily: "var(--font-mono)", textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--ink-faint)", marginBottom: 8 }}>
            Evaluator Narrative Script &bull; Minute-by-Minute Talk Track:
          </div>
          <ul style={{ margin: 0, paddingLeft: 18, fontSize: 13, color: "var(--ink)", lineHeight: 1.6 }}>
            {step.talkTrack.map((bullet, idx) => (
              <li key={idx} style={{ marginBottom: idx === step.talkTrack.length - 1 ? 0 : 6 }}>
                {bullet}
              </li>
            ))}
          </ul>
        </div>

        {/* Bottom Navigation & Controls */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", paddingTop: 8 }}>
          {/* Step Dots Progress */}
          <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
            {TOUR_STEPS.map((s, idx) => (
              <div
                key={idx}
                onClick={() => setCurrentStepIndex(idx)}
                style={{
                  width: idx === currentStepIndex ? 24 : 8,
                  height: 8,
                  backgroundColor: idx === currentStepIndex ? "var(--ink)" : "var(--rule)",
                  cursor: "pointer",
                  transition: "all 0.15s ease-in-out",
                }}
                title={s.title}
              />
            ))}
          </div>

          {/* Nav Buttons */}
          <div style={{ display: "flex", gap: 10 }}>
            <button
              onClick={handlePrev}
              disabled={currentStepIndex === 0}
              style={{
                backgroundColor: "transparent",
                color: currentStepIndex === 0 ? "var(--ink-faint)" : "var(--ink)",
                border: "1px solid var(--rule)",
                padding: "8px 16px",
                fontFamily: "var(--font-mono)",
                fontSize: 12,
                cursor: currentStepIndex === 0 ? "not-allowed" : "pointer",
              }}
            >
              &larr; Previous Step
            </button>

            <button
              onClick={handleNext}
              style={{
                backgroundColor: "var(--ink)",
                color: "var(--paper)",
                border: "none",
                padding: "8px 20px",
                fontFamily: "var(--font-mono)",
                fontSize: 12,
                fontWeight: 600,
                cursor: "pointer",
              }}
            >
              {currentStepIndex === TOUR_STEPS.length - 1 ? "Complete Tour & Close [Esc]" : "Next Step &rarr;"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

