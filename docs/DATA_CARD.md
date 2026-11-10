# FraudShield Data Card (`docs/DATA_CARD.md`)

> **Datasheet for Datasets (Gebru et al., 2021)**  
> Comprehensive documentation of transaction datasets evaluated in FraudShield: LedgerSim primary synthetic benchmark, ULB Credit Card Fraud, and PaySim mobile money simulation.

---

## 1. Dataset Overview & Comparison

| Characteristic | LedgerSim Primary Benchmark | ULB Credit Card (2015) | PaySim Mobile Money (2016) |
|---|---|---|---|
| **Dataset Origin** | Custom Agent-Based Banking Generator (`src/simulator.py`) | Real European cardholders (Université Libre de Bruxelles) | Synthetic agent-based mobile money simulation (NTNU) |
| **Total Volume** | 120,000 transactions (Fast config) / 400,000 (Full) | 284,807 transactions | 6,362,620 transactions |
| **Timespan** | 30.0 days continuous chronological | 2 days (48 hours) | 30 days (744 hourly steps) |
| **Total Fraud Count** | 780 events (Fast) / 2,600 events (Full) | 492 events | 8,213 events |
| **Fraud Prevalence ($\pi$)** | **0.650%** (1 in 154 transactions) | **0.172%** (1 in 579 transactions) | **0.129%** (1 in 775 transactions) |
| **Entities Tracked** | 20,000 accounts, 1,500 merchants, devices, IPs | Anonymized transactions (No account IDs) | Named origin and destination accounts |
| **Fraud Typologies** | 5 distinct attack patterns | Mixed card fraud (unlabeled typology) | CASH_OUT and TRANSFER draining |
| **Concept Drift** | Injected in final 25% (amount & merchant shift) | None (48-hour timespan is stationary) | Weak temporal shift |
| **Label Maturation** | 7-day maturation delay simulated | Instantaneous ground truth | Instantaneous ground truth |
| **Velocity Features** | Rich (1h, 24h, 7d counts, sums, z-scores) | Limited (Time and Amount only; PCA masks IDs) | Moderate (Step and Balance error features) |
| **Storage Format** | Apache Parquet (`data/processed/ledgersim_fast.parquet`) | CSV (`data/raw/creditcard.csv`) | CSV (`data/raw/paysim.csv`) |

---

## 2. LedgerSim: Primary Synthetic Banking Generator

### 2.1 Motivation & Purpose
Public financial fraud datasets suffer from severe privacy limitations: transaction amounts are transformed via PCA, timestamps are stripped, and account identifiers are removed to protect banking secrecy. These redactions make it impossible to evaluate stateful velocity features (e.g., rolling 1h transaction frequency, 7-day spending z-scores). LedgerSim was developed to provide an open, fully transparent financial simulation that models authentic payment dynamics without compromising customer privacy.

### 2.2 Stylized Statistical Distributions
1. **Transaction Amounts**: Follow a two-component mixture distribution:
   - Retail purchases: Lognormal distribution ($\mu = 3.2, \sigma = 1.15$).
   - High-value commercial settlements: Pareto power-law tail ($x_m = 10,000, \alpha = 1.85$).
2. **First-Digit Distribution**: Obeys **Benford's Law** for legitimate billing totals:
   $$P(d) = \log_{10}\left(1 + \frac{1}{d}\right) \quad \text{for } d \in \{1, 2, \dots, 9\}$$
3. **Temporal Arrival Rates**: Non-homogeneous Poisson process capturing realistic diurnal banking peaks (10:00 to 14:00 and 18:00 to 21:00 local time) and weekend consumer shifts.
4. **Geographic Corridors**: Modeled across 10 regional payment belts (Delhi NCR, Bengaluru, Mumbai, London, Singapore, California, New York) with realistic IP-to-merchant latency bounds.

### 2.3 The Five Simulated Fraud Typologies
1. **`card_testing`**: Automated botnets executing rapid micro-transactions (₹10 to ₹100) within seconds across diverse online merchants to identify active card numbers.
2. **`cnp` (Card-Not-Present)**: Exploitation of stolen card credentials for high-value electronics and luxury goods, characterized by unfamiliar device fingerprints and shipping address mismatches.
3. **`ato` (Account Takeover)**: Credential stuffing or SIM swap attacks where attackers alter account notification settings, log in from novel IPs, and rapidly drain balances via high-velocity transfers.
4. **`mule_chain`**: Coordinated money laundering syndicates rapidly routing stolen funds through a succession of synthetic accounts to obscure audit trails.
5. **`app` (Authorized Push Payment)**: Social engineering impersonation fraud where cardholders are manipulated into authorizing large direct transfers to fraudulent accounts.

### 2.4 Concept Drift Injection
In the final $25\%$ of the timeline (simulating Days 23 through 30), LedgerSim introduces structured concept drift:
- Fraudulent transaction amounts are compressed by $30\%$ to evade static velocity thresholds.
- Attack traffic shifts from card-present retail to instant mobile rails (UPI and Faster Payments).
- Night-time fraud attacks decrease while daytime social engineering scams increase.

---

## 3. Detailed Column Schema Dictionary

