"""
FraudShield Configuration module.
Central repository for all project paths, random seeds, cost parameters,
split ratios, threshold policies, and simulation defaults.
"""

from pathlib import Path
from typing import Dict, Any

# ==============================================================================
# 1. Project Paths
# ==============================================================================
PROJECT_ROOT = Path(__file__).resolve().parent

DATA_DIR = PROJECT_ROOT / "data"
DATA_RAW_DIR = DATA_DIR / "raw"
DATA_PROCESSED_DIR = DATA_DIR / "processed"

ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"
DOCS_DIR = PROJECT_ROOT / "docs"
TESTS_DIR = PROJECT_ROOT / "tests"
FRONTEND_DIR = PROJECT_ROOT / "frontend"
FRONTEND_DIST_DIR = FRONTEND_DIR / "dist"
SCRIPTS_DIR = PROJECT_ROOT / "scripts"

# SQLite storage for live analyst case management
DB_PATH = ARTIFACTS_DIR / "fraudshield.db"

# Ensure essential directories exist
for directory in [DATA_RAW_DIR, DATA_PROCESSED_DIR, ARTIFACTS_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# ==============================================================================
# 2. Reproducibility & Seeds
# ==============================================================================
RANDOM_SEED = 42

# ==============================================================================
# 3. Data Split & Timeline Protocol
# ==============================================================================
# Time-ordered split ratios (must sum to 1.0)
TRAIN_RATIO = 0.70
VAL_RATIO = 0.15
TEST_RATIO = 0.15

# Label maturity delay in seconds (7 days)
LABEL_MATURITY_SECONDS = 7 * 24 * 3600  # 604,800 seconds

# ==============================================================================
# 4. Business Cost Constants (Decision Policy)
# ==============================================================================
# Flat-ratio cost constants (Bayes-optimal threshold calculation)
FLAT_C_FN = 100.0  # Cost of a missed fraud (investigation + chargeback fee)
FLAT_C_FP = 1.0    # Cost of a false alarm (analyst triage friction)

# Amount-weighted loss constants: Cost(FN) = amount + FIXED_CHARGEBACK_FEE
AMOUNT_C_FP = 5.0  # Flat dollar/rupee cost of analyst friction per false alarm
FIXED_CHARGEBACK_FEE = 15.0  # Fixed operational handling overhead per missed fraud

# Operational review capacity ceiling (max review transactions per 1,000 transactions)
MAX_REVIEWS_PER_1000 = 6.0  # Max 0.6% queue capacity

# Target minimum precision required for automated blocking (t2)
TARGET_BLOCK_PRECISION = 0.90

# ==============================================================================
# 5. Primary Simulator Defaults ("LedgerSim")
# ==============================================================================
SIMULATOR_CONFIG_FULL: Dict[str, Any] = {
    "num_transactions": 400_000,
    "num_days": 60,
    "num_accounts": 20_000,
    "num_merchants": 1_500,
    "num_categories": 12,
    "fraud_rate_target": 0.0065,  # 0.65% (~2,600 frauds)
    "drift_start_ratio": 0.75,    # Concept drift starts in the final 25% of timeline
    "seed": RANDOM_SEED,
}

SIMULATOR_CONFIG_FAST: Dict[str, Any] = {
    "num_transactions": 120_000,
    "num_days": 30,
    "num_accounts": 8_000,
    "num_merchants": 600,
    "num_categories": 12,
    "fraud_rate_target": 0.0065,  # 0.65% (~780 frauds)
    "drift_start_ratio": 0.75,    # Concept drift starts in the final 25% of timeline
    "seed": RANDOM_SEED,
}

# Merchant categories
MERCHANT_CATEGORIES = [
    "groceries",
    "electronics",
    "dining",
    "travel_airline",
    "apparel",
    "utilities",
    "entertainment",
    "pharmacy",
    "luxury_goods",
    "fuel",
    "digital_services",
    "crypto_exchange",
]

# Geographic regions
REGIONS = ["IN-MH", "IN-DL", "IN-KA", "IN-TN", "IN-TS", "IN-WB", "US-NY", "US-CA", "GB-LON", "SG-SIN"]

# Channels
CHANNELS = ["card_present", "online", "upi", "transfer"]

# ==============================================================================
# 6. Hyperparameter Optimization & Model Budgets
# ==============================================================================
OPTUNA_TRIALS_FULL = 25
OPTUNA_TRIALS_FAST = 10
EARLY_STOPPING_ROUNDS = 50

# Bootstrap resamples for confidence interval estimation
BOOTSTRAP_ROUNDS = 1000

# ==============================================================================
# 7. Model Versioning & Registry
# ==============================================================================
CHAMPION_MODEL_FILE = ARTIFACTS_DIR / "model_champion.joblib"
CHALLENGER_MODEL_FILE = ARTIFACTS_DIR / "model_challenger.joblib"
METRICS_FILE = ARTIFACTS_DIR / "metrics.json"
EXPERIMENTS_FILE = ARTIFACTS_DIR / "experiments.json"
CURVES_FILE = ARTIFACTS_DIR / "curves.json"
THRESHOLDS_FILE = ARTIFACTS_DIR / "thresholds.json"
EDA_FILE = ARTIFACTS_DIR / "eda.json"
DATACARDS_FILE = ARTIFACTS_DIR / "datacards.json"
SHAP_GLOBAL_FILE = ARTIFACTS_DIR / "shap_global.json"
DRIFT_METRICS_FILE = ARTIFACTS_DIR / "drift_metrics.json"
FAIRNESS_FILE = ARTIFACTS_DIR / "fairness.json"
HYPOTHESES_FILE = ARTIFACTS_DIR / "hypotheses.json"

