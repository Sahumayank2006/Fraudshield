# FraudShield: Live Demonstration Script (`docs/DEMO_SCRIPT.md`)

> **Antigravity Presentation & Faculty Defense Runbook**  
> Minute-by-minute talk track, click-by-click UI actions, anticipated examiner questions, and a 2-minute emergency fallback script for evaluation day.

---

## 1. Quick Reference: Demo Hotkeys

| Key | Action | Purpose |
|---|---|---|
| **`P`** | Toggle Fullscreen Presentation Mode | Displays 7-step guided talk track overlay with step indicators |
| **`A`** | Inject Scripted Attack Burst | Triggers 15 micro-transactions (`card_testing`) into the live stream |
| **`Space`** | Play / Pause Stream | Freezes transaction flow to inspect a specific payment row |
| **`?`** | Toggle Keyboard Shortcuts | Displays command cheat sheet |
| **`G` + `1..0, G`** | Quick Section Jump | Instantly navigate between sections §01 through §11 |
| **`Esc`** | Dismiss Overlay | Closes modals, drawers, or presentation overlays |

---

## 2. The 6-Minute Standard Live Demo Script

```
TIMELINE SUMMARY
0:00 – 1:00  │ Screen §01 Briefing: The Production Fraud Problem & Headline KPIs
1:00 – 2:00  │ Screen §02 Live Desk: Real-Time Stream, Latency, & Two-Threshold Decisions
2:00 – 2:45  │ Attack Burst Simulation: Sub-Second Containment Telemetry
2:45 – 3:45  │ Screen §03 Case File: Exact TreeSHAP Waterfalls & SQLite Persistence
3:45 – 4:30  │ Screen §04 Threshold Lab: Cost Optimization & Human Review Capacity
4:30 – 5:15  │ Screen §05 Model Lab: E1–E10 Systematic Matrix & ROC Flattery
5:15 – 6:00  │ Screen §07 Drift & Operations: PSI Surveillance & Challenger Rollback
```

---

### Minute 0:00 – 1:00: Screen §01 Executive Briefing
- **UI Navigation**: Click **§01 Briefing** on the left rail (or press `G` then `1`).
- **What to Click**: Point cursor to the 4-column KPI ledger.
- **What to Say**:
  > *"Good morning, members of the evaluation committee. Today we present FraudShield, a production-grade machine learning system designed to solve three systemic failures in financial fraud prevention: future data leakage, probability miscalibration, and uncalibrated decision thresholds.*
  > *In commercial payment rails, fraud is rare—under 0.65% prevalence—yet highly asymmetric in cost. On an 18,000-transaction chronological holdout test set, FraudShield achieves a Precision-Recall AUC of 0.930, a Recall at 90% precision of 58.0%, and saves 96.8% of expected fraud losses relative to traditional rule-based baselines.*
  > *Notice our Precision-Recall curve: while traditional logistic and single-tree baselines collapse under high precision requirements, our hybrid anomaly fusion architecture maintains robust operational detection."*
- **Anticipated Question**: *"Why is your PR-AUC 0.930 but Recall@P90 is 58%?"*
  - **Your Answer**: *"Because in commercial payment authorization, we enforce a strict 90% precision constraint ($t_2 = 0.0591$) before automatically blocking transactions. Catching 58% of all fraud with 9 out of 10 blocks being truly fraudulent provides massive financial defense without generating customer-facing false declines."*

---

### Minute 1:00 – 2:00: Screen §02 Live Desk
- **UI Navigation**: Click **§02 Live Desk** on the left rail (or press `G` then `2`).
- **What to Click**: Adjust speed slider between $1\times$ and $10\times$; point to the live probability meter and latency gauge in the header.
- **What to Say**:
  > *"Here on the Live Desk, transactions stream continuously via Server-Sent Events (SSE). Every single transaction is evaluated end-to-end: feature extraction via our in-memory FeatureStore, model inference, and decision routing.*
  > *Observe our live latency meter: median scoring latency is approximately 3.2 milliseconds, well within standard Visa and Mastercard 50-millisecond authorization SLAs.*
  > *Notice our accessible three-way decision policy: Green circles indicate approved transactions (P < 0.0050); Amber squares indicate review holds routed to step-up 2FA (t1 <= P < t2); and Crimson solid squares indicate high-confidence automated blocks (P >= 0.0591)."*
- **Anticipated Question**: *"Is this mock data running in the browser?"*
  - **Your Answer**: *"No. Every transaction is streamed from a live FastAPI backend over SSE, scored in real-time by a compiled XGBoost and PyTorch Autoencoder pipeline running in Python."*

---

### Minute 2:00 – 2:45: Attack Burst Injection & Containment Telemetry
- **UI Navigation**: Stay on **§02 Live Desk**.
- **What to Click**: Click the **Card Testing Attack [A]** trigger button (or press `A`).
- **What to Say**:
  > *"To demonstrate real-time defense against active fraud rings, I will now inject a scripted attack burst—15 rapid card-testing micro-transactions.*
  > *Watch the stream and the top containment banner: as the attack arrives, our rolling 1-hour and 24-hour velocity features instantly detect the rapid repetition. The model probability spikes from 0.02 to over 0.85.*
  > *Look at the containment banner: Time-to-first-block was achieved in under 100 milliseconds, and the system automatically contained the attack, preventing capital drain while preserving normal legitimate transactions."*

