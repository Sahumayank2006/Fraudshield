# FraudShield: Master Build Progress Tracker (docs/PROGRESS.md)

> **Context Recovery Instructions**: If context is lost or you receive the prompt *"re-read PROGRESS.md and continue"*:
> 1. Re-read `docs/PROGRESS.md` (this file)
> 2. Re-read `docs/ANALYSIS.md`
> 3. Re-read `docs/DECISIONS.md`
> 4. Re-read `FRAUDSHIELD_BUILD_PROMPT.md`
> 5. Identify the **first unchecked item** below and resume execution in strict accordance with the rules.

---

## Phase Checklist & Status

| Phase | Milestone Description | Status | One-Line Note |
|---|---|:---:|---|
| **Phase 0** | Comprehensive Analysis & Foundations | [x] Complete | Analysed PDF (all 28 pages) and MD; wrote `ANALYSIS.md`, `DECISIONS.md`, and `PROGRESS.md`. Initialised git repo and created initial commit. |
| **Phase 1** | Scaffold, Data Simulator & Loaders | [x] Complete | Scaffolded config, requirements, run.py, LedgerSim simulator with 5 typologies and concept drift, ULB/PaySim loaders, DataCards, EDA artifact, and 9 passing tests. |
| **Phase 2** | Feature Engineering & Online/Batch Parity | [x] Complete | Built FeatureStore and extract_features with strict past-only rolling velocity/behavioural features; 17 passing tests proving future-invariance and 100% batch-online parity. |
| **Phase 3** | Models, E1–E10 Experiments, Hybrid & Evaluation | [x] Complete | Built E1–E10 models, imbalance resampling, K-fold OOF anomaly fusion, isotonic calibration, dual-threshold policy, 1000 bootstrap CIs, H1–H4 tests, and 25 passing test suite. |
| **Phase 4** | Explainability, Monitoring & Operations | [ ] Pending | Implement TreeSHAP explanations, reason code dictionary, PSI drift tracking, and challenger retrain/rollback. |
| **Phase 5** | FastAPI Backend, SQLite Store & SSE Engine | [ ] Pending | Build all 17+ REST endpoints, SQLite case repository, SSE replay stream, scripted attack bursts, and API test suite. |
| **Phase 6** | Frontend Foundation & Design System | [ ] Pending | Establish tokens.css, locally vendored Fraunces/IBM Plex fonts, paper light theme, layout shell, navigation, and SVG chart primitives. |
| **Phase 7** | Screen: §02 Live Desk | [ ] Pending | Streaming ledger table, volume strip, live counters, latency meter, play/pause/speed controls, attack trigger button. |
| **Phase 8** | Screen: §03 Case File | [ ] Pending | Transaction details ledger, probability gauge, SHAP waterfall, account history strip, similar cases, and SQLite action buttons. |
| **Phase 9** | Screen: §01 Briefing | [ ] Pending | Editorial headline, headline KPI ledger, champion PR curve, rules-engine baseline comparison, and marginal notes. |
| **Phase 10** | Screen: §04 Threshold Lab | [ ] Pending | Interactive dual-handle threshold slider, score distribution density, live confusion matrix, cost curve, snap-to-optimal. |
| **Phase 11** | Screen: §05 Model Lab | [ ] Pending | E1–E10 experiment table with CIs, PR vs ROC pedagogical panel, early/late drift tabs, calibration curves, and dataset selector. |
| **Phase 12** | Screen: §06 Why (Explainability) | [ ] Pending | Global SHAP summary bar & beeswarm, dependence plot picker, permutation importance cross-check, and causality caution. |
| **Phase 13** | Screen: §07 Drift & Operations | [ ] Pending | PSI feature table, score drift overlay, weekly PR tracker, retrain challenger workflow with side-by-side gate & rollback. |
| **Phase 14** | Screen: §08 Fairness & Risk | [ ] Pending | Multi-group FPR segment audit, -30% evasion probe, DPDP/RBI governance statement, human-in-the-loop review policy. |
| **Phase 15** | Screen: §09 Batch | [ ] Pending | CSV drag-and-drop, schema validation, batch scoring progress, flagged rows table with reason codes, downloadable results. |
| **Phase 16** | Screen: §10 Method (Academic Paper Page) | [ ] Pending | Five-layer architecture SVG diagram, leakage gate flow, data cards, dynamic H1–H4 hypothesis verdicts, printable CSS. |
| **Phase 17** | Screen: §11 Glossary | [ ] Pending | Formal definitions of all 13 core metrics and concepts from report Appendix C with formulas and visual explanations. |
| **Phase 18** | Screen: Present Mode & Welcome Tour | [ ] Pending | Full-screen presentation mode, 6-minute sequenced tour, keyboard navigation (`P`, `A`, `Space`), and dismissible first-run tour. |
| **Final** | Documentation, Verification & Acceptance Review | [ ] Pending | README.md, ARCHITECTURE.md, MODEL_CARD.md, DATA_CARD.md, DEMO_SCRIPT.md, VIVA_QA.md, DEMO_DAY_CHECKLIST.md, and full acceptance audit. |

---

## Detailed Screen Checklist

- [ ] **Live Desk (§02)**: Real-time SSE stream, speed controls (1x-50x), attack burst simulator, transaction drawer trigger.
- [ ] **Case File (§03)**: Form-like transaction record, SHAP waterfall, plain-English reasons, account history, persistent actions.
- [ ] **Briefing (§01)**: Dynamic editorial summary, headline metrics, PR curve with operating points, rule baseline comparison.
- [ ] **Threshold Lab (§04)**: Draggable $t_1, t_2$ handles, mirrored density plot, live cost model (flat vs amount-weighted), snap button.
- [ ] **Model Lab (§05)**: E1–E10 sortable matrix, bootstrap CIs, ROC vs PR flattery comparison, early vs late drift test, dataset switcher.
- [ ] **Why (§06)**: Global feature ranking, beeswarm plot, dependence plots, permutation importance cross-check.
- [ ] **Drift & Operations (§07)**: PSI table with status badges, score distribution drift, retrain trigger, champion vs challenger gate, rollback.
- [ ] **Fairness & Risk (§08)**: Segment FPR analysis, -30% evasion test results, privacy & compliance statements.
- [ ] **Batch (§09)**: Drag-and-drop CSV upload, validation report, flagged download with reasons, sample CSV generator.
- [ ] **Method (§10)**: 5-layer architecture SVG, 3 leakage gates, dynamic hypothesis verdicts (H1-H4), academic references, print stylesheet.
- [ ] **Glossary (§11)**: Complete definitions of all 13 concepts from report Appendix C with mathematical equations and practical notes.
- [ ] **Present Mode**: Fullscreen guided sequence, keyboard shortcuts (`P`, `A`, `Space`, `G`), cheat sheet overlay, first-run tour.

