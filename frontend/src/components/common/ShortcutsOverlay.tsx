import React from "react";
import { IconCross } from "./Icons";
import { ScreenId } from "../layout/LeftRail";

interface ShortcutsOverlayProps {
  isOpen: boolean;
  onClose: () => void;
  onNavigateScreen: (screenId: ScreenId) => void;
  onTriggerAttack: () => void;
  onTogglePresentMode: () => void;
}

export const ShortcutsOverlay: React.FC<ShortcutsOverlayProps> = ({
  isOpen,
  onClose,
  onNavigateScreen,
  onTriggerAttack,
  onTogglePresentMode,
}) => {
  if (!isOpen) return null;

  const shortcuts = [
    { key: "P", desc: "Toggle Fullscreen Presentation Mode (6-minute guided tour)", action: onTogglePresentMode },
    { key: "A", desc: "Inject Scripted Attack Burst (15 card testing txns)", action: onTriggerAttack },
    { key: "Space", desc: "Play / Pause Live SSE Replay Stream" },
    { key: "?", desc: "Toggle this Keyboard Shortcuts Cheatsheet", action: onClose },
    { key: "Esc", desc: "Close any open Drawer, Modal, or Overlay", action: onClose },
  ];

  const screenJumps: Array<{ key: string; label: string; id: ScreenId }> = [
    { key: "G 1", label: "§01 Briefing", id: "briefing" },
    { key: "G 2", label: "§02 Live Desk", id: "live" },
    { key: "G 3", label: "§03 Case File", id: "case" },
    { key: "G 4", label: "§04 Threshold Lab", id: "threshold" },
    { key: "G 5", label: "§05 Model Lab", id: "model" },
    { key: "G 6", label: "§06 Why (SHAP)", id: "why" },
    { key: "G 7", label: "§07 Drift & Ops", id: "drift" },
    { key: "G 8", label: "§08 Fairness & Risk", id: "fairness" },
    { key: "G 9", label: "§09 Batch Scoring", id: "batch" },
    { key: "G 0", label: "§10 Methodology", id: "method" },
    { key: "G G", label: "§11 Glossary", id: "glossary" },
  ];

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 9998,
        backgroundColor: "rgba(18, 17, 14, 0.65)",
        backdropFilter: "blur(2px)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: "var(--space-6)",
      }}
      onClick={onClose}
    >
      <div
        style={{
          width: "100%",
          maxWidth: 620,
          backgroundColor: "var(--paper-raised)",
          border: "2px solid var(--ink)",
          boxShadow: "0 12px 32px rgba(0, 0, 0, 0.25)",
          padding: "24px",
          position: "relative",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", borderBottom: "1px solid var(--rule)", paddingBottom: 12, marginBottom: 16 }}>
          <div>
            <span className="eyebrow" style={{ color: "var(--ink-faint)" }}>FraudDesk Command Line</span>
            <h3 style={{ margin: "2px 0 0 0", fontSize: 18, fontFamily: "var(--font-serif)" }}>
              Keyboard Shortcuts Cheat Sheet
            </h3>
          </div>
          <button
            onClick={onClose}
            style={{
              background: "none",
              border: "none",
              color: "var(--ink)",
              cursor: "pointer",
              padding: 4,
            }}
          >
            <IconCross size={16} />
          </button>
        </div>

        {/* Global Action Keys */}
        <div style={{ marginBottom: 16 }}>
          <span className="eyebrow" style={{ color: "var(--ink-soft)" }}>Action Controls</span>
          <div style={{ display: "flex", flexDirection: "column", gap: 6, marginTop: 6 }}>
            {shortcuts.map((s) => (
              <div
                key={s.key}
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  padding: "6px 10px",
                  backgroundColor: "var(--paper)",
                  border: "1px solid var(--rule-light)",
                }}
              >
                <span style={{ fontSize: 12, color: "var(--ink)" }}>{s.desc}</span>
                <span
                  style={{
                    fontFamily: "var(--font-mono)",
                    fontSize: 11,
                    fontWeight: 600,
                    backgroundColor: "var(--paper-raised)",
                    border: "1px solid var(--rule)",
                    padding: "2px 8px",
                  }}
                >
                  {s.key}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Navigation Jump Keys */}
        <div>
          <span className="eyebrow" style={{ color: "var(--ink-soft)" }}>Quick Section Jumps (G + Key)</span>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 6, marginTop: 6 }}>
            {screenJumps.map((j) => (
              <div
                key={j.key}
                onClick={() => {
                  onNavigateScreen(j.id);
                  onClose();
                }}
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  padding: "6px 10px",
                  backgroundColor: "var(--paper)",
                  border: "1px solid var(--rule-light)",
                  cursor: "pointer",
                }}
              >
                <span style={{ fontSize: 11, color: "var(--ink)" }}>{j.label}</span>
                <span
                  style={{
                    fontFamily: "var(--font-mono)",
                    fontSize: 10,
                    color: "var(--ink-soft)",
                    backgroundColor: "var(--paper-raised)",
                    padding: "1px 6px",
                    border: "1px solid var(--rule-light)",
                  }}
                >
                  {j.key}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Footer Note */}
        <div style={{ marginTop: 16, textAlign: "center", fontSize: 11, color: "var(--ink-faint)", fontFamily: "var(--font-mono)" }}>
          Press [?] anytime to toggle this cheatsheet &bull; Press [Esc] to dismiss
        </div>
      </div>
    </div>
  );
};
