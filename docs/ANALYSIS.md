# FraudShield: Comprehensive Academic & Technical Analysis

> **Document Purpose**: Exhaustive analysis and mapping between the academic project report (*Financial Fraud Detection Using Machine Learning: A complete study, system design and implementation blueprint for anomaly detection and classification on highly imbalanced data*, Version 1.0, October 2026) and the master build specification (*FRAUDSHIELD_BUILD_PROMPT.md*).
> 
> *Note*: In accordance with project instructions, all team member names and personal attributions have been strictly excluded.

---

## 1. Executive Summary

The project report establishes the scientific and operational foundation for **FraudShield**, a production-grade financial fraud detection engine designed to solve three fundamental challenges in digital payments:
1. **Extreme class imbalance**: Fraud represents 0.1% to 3.5% of total volume (0.173% in ULB, 0.129% in PaySim, ~0.6% in LedgerSim), rendering raw accuracy and standard ROC-AUC metrics deceptive.
2. **Asymmetric and uncertain business cost**: False negatives (missed frauds) cause direct capital loss and chargeback penalties ($C_{FN}$), while false positives (false alarms) create operational friction and analyst backlog ($C_{FP}$).
3. **Concept drift and label maturation latency**: Fraud schemes evolve rapidly (adversarial drift), while confirmed fraud chargebacks lag transaction events by 7 to 30 days.

To solve these challenges, the academic blueprint proposes a **hybrid detection architecture**:
- Unsupervised anomaly detectors (Isolation Forest and deep Autoencoder reconstruction error) fitted solely on legitimate behaviour to capture novel and unlabelled attack vectors.
- Class-weighted gradient boosting (XGBoost / LightGBM) that ingests behavioural velocity features and out-of-fold anomaly scores.
- Post-hoc probability calibration (Isotonic / Platt) ensuring that outputs represent true empirical posteriors.
- A dual-threshold operational policy ($t_1$ for analyst step-up/review, $t_2$ for automated blocking) bounded by operational capacity and cost minimization.
- Explainability via TreeSHAP and real-number translated business reason codes.
- Continuous drift monitoring using Population Stability Index (PSI) and an automated champion-challenger retraining pipeline with safe rollback.

The master build specification (*FRAUDSHIELD_BUILD_PROMPT.md*) adopts the scientific framework and elevates the execution to an enterprise-grade, offline-capable, interactive system ("The Fraud Desk") powered by FastAPI, Server-Sent Events (SSE), SQLite, and a hand-crafted Vite + React + TypeScript frontend with bespoke SVG data visualizations.

---

## 2. Complete Inventory of Academic Report Promises

### 2.1 Theoretical Formulations & Mathematical Models
- **Formal Problem Setting**: Feature space $x \in \mathbb{R}^d$, ground truth label $y \in \{0, 1\}$ with rare prior $\pi = P(y = 1) \in [0.001, 0.035]$.
- **Weighted Empirical Risk Minimization**:
  $$\mathcal{L}(\theta) = - \frac{1}{n} \sum_{i=1}^n \left[ w_1 \cdot y_i \log f(x_i) + w_0 \cdot (1 - y_i) \log (1 - f(x_i)) \right]$$
  where $w_1 / w_0 \approx N_{neg} / N_{pos}$.
- **Isolation Forest Anomaly Scoring**:
  $$s(x, n) = 2^{-\frac{\mathbb{E}[h(x)]}{c(n)}}$$
  where $h(x)$ is path length and $c(n) = 2 \ln(n - 1) + 0.5772156649 - \frac{2(n - 1)}{n}$. Trained exclusively on legitimate transactions ($y = 0$).
- **Deep Autoencoder Reconstruction Error**:
  $$\text{Score}_{AE}(x) = \|x - \hat{x}\|_2^2 = \frac{1}{d} \sum_{j=1}^d (x_j - \hat{x}_j)^2$$
  Architecture: $d \to 16 \to 8 \to 4 \to 8 \to 16 \to d$, ReLU activations, Adam optimizer ($\eta = 10^{-3}$), early stopping on validation loss, trained only on legitimate records.
- **Decision-Theoretic Cost Optimization**:
  $$\text{Cost}(\tau) = C_{FN} \cdot FN(\tau) + C_{FP} \cdot FP(\tau)$$
  $$\tau^* = \arg\min_\tau \text{Cost}(\tau)$$
  Bayes-optimal cut-off for calibrated probabilities: $\tau^* = \frac{C_{FP}}{C_{FP} + C_{FN}}$. For $C_{FN} = 100 \times C_{FP}$, $\tau^* \approx 0.0099$.
