import React, { useState } from "react";
import {
  SignalBlock,
  SignalReview,
  SignalApprove,
  IconShieldAlert,
} from "../components/common/Icons";

interface GlossaryTerm {
  id: string;
  term: string;
  category: "Metrics & Evaluation" | "Algorithms & Architecture" | "Operations & Governance" | "Data Engineering";
  definition: string;
  formula?: string;
  formulaNote?: string;
  operationalContext: string;
  implementationFile: string;
}

const GLOSSARY_TERMS: GlossaryTerm[] = [
  {
    id: "pr_auc",
    term: "PR-AUC (Precision-Recall Area Under Curve)",
    category: "Metrics & Evaluation",
    definition:
      "The definitive performance metric for heavily imbalanced fraud classification. Evaluates the trade-off between Precision (positive predictive value) and Recall (sensitivity) across all decision thresholds without being flattered by overwhelming true negative majorities.",
    formula: "PR-AUC = \\int_0^1 P(R) dR \\approx \\sum_k (R_k - R_{k-1}) P_k",
    formulaNote: "Interpolated Riemann sum of precision at successive recall thresholds.",
    operationalContext:
      "FraudShield evaluates all models (E1–E10) primarily on PR-AUC. The champion Hybrid model achieves 0.930 PR-AUC on the 18k holdout set, compared to 0.295 for unweighted Logistic Regression.",
    implementationFile: "src/evaluate.py",
  },
  {
    id: "mcc",
    term: "MCC (Matthews Correlation Coefficient)",
    category: "Metrics & Evaluation",
    definition:
      "A balanced correlation coefficient between observed and predicted binary classifications that incorporates all four confusion matrix quadrants (TP, FP, TN, FN). Returns a value between -1.0 (total disagreement) and +1.0 (perfect prediction).",
    formula: "MCC = \\frac{TP \\cdot TN - FP \\cdot FN}{\\sqrt{(TP+FP)(TP+FN)(TN+FP)(TN+FN)}}",
    formulaNote: "Denominator equals zero if any row or column sum is zero (returns 0.0).",
    operationalContext:
      "Used as the robust single-threshold benchmark indicator alongside F2 score. The champion model attains an MCC of 0.761 at operating threshold t1 = 0.0050.",
    implementationFile: "src/evaluate.py",
  },
  {
    id: "f_beta",
    term: "F-Beta Score (F_beta with beta = 2.0)",
    category: "Metrics & Evaluation",
    definition:
      "Weighted harmonic mean of Precision and Recall. Setting beta = 2.0 weights Recall twice as heavily as Precision, penalizing missed fraud events (false negatives) more severely than false friction alarms.",
    formula: "F_\\beta = (1 + \\beta^2) \\cdot \\frac{\\text{Precision} \\cdot \\text{Recall}}{(\\beta^2 \\cdot \\text{Precision}) + \\text{Recall}}",
    formulaNote: "At beta = 2: F_2 = 5 \\cdot (P \\cdot R) / (4P + R)",
    operationalContext:
      "Optimized in Threshold Lab when balancing analyst queue capacity against missed fraud liability. Champion model achieves F2 = 0.633 at operating cutoff.",
    implementationFile: "src/evaluate.py",
  },
  {
    id: "psi",
    term: "PSI (Population Stability Index)",
    category: "Operations & Governance",
    definition:
      "A quantitative metric measuring the divergence between an expected baseline distribution and an observed deployment distribution across quantile or decile bins. Identifies statistical concept and covariate drift.",
    formula: "PSI = \\sum_{i=1}^B (A_i - E_i) \\cdot \\ln\\left(\\frac{A_i}{E_i}\\right)",
    formulaNote: "B = 10 quantile bins; A_i = actual %, E_i = expected %. Standard thresholds: <0.10 Stable, 0.10-0.25 Moderate, >=0.25 Significant Shift.",
    operationalContext:
      "Monitored continuously across all 26 feature vectors and model output prediction scores in Screen §07. A score PSI >= 0.25 triggers an automated challenger retrain recommendation.",
    implementationFile: "src/monitor.py",
  },
  {
    id: "calibration",
    term: "Probability Calibration (Isotonic Regression)",
    category: "Algorithms & Architecture",
    definition:
      "The statistical process of ensuring that predicted model confidence probabilities match true empirical event frequencies: if a model outputs P = 0.80, exactly 80 out of 100 transactions must be fraudulent.",
    formula: "\\min_{m} \\sum_{i=1}^N (y_i - m(f_i))^2 \\quad \\text{subject to } m(a) \\le m(b) \\; \\forall a \\le b",
    formulaNote: "Fitted on chronological validation split to avoid target overfitting.",
    operationalContext:
      "Tree ensembles with class weighting distort raw probabilities towards 1.0. FraudShield applies isotonic regression, reducing Brier calibration loss to 0.0048.",
    implementationFile: "src/models.py",
  },
  {
    id: "cost_sensitive",
    term: "Cost-Sensitive Learning & Financial Threshold Policy",
    category: "Operations & Governance",
    definition:
      "Decision optimization where loss functions incorporate real asymmetric economic impact rather than uniform classification errors. Missed fraud incurs direct capital loss, while false alarms incur operational review and customer churn costs.",
    formula: "\\text{Loss}(t) = \\sum_{i \\in FN} \\text{Amount}_i + \\sum_{i \\in FP} (0.05 \\cdot \\text{Amount}_i + 25) + \\text{QueueCost}(t)",
    formulaNote: "Subject to human queue capacity constraint: Reviews / 1,000 txns <= 6.0.",
    operationalContext:
      "Powers Screen §04 (Threshold Lab), calculating optimal t1 = 0.0050 and t2 = 0.0591, which saves 96.8% of expected fraud costs compared to uncalibrated rules.",
    implementationFile: "src/policy.py",
  },
  {
    id: "shap",
    term: "TreeSHAP (Shapley Additive Explanations)",
    category: "Algorithms & Architecture",
    definition:
      "A game-theoretic algorithm providing exact, polynomial-time local feature attribution for decision tree ensembles. Decomposes any prediction score into the sum of contributions from each input feature plus a base value.",
    formula: "f(x) = \\phi_0 + \\sum_{j=1}^M \\phi_j(x), \\quad \\phi_j = \\sum_{S \\subseteq F \\setminus \\{j\\}} \\frac{|S|!(|F|-|S|-1)!}{|F|!} [f_x(S \\cup \\{j\\}) - f_x(S)]",
    formulaNote: "Computed in O(TLD^2) using native XGBoost margin contributions without sampling error.",
    operationalContext:
      "Powers the SVG waterfall charts and dynamic plain-English reason codes in Screen §03 (Case File) and global feature importance rankings in Screen §06.",
    implementationFile: "src/explain.py",
  },
  {
    id: "isolation_forest",
    term: "Isolation Forest (Unsupervised Anomaly Scoring)",
    category: "Algorithms & Architecture",
    definition:
      "An unsupervised ensemble of randomized isolation trees that isolates anomalous data points through random recursive partition cuts. Anomalies reside in sparse regions and require fewer tree splits to isolate, yielding shorter path lengths.",
    formula: "s(x, n) = 2^{-\\frac{E(h(x))}{c(n)}}, \\quad c(n) = 2 \\ln(n - 1) + 0.5772156649 - \\frac{2(n-1)}{n}",
    formulaNote: "h(x) = path length; c(n) = average path length of unsuccessful search in BST.",
    operationalContext:
      "Trained strictly on clean non-fraud training rows to model normal manifold geometry. The resulting iso_score serves as an input feature for Layer 3 hybrid fusion.",
    implementationFile: "src/models.py",
  },
  {
    id: "autoencoder",
    term: "Deep Autoencoder (Latent Reconstruction Error)",
    category: "Algorithms & Architecture",
    definition:
      "A symmetric neural network trained to compress high-dimensional input vectors into an information bottleneck (latent code) and reconstruct the original input. Points with high reconstruction error represent novel or anomalous patterns.",
    formula: "\\mathcal{L}_{AE}(x, x') = \\frac{1}{D} \\sum_{d=1}^D (x_d - g(f(x))_d)^2 = \\text{MSE}(x, \\hat{x})",
    formulaNote: "PyTorch CPU architecture: Linear(26 -> 16 -> 8 -> 16 -> 26) with ReLU activations.",
    operationalContext:
      "Trained on clean transactions. Its output ae_error feature detects structural and sequential behavioral shifts, boosting detection under adversarial evasion.",
    implementationFile: "src/models.py",
  },
  {
    id: "smote",
    term: "SMOTE (Synthetic Minority Over-sampling Technique)",
    category: "Data Engineering",
    definition:
      "An algorithmic data balancing method that synthesizes artificial minority class instances by finding k-nearest minority neighbors in feature space and interpolating new points along the interconnecting line segments.",
    formula: "x_{\\text{synthetic}} = x_i + \\lambda \\cdot (x_{zi} - x_i), \\quad \\lambda \\sim \\text{Uniform}(0, 1)",
    formulaNote: "Must strictly be fitted inside cross-validation pipelines (Leakage Gate 3).",
    operationalContext:
      "Evaluated in Experiment E5 and Hypothesis H3. Demonstrates that with properly tuned cost thresholds and class weights, SMOTE offers no consistent gain over class-weighted trees.",
    implementationFile: "src/imbalance.py",
  },
  {
    id: "leakage",
    term: "Data Leakage (Three Methodological Gates)",
    category: "Data Engineering",
    definition:
      "Spurious inflation of offline machine learning benchmark performance caused by introducing future information, target labels, or test set distributions into the training and feature engineering pipeline.",
    formula: "\\text{Information}(X_{\\text{train}}) \\cap \\text{Future}(t > t_{\\text{split}}) = \\emptyset",
    formulaNote: "Guaranteed by Gate 1 (Chronological Split), Gate 2 (Past-Only Deques), Gate 3 (SMOTE Isolation).",
    operationalContext:
      "Strictly enforced throughout FraudShield and mathematically verified in tests/test_no_leakage.py and tests/test_features_parity.py.",
    implementationFile: "tests/test_no_leakage.py",
  },
  {
    id: "velocity_feature",
    term: "Velocity Features (Rolling Entity State)",
    category: "Data Engineering",
    definition:
      "Dynamic statistical metrics computing transaction frequency, total capital spend, and variance over rolling historical time windows (e.g., 1 hour, 24 hours, 7 days) relative to an entity's historical baseline.",
    formula: "V_{\\Delta t}(u, t) = \\sum_{\\{i : \\text{account}_i = u, \\; t - \\Delta t \\le t_i < t\\}} \\text{Amount}_i",
    formulaNote: "Maintained in-memory using double-ended queues (deques) with sub-millisecond updates.",
    operationalContext:
      "Maintained by FeatureStore in src/features.py, generating 26 online/batch parity features that detect rapid card testing and account takeover bursts.",
    implementationFile: "src/features.py",
  },
  {
    id: "concept_drift",
    term: "Concept Drift & Covariate Shift",
    category: "Operations & Governance",
    definition:
      "The change over time in the statistical properties of the target variable (fraud patterns) or input feature distributions, causing offline trained models to lose predictive efficacy in production.",
    formula: "P_t(Y | X) \\neq P_{t+\\Delta t}(Y | X) \\quad \\text{or} \\quad P_t(X) \\neq P_{t+\\Delta t}(X)",
    formulaNote: "Simulated in the final 25% of LedgerSim transactions via amount deflation and channel shifts.",
    operationalContext:
      "Evaluated in Screen §05 (Early vs Late holdout splits) and continuously monitored in Screen §07 (Drift & Ops).",
    implementationFile: "src/monitor.py",
  },
  {
    id: "chargeback",
    term: "Chargeback & 7-Day Label Maturation Delay",
    category: "Operations & Governance",
    definition:
      "The formal payment reversal process initiated by an issuing bank when a cardholder disputes an unauthorized transaction. Serves as the primary source of verified ground-truth fraud labels in commercial banking.",
    formula: "t_{\\text{ground\\_truth}} = t_{\\text{transaction}} + \\Delta t_{\\text{maturation}}, \\quad \\Delta t_{\\text{maturation}} \\in [7, 30] \\text{ days}",
    formulaNote: "Recent unflagged transactions must be classified as 'unconfirmed' rather than clean.",
    operationalContext:
      "Enforced in Screen §07 weekly performance tracking: recent cohorts with < 7 days of maturation are shaded and excluded from final precision claims.",
    implementationFile: "src/monitor.py",
  },
  {
    id: "class_imbalance",
    term: "Class Imbalance & Positive Prevalence",
    category: "Data Engineering",
    definition:
      "The extreme skew between positive (fraud) and negative (legitimate) transaction frequencies. In payment rails, positive instances typically constitute between 0.1% and 1.0% of total volume.",
    formula: "\\pi = \\frac{N_{\\text{fraud}}}{N_{\\text{total}}} = \\frac{N_+}{N_+ + N_-} \\ll 0.01",
    formulaNote: "Requires scale_pos_weight = N_- / N_+ in gradient boosting objective functions.",
    operationalContext:
      "LedgerSim operates at pi = 0.0065 (0.65%), ULB at 0.173%, and PaySim at 0.129%. Addressed via class-weighted loss and dual-threshold routing.",
    implementationFile: "src/imbalance.py",
  },
  {
    id: "anomaly_detection",
    term: "Unsupervised Anomaly Detection",
    category: "Algorithms & Architecture",
    definition:
      "Techniques for identifying unusual patterns or rare observations that deviate substantially from the majority distribution without requiring historical ground-truth labels during training.",
    formula: "\\mathcal{A}(x) : \\mathbb{R}^D \\to [0, 1], \\quad \\text{where } \\mathcal{A}(x) > \\tau \\implies \\text{Anomaly}",
    formulaNote: "Crucial for capturing zero-day fraud typologies before chargebacks materialize.",
    operationalContext:
      "Combines Isolation Forest and Autoencoder in Layer 3 to provide defense against novel attack vectors.",
    implementationFile: "src/models.py",
  },
];

