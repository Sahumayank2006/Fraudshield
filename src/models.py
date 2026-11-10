"""
FraudShield Models Architecture Module.

Implements all model families for Experiments E1 through E10:
- Supervised: Logistic Regression (E1, E2), Random Forest (E3), XGBoost (E4, E5), LightGBM (E6)
- Unsupervised: Isolation Forest (E7), Deep Autoencoder (E8)
- Hybrid Fusion: Out-of-fold anomaly scores + XGBoost + Probability Calibration (E9)
- Stacked Ensemble: Meta-learner on out-of-fold predictions + calibration (E10)
"""

from __future__ import annotations

import logging
import math
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import joblib
import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import IsolationForest, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss
from sklearn.model_selection import KFold, StratifiedKFold
from sklearn.neural_network import MLPRegressor
from sklearn.preprocessing import RobustScaler
from xgboost import XGBClassifier

from config import EARLY_STOPPING_ROUNDS, RANDOM_SEED

logger = logging.getLogger("fraudshield.models")

# Attempt PyTorch import for Deep Autoencoder
try:
    import torch
    import torch.nn as nn
    import torch.optim as optim
    from torch.utils.data import DataLoader, TensorDataset

    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    logger.warning("PyTorch not available. Autoencoder will use sklearn MLPRegressor fallback.")


# ==============================================================================
# 1. Deep Autoencoder (PyTorch CPU with sklearn fallback)
# ==============================================================================
if TORCH_AVAILABLE:

    class PyTorchAE(nn.Module):
        """
        Deep Autoencoder matching the academic report specification:
        d -> 16 -> 8 -> 4 -> 8 -> 16 -> d with ReLU activations and Adam optimizer.
        """

        def __init__(self, input_dim: int):
            super().__init__()
            self.enc = nn.Sequential(
                nn.Linear(input_dim, 16),
                nn.BatchNorm1d(16),
                nn.ReLU(),
                nn.Linear(16, 8),
                nn.BatchNorm1d(8),
                nn.ReLU(),
                nn.Linear(8, 4),
            )
            self.dec = nn.Sequential(
                nn.Linear(4, 8),
                nn.BatchNorm1d(8),
                nn.ReLU(),
                nn.Linear(8, 16),
                nn.BatchNorm1d(16),
                nn.ReLU(),
                nn.Linear(16, input_dim),
            )

        def forward(self, x: torch.Tensor) -> torch.Tensor:
            z = self.enc(x)
            x_hat = self.dec(z)
            return x_hat


class AutoencoderAnomaly:
    """
    Unsupervised Reconstruction-Error Anomaly Detector.
    Trained strictly on legitimate transactions (y=0) to model normal behaviour.
    High reconstruction error indicates anomalous / suspicious activity.
    """

    def __init__(
        self,
        epochs: int = 40,
        batch_size: int = 256,
        lr: float = 1e-3,
        random_state: int = RANDOM_SEED,
    ):
        self.epochs = epochs
        self.batch_size = batch_size
        self.lr = lr
        self.random_state = random_state
        self.scaler = RobustScaler()
        self.model: Any = None
        self.use_torch = TORCH_AVAILABLE

    def fit(self, X: np.ndarray) -> "AutoencoderAnomaly":
        """Fit autoencoder on legitimate samples only."""
        X_scaled = self.scaler.fit_transform(X)
        input_dim = X.shape[1]

        if self.use_torch:
            torch.manual_seed(self.random_state)
            self.model = PyTorchAE(input_dim=input_dim)
            self.model.train()

            criterion = nn.MSELoss()
            optimizer = optim.Adam(self.model.parameters(), lr=self.lr)

            tensor_x = torch.tensor(X_scaled, dtype=torch.float32)
            dataset = TensorDataset(tensor_x)
            loader = DataLoader(dataset, batch_size=self.batch_size, shuffle=True)

            for epoch in range(self.epochs):
                for batch in loader:
                    bx = batch[0]
                    optimizer.zero_grad()
                    out = self.model(bx)
                    loss = criterion(out, bx)
                    loss.backward()
                    optimizer.step()

            self.model.eval()
        else:
            # Fallback using multi-layer bottleneck MLPRegressor
            self.model = MLPRegressor(
                hidden_layer_sizes=(16, 8, 4, 8, 16),
                activation="relu",
                solver="adam",
                alpha=1e-4,
                batch_size=self.batch_size,
                learning_rate_init=self.lr,
                max_iter=self.epochs,
                random_state=self.random_state,
                early_stopping=True,
            )
            self.model.fit(X_scaled, X_scaled)

        return self

    def score(self, X: np.ndarray) -> np.ndarray:
        """
        Compute mean-squared reconstruction error for each sample.
        Higher score = higher anomaly.
        """
        X_scaled = self.scaler.transform(X)

        if self.use_torch and isinstance(self.model, nn.Module):
            self.model.eval()
            with torch.no_grad():
                tensor_x = torch.tensor(X_scaled, dtype=torch.float32)
                recon = self.model(tensor_x).numpy()
                errors = np.mean((X_scaled - recon) ** 2, axis=1)
                return errors.astype(np.float32)
        else:
            recon = self.model.predict(X_scaled)
            errors = np.mean((X_scaled - recon) ** 2, axis=1)
            return errors.astype(np.float32)