- **Population Stability Index (PSI)**:
  $$\text{PSI} = \sum_{b=1}^B (p_b - q_b) \cdot \ln\left(\frac{p_b}{q_b}\right)$$
  Binned across reference quantiles with clipping $\epsilon = 10^{-6}$. Threshold bands: $<0.10$ stable, $0.10 - 0.25$ moderate drift, $>0.25$ significant drift requiring retrain trigger.
- **TreeSHAP Additive Feature Attribution**:
  $$f(x) = \phi_0 + \sum_{j=1}^d \phi_j(x)$$
  Local explanations satisfy local accuracy, missingness, and consistency.

### 2.2 The 10 Planned Experiments (E1 to E10 Matrix)
The report prescribes an explicit ablation matrix to isolate the contribution of weighting, resampling, anomaly detection, boosting, and ensembling:
1. **E1 (Logistic Regression - Unweighted)**: Baseline floor proving the cost of ignoring severe class imbalance.
2. **E2 (Logistic Regression - Class Weighted)**: `class_weight='balanced'`, transparent linear baseline.
3. **E3 (Random Forest - Balanced Subsample)**: Bagging baseline with `class_weight='balanced_subsample'` to reduce variance without inflating false positives.
4. **E4 (XGBoost - scale_pos_weight)**: State-of-the-art tree boosting with second-order gradient steps and `scale_pos_weight = N_neg / N_pos`.
5. **E5 (XGBoost + SMOTE in CV)**: Resampling ablation (`sampling_strategy=0.2`, $k=5$) embedded strictly inside training cross-validation folds via `imblearn.pipeline.Pipeline` to test whether synthetic oversampling beats algorithmic weighting.
6. **E6 (LightGBM - Class Weighted)**: Fast histogram-based gradient boosting comparing leaf-wise growth against depth-wise XGBoost.
7. **E7 (Isolation Forest - Unsupervised)**: 300 trees, fitted on legitimate transactions only; tests performance in the absence of fraud labels.
8. **E8 (Autoencoder - Unsupervised)**: Bottleneck neural network ($d \to 16 \to 8 \to 4 \to 8 \to 16 \to d$) scoring reconstruction error on legitimate transactions.
9. **E9 (Hybrid Fusion: XGBoost + Anomaly Scores)**: Supervised XGBoost augmented with out-of-fold `iso_score` and `ae_error` feature columns.
10. **E10 (Stacked Ensemble + Calibration)**: Meta-learner (Logistic Regression) combining out-of-fold predictions from base learners (E2, E3, E4, E6, E7, E8) followed by post-hoc probability calibration (Isotonic/Platt).

### 2.3 Evaluation Metric Suite & Uncertainty Reporting
- **Primary Model Selection Metric**: PR-AUC (Average Precision, area under Precision-Recall curve).
- **Secondary & Operational Metrics**:
  - Precision: $\frac{TP}{TP + FP}$ (governs analyst alert fatigue).
  - Recall / TPR: $\frac{TP}{TP + FN}$ (governs capital protection).
  - Recall @ Precision Target ($P \ge 0.80$ and $P \ge 0.90$).
  - $F_1$ score and $F_2$ score ($\beta = 2$, weighting recall twice as heavily as precision).
  - Matthews Correlation Coefficient (MCC):
    $$\text{MCC} = \frac{TP \cdot TN - FP \cdot FN}{\sqrt{(TP + FP)(TP + FN)(TN + FP)(TN + FN)}}$$
  - Expected Financial Cost: Evaluated under both flat cost ratio ($100:1$) and actual amount-weighted loss.
  - Brier Score & Expected Calibration Error (ECE) via Reliability Diagrams.
  - Latency: Median and 95th percentile inference time per transaction in milliseconds.
- **Statistical Significance & Confidence Bounds**:
  - 95% Bootstrap Confidence Intervals ($B = 1,000$ resamples) on all test metrics.
  - Paired bootstrap test / McNemar's test for comparative model claims.

