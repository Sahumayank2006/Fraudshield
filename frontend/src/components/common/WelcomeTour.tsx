import React, { useState, useEffect } from "react";
import { WordmarkMark, IconCross } from "./Icons";

interface WelcomeTourProps {
  onStartPresentation: () => void;
}

export const WelcomeTour: React.FC<WelcomeTourProps> = ({ onStartPresentation }) => {
  const [isVisible, setIsVisible] = useState<boolean>(false);

  useEffect(() => {
    const hasSeen = localStorage.getItem("fraudshield_welcomed");
    if (!hasSeen) {
      setIsVisible(true);
    }
  }, []);

  const dismiss = () => {
    localStorage.setItem("fraudshield_welcomed", "true");
    setIsVisible(false);
  };

  const handleStartTour = () => {
    dismiss();
    onStartPresentation();
  };

  if (!isVisible) return null;

  return (
    <div
      style={{
        position: "fixed",
        bottom: 24,
        right: 24,
        zIndex: 9990,
        width: 380,
        backgroundColor: "var(--paper-raised)",
        border: "2px solid var(--ink)",
        boxShadow: "0 12px 32px rgba(0, 0, 0, 0.22)",
        padding: "20px",
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 10 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <WordmarkMark size={16} color="var(--block)" />
          <span style={{ fontFamily: "var(--font-serif)", fontSize: 16, fontWeight: 600, color: "var(--ink)" }}>
            Welcome to FraudShield
          </span>
        </div>
        <button
          onClick={dismiss}
          style={{ background: "none", border: "none", color: "var(--ink-soft)", cursor: "pointer", padding: 2 }}
          title="Dismiss"
        >
          <IconCross size={14} />
        </button>
      </div>

      <p style={{ fontSize: 12, color: "var(--ink-soft)", lineHeight: 1.55, margin: "0 0 14px 0" }}>
        Production-grade financial fraud prevention prototype featuring hybrid anomaly fusion (Isolation Forest + Autoencoder + XGBoost),
        operational dual-threshold decisioning, and real-time SSE streaming.
      </p>

      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        <button
          onClick={handleStartTour}
          style={{
            backgroundColor: "var(--ink)",
            color: "var(--paper)",
            border: "none",
            padding: "8px 14px",
            fontFamily: "var(--font-mono)",
            fontSize: 12,
            fontWeight: 600,
            cursor: "pointer",
            textAlign: "center",
          }}
        >
          Launch 6-Minute Guided Tour [P]
        </button>

        <button
          onClick={dismiss}
          style={{
            backgroundColor: "transparent",
            color: "var(--ink-soft)",
            border: "1px solid var(--rule)",
            padding: "6px 14px",
            fontFamily: "var(--font-mono)",
            fontSize: 11,
            cursor: "pointer",
            textAlign: "center",
          }}
        >
          Explore Autonomously
        </button>
      </div>

      <div style={{ marginTop: 12, fontSize: 10, color: "var(--ink-faint)", fontFamily: "var(--font-mono)", textAlign: "center" }}>
        Tip: Press [?] anytime for keyboard shortcuts
      </div>
    </div>
  );
};

