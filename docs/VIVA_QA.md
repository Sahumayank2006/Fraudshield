# FraudShield: Comprehensive Viva Examination Q&A Guide (`docs/VIVA_QA.md`)

> **Authoritative Faculty & Oral Defense Reference**  
> Incorporates the **15 core viva questions** from the academic report (Appendix B, Page 26) answered with FraudShield's actual empirical results, supplemented by **15 advanced engineering questions** on calibration, leakage gates, adversarial probes, drift surveillance, and regulatory compliance.

---

## Part 1: Core Academic Viva Questions (From Report Appendix B)

### Q1. Why not just use accuracy?
**Answer:**  
In financial payment rails, fraud is an extreme minority event: fraud represents approximately **$0.17\%$** of ULB transactions and **$0.65\%$** in LedgerSim. A trivial dummy model that predicts "legitimate" for $100\%$ of transactions achieves **$99.35\%$ to $99.83\%$ classification accuracy**, yet detects exactly zero fraud events, resulting in total balance sheet vulnerability. Accuracy fails because it treats a false negative (a missed ₹50,000 wire theft) as mathematically equivalent to a false positive (a brief 2FA SMS challenge). Instead, FraudShield evaluates models using **PR-AUC** (0.930), **Recall at fixed precision** (Recall@P90 = 58.0%), **$F_2$ score** (0.633), **Matthews Correlation Coefficient** (MCC = 0.761), and **Expected Financial Loss** (₹7,971 vs ₹247,000 baseline).

### Q2. Why PR-AUC instead of ROC-AUC?
**Answer:**  
The False Positive Rate (FPR) in ROC-AUC has the vast legitimate class in its denominator:
$$\text{FPR} = \frac{\text{FP}}{\text{FP} + \text{TN}} = \frac{\text{FP}}{N_{\text{legitimate}}}$$
In an 18,000-transaction holdout set with 17,900 legitimate transactions, generating 180 false alarms yields an FPR of only $1.0\%$ ($0.010$), allowing the ROC-AUC curve to appear virtually flawless ($0.99977$). However, against 100 true fraud events, 180 false alarms drops Precision to an unusable $35.7\%$. Precision has False Positives directly in its denominator:
$$\text{Precision} = \frac{\text{TP}}{\text{TP} + \text{FP}}$$
PR-AUC directly reflects the operational burden on fraud investigators. As Saito and Rehmsmeier (2015) demonstrated, PR-AUC is non-flattering and exposes severe false alarm rates that ROC-AUC conceals.

### Q3. What is SMOTE and when does it fail?
**Answer:**  
SMOTE (Synthetic Minority Over-sampling Technique; Chawla et al., 2002) synthesizes artificial minority instances by finding the $k$-nearest minority neighbours in feature space and linearly interpolating new points:
$$x_{\text{synthetic}} = x_i + \lambda \cdot (x_{zi} - x_i), \quad \lambda \sim \text{Uniform}(0, 1)$$
SMOTE fails in three distinct ways:
1. **Majority Region Intrusion**: It generates artificial fraud points in regions where legitimate transactions cluster, distorting decision boundaries and increasing false positive friction.
2. **Noise Amplification**: If an outlier or mislabelled transaction is selected, SMOTE creates synthetic clusters around noise.
3. **Data Leakage**: If SMOTE is executed prior to chronological splitting, synthetic transactions interpolate across train, validation, and test partitions. In our experiments (E5 vs E4), tuning cost-optimal thresholds on class-weighted trees rendered SMOTE statistically indistinguishable on PR-AUC ($0.99913$ vs $0.99914$), while SMOTE increased total financial loss from ₹103 to ₹201.

### Q4. Why a time-ordered split instead of random $k$-fold cross-validation?
**Answer:**  
In production, a fraud model deployed at time $T$ must score transactions arriving at $t > T$. Randomized $k$-fold cross-validation randomly samples transactions throughout the dataset, allowing the model to train on transactions occurring *after* the events it is tested on. This creates severe temporal data leakage, as seasonal merchant patterns, compromised card batches, and emerging attack campaigns leak into the past. FraudShield enforces a strict **70% / 15% / 15% chronological split** ($T_{\text{train}} < T_{\text{val}} < T_{\text{test}}$). This accurately measures the model's resistance to non-stationary concept drift and degradation over time.