# ==============================================================================
# 2. Unsupervised Isolation Forest Wrapper
# ==============================================================================
class IsolationForestAnomaly:
    """
    Unsupervised Isolation Forest detector trained exclusively on legitimate rows.
    Inverts scikit-learn's score_samples so higher values indicate greater anomaly.
    """

    def __init__(
        self,
        n_estimators: int = 300,
        random_state: int = RANDOM_SEED,
        n_jobs: int = -1,
    ):
        self.n_estimators = n_estimators
        self.random_state = random_state
        self.n_jobs = n_jobs
        self.model = IsolationForest(
            n_estimators=self.n_estimators,
            random_state=self.random_state,
            n_jobs=self.n_jobs,
        )

    def fit(self, X: np.ndarray) -> "IsolationForestAnomaly":
        self.model.fit(X)
        return self

    def score(self, X: np.ndarray) -> np.ndarray:
        # Invert score_samples: score_samples returns negative values (lower=anomaly)
        # We negate it so higher score = more anomalous
        return -self.model.score_samples(X)


# ==============================================================================
# 3. Supervised Model Factory (E1 to E6)
# ==============================================================================
def create_model(
    model_id: str,
    scale_pos_weight: float = 1.0,
    random_state: int = RANDOM_SEED,
    fast: bool = False,
) -> Any:
    """
    Factory function creating model instances for experiments E1 through E6.
    """
    n_est = 100 if fast else 300

    if model_id == "E1_LR_None":
        # Logistic Regression without class weighting (floor baseline)
        return LogisticRegression(
            class_weight=None,
            max_iter=1000,
            random_state=random_state,
            solver="lbfgs",
        )

    elif model_id == "E2_LR_Weighted":
        # Logistic Regression with balanced class weights
        return LogisticRegression(
            class_weight="balanced",
            max_iter=1000,
            random_state=random_state,
            solver="lbfgs",
        )

    elif model_id == "E3_RF_Balanced":
        # Random Forest with balanced subsampling
        return RandomForestClassifier(
            n_estimators=n_est,
            max_depth=12 if fast else 16,
            class_weight="balanced_subsample",
            random_state=random_state,
            n_jobs=-1,
        )

    elif model_id in ("E4_XGBoost", "E5_XGBoost_SMOTE"):
        # Primary gradient boosting classifier
        early_stop = None if model_id == "E5_XGBoost_SMOTE" else EARLY_STOPPING_ROUNDS
        return XGBClassifier(
            n_estimators=300 if fast else 600,
            max_depth=5 if fast else 6,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            scale_pos_weight=scale_pos_weight,
            eval_metric="aucpr",
            early_stopping_rounds=early_stop,
            random_state=random_state,
            tree_method="hist",
            n_jobs=-1,
        )

    elif model_id == "E6_LightGBM":
        # Fast histogram boosting
        return LGBMClassifier(
            n_estimators=300 if fast else 600,
            num_leaves=31,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            scale_pos_weight=scale_pos_weight,
            random_state=random_state,
            n_jobs=-1,
            verbose=-1,
        )

    else:
        raise ValueError(f"Unknown model_id: {model_id}")


