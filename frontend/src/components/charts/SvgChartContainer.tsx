import React from "react";

interface SvgChartContainerProps {
  title: string;
  finding?: string;
  source?: string;
  width?: number;
  height?: number;
  children: (props: { innerWidth: number; innerHeight: number; margin: Margin }) => React.ReactNode;
}

export interface Margin {
  top: number;
  right: number;
  bottom: number;
  left: number;
}

const DEFAULT_MARGIN: Margin = { top: 20, right: 30, bottom: 35, left: 55 };

export const SvgChartContainer: React.FC<SvgChartContainerProps> = ({
  title,
  finding,
  source = "Held-out test partition · LedgerSim · n = 18,000",
  width = 640,
  height = 320,
  children,
}) => {
  const margin = DEFAULT_MARGIN;
  const innerWidth = Math.max(10, width - margin.left - margin.right);
  const innerHeight = Math.max(10, height - margin.top - margin.bottom);

  return (
    <div style={{ margin: "var(--space-4) 0" }}>
      {/* Editorial Title & Finding */}
      <div style={{ marginBottom: "var(--space-2)" }}>
        <h4 style={{ fontFamily: "var(--font-serif)", fontSize: 16, fontWeight: 500, color: "var(--ink)" }}>
          {title}
        </h4>
        {finding && (
          <p style={{ fontSize: 13, color: "var(--ink-soft)", marginTop: 2 }}>
            {finding}
          </p>
        )}
      </div>

      {/* SVG Canvas */}
      <div style={{ width: "100%", overflowX: "auto" }}>
        <svg
          viewBox={`0 0 ${width} ${height}`}
          style={{ width: "100%", height: "auto", display: "block", background: "var(--paper-raised)", border: "1px solid var(--rule)" }}
        >
          <g transform={`translate(${margin.left},${margin.top})`}>
            {children({ innerWidth, innerHeight, margin })}
          </g>
        </svg>
      </div>

      {/* Source Citation */}
      <div style={{ marginTop: 4, fontSize: 11, color: "var(--ink-faint)", fontStyle: "italic", textAlign: "right" }}>
        Source: {source}
      </div>
    </div>
  );
};