### Q5. Why gradient boosting (XGBoost / LightGBM) for this problem?
**Answer:**  
Financial transaction logs are heterogeneous tabular datasets containing continuous amounts, skewed power-law distributions, high-cardinality discrete categories, and complex non-linear feature interactions (e.g., high transaction amount is normal for corporate payroll accounts, but fraudulent when paired with an unfamiliar device and midnight timestamp). Gradient-boosted decision trees (XGBoost/LightGBM) excel on tabular data because they:
1. Are invariant to monotonic feature scaling (no standardization distortion).
2. Efficiently partition sparse categorical interactions without dimensional explosion.
3. Support exact cost and class weighting via `scale_pos_weight`.
4. Provide polynomial-time exact Shapley value explanations via native TreeSHAP ($O(TLD^2)$), enabling sub-5ms operational latency.

### Q6. What does the unsupervised branch add if we have labels?
**Answer:**  
Supervised models can only learn decision splits that separate known historical fraud patterns. However, financial fraud is inherently adversarial: organized syndicates continually invent novel typologies (e.g., zero-day APP social engineering scams, new money mule routing algorithms). FraudShield's Layer 3 unsupervised branch combines an **Isolation Forest** (detecting geometric sparsity) and a **PyTorch Deep Autoencoder** (measuring latent reconstruction loss). These models are trained strictly on clean legitimate transactions. When a novel attack occurs, it triggers high isolation and reconstruction error regardless of whether historical supervised trees have encountered that specific pattern. In our adversarial evasion probe, this hybrid fusion retained **$93.1\%$** of baseline recall, whereas single-layer supervised trees collapsed.

### Q7. How did you choose the operational decision thresholds?
**Answer:**  
Operating thresholds are derived strictly on the **chronological validation set** ($15\%$), with the holdout test set touched exactly once during final evaluation. Rather than using arbitrary cutoffs ($P = 0.50$), FraudShield minimizes an asymmetric economic cost function:
$$\mathcal{L}(t) = \sum_{i \in \text{FN}} \text{Amount}_i + \sum_{i \in \text{FP}} (0.05 \cdot \text{Amount}_i + 25) + \text{QueueCost}(t)$$
This yields a two-threshold operational policy:
- **$t_1 = 0.0050$ (Review Threshold)**: Balances missed fraud prevention against human investigative capacity, strictly capped at $\le 6.0$ reviews per 1,000 transactions.
- **$t_2 = 0.0591$ (Block Threshold)**: Calibrated to ensure $\ge 90.0\%$ precision on autonomous automated transaction holds.

### Q8. What is calibration and why does it matter?
**Answer:**  
Class weighting (`scale_pos_weight = 153`) and oversampling artificially shift decision margins, causing raw tree probabilities to cluster near $1.0$. A raw output of $0.85$ does not mean the transaction has an $85\%$ empirical probability of being fraud. Probability calibration maps raw outputs into true posterior probabilities:
$$P(\hat{Y} = 1 \mid \hat{p} = p) \approx p$$
Calibrated probabilities are essential because the economic decision policy and human review band rely on mathematically meaningful risk expectations ($E[\text{Loss}] = P \cdot \text{Amount}$). FraudShield applies non-parametric **Isotonic Regression** fitted on validation folds, achieving a calibrated Brier score of **$0.00479$**.

### Q9. How do you prevent data leakage?
**Answer:**  
FraudShield implements and unit-tests **Three Strict Leakage Prevention Gates**:
1. **Gate 1 (Temporal Split Integrity)**: Strict chronological 70/15/15 partitioning ($t_{\text{train}} < t_{\text{val}} < t_{\text{test}}$). Random cross-validation is prohibited (`tests/test_no_leakage.py`).
2. **Gate 2 (Past-Only Rolling Deques)**: In `src/features.py`, rolling 1h, 24h, and 7d velocity counts and sums evaluate strictly on transactions prior to the current timestamp ($t_i < t$). Future rows never modify historical states. Verified by `tests/test_features_parity.py`.
3. **Gate 3 (Pipeline-Enclosed Resampling)**: Over-sampling algorithms (SMOTE) are fitted exclusively within training folds. Validation and holdout test sets are never touched by synthetic data.

### Q10. What is concept drift and how do you handle it?
**Answer:**  
Concept drift is the temporal shift in the conditional distribution of fraud $P_t(Y \mid X)$ or covariate distribution $P_t(X)$ as fraudsters adapt their techniques. FraudShield monitors drift using:
1. **Decile Population Stability Index (PSI)**: Monitored continuously across all 26 feature vectors and prediction scores. A score $\text{PSI} \ge 0.25$ triggers an automated retrain alert.
2. **Weekly Performance Tracking**: Tracks Recall@P90 and Precision while respecting the **7-day chargeback maturation embargo** (unflagged recent transactions are marked unconfirmed).
3. **Champion-Challenger Workflow**: Background retraining on mature windows, requiring challengers to pass side-by-side validation gating before atomic promotion, with instant rollback support.

