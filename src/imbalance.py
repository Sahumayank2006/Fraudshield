"""
FraudShield Imbalance Handling Module.

Provides:
- Class weight computation functions (balanced, inverse ratio, custom prior)
- Safe resampling pipelines utilizing imblearn.pipeline.Pipeline (fit inside folds only)
- SMOTE, BorderlineSMOTE, RandomUnderSampler, and RandomOverSampler wrappers
- Ablation experiment helpers for comparing weighting vs resampling vs hybrid
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Tuple, Union

import numpy as np
from imblearn.over_sampling import BorderlineSMOTE, RandomOverSampler, SMOTE
from imblearn.pipeline import Pipeline
from imblearn.under_sampling import RandomUnderSampler
from sklearn.utils.class_weight import compute_class_weight

from config import RANDOM_SEED

logger = logging.getLogger("fraudshield.imbalance")


def compute_class_weights(
    y: Union[np.ndarray, list],
    strategy: str = "balanced",
) -> Dict[int, float]:
    """
    Compute class weights for imbalanced binary classification.
    y: 1D array of binary labels {0, 1}
    strategy: 'balanced' or 'inverse'
    """
    y_arr = np.asarray(y, dtype=int)
    classes = np.unique(y_arr)
    n_samples = len(y_arr)
    n_pos = int(np.sum(y_arr == 1))
    n_neg = n_samples - n_pos

    if n_pos == 0:
        return {0: 1.0, 1: 1.0}

    if strategy == "balanced":
        weights = compute_class_weight(class_weight="balanced", classes=classes, y=y_arr)
        return {int(cls): float(w) for cls, w in zip(classes, weights)}
    elif strategy == "inverse":
        # w1 = N_neg / N_pos, w0 = 1.0
        return {0: 1.0, 1: float(n_neg / n_pos)}
    elif strategy == "none":
        return {0: 1.0, 1: 1.0}
    else:
        raise ValueError(f"Unknown class weight strategy: {strategy}")


def get_scale_pos_weight(y: Union[np.ndarray, list]) -> float:
    """
    Calculate scale_pos_weight parameter for XGBoost and LightGBM:
    scale_pos_weight = N_neg / N_pos
    """
    y_arr = np.asarray(y, dtype=int)
    n_pos = int(np.sum(y_arr == 1))
    n_neg = len(y_arr) - n_pos
    if n_pos == 0:
        return 1.0
    return float(n_neg / n_pos)


def build_resampling_pipeline(
    classifier: Any,
    resampler_name: str = "smote",
    sampling_strategy: float = 0.20,
    k_neighbors: int = 5,
    random_state: int = RANDOM_SEED,
) -> Pipeline:
    """
    Construct a leakage-safe Pipeline where resampling is strictly confined
    to the training step inside cross-validation or training partitions.
    """
    if resampler_name == "smote":
        resampler = SMOTE(
            sampling_strategy=sampling_strategy,
            k_neighbors=k_neighbors,
            random_state=random_state,
        )
    elif resampler_name == "borderline_smote":
        resampler = BorderlineSMOTE(
            sampling_strategy=sampling_strategy,
            k_neighbors=k_neighbors,
            random_state=random_state,
        )
    elif resampler_name == "undersample":
        resampler = RandomUnderSampler(
            sampling_strategy=sampling_strategy,
            random_state=random_state,
        )
    elif resampler_name == "oversample":
        resampler = RandomOverSampler(
            sampling_strategy=sampling_strategy,
            random_state=random_state,
        )
    elif resampler_name in ("none", "", None):
        return Pipeline([("clf", classifier)])
    else:
        raise ValueError(f"Unknown resampler: {resampler_name}")

    return Pipeline([("resampler", resampler), ("clf", classifier)])

