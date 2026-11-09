import React from "react";
import { SvgChartContainer } from "./SvgChartContainer";

export interface WaterfallStep {
  step: string;
  delta: number;
  start_value?: number;
  end_value: number;
  type: string;
}

interface SvgWaterfallProps {
  steps: WaterfallStep[];
  width?: number;
  height?: number;
  title?: string;
  finding?: string;
}

export const SvgWaterfall: React.FC<SvgWaterfallProps> = ({
  steps,
  width = 620,
  height = 300,
  title = "SHAP Waterfall Decomposition",
  finding = "How individual feature attributions shifted model prediction from base prior to final risk margin.",
}) => {
  if (!steps || steps.length === 0) {
    return (
      <div style={{ padding: "var(--space-4)", border: "1px dashed var(--rule)", color: "var(--ink-faint)" }}>
        No SHAP attribution steps available for this transaction.
      </div>
    );
  }

  // Determine domain range
  let minVal = 0.0;
  let maxVal = 0.0;
  steps.forEach((s) => {
    if (s.start_value !== undefined) {
      minVal = Math.min(minVal, s.start_value);
      maxVal = Math.max(maxVal, s.start_value);
    }
    minVal = Math.min(minVal, s.end_value);
    maxVal = Math.max(maxVal, s.end_value);
  });
  const span = Math.max(1.0, maxVal - minVal);
  const padMin = minVal - span * 0.1;
  const padMax = maxVal + span * 0.1;

  return (
    <SvgChartContainer title={title} finding={finding} width={width} height={height}>
      {({ innerWidth, innerHeight }) => {
        const barWidth = Math.max(8, (innerWidth / steps.length) * 0.65);
        const stepWidth = innerWidth / steps.length;

        const yScale = (val: number) => {
          return innerHeight - ((val - padMin) / (padMax - padMin)) * innerHeight;
        };

        const zeroY = yScale(0.0);

        return (
          <>
            {/* Zero Axis Line */}
            <line x1={0} y1={zeroY} x2={innerWidth} y2={zeroY} stroke="var(--ink-faint)" strokeWidth="1" strokeDasharray="2,2" />

            {/* Step Bars & Connectors */}
            {steps.map((st, i) => {
              const xCenter = i * stepWidth + stepWidth / 2;
              const xLeft = xCenter - barWidth / 2;

              let start = st.start_value !== undefined ? st.start_value : 0;
              let end = st.end_value;

              const yTop = yScale(Math.max(start, end));
              const yBottom = yScale(Math.min(start, end));
              const barHeight = Math.max(2, yBottom - yTop);

              let fillColor = "var(--ink-soft)";
              if (st.type === "positive") fillColor = "var(--block)";
              else if (st.type === "negative") fillColor = "var(--approve)";
              else if (st.type === "base") fillColor = "var(--info)";
              else if (st.type === "total") fillColor = "var(--ink)";

              return (
                <g key={`step-${i}`}>
                  {/* Step Connector Line to Next */}
                  {i < steps.length - 1 && (
                    <line
                      x1={xLeft}
                      y1={yScale(end)}
                      x2={xLeft + stepWidth}
                      y2={yScale(end)}
                      stroke="var(--rule)"
                      strokeWidth="1"
                      strokeDasharray="2,2"
                    />
                  )}

                  {/* Step Bar */}
                  <rect
                    x={xLeft}
                    y={yTop}
                    width={barWidth}
                    height={barHeight}
                    fill={fillColor}
                    rx="1"
                  />

                  {/* Delta Label */}
                  <text
                    x={xCenter}
                    y={yTop - 5}
                    textAnchor="middle"
                    fontSize="9.5"
                    fontFamily="var(--font-mono)"
                    fill={fillColor}
                  >
                    {st.delta > 0 ? `+${st.delta.toFixed(2)}` : st.delta !== 0 ? st.delta.toFixed(2) : ""}
                  </text>

                  {/* Step Name */}
                  <text
                    transform={`translate(${xCenter}, ${innerHeight + 14}) rotate(35)`}
                    textAnchor="start"
                    fontSize="10"
                    fontFamily="var(--font-sans)"
                    fill="var(--ink-soft)"
                  >
                    {st.step.replace(/_/g, " ").slice(0, 14)}
                  </text>
                </g>
              );
            })}
          </>
        );
      }}
    </SvgChartContainer>
  );
};

