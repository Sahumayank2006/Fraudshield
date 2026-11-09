# FraudShield: Architectural & Scientific Decision Log (docs/DECISIONS.md)

> This document formally records all architectural choices, engineering trade-offs, standard reconciliations between the academic project report (*Financial Fraud Detection Using Machine Learning*, Team 01, Version 1.0) and the master build specification (*FRAUDSHIELD_BUILD_PROMPT.md*), and value-add enhancements introduced to maximize project rigor.

---

## 1. Guiding Reconciliation Rule

As established in the project directives:
- **Implementation & System Engineering**: Follow the Master Build Prompt (*FRAUDSHIELD_BUILD_PROMPT.md*) and user priority overrides.
- **Scientific Definitions, Statistical Rigor & Viva Theory**: Follow the Academic Project Report (*Financial Fraud Detection Using Machine Learning*).
- **Personal Attributions**: All team member names and personal credentials from the PDF are strictly omitted from the product, codebase, and documentation.

---

## 2. Core Architectural & Methodological Decisions

### DECISION 001: Primary Dataset Strategy — LedgerSim vs. Public Benchmarks
- **Context**: The PDF report focuses on the ULB Credit Card Fraud dataset (284,807 txns, 492 frauds) as its primary benchmark, with PaySim as secondary. However, the report itself documents severe operational limitations of ULB: it spans only 48 hours (precluding concept drift analysis), has no customer/account identifiers (precluding velocity and rolling behavioural features), and masks all fields behind anonymized PCA components $V_1 - V_{28}$ (precluding human-interpretable business reason codes).
- **Decision**: Adopt the master build prompt's specification of **LedgerSim** as the primary demo and operational dataset. LedgerSim simulates 20,000 accounts, 1,500 merchants, 12 categories, 60 days (400,000 txns; 120,000 in fast mode), realistic diurnal and weekly spend cycles, account-level balance tracking, 5 authentic fraud typologies, concept drift injected into the final 25% of the timeline, and a realistic 7-day label-maturity delay.
- **Benchmark Compatibility**: ULB (`creditcard.csv`) and PaySim (`paysim.csv`) remain fully supported via auto-detecting data loaders in `src/data.py`. When placed in `data/raw/`, benchmark pipelines run and their results are accessible via the Model Lab dataset switcher.
- **Scientific Rationale**: Using LedgerSim enables true testing of Hypothesis H2 (drift robustness of hybrid models) and allows SHAP to produce genuine banking reason codes ("Amount 14x above user norm", "New device after password reset") while keeping the entire project 100% self-contained and reproducible offline without requiring multi-gigabyte manual downloads.

---

### DECISION 002: Frontend Architecture — Bespoke React + TypeScript vs. Streamlit
- **Context**: The PDF blueprint mentions a rapid prototype built in Streamlit (`app/dashboard.py`). The Master Build Prompt calls for "The Fraud Desk": a calm, editorial, bespoke interface built with Vite, React, TypeScript, custom CSS design tokens, and hand-crafted SVG chart components.
- **Decision**: Implement the full **Vite + React + TypeScript** single-page application and static build served directly by FastAPI.
- **Scientific & Operational Rationale**: Streamlit enforces full-page reruns on interaction and cannot achieve sub-50ms reactive Server-Sent Events (SSE) streaming, smooth continuous draggable dual-threshold updates, or bespoke typography and newspaper-grade data visualizations. The React architecture provides a professional financial operations console that meets the aesthetic and technical bar of modern production desks.

---

### DECISION 003: Deep Autoencoder Implementation & Resilient Fallback
- **Context**: The PDF defines an Autoencoder with architecture $d \to 16 \to 8 \to 4 \to 8 \to 16 \to d$, trained on legitimate transactions using PyTorch with Adam optimizer. The MD allows PyTorch CPU with an sklearn `MLPRegressor` fallback.
- **Decision**: Implement the deep autoencoder primarily in PyTorch CPU matching the exact architecture specified in the report. Provide an automatic, transparent fallback to an sklearn-based multi-layer autoencoder proxy (`MLPRegressor` predicting $x$ from $x$ with bottleneck layers) if PyTorch encounters environment wheel conflicts on Windows.
- **Scientific Rationale**: Guarantees zero runtime crashes while preserving the theoretical principle: measuring non-linear reconstruction error $\|x - \hat{x}\|_2^2$ on legitimate transaction distributions.

---

### DECISION 004: Dual-Threshold Optimization with Capacity Capping
- **Context**: The PDF describes choosing $t_1$ by unconstrained cost minimization ($C_{FN} \cdot FN + C_{FP} \cdot FP$) with $C_{FN} = 100 \times C_{FP}$, and $t_2$ where precision $\ge 0.90$. In practice, an unconstrained cost-optimal threshold on highly imbalanced data can place thousands of borderline transactions into the manual review queue, instantly overwhelming the fraud analyst team.
- **Decision**: Enforce an operational capacity ceiling in `src/policy.py`. Threshold $t_1$ is chosen to minimize expected cost subject to the constraint that the resulting review queue does not exceed a configurable analyst capacity (default: 6 reviews per 1,000 transactions). Furthermore, enforce $t_1 < t_2$ strictly. Both flat-ratio (100:1) and amount-weighted loss formulations are computed and selectable in the UI.
- **Scientific Rationale**: Bridges theoretical decision theory with operational reality. A bank cannot hire an infinite number of analysts; the review band must fit available human bandwidth.