### 2.4 The Four Scientific Hypotheses (H1 to H4)
- **H1**: Gradient boosting with class weighting significantly outperforms logistic regression and unsupervised detectors on PR-AUC.
- **H2**: Adding unsupervised anomaly scores (hybrid fusion) improves recall at fixed precision ($P \ge 0.80 / 0.90$), especially on the later (drifting) portion of the time-ordered test split.
- **H3**: Resampling with SMOTE yields no statistically significant performance gain over well-tuned class weighting once decision thresholds are optimized on validation data.
- **H4**: The cost-optimal decision threshold $\tau^*$ diverges substantially from the default $0.5$ cut-off (operating typically around $0.01 - 0.08$) and delivers substantial monetary savings compared to default cut-offs or rule heuristics.

### 2.5 Figures and Visualizations in the Report
- **Figure 1**: Fraud prevalence across public datasets (ULB 0.173%, PaySim 0.129%, IEEE-CIS 3.5%).
- **Figure 2**: SMOTE synthetic point interpolation schematic between minority neighbours.
- **Figure 3**: Eight-step experimental workflow enforcing the three Leakage Gates:
  - *Gate A*: Strict time-ordered train/val/test splitting without random shuffling.
  - *Gate B*: All transformers, scalers, encoders, and resamplers fit strictly inside training folds.
  - *Gate C*: Thresholds determined on validation set and frozen before test evaluation.
- **Figure 4**: FraudShield four-layer real-time detection pipeline (Data $\to$ Features $\to$ Detection $\to$ Decision).
- **Figure 5**: Layer 5 Operations closed feedback loop (Analyst review $\to$ Feedback store $\to$ Drift monitor $\to$ Retraining trigger $\to$ Model registry).
- **Figure 6**: Comparative ROC vs. Precision-Recall curves on imbalanced data demonstrating ROC flattery.
- **Figure 7**: Dual-panel trade-off: Precision/Recall vs. Threshold alongside Expected Cost vs. Threshold showing distinct cost minima.

### 2.6 Five-Layer Architectural Model
- **Layer 1 (Data)**: Ingestion, schema validation, type enforcement, data cleaning, and time-aware splitting.
- **Layer 2 (Features)**: Stateful behavioral velocity, expanding account statistics, time cycles, balance accounting checks, and out-of-fold anomaly scoring with parity between batch training and single-event serving.
- **Layer 3 (Detection)**: Dual-branch detection (unsupervised Isolation Forest + Autoencoder, supervised tree ensembles, stacked meta-learner) with probability calibration.
- **Layer 4 (Decision)**: Asymmetric cost model producing three operational routing states:
  - $\text{Score} < t_1 \implies \textbf{APPROVE}$
  - $t_1 \le \text{Score} < t_2 \implies \textbf{REVIEW / STEP-UP}$
  - $\text{Score} \ge t_2 \implies \textbf{BLOCK}$
  Capacity constraints cap $t_1$ to available analyst headcount (e.g., maximum 6 reviews per 1,000 txns).
- **Layer 5 (Operations)**: Persistent analyst case management, feedback queue, drift surveillance (PSI), trigger-based challenger retraining, validation gating, and model registry with rollback.

### 2.7 Security, Privacy, Fairness & Operational Governance
- **Fairness Audit**: Multi-group evaluation measuring False Positive Rate (FPR) parity across geographic regions, transaction channels, and account age cohorts to prevent algorithmic discrimination.
- **Adversarial Robustness Probe**: Evasion simulation where fraudulent transaction amounts are reduced by 30% to assess detection resilience against boundary-probing attackers.
- **Data Privacy & Governance**: Adherence to the Digital Personal Data Protection (DPDP) Act 2023 (India) and Reserve Bank of India (RBI) master directions on digital payment security and model risk management.
- **Human-in-the-Loop Mandate**: Automated blocking strictly reserved for high-confidence alerts ($P \ge t_2$), with all severe interventions (account freezing, SAR filing) requiring certified analyst verification.

---

## 3. Traceability Matrix: PDF Promises vs. Master Build Prompt (MD)

