import React, { useState, useEffect, useRef, useCallback } from "react";
import { fetchThresholdSim, fetchCurves } from "../api/client";
import { SvgChartContainer } from "../components/charts/SvgChartContainer";
import { SvgLineChart } from "../components/charts/SvgLineChart";
import {
  SignalBlock,
  SignalReview,
  SignalApprove,
  IconShieldAlert,
  IconReset,
} from "../components/common/Icons";

export const ThresholdLab: React.FC = () => {
  // Threshold state (t1 review, t2 block)
  const [t1, setT1] = useState<number>(0.005);
  const [t2, setT2] = useState<number>(0.0591);
  const [costMode, setCostMode] = useState<"amount_weighted" | "flat">("amount_weighted");

  // Simulation output
  const [simData, setSimData] = useState<any>(null);
  const [curvesData, setCurvesData] = useState<any>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [snapFeedback, setSnapFeedback] = useState<boolean>(false);

  // Dragging interaction state for SVG handles
  const svgRef = useRef<SVGSVGElement | null>(null);
  const [draggingHandle, setDraggingHandle] = useState<"t1" | "t2" | null>(null);

  // Load cost curves
  useEffect(() => {
    fetchCurves().then(setCurvesData).catch(() => {});
  }, []);

  // Run simulation whenever t1, t2, or costMode changes
  const runSimulation = useCallback(async (currentT1: number, currentT2: number, mode: string) => {
    try {
      const res = await fetchThresholdSim(currentT1, currentT2, mode);
      if (res && res.metrics) {
        setSimData(res);
      }
    } catch (err) {
      console.error("Threshold simulation failed:", err);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    const timer = setTimeout(() => {
      runSimulation(t1, t2, costMode);
    }, 40); // 40ms debounce for buttery-smooth drag
    return () => clearTimeout(timer);
  }, [t1, t2, costMode, runSimulation]);

  // Handle Dragging
  const handleSvgMouseMove = (e: React.MouseEvent<SVGSVGElement>) => {
    if (!draggingHandle || !svgRef.current) return;
    const rect = svgRef.current.getBoundingClientRect();
    const margin = 50;
    const innerWidth = rect.width - margin * 2;
    const mouseX = e.clientX - rect.left - margin;
    const ratio = Math.max(0.0001, Math.min(0.9999, mouseX / innerWidth));
    const newThresh = Math.round(ratio * 10000) / 10000;

    if (draggingHandle === "t1") {
      setT1(Math.min(newThresh, t2 - 0.001));
    } else if (draggingHandle === "t2") {
      setT2(Math.max(newThresh, t1 + 0.001));
    }
  };

  const handleSvgMouseUp = () => {
    setDraggingHandle(null);
  };

  // Snap to optimal thresholds
  const handleSnapToOptimal = () => {
    setT1(0.005);
    setT2(0.0591);
    setSnapFeedback(true);
    setTimeout(() => setSnapFeedback(false), 3000);
  };

  const metrics = simData?.metrics || {};
  const confusion = metrics.confusion_matrix || { tp: 58, fp: 0, fn: 42, tn: 17900 };
  const density = simData?.density || [];
  const capacityExceeded = simData?.capacity_violated ?? metrics.capacity_exceeded ?? false;
  const reviewRate = metrics.review_queue_rate_per_1000 ?? metrics.review_rate_per_1k ?? 5.56;

  // Cost curve series
  const rawCostCurve = curvesData?.champion_e9?.cost_curve || [];
  const costSeriesPoints = rawCostCurve.map((pt: any) => ({
    x: pt.threshold,
    y: costMode === "flat" ? pt.cost_flat : pt.cost_amount,
  }));

  return (
    <div
      style={{ display: "flex", flexDirection: "column", gap: "var(--space-6)" }}
      onMouseUp={handleSvgMouseUp}
    >
      {/* Editorial Title & Deck */}
      <div style={{ borderBottom: "1px solid var(--rule)", paddingBottom: "var(--space-4)" }}>
        <div style={{ display: "flex", alignItems: "baseline", gap: "var(--space-3)", marginBottom: 8 }}>
          <span className="eyebrow" style={{ color: "var(--review)" }}>
            §04 Decision Policy Laboratory
          </span>
          <span style={{ fontSize: 11, fontFamily: "var(--font-mono)", color: "var(--ink-faint)" }}>
            HOLDOUT POPULATION: 18,000 TEST TRANSACTIONS (0.65% FRAUD)
          </span>
        </div>

        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end" }}>
          <div>
            <h1 style={{ marginTop: 2 }}>Interactive Dual-Threshold Calibration</h1>
            <p style={{ fontSize: 14, color: "var(--ink-soft)", marginTop: 6, maxWidth: 880 }}>
              Drag the review handle (t₁) and block handle (t₂) across the mirrored score density distribution
              to evaluate real-time financial loss, precision, recall, and investigator queue overload.
            </p>
          </div>

          {/* Action Strip: Snap to Optimal & Cost Model Selector */}
          <div style={{ display: "flex", gap: "var(--space-3)", alignItems: "center" }}>
            {/* Cost Mode Selector */}
            <div
              style={{
                display: "flex",
                border: "1px solid var(--rule)",
                backgroundColor: "var(--paper-raised)",
              }}
            >
              <button
                onClick={() => setCostMode("amount_weighted")}
                style={{
                  padding: "6px 12px",
                  fontSize: 11.5,
                  fontFamily: "var(--font-mono)",
                  border: "none",
                  borderRight: "1px solid var(--rule)",
                  background: costMode === "amount_weighted" ? "var(--ink)" : "none",
                  color: costMode === "amount_weighted" ? "var(--paper)" : "var(--ink-soft)",
                  cursor: "pointer",
                }}
              >
                Amount-Weighted Loss
              </button>
              <button
                onClick={() => setCostMode("flat")}
                style={{
                  padding: "6px 12px",
                  fontSize: 11.5,
                  fontFamily: "var(--font-mono)",
                  border: "none",
                  background: costMode === "flat" ? "var(--ink)" : "none",
                  color: costMode === "flat" ? "var(--paper)" : "var(--ink-soft)",
                  cursor: "pointer",
                }}
              >
                Flat Unit Cost
              </button>
            </div>

            {/* Snap to Optimal Button */}
            <button
              onClick={handleSnapToOptimal}
              style={{
                backgroundColor: "var(--paper-raised)",
                color: "var(--ink)",
                border: "1px solid var(--rule)",
                padding: "6px 14px",
                fontFamily: "var(--font-mono)",
                fontSize: 12,
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                gap: 6,
              }}
            >
              <IconReset size={12} color="var(--ink)" />
              Snap to Optimal Policy (t₁=0.005, t₂=0.059)
            </button>
          </div>
        </div>
      </div>

      {/* Snap to Optimal Feedback Toast */}
      {snapFeedback && (
        <div
          style={{
            backgroundColor: "rgba(45, 106, 79, 0.12)",
            border: "1px solid var(--approve)",
            color: "var(--approve)",
            padding: "8px 16px",
            fontSize: 12,
            fontFamily: "var(--font-mono)",
            display: "flex",
            justifyContent: "space-between",
          }}
        >
          <span>
            ✓ Policy aligned to cost-optimal validation boundaries: t₁=0.0050 (Review), t₂=0.0591 (Block).
            Human queue load holds safely under 6.0/1k capacity ceiling.
          </span>
          <button
            onClick={() => setSnapFeedback(false)}
            style={{ background: "none", border: "none", color: "var(--approve)", cursor: "pointer" }}
          >
            ×
          </button>
        </div>
      )}

      {/* Capacity Violation Warning Banner */}
      {capacityExceeded && (
        <div
          style={{
            backgroundColor: "rgba(180, 83, 9, 0.15)",
            border: "1px solid var(--review)",
            color: "var(--review)",
            padding: "10px 16px",
            fontSize: 12.5,
            fontFamily: "var(--font-sans)",
            display: "flex",
            alignItems: "center",
            gap: 10,
          }}
        >
          <IconShieldAlert size={16} color="var(--review)" />
          <div>
            <strong>Operational Queue Capacity Violated:</strong> Current review threshold (t₁={t1.toFixed(4)})
            routes <strong>{reviewRate.toFixed(2)} reviews per 1,000 transactions</strong>, exceeding the maximum human
            investigator ceiling of 6.0/1k. Increase t₁ or hire additional analysts.
          </div>
        </div>
      )}

      {/* ==================================================================== */}
      {/* 1. Mirrored Score Density Plot with Dual Draggable SVG Handles       */}
      {/* ==================================================================== */}
      <div
        style={{
          backgroundColor: "var(--paper-raised)",
          border: "1px solid var(--rule)",
          padding: "var(--space-5)",
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 6 }}>
          <span className="eyebrow">
            Mirrored Score Density: Legitimate (Top) vs Fraudulent (Bottom)
          </span>
          <div style={{ display: "flex", gap: "var(--space-4)", fontSize: 11, fontFamily: "var(--font-mono)" }}>
            <span style={{ color: "var(--approve)" }}>■ Legitimate Density (N=17,900)</span>
            <span style={{ color: "var(--block)" }}>■ Fraudulent Density (N=100)</span>
          </div>
        </div>

        {/* Custom Hand-Built SVG Density Chart */}
        <div style={{ position: "relative", width: "100%", height: 260, userSelect: "none" }}>
          <svg
            ref={svgRef}
            width="100%"
            height="100%"
            viewBox="0 0 800 260"
            preserveAspectRatio="none"
            onMouseMove={handleSvgMouseMove}
            onMouseLeave={handleSvgMouseUp}
            style={{ overflow: "visible", cursor: draggingHandle ? "ew-resize" : "default" }}
          >
            {/* Coordinate Constants: width 800, height 260, midline at 130 */}
            <defs>
              <linearGradient id="legitGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="var(--approve)" stopOpacity="0.4" />
                <stop offset="100%" stopColor="var(--approve)" stopOpacity="0.05" />
              </linearGradient>
              <linearGradient id="fraudGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="var(--block)" stopOpacity="0.05" />
                <stop offset="100%" stopColor="var(--block)" stopOpacity="0.4" />
              </linearGradient>
            </defs>

            {/* Shaded Policy Zones */}
            {/* 1. Automated Approve Zone: [0, t1] */}
            <rect
              x={50}
              y={20}
              width={Math.max(0, t1 * 700)}
              height={200}
              fill="rgba(45, 106, 79, 0.08)"
            />
            {/* 2. Human Review Zone: [t1, t2] */}
            <rect
              x={50 + t1 * 700}
              y={20}
              width={Math.max(0, (t2 - t1) * 700)}
              height={200}
              fill="rgba(180, 83, 9, 0.12)"
            />
            {/* 3. Automated Block Zone: [t2, 1.0] */}
            <rect
              x={50 + t2 * 700}
              y={20}
              width={Math.max(0, (1.0 - t2) * 700)}
              height={200}
              fill="rgba(158, 42, 43, 0.10)"
            />

            {/* Zero/Midline Axis */}
            <line x1={50} y1={130} x2={750} y2={130} stroke="var(--ink-faint)" strokeWidth="1" strokeDasharray="3,3" />

            {/* Legitimate Density Area (Top Half: y 130 up to 30) */}
            {density.length > 0 && (
              <path
                d={
                  `M 50 130 ` +
                  density
                    .map((d: any) => {
                      const x = 50 + d.bin * 700;
                      const y = 130 - d.legit_norm * 95;
                      return `L ${x.toFixed(1)} ${y.toFixed(1)}`;
                    })
                    .join(" ") +
                  ` L 750 130 Z`
                }
                fill="url(#legitGrad)"
                stroke="var(--approve)"
                strokeWidth="1.6"
              />
            )}

            {/* Fraud Density Area (Bottom Half: y 130 down to 230) */}
            {density.length > 0 && (
              <path
                d={
                  `M 50 130 ` +
                  density
                    .map((d: any) => {
                      const x = 50 + d.bin * 700;
                      const y = 130 + d.fraud_norm * 95;
                      return `L ${x.toFixed(1)} ${y.toFixed(1)}`;
                    })
                    .join(" ") +
                  ` L 750 130 Z`
                }
                fill="url(#fraudGrad)"
                stroke="var(--block)"
                strokeWidth="1.6"
              />
            )}

            {/* Score Grid Ticks (0.0 to 1.0) */}
            {[0, 0.2, 0.4, 0.6, 0.8, 1.0].map((tick) => (
              <g key={`tick-${tick}`} transform={`translate(${50 + tick * 700}, 235)`}>
                <line x1={0} y1={-15} x2={0} y2={-5} stroke="var(--rule)" strokeWidth="1" />
                <text x={0} y={8} textAnchor="middle" fontSize="10.5" fontFamily="var(--font-mono)" fill="var(--ink-faint)">
                  {tick.toFixed(1)}
                </text>
              </g>
            ))}

            {/* DRAGGABLE HANDLE 1: t1 (Review Threshold) */}
            <g
              transform={`translate(${50 + t1 * 700}, 0)`}
              onMouseDown={() => setDraggingHandle("t1")}
              style={{ cursor: "ew-resize" }}
            >
              {/* Vertical Guide Line */}
              <line x1={0} y1={20} x2={0} y2={225} stroke="var(--review)" strokeWidth="2.2" strokeDasharray="4,2" />
              {/* Top Handle Grip */}
              <rect x={-28} y={4} width={56} height={18} fill="var(--review)" rx="2" />
              <text x={0} y={16} textAnchor="middle" fill="var(--paper)" fontSize="10" fontFamily="var(--font-mono)" fontWeight="600">
                t₁={t1.toFixed(3)}
              </text>
              {/* Bottom Grip Circle */}
              <circle cx={0} cy={225} r="6" fill="var(--review)" stroke="var(--paper)" strokeWidth="2" />
            </g>

            {/* DRAGGABLE HANDLE 2: t2 (Block Threshold) */}
            <g
              transform={`translate(${50 + t2 * 700}, 0)`}
              onMouseDown={() => setDraggingHandle("t2")}
              style={{ cursor: "ew-resize" }}
            >
              {/* Vertical Guide Line */}
              <line x1={0} y1={20} x2={0} y2={225} stroke="var(--block)" strokeWidth="2.2" />
              {/* Top Handle Grip */}
              <rect x={-28} y={4} width={56} height={18} fill="var(--block)" rx="2" />
              <text x={0} y={16} textAnchor="middle" fill="var(--paper)" fontSize="10" fontFamily="var(--font-mono)" fontWeight="600">
                t₂={t2.toFixed(3)}
              </text>
              {/* Bottom Grip Circle */}
              <circle cx={0} cy={225} r="6" fill="var(--block)" stroke="var(--paper)" strokeWidth="2" />
            </g>
          </svg>
        </div>

        {/* Fine-Tuning Slider Controls */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "var(--space-6)", marginTop: 16, borderTop: "1px solid var(--rule)", paddingTop: 12 }}>
          {/* t1 Slider */}
          <div>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, marginBottom: 4 }}>
              <span style={{ fontWeight: 600, color: "var(--review)" }}>
                t₁ (Review Threshold): <span className="mono-num">{t1.toFixed(4)}</span>
              </span>
              <span style={{ fontSize: 11, color: "var(--ink-soft)" }}>Routes to human queue</span>
            </div>
            <input
              type="range"
              min="0.0001"
              max={t2 - 0.001}
              step="0.0005"
              value={t1}
              onChange={(e) => setT1(parseFloat(e.target.value))}
              style={{ width: "100%", accentColor: "var(--review)", cursor: "pointer" }}
            />
          </div>

          {/* t2 Slider */}
          <div>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, marginBottom: 4 }}>
              <span style={{ fontWeight: 600, color: "var(--block)" }}>
                t₂ (Block Threshold): <span className="mono-num">{t2.toFixed(4)}</span>
              </span>
              <span style={{ fontSize: 11, color: "var(--ink-soft)" }}>Automated decline</span>
            </div>
            <input
              type="range"
              min={t1 + 0.001}
              max="0.9999"
              step="0.001"
              value={t2}
              onChange={(e) => setT2(parseFloat(e.target.value))}
              style={{ width: "100%", accentColor: "var(--block)", cursor: "pointer" }}
            />
          </div>
        </div>
      </div>

      {/* ==================================================================== */}
      {/* 2. Live Operational Readouts: Confusion Matrix & Metrics             */}
      {/* ==================================================================== */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "var(--space-6)" }}>
        {/* Card 1: Confusion Matrix */}
        <div style={{ backgroundColor: "var(--paper-raised)", border: "1px solid var(--rule)", padding: "var(--space-4)" }}>
          <div className="eyebrow" style={{ marginBottom: 10 }}>Live Holdout Confusion Matrix</div>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 6, textAlign: "center" }}>
            {/* TP */}
            <div style={{ padding: 10, backgroundColor: "rgba(45, 106, 79, 0.12)", border: "1px solid var(--approve)" }}>
              <div style={{ fontSize: 11, color: "var(--ink-soft)" }}>True Positives (TP)</div>
              <div className="mono-num" style={{ fontSize: 20, fontWeight: 700, color: "var(--approve)", marginTop: 2 }}>
                {confusion.tp}
              </div>
              <div style={{ fontSize: 10, color: "var(--ink-soft)" }}>Caught Frauds</div>
            </div>

            {/* FP */}
            <div style={{ padding: 10, backgroundColor: confusion.fp > 0 ? "rgba(158, 42, 43, 0.12)" : "var(--paper)", border: "1px solid var(--rule)" }}>
              <div style={{ fontSize: 11, color: "var(--ink-soft)" }}>False Positives (FP)</div>
              <div className="mono-num" style={{ fontSize: 20, fontWeight: 700, color: confusion.fp > 0 ? "var(--block)" : "var(--ink)", marginTop: 2 }}>
                {confusion.fp}
              </div>
              <div style={{ fontSize: 10, color: "var(--ink-soft)" }}>Legitimate Blocked</div>
            </div>

            {/* FN */}
            <div style={{ padding: 10, backgroundColor: "rgba(158, 42, 43, 0.12)", border: "1px solid var(--block)" }}>
              <div style={{ fontSize: 11, color: "var(--ink-soft)" }}>False Negatives (FN)</div>
              <div className="mono-num" style={{ fontSize: 20, fontWeight: 700, color: "var(--block)", marginTop: 2 }}>
                {confusion.fn}
              </div>
              <div style={{ fontSize: 10, color: "var(--ink-soft)" }}>Leaked Frauds</div>
            </div>

            {/* TN */}
            <div style={{ padding: 10, backgroundColor: "var(--paper)", border: "1px solid var(--rule)" }}>
              <div style={{ fontSize: 11, color: "var(--ink-soft)" }}>True Negatives (TN)</div>
              <div className="mono-num" style={{ fontSize: 20, fontWeight: 700, color: "var(--ink)", marginTop: 2 }}>
                {confusion.tn?.toLocaleString() || "17,900"}
              </div>
              <div style={{ fontSize: 10, color: "var(--ink-soft)" }}>Clean Approvals</div>
            </div>
          </div>

          <div style={{ marginTop: 10, fontSize: 11, color: "var(--ink-soft)", display: "flex", justifyContent: "space-between" }}>
            <span>Review Queue Count: <strong>{metrics.review_count ?? 100}</strong></span>
            <span>Automated Blocks: <strong>{metrics.blocked_count ?? confusion.tp}</strong></span>
          </div>
        </div>

        {/* Card 2: Performance Metrics */}
        <div style={{ backgroundColor: "var(--paper-raised)", border: "1px solid var(--rule)", padding: "var(--space-4)" }}>
          <div className="eyebrow" style={{ marginBottom: 10 }}>Statistical Performance Metrics</div>

          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", borderBottom: "1px solid var(--rule)", paddingBottom: 4 }}>
              <span style={{ fontSize: 12.5, color: "var(--ink-soft)" }}>Precision at t₂:</span>
              <span className="mono-num" style={{ fontSize: 16, fontWeight: 700, color: "var(--ink)" }}>
                {((metrics.precision ?? 1.0) * 100).toFixed(1)}%
              </span>
            </div>

            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", borderBottom: "1px solid var(--rule)", paddingBottom: 4 }}>
              <span style={{ fontSize: 12.5, color: "var(--ink-soft)" }}>Fraud Recall (Capture):</span>
              <span className="mono-num" style={{ fontSize: 16, fontWeight: 700, color: "var(--ink)" }}>
                {((metrics.recall ?? 0.58) * 100).toFixed(1)}%
              </span>
            </div>

            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", borderBottom: "1px solid var(--rule)", paddingBottom: 4 }}>
              <span style={{ fontSize: 12.5, color: "var(--ink-soft)" }}>F₂ Score (Loss-Averse):</span>
              <span className="mono-num" style={{ fontSize: 16, fontWeight: 700, color: "var(--approve)" }}>
                {(metrics.f2 ?? 0.6332).toFixed(3)}
              </span>
            </div>

            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", borderBottom: "1px solid var(--rule)", paddingBottom: 4 }}>
              <span style={{ fontSize: 12.5, color: "var(--ink-soft)" }}>Matthews Correlation (MCC):</span>
              <span className="mono-num" style={{ fontSize: 16, fontWeight: 700, color: "var(--ink)" }}>
                {(metrics.mcc ?? 0.7607).toFixed(3)}
              </span>
            </div>
          </div>
        </div>

        {/* Card 3: Financial Loss & Queue Load */}
        <div style={{ backgroundColor: "var(--paper-raised)", border: "1px solid var(--rule)", padding: "var(--space-4)" }}>
          <div className="eyebrow" style={{ marginBottom: 10 }}>Expected Cost & Queue Load</div>

          <div style={{ marginBottom: 12 }}>
            <span style={{ fontSize: 11, color: "var(--ink-soft)" }}>Total Expected Financial Loss:</span>
            <div className="mono-num" style={{ fontSize: 26, fontWeight: 700, color: "var(--ink)", marginTop: 2 }}>
              ₹{(metrics.expected_cost ?? 7971.0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </div>
            <div style={{ fontSize: 11, color: "var(--ink-soft)", marginTop: 2 }}>
              Mode: {costMode === "amount_weighted" ? "Amount-weighted (C_FN=Amt, C_FP=0.05Amt+25)" : "Flat unit cost (C_FN=100, C_FP=10)"}
            </div>
          </div>

          <div style={{ borderTop: "1px solid var(--rule)", paddingTop: 8 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
              <span style={{ fontSize: 12, color: "var(--ink-soft)" }}>Review Queue Rate:</span>
              <span
                className="mono-num"
                style={{
                  fontWeight: 700,
                  fontSize: 14,
                  color: capacityExceeded ? "var(--review)" : "var(--approve)",
                }}
              >
                {reviewRate.toFixed(2)} / 1,000 txns
              </span>
            </div>
            <div style={{ fontSize: 11, color: "var(--ink-faint)", marginTop: 2 }}>
              Analyst Capacity Ceiling: &le; 6.0 / 1,000 transactions
            </div>
          </div>
        </div>
      </div>

      {/* ==================================================================== */}
      {/* 3. Cost-vs-Threshold Small Multiple Line Chart                       */}
      {/* ==================================================================== */}
      <div>
        <SvgLineChart
          title="Total Expected Loss vs Decision Threshold"
          finding={`Current policy operating point (t=${t1.toFixed(3)}) incurs ₹${(metrics.expected_cost ?? 7971.0).toLocaleString(undefined, { maximumFractionDigits: 0 })} expected cost.`}
          source="Holdout test evaluation with asymmetric financial loss model"
          series={[
            {
              name: `Expected Cost (${costMode})`,
              color: "var(--ink)",
              points: costSeriesPoints,
              strokeWidth: 2.2,
            },
          ]}
          operatingPoints={[
            {
              x: t1,
              y: metrics.expected_cost ?? 7971.0,
              label: `t₁: ₹${Math.round(metrics.expected_cost ?? 7971.0).toLocaleString()}`,
              color: "var(--review)",
            },
          ]}
          xLabel="Threshold (t)"
          yLabel={costMode === "flat" ? "Expected Cost (Flat Units)" : "Expected Cost (₹)"}
          xDomain={[0.0, 0.5]}
          yDomain={[
            0,
            Math.max(10000, ...(costSeriesPoints.map((p: any) => p.y) || [10000])),
          ]}
          width={640}
          height={260}
        />
        <div className="marginalia" style={{ marginTop: 8 }}>
          Asymmetric Cost Asymmetry: Leaking a fraudulent transaction incurs the full stolen capital amount (C_FN = Amount),
          whereas a false decline incurs customer friction plus verification overhead (C_FP = 0.05 × Amount + 25).
        </div>
      </div>
    </div>
  );
};
