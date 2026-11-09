import React, { useState } from "react";
import { SvgChartContainer } from "./SvgChartContainer";

export interface LineSeries {
  name: string;
  color: string;
  points: Array<{ x: number; y: number }>;
  strokeDash?: string;
  strokeWidth?: number;
}

export interface OperatingPoint {
  x: number;
  y: number;
  label: string;
  color?: string;
}

interface SvgLineChartProps {
  title: string;
  finding?: string;
  source?: string;
  series: LineSeries[];
  operatingPoints?: OperatingPoint[];
  width?: number;
  height?: number;
  xLabel?: string;
  yLabel?: string;
  xDomain?: [number, number];
  yDomain?: [number, number];
}

export const SvgLineChart: React.FC<SvgLineChartProps> = ({
  title,
  finding,
  source,
  series,
  operatingPoints = [],
  width = 640,
  height = 320,
  xLabel = "Recall",
  yLabel = "Precision",
  xDomain = [0, 1],
  yDomain = [0, 1],
}) => {
  const [hoverPt, setHoverPt] = useState<{ xVal: number; yVal: number; xPx: number; yPx: number } | null>(null);

  return (
    <SvgChartContainer title={title} finding={finding} source={source} width={width} height={height}>
      {({ innerWidth, innerHeight }) => {
        const xScale = (val: number) => {
          const clamped = Math.max(xDomain[0], Math.min(xDomain[1], val));
          return ((clamped - xDomain[0]) / (xDomain[1] - xDomain[0])) * innerWidth;
        };

        const yScale = (val: number) => {
          const clamped = Math.max(yDomain[0], Math.min(yDomain[1], val));
          return innerHeight - ((clamped - yDomain[0]) / (yDomain[1] - yDomain[0])) * innerHeight;
        };

        // Gridlines
        const xTicks = [0, 0.2, 0.4, 0.6, 0.8, 1.0];
        const yTicks = [0, 0.2, 0.4, 0.6, 0.8, 1.0];

        return (
          <>
            {/* Horizontal Gridlines */}
            {yTicks.map((t) => (
              <g key={`y-${t}`}>
                <line
                  x1={0}
                  y1={yScale(t)}
                  x2={innerWidth}
                  y2={yScale(t)}
                  stroke="var(--rule)"
                  strokeWidth="1"
                  strokeDasharray="2,3"
                />
                <text
                  x={-8}
                  y={yScale(t) + 3}
                  textAnchor="end"
                  fontSize="11"
                  fontFamily="var(--font-mono)"
                  fill="var(--ink-faint)"
                >
                  {t.toFixed(1)}
                </text>
              </g>
            ))}

            {/* Vertical Gridlines */}
            {xTicks.map((t) => (
              <g key={`x-${t}`}>
                <line
                  x1={xScale(t)}
                  y1={0}
                  x2={xScale(t)}
                  y2={innerHeight}
                  stroke="var(--rule)"
                  strokeWidth="1"
                  strokeDasharray="2,3"
                />
                <text
                  x={xScale(t)}
                  y={innerHeight + 16}
                  textAnchor="middle"
                  fontSize="11"
                  fontFamily="var(--font-mono)"
                  fill="var(--ink-faint)"
                >
                  {t.toFixed(1)}
                </text>
              </g>
            ))}

            {/* Axes Labels */}
            <text
              x={innerWidth / 2}
              y={innerHeight + 30}
              textAnchor="middle"
              fontSize="11"
              fontFamily="var(--font-sans)"
              fontWeight="600"
              fill="var(--ink-soft)"
              letterSpacing="0.05em"
              style={{ textTransform: "uppercase" }}
            >
              {xLabel}
            </text>

            <text
              transform="rotate(-90)"
              x={-innerHeight / 2}
              y={-40}
              textAnchor="middle"
              fontSize="11"
              fontFamily="var(--font-sans)"
              fontWeight="600"
              fill="var(--ink-soft)"
              letterSpacing="0.05em"
              style={{ textTransform: "uppercase" }}
            >
              {yLabel}
            </text>

            {/* Line Series Paths */}
            {series.map((s) => {
              if (!s.points || s.points.length === 0) return null;
              const pathD = s.points
                .map((pt, i) => `${i === 0 ? "M" : "L"} ${xScale(pt.x).toFixed(1)} ${yScale(pt.y).toFixed(1)}`)
                .join(" ");

              return (
                <path
                  key={s.name}
                  d={pathD}
                  fill="none"
                  stroke={s.color}
                  strokeWidth={s.strokeWidth || 2}
                  strokeDasharray={s.strokeDash}
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              );
            })}

            {/* Legend in top-right */}
            <g transform={`translate(${innerWidth - 180}, 10)`}>
              {series.map((s, idx) => (
                <g key={s.name} transform={`translate(0, ${idx * 16})`}>
                  <line x1={0} y1={-4} x2={16} y2={-4} stroke={s.color} strokeWidth="2" strokeDasharray={s.strokeDash} />
                  <text x={22} y={0} fontSize="11" fontFamily="var(--font-sans)" fill="var(--ink)">
                    {s.name}
                  </text>
                </g>
              ))}
            </g>

            {/* Operating Points */}
            {operatingPoints.map((op, idx) => {
              const cx = xScale(op.x);
              const cy = yScale(op.y);
              const opColor = op.color || "var(--ink)";
              return (
                <g key={`op-${idx}`}>
                  <line
                    x1={cx}
                    y1={cy}
                    x2={cx}
                    y2={innerHeight}
                    stroke={opColor}
                    strokeWidth="1"
                    strokeDasharray="2,2"
                    opacity={0.6}
                  />
                  <circle cx={cx} cy={cy} r="5" fill={opColor} stroke="var(--paper)" strokeWidth="2" />
                  <rect
                    x={cx - 35}
                    y={Math.max(4, cy - 22)}
                    width="70"
                    height="16"
                    fill="var(--paper-raised)"
                    stroke={opColor}
                    strokeWidth="1"
                    rx="1"
                  />
                  <text
                    x={cx}
                    y={Math.max(4, cy - 22) + 11}
                    textAnchor="middle"
                    fontSize="9.5"
                    fontFamily="var(--font-mono)"
                    fontWeight="600"
                    fill={opColor}
                  >
                    {op.label}
                  </text>
                </g>
              );
            })}

            {/* Interactive Overlay for Hover */}
            <rect
              width={innerWidth}
              height={innerHeight}
              fill="transparent"
              onMouseMove={(e) => {
                const rect = e.currentTarget.getBoundingClientRect();
                const mouseX = e.clientX - rect.left;
                const ratio = Math.max(0, Math.min(1, mouseX / innerWidth));
                const xVal = xDomain[0] + ratio * (xDomain[1] - xDomain[0]);

                // Find closest point on first series
                const first = series[0]?.points;
                if (first && first.length > 0) {
                  let closest = first[0];
                  let minDiff = Math.abs(first[0].x - xVal);
                  for (const pt of first) {
                    const diff = Math.abs(pt.x - xVal);
                    if (diff < minDiff) {
                      minDiff = diff;
                      closest = pt;
                    }
                  }
                  setHoverPt({
                    xVal: closest.x,
                    yVal: closest.y,
                    xPx: xScale(closest.x),
                    yPx: yScale(closest.y),
                  });
                }
              }}
              onMouseLeave={() => setHoverPt(null)}
              style={{ cursor: "crosshair" }}
            />

            {/* Hover Crosshair & Tooltip */}
            {hoverPt && (
              <g pointerEvents="none">
                <line x1={hoverPt.xPx} y1={0} x2={hoverPt.xPx} y2={innerHeight} stroke="var(--ink)" strokeWidth="1" strokeDasharray="3,3" />
                <line x1={0} y1={hoverPt.yPx} x2={innerWidth} y2={hoverPt.yPx} stroke="var(--ink)" strokeWidth="1" strokeDasharray="3,3" />
                <circle cx={hoverPt.xPx} cy={hoverPt.yPx} r="4" fill="var(--ink)" stroke="var(--paper)" strokeWidth="1.5" />
                <g transform={`translate(${Math.min(innerWidth - 110, hoverPt.xPx + 10)}, ${Math.max(25, hoverPt.yPx - 10)})`}>
                  <rect width="105" height="32" fill="var(--ink)" rx="1" />
                  <text x="8" y="14" fill="var(--paper)" fontSize="10" fontFamily="var(--font-mono)">
                    {xLabel}: {hoverPt.xVal.toFixed(3)}
                  </text>
                  <text x="8" y="26" fill="var(--paper)" fontSize="10" fontFamily="var(--font-mono)">
                    {yLabel}: {hoverPt.yVal.toFixed(3)}
                  </text>
                </g>
              </g>
            )}
          </>
        );
      }}
    </SvgChartContainer>
  );
};