| # | Academic Report Promise | MD Delivery Mechanism | Location in Code / Artifacts | Status & Alignment |
|---|------------------------|-----------------------|------------------------------|--------------------|
| 1 | Time-ordered split 70/15/15 without shuffle | MD Section 5.1 | `src/data.py` (`time_split`) | Full alignment. Untouched test set. |
| 2 | Leakage Gates A, B, C | MD Section 5.1, 7 | `src/data.py`, `src/train.py`, `tests/test_no_leakage.py` | Full alignment. Formal unit tests proving past-only features. |
| 3 | Past-only velocity & behavioural features | MD Section 5.2 | `src/features.py` | Full alignment. Strict `<` timestamp check. |
| 4 | Batch and online feature parity | MD Section 5.2 | `src/features.py` (`FeatureStore`) | Full alignment. Verified by `tests/test_features_parity.py`. |
| 5 | Isolation Forest anomaly score feature | MD Section 5.4 | `src/models.py` (`AnomalyBranch`) | Full alignment. 300 trees, legitimate-only training, OOF scores. |
| 6 | Deep Autoencoder reconstruction error | MD Section 5.4 | `src/models.py` (`AutoencoderAnomaly`) | Full alignment. PyTorch CPU $d$-16-8-4-8-16-$d$ with MLP fallback. |
| 7 | Full experiment matrix E1 to E10 | MD Section 5.3 | `src/train.py` | Full alignment. All 10 models evaluated on validation & test. |
| 8 | Early vs Late test period split | MD Section 5.3 | `src/evaluate.py`, `artifacts/experiments.json` | Full alignment. Directly validates Hypothesis H2 on drift. |
| 9 | Bootstrap 95% Confidence Intervals | MD Section 5.1, 5.3 | `src/evaluate.py` (`bootstrap_ci`) | Full alignment. 1,000 resamples per metric. |
| 10 | Probability calibration (Isotonic/Platt) | MD Section 5.4 | `src/train.py` | Full alignment. Evaluates Brier score, saves reliability curves. |
| 11 | Cost-optimal thresholds $t_1, t_2$ with capacity cap | MD Section 5.5 | `src/policy.py` | Full alignment. Written to `artifacts/thresholds.json`. |
| 12 | TreeSHAP explanations & Reason Codes | MD Section 5.6 | `src/explain.py` | Full alignment. Native `pred_contribs` + parameterized text mapping. |
| 13 | Population Stability Index (PSI) drift tracking | MD Section 5.7 | `src/monitor.py` | Full alignment. Quantile bins, 10 bins, status badges. |
| 14 | Champion-challenger retrain & rollback | MD Section 5.7 | `src/monitor.py`, `api/main.py` (`/api/retrain`, `/rollback`) | Full alignment. Side-by-side gate evaluation. |
| 15 | Segment fairness audit & Evasion probe | MD Section 5.8 | `src/evaluate.py`, `artifacts/fairness.json` | Full alignment. FPR across segments, -30% amount evasion test. |
| 16 | Five-layer REST API | MD Section 6 | `api/main.py`, `api/schemas.py` | Full alignment. 17+ endpoints, OpenAPI documentation. |
| 17 | Server-Sent Events (SSE) live ledger stream | MD Section 6, 8.3 | `src/stream.py`, `api/main.py` (`/api/stream`) | Full alignment. 1x to 50x replay speed with pause/resume. |
| 18 | Scripted attack simulation | MD Section 6, 8.3 | `src/stream.py`, `api/main.py` (`/api/stream/attack`) | Full alignment. Injects card testing, ATO, or mule bursts. |
| 19 | Persistent SQLite analyst case desk | MD Section 4, 6 | `src/store.py`, `api/main.py` (`/api/cases`) | Full alignment. Full case notes, escalation, persistent decisions. |
| 20 | Hand-crafted design system ("The Fraud Desk") | MD Section 8 | `frontend/src/styles/tokens.css`, bespoke SVG | Elevated from Streamlit to bespoke React+TypeScript application. |
| 21 | Ten dedicated screens & Present mode | MD Section 8.3 | `frontend/src/screens/*` | Full alignment. All 10 screens + full-screen presenter tour. |

---

## 4. Detailed Gap Analysis: What the MD Missed & How We Bridge It

While the Master Build Prompt (*FRAUDSHIELD_BUILD_PROMPT.md*) is comprehensive regarding software engineering and user interface design, the Academic Project Report contains specific scientific, theoretical, and educational assets that must be explicitly incorporated into the implementation:

