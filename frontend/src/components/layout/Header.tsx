import React from "react";
import { WordmarkMark } from "../common/Icons";

interface HeaderProps {
  theme: "light" | "dark";
  onToggleTheme: () => void;
  onEnterPresentMode: () => void;
  modelVersion?: string;
  latencyMs?: number;
  isStreamLive?: boolean;
}

export const Header: React.FC<HeaderProps> = ({
  theme,
  onToggleTheme,
  onEnterPresentMode,
  modelVersion = "v1.0-champion",
  latencyMs = 3.2,
  isStreamLive = true,
}) => {
  return (
    <header
      style={{
        height: "var(--header-height)",
        backgroundColor: "var(--paper-raised)",
        borderBottom: "1px solid var(--rule)",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        padding: "0 var(--space-6)",
        position: "sticky",
        top: 0,
        zIndex: 100,
      }}
    >
      {/* Brand Wordmark & System Badge */}
      <div style={{ display: "flex", alignItems: "center", gap: "var(--space-3)" }}>
        <WordmarkMark size={18} color="var(--block)" />
        <span
          style={{
            fontFamily: "var(--font-serif)",
            fontSize: 18,
            fontWeight: 600,
            letterSpacing: "-0.01em",
            color: "var(--ink)",
          }}
        >
          FraudShield
        </span>
        <span
          style={{
            fontSize: 11,
            color: "var(--ink-soft)",
            fontFamily: "var(--font-mono)",
            borderLeft: "1px solid var(--rule)",
            paddingLeft: "var(--space-3)",
          }}
        >
          {modelVersion} · Isotonic Calibrated
        </span>
      </div>

      {/* Telemetry & Controls */}
      <div style={{ display: "flex", alignItems: "center", gap: "var(--space-6)" }}>
        {/* Latency Meter */}
        <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)", fontSize: 12 }}>
          <span className="eyebrow">Latency:</span>
          <span className="mono-num" style={{ fontWeight: 600, color: "var(--ink)" }}>
            {latencyMs.toFixed(1)} ms
          </span>
        </div>

        {/* Live SSE Stream Status */}
        <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12 }}>
          <span
            style={{
              width: 7,
              height: 7,
              backgroundColor: isStreamLive ? "var(--approve)" : "var(--ink-faint)",
              borderRadius: "50%",
              display: "inline-block",
            }}
          />
          <span className="eyebrow" style={{ color: isStreamLive ? "var(--ink)" : "var(--ink-faint)" }}>
            Stream: {isStreamLive ? "Live" : "Paused"}
          </span>
        </div>

        {/* Theme Toggle Button */}
        <button
          onClick={onToggleTheme}
          style={{
            background: "none",
            border: "1px solid var(--rule)",
            color: "var(--ink-soft)",
            padding: "4px 8px",
            fontSize: 11,
            fontFamily: "var(--font-mono)",
            cursor: "pointer",
            borderRadius: "var(--border-radius)",
          }}
          title="Toggle Day Desk / Night Desk theme"
        >
          {theme === "light" ? "Night Desk" : "Day Desk"}
        </button>

        {/* Present Mode Button */}
        <button
          onClick={onEnterPresentMode}
          style={{
            backgroundColor: "var(--ink)",
            color: "var(--paper)",
            border: "1px solid var(--ink)",
            padding: "5px 12px",
            fontSize: 12,
            fontFamily: "var(--font-sans)",
            fontWeight: 500,
            cursor: "pointer",
            borderRadius: "var(--border-radius)",
            display: "flex",
            alignItems: "center",
            gap: 6,
          }}
        >
          <span style={{ fontFamily: "var(--font-mono)", fontSize: 10, opacity: 0.8 }}>[P]</span> Present
        </button>
      </div>
    </header>
  );
};