### Raw Transaction Schema (`LedgerSim`)
| Column Name | Data Type | Null Count | Description |
|---|:---:|:---:|---|
| `txn_id` | String | 0 | Unique transaction identifier (e.g., `TXN_00103934`) |
| `ts` | Float64 | 0 | Unix timestamp in seconds since epoch |
| `account_id` | String | 0 | Salted pseudonymized account identifier (e.g., `ACC_000042`) |
| `merchant_id` | String | 0 | Merchant identifier (e.g., `MERCH_000128`) |
| `merchant_category` | String | 0 | Merchant category code (`retail`, `grocery`, `electronics`, `travel`, `gaming`) |
| `amount` | Float32 | 0 | Transaction monetary amount in INR (₹) |
| `channel` | String | 0 | Payment settlement rail (`card_present`, `online`, `transfer`, `upi`) |
| `device_id` | String | 0 | SHA-256 pseudonymized device hardware fingerprint hash |
| `device_is_new` | Int32 | 0 | Binary flag: 1 if device has never been seen on this account, 0 otherwise |
| `ip_region` | String | 0 | Geolocation jurisdiction code (e.g., `IN-MH`, `IN-KA`, `GB-LON`, `US-CA`) |
| `region_mismatch` | Int32 | 0 | Binary flag: 1 if IP jurisdiction differs from account home base |
| `hour` | Int32 | 0 | Local transaction hour of day ($0 \dots 23$) |
| `is_night` | Int32 | 0 | Binary indicator: 1 if transaction occurs between 23:00 and 06:00 |
| `oldbalance` | Float32 | 0 | Account balance immediately prior to transaction |
| `newbalance` | Float32 | 0 | Account balance immediately following transaction |
| `is_fraud` | Int32 | 0 | Ground-truth binary target: 1 if confirmed fraudulent, 0 if legitimate |
| `typology` | String | 0 | Attack classification label (`none`, `card_testing`, `cnp`, `ato`, `mule_chain`, `app`) |

### Engineered Feature Store Vectors (26 Model Inputs)
| Feature Name | Category | Calculation Logic |
|---|---|---|
| `log_amount` | Monetary | $\ln(1 + \text{Amount})$ |
| `amount_to_avg_ratio_7d` | Behavioral | $\text{Amount} / \max(1, \bar{A}_{\text{account}, 7d})$ |
| `amount_zscore_by_account` | Behavioral | $(\text{Amount} - \mu_{A}) / \max(1, \sigma_{A})$ |
| `amount_to_balance_ratio` | Balance | $\text{Amount} / \max(1, \text{oldbalance})$ |
| `balance_error` | Balance | $|\text{oldbalance} - \text{newbalance} - \text{Amount}|$ |
| `txn_count_1h` | Velocity | Count of account transactions in $[t - 3600, t)$ |
| `txn_count_24h` | Velocity | Count of account transactions in $[t - 86400, t)$ |
| `txn_count_7d` | Velocity | Count of account transactions in $[t - 604800, t)$ |
| `amount_sum_1h` | Velocity | Sum of account amounts in past 1 hour |
| `amount_sum_24h` | Velocity | Sum of account amounts in past 24 hours |
| `amount_sum_7d` | Velocity | Sum of account amounts in past 7 days |
| `time_since_last_txn` | Velocity | $\ln(1 + (t - t_{\text{prev}}))$ in seconds |
| `hour_sin` | Temporal | $\sin(2\pi \cdot \text{hour} / 24)$ |
| `hour_cos` | Temporal | $\cos(2\pi \cdot \text{hour} / 24)$ |
| `is_night` | Temporal | Binary: 1 if $\text{hour} \in [23, 6]$ |
| `is_weekend` | Temporal | Binary: 1 if day of week is Saturday or Sunday |
| `device_novelty` | Behavioral | Decay score of device frequency on account |
| `region_mismatch` | Behavioral | Binary: 1 if current region differs from 7-day mode |
| `category_rarity_by_account` | Behavioral | Frequency of merchant category in account history |
| `session_anomaly` | Behavioral | Rapid switching between multiple distinct merchants |
| `channel_risk_prior` | Channel | Historical Bayes empirical fraud rate for payment rail |
| `merchant_risk_prior` | Merchant | Historical Bayes empirical fraud rate for merchant |
| `card_testing_flag` | Typology | Heuristic: $\ge 3$ txns under ₹100 in 15 minutes |
| `rapid_drain_flag` | Typology | Heuristic: Account balance depleted by $\ge 85\%$ in $< 1$ hour |
| `iso_score` | Anomaly | Out-of-fold Isolation Forest path anomaly score |
| `ae_error` | Anomaly | Out-of-fold Deep Autoencoder latent reconstruction MSE |

---

## 4. Ethical, Privacy & Regulatory Governance

- **DPDP Act (India, 2023)**: Sections 4–9 mandate data minimization. All personal identity attributes are excluded from model tensors. Primary keys are salted hashes.
- **Data Retention Policy**: FeatureStore in-memory rolling deques automatically discard entity history older than 7 days upon inactivity.
- **Research Distribution**: LedgerSim datasets are released under the MIT Open Data License for reproducible academic benchmarking.