---

### DECISION 005: Cross-Platform Execution — Windows 11 Primary Launcher
- **Context**: The target machine is Windows 11 Home (HP OmniBook 5 16, Intel Core i5-1334U, 16 GB RAM), without guaranteed WSL or Unix `make`.
- **Decision**: Establish `python run.py` as the primary cross-platform entrypoint with subcommands:
  - `python run.py setup` (creates venv, installs dependencies)
  - `python run.py train-fast` (runs fast training in <3 minutes)
  - `python run.py train` (runs full training after authorization)
  - `python run.py demo` (launches backend and serves UI)
  - `python run.py test` (executes pytest test suite)
  A standard `Makefile` is also provided for Unix/macOS portability.
- **Implementation Rationale**: Standard library `subprocess`, `sys`, and `pathlib` ensure uniform behavior across Windows PowerShell, Command Prompt, and Unix shells without platform-dependent bash scripts.

---

### DECISION 006: Local Font Bundling & Complete Offline Operation
- **Context**: The UI design requires Fraunces (display serif), IBM Plex Sans (interface sans), and IBM Plex Mono (tabular numerals). Production guidelines prohibit external CDN requests (Google Fonts, Cloudflare).
- **Decision**: Vendor fonts locally via `@fontsource` npm packages (`@fontsource/fraunces`, `@fontsource/ibm-plex-sans`, `@fontsource/ibm-plex-mono`) within the frontend repository, serving pre-packaged WOFF2 files with `font-display: swap` and local fallback stacks.
- **Design Rationale**: Guarantees instant page loads, zero layout shift (CLS), and 100% offline functionality when running demos without internet access.

---

### DECISION 007: Visual Verification Strategy — Manual Stop-and-Check
- **Context**: The MD mentions Playwright screenshot scripts (`scripts/screenshots.py`). The user instruction explicitly overrides this: *"SKIP all of that. I will check the look manually. Do not create scripts/screenshots.py or docs/screens/."*
- **Decision**: Completely exclude Playwright dependencies and automated screenshot generation. Testing will focus on:
  - Code-level testing via `pytest` (leakage, parity, metrics, policy, API).
  - TypeScript compilation check (`tsc --noEmit`).
  - Code-based design audits (reviewing CSS variables, spacing scales, contrast ratios, and semantic layouts).
  - Phased human verification after each screen is delivered.

---

### DECISION 008: Training Protocol & Pause Rule
- **Context**: Training heavy models on 400,000 transactions with Optuna hyperparameter searches can consume significant CPU resources.
- **Decision**:
  - All early phases (Phases 1 to 3 preliminary testing) will utilize `train-fast` (120,000 transactions, 10 Optuna trials).
  - Full training (`python run.py train`) will only execute after Phase 3 completion and upon explicit user confirmation following the exact prompt: *"Ready for full training. Please close all other apps (browsers, editors you do not need, etc.), plug in the charger, set Windows power mode to Best performance, then reply READY."*

---

### DECISION 009: Strict Leakage Prevention & Unit Test Verification
- **Context**: The PDF details the three most common student errors: resampling before splitting, evaluating on resampled data, and reporting accuracy/ROC-AUC alone.
- **Decision**:
  - Enforce time-ordered splitting ($70\%$ train, $15\%$ val, $15\%$ test) on raw timestamp order without shuffling.
  - Wrap SMOTE and any transformers inside `imblearn.pipeline.Pipeline`, fitting strictly on training folds.
  - Implement out-of-fold scoring for anomaly detectors on the training set so supervised models never train on overly optimistic in-sample anomaly scores.
  - Encode formal mathematical assertions into `tests/test_no_leakage.py` (verifying future data shuffling does not alter past features) and `tests/test_features_parity.py` (verifying batch vs online streaming feature equality).

---

## 3. Value-Add Enhancements (Above Baseline Spec)

The following value-add features are incorporated to elevate the system's scientific and presentation quality:

1. **Automated Hypothesis Verification Engine (`artifacts/hypotheses.json`)**:
   - Programmatically evaluates Hypotheses H1 through H4 using the actual test set outputs and outputs formal mathematical verdicts (Confirmed / Rejected with exact empirical delta) displayed on the Method screen.
2. **Pedagogical "ROC vs. PR" Demonstration Panel**:
   - Reproduces the synthetic demonstration from Figure 6 in the report, allowing faculty to toggle fraud prevalence ($\pi = 0.2\%, 1.0\%, 5.0\%$) and witness why ROC-AUC creates an illusion of high performance on imbalanced data.
3. **Regulatory Governance & Compliance Mapping**:
   - Maps FraudShield's architectural safeguards directly to India's DPDP Act 2023 and RBI Master Directions on digital payment security and model risk management.
4. **Interactive Welcome Tour in Present Mode**:
   - A guided 6-minute presentation mode with keyboard-driven walkthrough (`P`, `Space`, `A`, `G` shortcuts) and state preservation in `localStorage`.
5. **Print-Optimized Method Page**:
   - CSS `@media print` styling enabling one-click browser export of the entire §10 Method screen into an academic-style research paper PDF.

