# Benchmark Dataset Acquisition Guide

FraudShield includes **LedgerSim**, a built-in synthetic bank simulator that generates rich transaction feeds with account histories, velocity features, 5 real fraud typologies, concept drift, and label maturation delays without requiring any external downloads.

However, to replicate the academic benchmark experiments from the project report on historical datasets, you can optionally place the public Kaggle datasets into `data/raw/`.

---

## 1. ULB Credit Card Fraud Dataset (Primary Academic Benchmark)

- **Source**: Machine Learning Group (MLG) at Université Libre de Bruxelles (ULB) & Worldline.
- **Kaggle URL**: [https://www.kaggle.com/datasets/mlg-ulb/creditcardfraud](https://www.kaggle.com/datasets/mlg-ulb/creditcardfraud)
- **Local File Path**: `data/raw/creditcard.csv`
- **Expected Records**: 284,807 transactions
- **Expected Frauds**: 492 (0.173%)
- **Time Span**: 2 days (172,792 seconds) of European cardholder transactions in September 2013.
- **Columns**:
  - `Time`: Number of seconds elapsed between this transaction and the first transaction in the dataset.
  - `V1` to `V28`: Principal components obtained with PCA (features transformed for confidentiality).
  - `Amount`: Transaction amount in Euros.
  - `Class`: Ground truth label (1 for fraud, 0 for legitimate).
- **Notes & Caveats**:
  - Because features $V_1 - V_{28}$ are principal components, business-level behavioural features and semantic reason codes cannot be generated from raw fields.
  - SHAP explanations on ULB will reflect mathematical component contributions rather than human-readable business reasons.

---

## 2. PaySim Mobile Money Simulator (Secondary Benchmark)

- **Source**: E. A. Lopez-Rojas, A. Elmir, and S. Axelsson (2016), European Modeling and Simulation Symposium.
- **Kaggle URL**: [https://www.kaggle.com/datasets/ealaxi/paysim1](https://www.kaggle.com/datasets/ealaxi/paysim1)
- **Local File Path**: `data/raw/paysim.csv`
- **Expected Records**: 6,362,620 transactions (FraudShield automatically samples legitimate transactions if memory is constrained, retaining 100% of frauds).
- **Expected Frauds**: 8,213 (0.129%)
- **Time Span**: 30 simulated days (744 steps, 1 step = 1 hour).
- **Columns**:
  - `step`: Maps a unit of time in the real world (1 step is 1 hour).
  - `type`: CASH_IN, CASH_OUT, DEBIT, PAYMENT, TRANSFER. (Fraud occurs strictly in `TRANSFER` and `CASH_OUT`).
  - `amount`: Transaction amount in local currency.
  - `nameOrig`: Customer starting the transaction.
  - `oldbalanceOrg`: Initial balance before the transaction.
  - `newbalanceOrig`: New balance after the transaction.
  - `nameDest`: Recipient of the transaction.
  - `oldbalanceDest`: Initial balance of recipient before transaction.
  - `newbalanceDest`: New balance of recipient after transaction.
  - `isFraud`: Ground truth label (1 for fraud, 0 for legitimate).
  - `isFlaggedFraud`: Status from business rule (transfer > 200,000).

---

## 3. Placement & Auto-Detection

1. Download the CSV files from Kaggle.
2. Place them directly in the raw data directory:
   ```
   fraudshield/
     data/
       raw/
         creditcard.csv
         paysim.csv
   ```
3. When FraudShield executes `python run.py train` or `python run.py train-fast`, it automatically checks for the presence of these files, runs the E1–E10 benchmark matrix, generates the corresponding DataCards in `artifacts/datacards.json`, and enables the dataset switcher on the **Model Lab** screen.