### 4.1 Missing in MD #1: Hand-Calculated Metric Reference Verification
- **Report Section**: Section 10.3 presents a precise hypothetical worked example:
  - Input: $N = 100,000$ transactions, $N_{pos} = 200$ ($0.20\%$).
  - Results: $\text{TP} = 160, \text{FN} = 40, \text{FP} = 80, \text{TN} = 99,720$.
  - Target metrics: Accuracy $= 99.88\%$, Precision $= 0.6667$, Recall $= 0.8000$, $F_1 = 0.7273$, $F_2 = 0.7692$, $\text{FPR} = 0.0802\%$, $\text{MCC} = 0.7303$.
- **Action**: Implement exact validation in `tests/test_metrics.py` asserting that the evaluation module reproduces these exact numbers within $10^{-4}$ tolerance.

### 4.2 Missing in MD #2: Explicit Evaluation & Reporting of the 4 Formal Hypotheses
- **Report Section**: Section 15.4 defines formal hypotheses H1, H2, H3, and H4.
- **Gap in MD**: The MD mentions testing hypotheses on the Method screen, but does not provide the explicit verification criteria or programmatic logic.
- **Action**: In `src/evaluate.py`, generate a dedicated hypothesis verification artifact (`artifacts/hypotheses.json`) that computes whether:
  1. $\text{PR-AUC}(E4, E6, E9) > \text{PR-AUC}(E1, E2, E7, E8)$ with $p < 0.05$ (H1: Gradient boosting superiority).
  2. $\text{Recall@P90}_{late}(E9) - \text{Recall@P90}_{late}(E4) > \text{Recall@P90}_{early}(E9) - \text{Recall@P90}_{early}(E4)$ (H2: Anomaly branch improves drift resilience).
  3. $|\text{PR-AUC}(E5) - \text{PR-AUC}(E4)| \le \text{CI}_{\text{width}}$ or cost at optimal threshold is within 2% (H3: SMOTE does not surpass tuned class weighting).
  4. $|\tau^* - 0.5| > 0.3$ and $\text{Cost}(\tau^*) < 0.5 \times \text{Cost}(0.5)$ (H4: Cost-optimal threshold diverges from 0.5 and drastically reduces loss).
  Render these dynamic verdicts (Confirmed / Rejected with exact numerical delta) on the **§10 Method** screen.

### 4.3 Missing in MD #3: Formal Mathematical Glossary and Viva Defense Answers
- **Report Section**: Appendix B (15 Viva Questions & Model Answers), Appendix C (Glossary of 13 Core Terms), and Appendix D (15 Academic Citations).
- **Gap in MD**: The MD requires a glossary page and viva QA document, but does not specify the exact text and mathematical terminology required by the academic committee.
- **Action**:
  - Incorporate the 13 formal glossary entries from Appendix C directly into the frontend Glossary screen, augmented with visual formulas and interactive tooltips.
  - Populate `docs/VIVA_QA.md` with the 15 exact questions and model answers from Appendix B, supplemented by 15 advanced engineering questions using the exact numbers computed by our training run.
  - Embed the formal citations [1]–[15] into the Method screen and documentation.

### 4.4 Missing in MD #4: Comparative ROC-AUC vs. PR-AUC Pedagogical Demonstration
- **Report Section**: Section 10.4 and Figure 6 detail the mathematical reason why ROC-AUC flatters binary classifiers under rare-class priors ($\pi \approx 0.002$), while PR-AUC does not.
- **Gap in MD**: MD mentions showing ROC and PR curves in Model Lab, but does not explicitly structure the side-by-side comparative panel that illustrates the synthetic demonstration from Figure 6.
- **Action**: Generate `artifacts/synthetic_roc_pr_demo.json` simulating scores with $0.2\%$ positives to power the dedicated pedagogical "ROC vs PR" comparison component in the Model Lab screen.

### 4.5 Missing in MD #5: Regulatory and Compliance Architecture
- **Report Section**: Section 14 highlights compliance with India's DPDP Act 2023 and RBI guidelines on digital payments and Model Risk Management (MRM).
- **Gap in MD**: MD mentions privacy and fairness, but omits the explicit regulatory governance mappings.
- **Action**: In `docs/ARCHITECTURE.md` and the Fairness & Risk screen, include formal compliance mappings for automated decision governance, model drift thresholds, data minimization, and audit trail retention.

---

## 5. Synthesis of Data Strategies: LedgerSim vs. Public Datasets