### Q11. Is SHAP causal?
**Answer:**  
**No.** As highlighted in Lundberg and Lee (2017) and emphasized in FraudShield's UI callouts, Shapley values explain which model features drove a specific prediction score relative to the baseline training expectation. They reflect statistical associations and conditional dependencies learned by decision trees, and do **not** prove real-world causality. For example, a high SHAP value for `device_novelty` means an unrecognized device was strongly associated with elevated fraud scores in historical data, not that the device hardware caused the fraud.

### Q12. Why are public fraud datasets limited, and how does that change your claims?
**Answer:**  
Public datasets suffer from major limitations:
- **ULB Credit Card**: Anonymized via Principal Component Analysis (PCA $V_1..V_{28}$), removing timestamps and entity IDs, making velocity feature engineering impossible; spans only 48 hours.
- **PaySim**: A simplified synthetic mobile money simulation lacking web/browser device fingerprints and network graph dynamics.
Because of these limitations, we do not claim universal production infallibility. Instead, we claim **relative methodological superiority** under a rigorous, leakage-safe evaluation protocol, and report all metrics with $95\%$ bootstrap confidence intervals across multiple datasets.

### Q13. How would FraudShield run in a real commercial bank?
**Answer:**  
In production banking infrastructure:
1. **Authorization Engine**: Placed inline behind the payment switch (ISO 8583 / ISO 20022 message protocol) with an SLA of $< 15$ ms.
2. **Stateful Feature Store**: In-memory Redis cluster maintaining rolling entity deques for 20k+ active accounts.
3. **Decision Gateway**:
   - $P < 0.0050$: Instant approval ($99.3\%$ of traffic).
   - $0.0050 \le P < 0.0591$: Step-up friction (SMS OTP / Biometric 2FA) or analyst queue.
   - $P \ge 0.0591$: Automated hold and card temporary freeze.
4. **Surveillance & Registry**: SQLite/PostgreSQL audit logging, daily PSI drift jobs, and model registry with blue/green deployment.

### Q14. What are the ethical and regulatory risks?
**Answer:**  
Key ethical and compliance risks include:
1. **Disparate Impact & Proxy Bias**: Models using location or channel can inadvertently discriminate against emerging economic corridors. FraudShield normalizes velocity against the entity's *own historical baseline* and audits FPR across 10 regions and 4 channels (verifying a 1.00x disparity ratio).
2. **Customer Harm from False Declines**: False blocks strand legitimate cardholders. FraudShield reserves automated rejection strictly for $P \ge 0.0591$ ($\ge 90\%$ precision), using step-up 2FA for intermediate alerts.
3. **Privacy Compliance**: Full alignment with India's **DPDP Act 2023** (SHA-256 pseudonymization, zero PII in tensors) and RBI Master Directions.

### Q15. What is the team's core scientific contribution?
**Answer:**  
The primary contribution is an **integrated, leakage-free financial engineering framework** that bridges the gap between academic benchmarks and banking operations:
1. A hybrid architecture fusing unsupervised geometric isolation and deep autoencoders into class-weighted gradient boosting.
2. An economically grounded dual-threshold decision policy bounding human review capacity to $\le 6.0/1\text{k}$ transactions.
3. Exact TreeSHAP local interpretability generating dynamic, non-prejudicial plain-English reason codes.
4. A production-ready prototype featuring live SSE transaction replay, automated drift surveillance, and atomic challenger governance.

---

## Part 2: Advanced Engineering Viva Questions (Oral Defense)

### Q16. How does your Hybrid Anomaly Fusion work mathematically without target leakage?
**Answer:**  
To prevent target leakage during training, anomaly scores (`iso_score` and `ae_error`) cannot be generated on the same data used to fit the supervised tree. In `src/models.py`, `HybridFraudDetector` implements a **$K=3$ Out-of-Fold (OOF) anomaly fusion strategy**:
1. The training partition is divided into 3 temporal folds.
2. For each fold $k$, the Isolation Forest and PyTorch Autoencoder are fitted on clean rows from the remaining folds.
3. Anomaly scores are inferred on fold $k$.
4. The resulting out-of-fold scores are concatenated as feature columns $27$ and $28$ to train the XGBoost booster.
5. On the test set, the anomaly models fitted on the full training set infer static features.

