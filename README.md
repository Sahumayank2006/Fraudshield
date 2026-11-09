# FraudShield: Production-Grade Financial Fraud Prevention Prototype

[![Python 3.12](https://img.shields.io/badge/Python-3.12-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688.svg)](https://fastapi.tiangolo.com/)
[![React 18](https://img.shields.io/badge/React-18-61DAFB.svg)](https://react.dev/)
[![TypeScript 5.3](https://img.shields.io/badge/TypeScript-5.3-3178C6.svg)](https://www.typescriptlang.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Tests Passing](https://img.shields.io/badge/Tests-50%20Passing-brightgreen.svg)]()

> **Antigravity Technical Deliverable · Applied AI Team 01**  
> An end-to-end financial transaction fraud prevention prototype featuring hybrid anomaly fusion (Isolation Forest + Deep Autoencoder + Class-Weighted XGBoost), probability calibration, an operational two-threshold decision policy (`APPROVE | REVIEW | BLOCK`), exact TreeSHAP explainability, decile Population Stability Index (PSI) drift monitoring, and a bespoke web console (*"The Fraud Desk"*).

---

## 1. Quickstart (3 Commands to a Running Demo)

Launch the full interactive application (FastAPI backend + Vite React SPA) from a single command:

```powershell
# 1. Clone or navigate to the repository
cd "c:\Users\licsa\Downloads\fraud detaction"

# 2. Run verification test suite (verifies all 50 unit and integration tests)
python run.py test

# 3. Start unified application (API server + The Fraud Desk web console)
python run.py demo
```

Once running, open your browser to **`http://127.0.0.1:8000`**.  
Press **`P`** to enter the 6-minute guided presentation tour, or **`?`** to view all keyboard shortcuts.

---

## 2. Key Scientific Results & Systematic Experiment Matrix

All models evaluated on the **18,000-transaction chronological holdout test set** (100 fraud events, $0.556\%$ positive prevalence) strictly occurring after training ($70\%$) and validation ($15\%$) partitions ($T_{\text{train}} < T_{\text{val}} < T_{\text{test}}$), with $1,000$ bootstrap iterations:

| Experiment | Architecture / Method | PR-AUC (95% CI) | Recall @ P=0.90 | $F_2$ Score | MCC | Expected Cost (₹) | Median Latency |
|---|---|:---:|:---:|:---:|:---:|:---:|:---:|
| **E1** | Baseline Logistic Regression (Unweighted) | 0.2954 [0.245, 0.350] | 0.0% | 0.000 | 0.000 | ₹247,000 | 0.8 ms |
| **E2** | Balanced Logistic Regression (`class_weight`) | 0.5120 [0.445, 0.582] | 18.0% | 0.385 | 0.412 | ₹182,500 | 0.9 ms |
| **E3** | Balanced Random Forest (150 trees) | 0.8620 [0.812, 0.908] | 48.0% | 0.554 | 0.685 | ₹42,100 | 4.8 ms |
| **E4** | Tuned XGBoost (`scale_pos_weight=153`) | 0.9080 [0.865, 0.942] | 54.0% | 0.612 | 0.745 | ₹12,400 | 1.8 ms |
| **E5** | XGBoost + Pipeline SMOTE (Fit-Inside-Fold) | 0.9079 [0.864, 0.942] | 54.0% | 0.610 | 0.742 | ₹13,100 | 2.1 ms |
| **E6** | LightGBM Gradient Booster | 0.8950 [0.850, 0.935] | 52.0% | 0.598 | 0.730 | ₹14,800 | 1.5 ms |
| **E7** | Isolation Forest (Clean rows, unsupervised) | 0.3725 [0.315, 0.430] | 8.0% | 0.210 | 0.245 | ₹210,000 | 2.4 ms |
| **E8** | Deep Autoencoder (PyTorch CPU, latent MSE) | 0.4150 [0.355, 0.475] | 12.0% | 0.265 | 0.302 | ₹195,000 | 3.5 ms |
| **E9 (★)** | **Hybrid Anomaly Fusion (XGB + IF + AE)** | **0.9300 [0.892, 0.959]** | **58.0%** | **0.633** | **0.761** | **₹7,971** | **3.2 ms** |
| **E10** | Stacked Ensemble (Hybrid + Isotonic) | 0.9295 [0.891, 0.958] | 57.5% | 0.630 | 0.758 | ₹8,150 | 4.1 ms |

---

## 3. High-Level Architecture Overview

FraudShield is structured into **Five Decoupled Pipeline Layers**:

```
+-----------------------------------------------------------------------------------+
| LAYER 1: DATA INGESTION & LEDGERSIM SIMULATION                                    |
| 20k Accounts · 1.5k Merchants · 5 Typologies (Card Testing, CNP, ATO, Mule, APP) |
| Strict Chronological 70% / 15% / 15% Split (Gate 1: Zero Future Data Leakage)     |
+-----------------------------------------------------------------------------------+
                                      │
                                      ▼
+-----------------------------------------------------------------------------------+
| LAYER 2: STATEFUL FEATURE STORE & PARITY ENGINE                                   |
| Online/Batch Parity · Past-Only Deques (1h, 24h, 7d) (Gate 2: Temporal Invariance)|
| 26 Feature Vectors: Velocity, Balance Drains, Device Novelty, Session Entropy     |
+-----------------------------------------------------------------------------------+
                                      │
                                      ▼
+-----------------------------------------------------------------------------------+
| LAYER 3: HYBRID ANOMALY FUSION & MODEL ENSEMBLE                                   |
| Isolation Forest + PyTorch Deep Autoencoder [26-16-8-16-26] on Clean Rows         |
| K=3 Out-of-Fold (OOF) Fusion into Class-Weighted XGBoost (Gate 3: SMOTE Isolation)|
+-----------------------------------------------------------------------------------+
                                      │
                                      ▼
+-----------------------------------------------------------------------------------+
| LAYER 4: PROBABILITY CALIBRATION & DUAL-THRESHOLD POLICY                          |
| Isotonic Regression (Brier Loss: 0.0048) · Amount-Weighted Loss Optimization      |
| APPROVE (P < 0.0050) | REVIEW (0.0050 <= P < 0.0591, <=6.0/1k) | BLOCK (P>=0.0591)|
+-----------------------------------------------------------------------------------+
                                      │
                                      ▼
+-----------------------------------------------------------------------------------+
| LAYER 5: OPERATIONS, EXPLAINABILITY & DRIFT SURVEILLANCE                          |
| Exact Native TreeSHAP (O(TLD^2)) · Plain-English Reason Codes · Decile PSI Alerts |
| 7-Day Chargeback Maturation Embargo · Challenger Retrain · SQLite Desk Persistence|
+-----------------------------------------------------------------------------------+
```

---

## 4. The 11 Frontend Screens ("The Fraud Desk")

The web console is built from scratch with **React 18 + TypeScript + Vite**, hand-crafted bespoke SVGs, and zero generic CSS frameworks or emojis:

- **§01 Briefing**: Dynamic executive summary, headline KPI ledger, multi-series PR curves with marked operating points, and rules vs ML benchmark.
- **§02 Live Desk**: Real-time SSE streaming ledger, live probability meter, speed regulation ($0.5\times$ to $50\times$), scripted attack burst simulator, and containment telemetry.
- **§03 Case File**: Full transaction dossier, dual-threshold decision gauge with $95\%$ CI, hand-built SVG TreeSHAP waterfall, dynamic reason codes, and persistent SQLite analyst actions.
- **§04 Threshold Lab**: Mirrored legitimate vs fraud score density plot with dual draggable handles ($t_1, t_2$), live 2x2 confusion matrix, amount-weighted loss curves, and human capacity constraints ($\le 6.0/1\text{k}$).
- **§05 Model Lab**: Sortable E1–E10 experiment matrix, diagnostic tabs (PR, ROC flattery, calibration, drift splits, ablation), and multi-dataset switcher (LedgerSim, ULB, PaySim).
- **§06 Why (Explainability)**: Global feature ranking (`mean(|SHAP|)`), hand-crafted SVG beeswarm plot ($2,000+$ transactions), partial dependence plot picker, and causality caution.
- **§07 Drift & Operations**: Decile PSI feature surveillance table, score drift overlay, weekly ground truth tracking with 7-day maturation delay, and challenger retrain/rollback.
- **§08 Fairness & Risk**: Multi-group FPR table across 10 regions and 4 channels ($1.00$x disparity ratio), adversarial -30% amount evasion probe, and DPDP/RBI/SR 11-7 compliance statements.
- **§09 Batch Scoring**: Drag-and-drop CSV upload, schema and data type validation report, batch inference progress bar, downloadable sample CSV, and flagged CSV export.
- **§10 Methodology**: Academic paper page with 5-layer SVG diagram, 3-leakage-gate flow, DataCards, dynamic H1–H4 hypothesis verdicts, and printable stylesheet (`@media print`).
- **§11 Glossary**: Comprehensive definitions of 16 core metrics and concepts from report Appendix C with mathematical equations and search lookup.

---

## 5. CLI Execution & Commands

FraudShield provides a unified command-line dispatcher (`run.py`):

```powershell
# Run the automated test suite (all 50 unit and integration tests)
python run.py test

# Start the unified API server and web console (http://127.0.0.1:8000)
python run.py demo

# Run rapid training rehearsal (fast config: 120k records, 30 days)
python run.py train-fast

# Run heavy full training (full config: 400k records, 60 days, 1000 bootstrap CIs)
python run.py train

# Generate LedgerSim synthetic transaction parquet dataset
python run.py data
```

---

## 6. Repository Structure

```
├── api/
│   ├── main.py                 # FastAPI service with 21 REST endpoints, CORS & static SPA mounting
│   └── schemas.py              # Pydantic validation schemas
├── artifacts/                  # Verified JSON and Joblib production artifacts
│   ├── model_champion.joblib   # Active Champion Model bundle
│   ├── metrics.json            # Headline holdout evaluation metrics
│   ├── experiments.json        # E1–E10 matrix with 95% bootstrap CIs
│   ├── curves.json             # PR, ROC, calibration, and cost curves
│   ├── thresholds.json         # Optimal policy thresholds (t1=0.0050, t2=0.0591)
│   ├── shap_summary.json       # TreeSHAP importance and beeswarm coordinates
│   ├── drift_monitor.json      # Decile PSI table, score drift & weekly cohorts
│   ├── fairness.json           # Segment FPR audit and -30% evasion probe
│   ├── datacards.json          # Dataset metadata cards (LedgerSim, ULB, PaySim)
│   └── hypotheses.json         # Dynamic H1–H4 empirical test verdicts
├── data/                       # Parquet datasets and SQLite audit database
│   ├── processed/              # Parquet files (ledgersim_fast.parquet)
│   └── fraudshield.db          # Persistent SQLite database (cases, decision log)
├── docs/                       # Authoritative academic and engineering documentation
│   ├── ANALYSIS.md             # Complete 28-page PDF report analysis & gap matrix
│   ├── ARCHITECTURE.md         # Five-layer architectural specification
│   ├── MODEL_CARD.md           # Model card with fairness & caveats (Mitchell et al.)
│   ├── DATA_CARD.md            # Data card for LedgerSim, ULB & PaySim (Gebru et al.)
│   ├── DEMO_SCRIPT.md          # Minute-by-minute 6-minute live presentation script
│   ├── VIVA_QA.md              # 30 oral viva questions & verified empirical answers
│   ├── DECISIONS.md            # Architectural decision records & tradeoffs
│   ├── DEMO_DAY_CHECKLIST.md   # Pre-flight demo day verification checklist
│   └── PROGRESS.md             # Master phase progress tracker
├── frontend/                   # Bespoke React + TypeScript application
│   ├── dist/                   # Bundled production SPA (mounted into FastAPI)
│   ├── src/
│   │   ├── api/client.ts       # Typed fetch client and useSseStream hook
│   │   ├── components/         # SVG charts, icons, layout, modals, tours
│   │   ├── styles/tokens.css   # Warm paper design system & hairline rules
│   │   ├── views/              # Screens §01 through §11
│   │   └── App.tsx             # Root router, keyboard listeners & present mode
│   └── package.json            # Vite + TypeScript dependencies
├── src/                        # Core Python ML and operations engine
│   ├── simulator.py            # LedgerSim multi-agent synthetic bank generator
│   ├── data.py                 # Loaders, time-split, and DataCard generators
│   ├── features.py             # Stateful FeatureStore with online/batch parity
│   ├── imbalance.py            # Class weighting and leakage-safe pipeline SMOTE
│   ├── models.py               # E1–E10 estimators, Autoencoder, and Hybrid Detector
│   ├── evaluate.py             # Bootstrap CIs, cost curves, fairness & evasion probes
│   ├── policy.py               # Two-threshold decision policy optimization
│   ├── explain.py              # Exact polynomial TreeSHAP & dynamic reason codes
│   ├── monitor.py              # Decile PSI, 7-day maturation delay & challenger registry
│   ├── store.py                # SQLite repository for cases and decision logs
│   ├── stream.py               # Real-time SSE generator with attack burst injection
│   └── train.py                # End-to-end training pipeline orchestrator
├── tests/                      # Automated test suite (50 unit & integration tests)
├── config.py                   # Central paths, random seeds, and hyperparameters
├── run.py                      # CLI entrypoint dispatcher
├── Dockerfile                  # Production container definition
├── Makefile                    # Standard CI/CD tasks
└── requirements.txt            # Python dependencies
```

---

## 7. Authoritative Documentation Index

For deeper evaluation and oral defense, refer directly to our specialized documentation:
- [**Architecture Whitepaper (`docs/ARCHITECTURE.md`)**](file:///c:/Users/licsa/Downloads/fraud%20detaction/docs/ARCHITECTURE.md): Deep-dive into the five layers, past-only deques, and serving parity.
- [**Model Card (`docs/MODEL_CARD.md`)**](file:///c:/Users/licsa/Downloads/fraud%20detaction/docs/MODEL_CARD.md): Complete quantitative breakdown, fairness parity audit, and evasion resilience.
- [**Data Card (`docs/DATA_CARD.md`)**](file:///c:/Users/licsa/Downloads/fraud%20detaction/docs/DATA_CARD.md): Data provenance, Benford's Law distribution, and 26-feature dictionary.
- [**Viva Preparation Guide (`docs/VIVA_QA.md`)**](file:///c:/Users/licsa/Downloads/fraud%20detaction/docs/VIVA_QA.md): 30 oral defense questions and verified answers with real project figures.
- [**Live Demo Runbook (`docs/DEMO_SCRIPT.md`)**](file:///c:/Users/licsa/Downloads/fraud%20detaction/docs/DEMO_SCRIPT.md): Minute-by-minute presentation script and 2-minute emergency fallback.
- [**Pre-Flight Checklist (`docs/DEMO_DAY_CHECKLIST.md`)**](file:///c:/Users/licsa/Downloads/fraud%20detaction/docs/DEMO_DAY_CHECKLIST.md): Hardware, environment, and startup verification steps.
- [**Architectural Decisions (`docs/DECISIONS.md`)**](file:///c:/Users/licsa/Downloads/fraud%20detaction/docs/DECISIONS.md): Justification for key design judgments and technical trade-offs.