| Dimension | Primary Dataset: LedgerSim (Built-in) | Secondary Dataset: ULB Credit Card | Secondary Dataset: PaySim |
|-----------|--------------------------------------|-----------------------------------|---------------------------|
| **Origin** | Custom synthetic bank generator (`src/simulator.py`) | Real European card transactions (Kaggle) | Synthetic mobile money simulation (Kaggle) |
| **Volume & Duration** | 400,000 txns / 60 days (Fast: 120k / 30 days) | 284,807 txns / 2 days (Sept 2013) | ~6.36M txns / 30 days (subsampled) |
| **Entities Tracked** | 20,000 accounts, 1,500 merchants, devices, IPs | Anonymised transactions only | Named origin & destination accounts |
| **Fraud Rate** | 0.50% – 0.80% (~2,000 – 3,200 frauds) | 0.173% (492 frauds) | 0.129% (8,213 frauds) |
| **Fraud Typologies** | 5 distinct patterns (Card Testing, CNP, ATO, Mule, APP) | Mixed card fraud (unlabeled typology) | TRANSFER and CASH_OUT draining |
| **Concept Drift** | Injected in final 25% (amount shift, merchant shift) | None (span is only 48 hours) | Weak temporal shift |
| **Label Latency** | 7-day maturity delay simulated | Immediate ground truth | Immediate ground truth |
| **Velocity Features** | Rich (1h/24h/7d rolling counts, sums, z-scores) | Limited (Time and Amount only, no account ID) | Strong balance-error features |
| **Interpretability** | 100% human-readable business fields | PCA components ($V_1 - V_{28}$) obscure meaning | Clear transaction types and balance fields |
| **Role in FraudShield** | **Primary operational engine**: drives live stream, attack simulation, case queue, drift, and retraining | **Benchmark comparison**: validates E1–E10 against published academic literature | **Benchmark comparison**: validates accounting balance-error features |

---

## 6. Implementation Action Plan Across Build Phases

To ensure zero drift from specifications, the findings of this analysis are directly mapped to the scheduled project phases:

- **Phase 1 (Scaffold, Simulator, Data Loaders, EDA)**:
  - Implement `LedgerSim` with all 5 fraud typologies, concept drift in the final 25%, and 7-day label maturity.
  - Implement optional auto-loaders for `creditcard.csv` and `paysim.csv` generating standardized `DataCard` metadata.
  - Implement full EDA summary outputting `artifacts/eda.json`.
- **Phase 2 (Feature Engineering & Parity)**:
  - Implement rolling velocity, expanding account statistics, time cyclicality, and balance-error features.
  - Build `FeatureStore` stateful online aggregator.
  - Formulate leak-proof tests in `tests/test_no_leakage.py` and batch-online parity in `tests/test_features_parity.py`.
- **Phase 3 (Models, Experiments E1–E10, Calibration & Policy)**:
  - Build Isolation Forest and PyTorch Autoencoder (with MLP fallback) with out-of-fold scoring on training folds.
  - Execute E1 through E10 with Optuna tuning and Isotonic/Platt calibration.
  - Compute bootstrap 95% CIs, early/late split metrics, cost-optimal $t_1$ (capacity-constrained) and $t_2$, and test the 4 formal hypotheses.
  - Implement `tests/test_metrics.py` asserting the report's worked example.
- **Phase 4 (Explainability, Monitoring & Operations)**:
  - Implement TreeSHAP extraction and real-number business reason codes.
  - Implement PSI tracking across feature quantiles and output scores.
  - Build champion-challenger retraining pipeline with rollback store.
- **Phase 5 (FastAPI Backend & SSE Live Engine)**:
  - Build all 17+ endpoints, decision logging, SQLite case store, SSE stream replay, and attack burst generator.
- **Phase 6 & Screens 7–16 (Design System & Bespoke Frontend Screens)**:
  - Implement the "The Fraud Desk" design system in light and dark palettes with Fraunces, IBM Plex Sans, and IBM Plex Mono fonts.
  - Construct all screens (§01 Briefing through §10 Method + Present Mode) featuring custom SVG charts, interactive threshold sliders, and real-time attack simulation.
- **Final Phase (Documentation & Verification)**:
  - Compile `README.md`, `ARCHITECTURE.md`, `MODEL_CARD.md`, `DATA_CARD.md`, `DEMO_SCRIPT.md`, `VIVA_QA.md` (30 questions), and `DEMO_DAY_CHECKLIST.md`.
  - Validate 100% acceptance checklist compliance.