export const Glossary: React.FC = () => {
  const [selectedCategory, setSelectedCategory] = useState<string>("ALL");
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [expandedTermId, setExpandedTermId] = useState<string | null>("pr_auc");

  const categories = ["ALL", "Metrics & Evaluation", "Algorithms & Architecture", "Operations & Governance", "Data Engineering"];

  const filteredTerms = GLOSSARY_TERMS.filter((item) => {
    const matchesCategory = selectedCategory === "ALL" || item.category === selectedCategory;
    const matchesSearch =
      searchQuery.trim() === "" ||
      item.term.toLowerCase().includes(searchQuery.toLowerCase()) ||
      item.definition.toLowerCase().includes(searchQuery.toLowerCase()) ||
      item.operationalContext.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesCategory && matchesSearch;
  });

  return (
    <div className="section-container" style={{ paddingBottom: "var(--space-8)" }}>
      {/* Header Block */}
      <div style={{ marginBottom: "var(--space-6)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
          <span className="eyebrow" style={{ color: "var(--ink-soft)" }}>§11 Academic Terminology & Metric Formulas</span>
          <span className="pill" style={{ backgroundColor: "var(--paper-raised)", border: "1px solid var(--rule)" }}>
            Appendix C Reference
          </span>
        </div>
        <h1 style={{ fontFamily: "var(--font-serif)", fontSize: 28, margin: "4px 0 8px 0", letterSpacing: "-0.01em" }}>
          Glossary of Core Mathematical & Operational Concepts
        </h1>
        <p style={{ fontSize: 14, color: "var(--ink-soft)", maxWidth: 960, lineHeight: 1.55 }}>
          Formal definitions, mathematical formulations, and operational deployment mappings for all core terms
          specified in the authoritative academic report (Appendix C) and viva examination defense guidelines.
        </p>
      </div>

      {/* Filter and Search Bar */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          backgroundColor: "var(--paper-raised)",
          border: "1px solid var(--rule)",
          padding: "12px 16px",
          marginBottom: "var(--space-6)",
          gap: 12,
        }}
      >
        {/* Category Pills */}
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
          {categories.map((cat) => (
            <button
              key={cat}
              onClick={() => setSelectedCategory(cat)}
              style={{
                border: "none",
                padding: "5px 12px",
                fontSize: 11,
                fontFamily: "var(--font-mono)",
                cursor: "pointer",
                backgroundColor: selectedCategory === cat ? "var(--ink)" : "var(--paper)",
                color: selectedCategory === cat ? "var(--paper)" : "var(--ink-soft)",
                borderWidth: 1,
                borderStyle: "solid",
                borderColor: selectedCategory === cat ? "var(--ink)" : "var(--rule)",
              }}
            >
              {cat === "ALL" ? "All Terms (16)" : cat}
            </button>
          ))}
        </div>

        {/* Search Input */}
        <input
          type="text"
          placeholder="Filter concepts, formulas, or code..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          style={{
            border: "1px solid var(--rule)",
            backgroundColor: "var(--paper)",
            padding: "6px 12px",
            fontSize: 12,
            fontFamily: "var(--font-mono)",
            width: 280,
          }}
        />
      </div>

      {/* Terms Grid / Accordion Ledger */}
      <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
        {filteredTerms.map((item) => {
          const isExpanded = expandedTermId === item.id;

          return (
            <div
              key={item.id}
              style={{
                backgroundColor: "var(--paper-raised)",
                border: isExpanded ? "1px solid var(--ink)" : "1px solid var(--rule)",
                transition: "all 0.15s ease-in-out",
              }}
            >
              {/* Term Header Row */}
              <div
                onClick={() => setExpandedTermId(isExpanded ? null : item.id)}
                style={{
                  padding: "16px 20px",
                  cursor: "pointer",
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  backgroundColor: isExpanded ? "rgba(31, 94, 61, 0.03)" : "transparent",
                }}
              >
                <div>
                  <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                    <span
                      className="pill"
                      style={{
                        backgroundColor: "var(--paper)",
                        border: "1px solid var(--rule-light)",
                        fontSize: 10,
                        color: "var(--ink-faint)",
                      }}
                    >
                      {item.category}
                    </span>
                    <span style={{ fontSize: 11, fontFamily: "var(--font-mono)", color: "var(--ink-faint)" }}>
                      <code>{item.implementationFile}</code>
                    </span>
                  </div>
                  <h3 style={{ margin: 0, fontSize: 17, fontFamily: "var(--font-serif)", color: "var(--ink)" }}>
                    {item.term}
                  </h3>
                </div>

                <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                  <span style={{ fontSize: 12, fontFamily: "var(--font-mono)", color: "var(--ink-faint)" }}>
                    {isExpanded ? "▲ Collapse" : "▼ Details & Formula"}
                  </span>
                </div>
              </div>

              {/* Collapsed Brief Preview */}
              {!isExpanded && (
                <div style={{ padding: "0 20px 14px 20px", fontSize: 12, color: "var(--ink-soft)", lineHeight: 1.5 }}>
                  {item.definition.slice(0, 160)}...
                </div>
              )}

              {/* Expanded Full Content */}
              {isExpanded && (
                <div style={{ padding: "0 20px 20px 20px", borderTop: "1px solid var(--rule-light)" }}>
                  {/* Formal Definition */}
                  <div style={{ marginTop: 16 }}>
                    <span className="eyebrow" style={{ color: "var(--ink-faint)" }}>Formal Academic Definition</span>
                    <p style={{ fontSize: 13, color: "var(--ink)", lineHeight: 1.6, margin: "4px 0 12px 0" }}>
                      {item.definition}
                    </p>
                  </div>

                  {/* Mathematical Formulation (if available) */}
                  {item.formula && (
                    <div style={{ marginBottom: 16 }}>
                      <span className="eyebrow" style={{ color: "var(--ink-faint)" }}>Mathematical Equation</span>
                      <div
                        style={{
                          backgroundColor: "var(--paper)",
                          border: "1px solid var(--rule)",
                          padding: "12px 16px",
                          marginTop: 4,
                          fontFamily: "var(--font-mono)",
                          fontSize: 13,
                          color: "var(--ink)",
                          overflowX: "auto",
                        }}
                      >
                        {item.formula}
                      </div>
                      {item.formulaNote && (
                        <div style={{ fontSize: 11, color: "var(--ink-soft)", marginTop: 4, fontStyle: "italic" }}>
                          &bull; {item.formulaNote}
                        </div>
                      )}
                    </div>
                  )}

                  {/* Operational Deployment Context */}
                  <div style={{ backgroundColor: "var(--paper)", border: "1px solid var(--rule-light)", padding: "12px 14px" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 4 }}>
                      <span className="eyebrow" style={{ color: "var(--accent)" }}>FraudShield Implementation Context</span>
                    </div>
                    <p style={{ fontSize: 12, color: "var(--ink-soft)", margin: 0, lineHeight: 1.55 }}>
                      {item.operationalContext}
                    </p>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Footer Summary Notice */}
      <div style={{ marginTop: "var(--space-6)", textAlign: "center", fontSize: 12, color: "var(--ink-faint)", fontFamily: "var(--font-mono)" }}>
        Showing {filteredTerms.length} of {GLOSSARY_TERMS.length} documented academic terms &bull; Aligned with Team 01 Project Report Appendix C
      </div>
    </div>
  );
};