# ==============================================================================
# 4. Hybrid Detection Model (E9: The Headline Contribution)
# ==============================================================================
class HybridFraudDetector:
    """
    Hybrid Fraud Architecture:
    1. Unsupervised branch (Isolation Forest + Autoencoder) fits strictly on legitimate training rows.
    2. Generates out-of-fold anomaly scores on training data via K-Fold CV to avoid optimistic leakage.
    3. Appends iso_score and ae_error to the feature matrix.
    4. Trains class-weighted XGBoost on the extended matrix.
    5. Calibrates output probabilities using Isotonic or Platt scaling on the validation set.
    """

    def __init__(
        self,
        scale_pos_weight: float = 1.0,
        n_folds: int = 5,
        fast: bool = False,
        random_state: int = RANDOM_SEED,
    ):
        self.scale_pos_weight = scale_pos_weight
        self.n_folds = n_folds
        self.fast = fast
        self.random_state = random_state

        # Unsupervised models for scoring new incoming transactions
        self.iso_full = IsolationForestAnomaly(
            n_estimators=100 if fast else 300, random_state=random_state
        )
        self.ae_full = AutoencoderAnomaly(
            epochs=20 if fast else 40, random_state=random_state
        )

        # Supervised boosted tree
        self.xgb = XGBClassifier(
            n_estimators=300 if fast else 600,
            max_depth=5 if fast else 6,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            scale_pos_weight=scale_pos_weight,
            eval_metric="aucpr",
            early_stopping_rounds=EARLY_STOPPING_ROUNDS,
            random_state=random_state,
            tree_method="hist",
            n_jobs=-1,
        )

        # Calibration wrapper
        self.calibrated_model: Optional[Any] = None
        self.calibration_method: str = "isotonic"
        self.brier_score_val: float = 1.0
        self.feature_names: List[str] = []

    def fit(
        self,
        X_train: pd.DataFrame,
        y_train: np.ndarray,
        X_val: pd.DataFrame,
        y_val: np.ndarray,
    ) -> "HybridFraudDetector":
        """
        Fit hybrid model following the strict out-of-fold anomaly fusion protocol.
        """
        logger.info("Fitting Hybrid Fraud Detector (OOF anomaly scores -> XGBoost -> Calibration)...")
        self.feature_names = list(X_train.columns)

        # Columns to exclude from anomaly model fitting (e.g., existing placeholder anomaly cols)
        raw_feat_cols = [c for c in X_train.columns if c not in ("iso_score", "ae_error")]
        X_train_raw = X_train[raw_feat_cols].values
        X_val_raw = X_val[raw_feat_cols].values

        n_samples = len(X_train)
        oof_iso = np.zeros(n_samples, dtype=np.float32)
        oof_ae = np.zeros(n_samples, dtype=np.float32)

        # 1. Out-of-Fold Anomaly Scoring on Training Set (Legitimate rows only)
        # Ensures supervised tree does not train on optimistic in-sample anomaly scores
        logger.info("Computing K=%d Out-of-Fold anomaly scores on training partition...", self.n_folds)
        skf = StratifiedKFold(n_splits=self.n_folds, shuffle=True, random_state=self.random_state)

        for fold, (train_idx, val_idx) in enumerate(skf.split(X_train_raw, y_train)):
            # Fit on fold's legitimate rows only
            legit_fold_mask = (y_train[train_idx] == 0)
            X_fold_legit = X_train_raw[train_idx][legit_fold_mask]

            fold_iso = IsolationForestAnomaly(
                n_estimators=80 if self.fast else 150, random_state=self.random_state + fold
            ).fit(X_fold_legit)
            fold_ae = AutoencoderAnomaly(
                epochs=15 if self.fast else 25, random_state=self.random_state + fold
            ).fit(X_fold_legit)

            oof_iso[val_idx] = fold_iso.score(X_train_raw[val_idx])
            oof_ae[val_idx] = fold_ae.score(X_train_raw[val_idx])

        # 2. Fit Full-Train Anomaly Models (Used to score validation, test, and live serving)
        logger.info("Fitting full-train anomaly models on all legitimate training data...")
        legit_train_mask = (y_train == 0)
        X_train_legit = X_train_raw[legit_train_mask]
        self.iso_full.fit(X_train_legit)
        self.ae_full.fit(X_train_legit)

        # Score validation set with full anomaly models
        val_iso = self.iso_full.score(X_val_raw)
        val_ae = self.ae_full.score(X_val_raw)

        # 3. Construct Extended Feature Matrices
        X_train_ext = X_train.copy()
        X_train_ext["iso_score"] = oof_iso
        X_train_ext["ae_error"] = oof_ae

        X_val_ext = X_val.copy()
        X_val_ext["iso_score"] = val_iso
        X_val_ext["ae_error"] = val_ae

        self.feature_names = list(X_train_ext.columns)

        # 4. Train Supervised XGBoost on Extended Matrix
        logger.info("Training XGBoost on extended feature matrix...")
        self.xgb.fit(
            X_train_ext,
            y_train,
            eval_set=[(X_val_ext, y_val)],
            verbose=False,
        )

        # 5. Probability Calibration on Validation Set
        # Compare Isotonic vs Platt (sigmoid) scaling and select lowest Brier score
        val_raw_preds = self.xgb.predict_proba(X_val_ext)[:, 1]
        raw_brier = brier_score_loss(y_val, val_raw_preds)
        logger.info("Raw XGBoost Brier score on validation: %.5f", raw_brier)

        # Fit isotonic calibrator
        iso_cal = CalibratedClassifierCV(self.xgb, method="isotonic", cv="prefit")
        iso_cal.fit(X_val_ext, y_val)
        iso_preds = iso_cal.predict_proba(X_val_ext)[:, 1]
        iso_brier = brier_score_loss(y_val, iso_preds)

        # Fit platt (sigmoid) calibrator
        sig_cal = CalibratedClassifierCV(self.xgb, method="sigmoid", cv="prefit")
        sig_cal.fit(X_val_ext, y_val)
        sig_preds = sig_cal.predict_proba(X_val_ext)[:, 1]
        sig_brier = brier_score_loss(y_val, sig_preds)

        if iso_brier <= sig_brier and iso_brier < raw_brier:
            self.calibrated_model = iso_cal
            self.calibration_method = "isotonic"
            self.brier_score_val = iso_brier
        elif sig_brier < raw_brier:
            self.calibrated_model = sig_cal
            self.calibration_method = "sigmoid"
            self.brier_score_val = sig_brier
        else:
            self.calibrated_model = self.xgb
            self.calibration_method = "none"
            self.brier_score_val = raw_brier

        logger.info(
            "Selected calibration: %s (Validation Brier score: %.5f)",
            self.calibration_method,
            self.brier_score_val,
        )
        return self

    def transform_features(self, X: pd.DataFrame) -> pd.DataFrame:
        """Score incoming raw features with full anomaly branch and append scores."""
        raw_cols = [c for c in self.feature_names if c not in ("iso_score", "ae_error")]
        X_df = X.copy()
        for col in raw_cols:
            if col not in X_df.columns:
                X_df[col] = 0.0
        X_raw = X_df[raw_cols].values

        X_df["iso_score"] = self.iso_full.score(X_raw)
        X_df["ae_error"] = self.ae_full.score(X_raw)
        return X_df[self.feature_names]

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """Predict calibrated probabilities."""
        needs_transform = (
            "iso_score" not in X.columns
            or "ae_error" not in X.columns
            or (X["iso_score"] == 0.0).all()
        )
        if needs_transform:
            X_ext = self.transform_features(X)
        else:
            X_ext = X.copy()
            for col in self.feature_names:
                if col not in X_ext.columns:
                    X_ext[col] = 0.0
            X_ext = X_ext[self.feature_names]

        raw_probs = self.xgb.predict_proba(X_ext)

        if self.calibrated_model is not None and self.calibration_method != "none":
            cal_probs = self.calibrated_model.predict_proba(X_ext)
            p_cal = cal_probs[:, 1]
            p_raw = raw_probs[:, 1]
            # Smooth out coarse isotonic step plateau (<0.005) when raw model detects elevated risk
            p_final = np.where((p_raw >= 0.005) & (p_cal < 0.005), p_raw, p_cal)
            return np.column_stack([1.0 - p_final, p_final])

        return raw_probs

    def predict(self, X: pd.DataFrame, threshold: float = 0.5) -> np.ndarray:
        probs = self.predict_proba(X)[:, 1]
        return (probs >= threshold).astype(int)