---

### Minute 2:45 – 3:45: Screen §03 Case File
- **UI Navigation**: Click **Inspect Case** on any blocked transaction row in the Live Desk (or press `G` then `3`).
- **What to Click**: Point to the dual-threshold score gauge, hover over the TreeSHAP waterfall bars, and click "Confirm Fraud".
- **What to Say**:
  > *"When an investigator investigates an alert, black-box scores are legally and operationally unacceptable under the DPDP Act and RBI guidelines. FraudShield provides complete mathematical explainability.*
  > *Here is our transaction dossier. This hand-built SVG waterfall chart displays exact Shapley feature attributions computed via native TreeSHAP in O(TLD^2) polynomial time. It decomposes the log-odds margin into specific positive risk drivers—such as log transaction scale and device novelty—and negative mitigating factors.*
  > *Beneath the chart, each Shapley value is translated into dynamic plain-English reason codes for investigators and customer support. Finally, when an analyst clicks 'Confirm Fraud', the disposition persists atomically to SQLite for regulatory auditability."*

---

### Minute 3:45 – 4:30: Screen §04 Threshold Lab
- **UI Navigation**: Click **§04 Threshold Lab** on the left rail (or press `G` then `4`).
- **What to Click**: Drag the $t_1$ and $t_2$ handles on the mirrored density plot; click **"Snap to Optimal Policy"**.
- **What to Say**:
  > *"A critical flaw in standard machine learning projects is assuming a default 0.50 probability cutoff. In Threshold Lab, we demonstrate cost-optimal decision theory.*
  > *This mirrored score density plot contrasts legitimate transactions curving upward in green against fraudulent transactions curving downward in crimson. As I drag the thresholds, our 2x2 confusion matrix and expected financial cost recalculate live.*
  > *Notice the yellow capacity banner: our operational policy strictly enforces that the human review queue rate cannot exceed 6.0 reviews per 1,000 transactions to prevent investigator overload.*
  > *Clicking 'Snap to Optimal Policy' automatically restores our mathematically proven cost-minimal thresholds: t1 = 0.0050 and t2 = 0.0591, reducing total financial loss by over 96%."*

---

### Minute 4:30 – 5:15: Screen §05 Model Lab
- **UI Navigation**: Click **§05 Model Lab** on the left rail (or press `G` then `5`).
- **What to Click**: Sort columns by PR-AUC; click the **ROC vs PR Flattery** diagnostic tab.
- **What to Say**:
  > *"In Model Lab, we present our systematic experimental matrix across models E1 through E10, all evaluated with 1,000 bootstrap confidence intervals on the chronological holdout set.*
  > *Notice our diagnostic tab on ROC vs PR curves. In extreme 0.65% fraud imbalance, ROC-AUC gives a misleading 0.999 score because the massive legitimate class dilutes the false positive rate denominator. Precision-Recall AUC exposes the true operational precision.*
  > *Our ablation study proves that adding unsupervised Isolation Forest and Deep Autoencoder features boosts adversarial robustness without inflating false alarms."*

---

### Minute 5:15 – 6:00: Screen §07 Drift & Operations
- **UI Navigation**: Click **§07 Drift & Ops** on the left rail (or press `G` then `7`).
- **What to Click**: Point to the PSI surveillance table and click **"Train Challenger Model"**.
- **What to Say**:
  > *"Finally, we address operational production surveillance in Screen §07. FraudShield monitors decile Population Stability Index (PSI) across all 26 feature vectors.*
  > *Crucially, we enforce a mandatory 7-Day Ground Truth Maturation Delay: because chargebacks take 7 to 30 days to clear, recent unflagged transactions cannot be assumed innocent. Our weekly performance tracking explicitly shades recent unconfirmed cohorts.*
  > *When drift occurs, an analyst clicks 'Train Challenger Model'. The system retrains a model on updated mature data, runs side-by-side validation gating against the active champion, and supports instant atomic rollback if a regression is detected.*
  > *Thank you. We welcome your questions."*

---

## 3. The 2-Minute Emergency Fallback Script

Use this compressed script if the evaluators or committee allocate only two minutes:

1. **Minute 0:00 – 0:45 (Briefing & Live Stream)**:
   - Start on **§01 Briefing**. Highlight: *"FraudShield achieves 0.930 PR-AUC and 96.8% expected cost reduction on an 18k holdout set under strict chronological splitting."*
   - Switch to **§02 Live Desk** (`G 2`). Show live SSE transactions at $3.2$ ms latency. Press **`A`** to inject a card testing attack burst and show instant sub-100ms containment.
2. **Minute 0:45 – 1:30 (Case File & Threshold Lab)**:
   - Jump to **§03 Case File** (`G 3`). Show the hand-crafted SVG TreeSHAP waterfall and dynamic reason codes. Click *Confirm Fraud* to prove SQLite persistence.
   - Jump to **§04 Threshold Lab** (`G 4`). Drag the threshold handles on the mirrored density plot, show the capacity check ($\le 6.0/1\text{k}$), and click *Snap to Optimal Policy*.
3. **Minute 1:30 – 2:00 (Governance & Rollback)**:
   - Jump to **§07 Drift & Ops** (`G 7`). Show decile PSI tracking, explain the 7-day maturation embargo, and demonstrate one-click challenger promotion and rollback.
