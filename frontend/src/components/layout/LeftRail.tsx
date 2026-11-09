import React from "react";

export type ScreenId =
  | "briefing"
  | "live"
  | "case"
  | "threshold"
  | "model"
  | "why"
  | "drift"
  | "fairness"
  | "batch"
  | "method"
  | "glossary";

interface NavItem {
  id: ScreenId;
  sectionNum: string;
  label: string;
  badge?: string;
}

const NAV_ITEMS: NavItem[] = [
  { id: "briefing", sectionNum: "§01", label: "Briefing" },
  { id: "live", sectionNum: "§02", label: "Live Desk" },
  { id: "case", sectionNum: "§03", label: "Case File" },
  { id: "threshold", sectionNum: "§04", label: "Threshold Lab" },
  { id: "model", sectionNum: "§05", label: "Model Lab" },
  { id: "why", sectionNum: "§06", label: "Why (SHAP)" },
  { id: "drift", sectionNum: "§07", label: "Drift & Ops" },
  { id: "fairness", sectionNum: "§08", label: "Fairness & Risk" },
  { id: "batch", sectionNum: "§09", label: "Batch Scoring" },
  { id: "method", sectionNum: "§10", label: "Methodology" },
  { id: "glossary", sectionNum: "§11", label: "Glossary" },
];

interface LeftRailProps {
  activeScreen: ScreenId;
  onSelectScreen: (id: ScreenId) => void;
  openCasesCount?: number;
}

export const LeftRail: React.FC<LeftRailProps> = ({
  activeScreen,
  onSelectScreen,
  openCasesCount = 0,
}) => {
  return (
    <nav
      style={{
        width: "var(--rail-width)",
        minWidth: "var(--rail-width)",
        borderRight: "1px solid var(--rule)",
        backgroundColor: "var(--paper)",
        display: "flex",
        flexDirection: "column",
        justifyContent: "space-between",
        padding: "var(--space-4) 0",
        userSelect: "none",
      }}
    >
      {/* Navigation List */}
      <div>
        <div style={{ padding: "0 var(--space-4) var(--space-3)", borderBottom: "1px solid var(--rule)" }}>
          <span className="eyebrow">Desk Operations</span>
        </div>

        <ul style={{ listStyle: "none", marginTop: "var(--space-2)" }}>
          {NAV_ITEMS.map((item) => {
            const isActive = activeScreen === item.id;
            return (
              <li key={item.id}>
                <button
                  onClick={() => onSelectScreen(item.id)}
                  style={{
                    width: "100%",
                    display: "flex",
                    alignItems: "center",
                    gap: "var(--space-3)",
                    padding: "9px var(--space-4)",
                    backgroundColor: isActive ? "var(--paper-raised)" : "transparent",
                    color: isActive ? "var(--ink)" : "var(--ink-soft)",
                    fontWeight: isActive ? 600 : 400,
                    border: "none",
                    borderLeft: isActive ? "3px solid var(--block)" : "3px solid transparent",
                    borderBottom: "1px solid var(--rule)",
                    textAlign: "left",
                    cursor: "pointer",
                    fontSize: 13,
                    fontFamily: "var(--font-sans)",
                    transition: "all var(--transition-fast)",
                  }}
                >
                  <span
                    style={{
                      fontFamily: "var(--font-mono)",
                      fontSize: 11,
                      color: isActive ? "var(--block)" : "var(--ink-faint)",
                      width: 24,
                    }}
                  >
                    {item.sectionNum}
                  </span>
                  <span style={{ flex: 1 }}>{item.label}</span>
                  {item.id === "case" && openCasesCount > 0 && (
                    <span
                      style={{
                        backgroundColor: "var(--block)",
                        color: "var(--paper)",
                        fontFamily: "var(--font-mono)",
                        fontSize: 10,
                        padding: "1px 5px",
                        borderRadius: "2px",
                      }}
                    >
                      {openCasesCount}
                    </span>
                  )}
                </button>
              </li>
            );
          })}
        </ul>
      </div>

      {/* Keyboard Shortcuts Hint Bar */}
      <div style={{ padding: "var(--space-4)", borderTop: "1px solid var(--rule)", fontSize: 11, color: "var(--ink-faint)" }}>
        <p style={{ fontFamily: "var(--font-mono)", lineHeight: 1.6 }}>
          <span style={{ color: "var(--ink)" }}>[Space]</span> Pause stream<br />
          <span style={{ color: "var(--ink)" }}>[A]</span> Attack simulation<br />
          <span style={{ color: "var(--ink)" }}>[P]</span> Present mode
        </p>
      </div>
    </nav>
  );
};