# ==============================================================================
# 5. Stacked Ensemble Model (E10)
# ==============================================================================
class StackedFraudEnsemble:
    """
    Stacked Ensemble (E10):
    Meta-learner (Logistic Regression) fitted on out-of-fold probability predictions
    of base models (E2 LR, E3 RF, E4 XGBoost, E6 LightGBM, and anomaly detectors) + calibration.
    """

    def __init__(self, random_state: int = RANDOM_SEED):
        self.random_state = random_state
        self.meta_learner = LogisticRegression(class_weight="balanced", random_state=random_state)
        self.calibrator: Optional[CalibratedClassifierCV] = None

    def fit(
        self,
        base_oof_preds: np.ndarray,  # Shape (n_samples, n_base_models)
        y_train: np.ndarray,
        base_val_preds: np.ndarray,
        y_val: np.ndarray,
    ) -> "StackedFraudEnsemble":
        logger.info("Fitting Stacked Ensemble meta-learner on base predictions...")
        self.meta_learner.fit(base_oof_preds, y_train)

        # Calibrate meta-learner on validation predictions
        self.calibrator = CalibratedClassifierCV(self.meta_learner, method="isotonic", cv="prefit")
        self.calibrator.fit(base_val_preds, y_val)
        return self

    def predict_proba(self, base_preds: np.ndarray) -> np.ndarray:
        if self.calibrator is not None:
            return self.calibrator.predict_proba(base_preds)
        return self.meta_learner.predict_proba(base_preds)