### Q17. Why native TreeSHAP `pred_contribs=True` instead of KernelSHAP?
**Answer:**  
KernelSHAP is model-agnostic but requires sampling $2^{|F|}$ feature subsets, incurring $O(2^M)$ complexity. Scoring a single transaction with 26 features takes over 800 ms with KernelSHAP, violating banking $<15$ ms SLAs. In contrast, Lundberg et al. (2018) developed **TreeSHAP**, which optimizes subtree paths in decision ensembles in polynomial time:
$$O(T \cdot L \cdot D^2)$$
where $T$ is the number of trees ($150$), $L$ is maximum leaves ($31$), and $D$ is maximum tree depth ($5$). Native XGBoost C++ `predict(..., pred_contribs=True)` computes exact Shapley margin values in **$< 1.2$ milliseconds**.

### Q18. What is the mathematical definition and operational threshold for PSI?
**Answer:**  
Population Stability Index (PSI) evaluates the symmetric Kullback-Leibler divergence between actual deployment deciles $A_i$ and baseline training deciles $E_i$:
$$\text{PSI} = \sum_{i=1}^{10} (A_i - E_i) \cdot \ln\left(\frac{A_i}{E_i}\right)$$
In `src/monitor.py`:
- $\text{PSI} < 0.10$: **Stable** (No action).
- $0.10 \le \text{PSI} < 0.25$: **Moderate Shift** (Monitor weekly).
- $\text{PSI} \ge 0.25$: **Significant Shift** (Triggers `RETRAIN_RECOMMENDED` alert).

### Q19. How do you handle the 7-day chargeback maturation embargo in live monitoring?
**Answer:**  
In credit card systems, chargebacks take between 7 and 30 days to be filed by cardholders and confirmed by issuing networks. If weekly precision/recall is computed on transactions from the past 48 hours, every unflagged transaction will be labeled legitimate because no dispute has arrived yet. This produces a false $100\%$ precision artifact. In `src/monitor.py`, FraudShield enforces an embargo window: weekly cohort performance is computed strictly on cohorts older than 7 days ($\text{Age} \ge 7 \text{ days}$). Transactions inside the recent 7-day window are shaded in UI Screen §07 as "Unconfirmed Pending Maturation".

### Q20. Why does Isotonic Regression outperform Platt Scaling in this architecture?
**Answer:**  
Platt scaling assumes a parametric sigmoid relationship between log-odds margins and true class posterior probabilities:
$$P(Y = 1 \mid f) = \frac{1}{1 + \exp(A \cdot f + B)}$$
Because tree ensembles with extreme `scale_pos_weight` produce step-wise, non-smooth margin distributions with heavy tails, the logistic assumption is systematically violated. **Isotonic Regression** fits a non-parametric, piece-wise constant monotonic step function using the Pool Adjacent Violators Algorithm (PAVA). It makes no distributional assumptions, yielding a superior Brier score ($0.00479$ vs $0.00921$).

### Q21. What happens during an adversarial -30% transaction amount evasion probe?
**Answer:**  
Attack syndicates execute "smurfing" by deflating fraudulent transaction amounts by $30\%$ to slip under velocity and dollar alerts. In `artifacts/fairness.json`, FraudShield simulates this attack across the test set:
- Baseline Champion PR-AUC: $0.9300 \to 0.8325$ (Evasion).
- Baseline Recall@P90: $58.0\% \to 54.0\%$ (Retaining **$93.1\%$** of detection ability).
- Single-layer XGBoost collapses from $54.0\%$ to $42.0\%$ recall.
The hybrid architecture survives because `iso_score` and `ae_error` capture non-monetary structural anomalies (device novelty, burst frequency, session entropy).

### Q22. How do you guarantee sub-15ms inference latency in production?
**Answer:**  
Scoring latency is measured live in `src/stream.py`:
1. **In-Memory Feature Updates**: Entity velocity deques (`deque(maxlen=100)`) allow $O(1)$ appends and $O(K)$ sliding window sums, executing in $< 0.8$ ms.
2. **C++ Native Tree Inference**: XGBoost executes forward tree traversal in $< 0.5$ ms.
3. **Exact C++ TreeSHAP**: `pred_contribs=True` runs in $< 1.2$ ms.
4. **Overall Median Latency**: **$3.2$ ms** (p95 latency $< 8.4$ ms), satisfying strict real-time payment gateway SLAs.

### Q23. What are the three strict leakage gates and how do tests enforce them?
**Answer:**  
- `tests/test_no_leakage.py` verifies that shifting future records in the dataset does not change historical feature vectors, proving past-only invariance.
- `tests/test_features_parity.py` asserts that online feature extraction from streaming `FeatureStore` matches offline batch feature extraction with zero floating-point divergence ($100\%$ parity).
- `test_smote_pipeline_isolation` asserts that SMOTE is never applied to validation or test splits.

### Q24. How does FraudShield comply with India's DPDP Act 2023?
**Answer:**  
Under the Digital Personal Data Protection (DPDP) Act 2023:
- **Data Minimization**: No personal identifiers (names, phone numbers, Aadhaar, PAN) enter model feature tensors.
- **Pseudonymization**: Account IDs and device hashes are irreversibly hashed using SHA-256 with rotating salt.
- **Storage Limitation**: Historical state deques in `FeatureStore` expire automatically after 7 days of inactivity.

### Q25. What is the Challenger Retrain promotion gate criteria?
**Answer:**  
In `src/monitor.py`, when a challenger model is trained on updated mature data (`POST /api/retrain`), it must satisfy three automated criteria before promotion:
1. **PR-AUC Gate**: $\text{PR-AUC}_{\text{challenger}} \ge \text{PR-AUC}_{\text{champion}} - 0.01$.
2. **Cost Gate**: $\text{Expected Cost}_{\text{challenger}} \le \text{Expected Cost}_{\text{champion}}$.
3. **Capacity Gate**: Review queue rate $\le 6.0$ reviews per 1,000 transactions.
If any criterion fails, the challenger is marked `REJECTED`, preserving the champion. The previous champion bundle is archived to enable instant one-click rollback (`POST /api/rollback`).

### Q26. Why is the review queue constrained to $\le 6.0$ reviews per 1,000 transactions?
**Answer:**  
Human fraud investigators can review approximately 15 to 20 complex cases per hour. In a banking system processing 100,000 transactions daily, an unconstrained threshold of $P = 0.001$ would route 2,000 transactions to review, overwhelming investigative staff and causing multi-hour authorization backlogs. Restricting queue capacity to $\le 6.0/1\text{k}$ ensures that total daily cases do not exceed team bandwidth, maintaining an average turnaround SLA under 3 minutes per case.

### Q27. How does FraudShield prevent demographic/geographic proxy bias?
**Answer:**  
Algorithms can inadvertently learn to reject transactions from specific postal codes or lower-income corridors. FraudShield prevents this by:
1. Normalizing transaction behavior relative to the user's *own* baseline (e.g., `amount_to_avg_ratio_7d`, `amount_zscore_by_account`).
2. Excluding static socio-demographic indicators.
3. Auditing False Positive Rates across 10 regions in Screen §08, ensuring a disparity ratio of $1.00$x (zero disparate impact).

### Q28. How does the PyTorch Deep Autoencoder operate?
**Answer:**  
The Autoencoder in `src/models.py` has a symmetric funnel architecture:
$$\text{Linear}(26 \to 16) \to \text{ReLU} \to \text{Linear}(16 \to 8) \to \text{ReLU} \to \text{Linear}(8 \to 16) \to \text{ReLU} \to \text{Linear}(16 \to 26)$$
It is trained exclusively on clean non-fraud rows using Adam optimizer and Mean Squared Error (MSE) loss. Legitimate transactions compress and reconstruct with low loss ($\text{MSE} < 0.05$). Fraudulent transactions, containing uncharacteristic combinations of velocity, balance drain, and device mismatch, cannot be reconstructed accurately, yielding high $\text{MSE}$ values that expose the anomaly.

### Q29. Why did SMOTE fail to beat class-weighted trees in Hypothesis H3?
**Answer:**  
Gradient-boosted decision trees partition feature space using orthogonal hyperplanes. In `src/imbalance.py`, class weighting (`scale_pos_weight = N_neg / N_pos`) scales the gradient and hessian of minority instances in the loss function, directly magnifying split rewards for rare events. Because boosted trees split on marginal densities, synthesizing interpolated points between existing minority examples does not provide new topological information—it merely populates noise into sparse boundary regions. Once cost-optimal thresholds are tuned, SMOTE offers zero advantage and increases training complexity.

### Q30. How do you compute 1,000 bootstrap confidence intervals on holdout metrics?
**Answer:**  
In `src/evaluate.py`, point estimates (e.g., PR-AUC = 0.930) can be noisy. FraudShield draws $B = 1,000$ bootstrap iterations with replacement from the 18,000-transaction holdout set:
1. Sample $N = 18,000$ indices with replacement.
2. Evaluate PR-AUC, Recall@P90, and Expected Cost.
3. Compute the empirical $2.5^{\text{th}}$ and $97.5^{\text{th}}$ percentiles.
This yields our verified $95\%$ bootstrap confidence interval:
$$\text{PR-AUC} = 0.930 \quad [0.892, 0.959]$$
proving statistical significance at the $p < 0.01$ level over baseline Logistic Regression ($[0.245, 0.350]$).

