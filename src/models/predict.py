"""
src/models/predict.py
----------------------
Inference interface for the trained prioritization model.

Provides:
  predict_single(feature_dict)  → single encounter prediction
  predict_batch(feature_df)     → batch DataFrame prediction

Output contract (PROJECT_CONTEXT §19):
  {
    "encounter_id": str,
    "risk_probability": float [0.0, 1.0],
    "priority": "LOW" | "MEDIUM" | "HIGH",
    "model_version": str
  }

Clinical safety: risk_probability is a MODEL ESTIMATE, not a clinical
probability of error. All outputs require pharmacist review.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Union

import joblib
import numpy as np
import pandas as pd

from src.features.feature_pipeline import FEATURE_COLUMNS

DEFAULT_MODEL_PATH      = "models/priomed_prioritization_model.pkl"
DEFAULT_METADATA_PATH   = "models/metadata.json"
DEFAULT_THRESHOLDS_PATH = "models/thresholds.json"


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

def load_model(model_path: str = DEFAULT_MODEL_PATH):
    """Load a trained model from disk."""
    return joblib.load(model_path)


def load_thresholds(thresholds_path: str = DEFAULT_THRESHOLDS_PATH) -> dict:
    with open(thresholds_path, encoding="utf-8") as fh:
        return json.load(fh)


def load_metadata(metadata_path: str = DEFAULT_METADATA_PATH) -> dict:
    with open(metadata_path, encoding="utf-8") as fh:
        return json.load(fh)


# ---------------------------------------------------------------------------
# Priority mapping
# ---------------------------------------------------------------------------

def _label_to_priority(label: int, thresholds: dict) -> str:
    """Map ordinal label (0/1/2) to priority string."""
    mapping = thresholds.get("mapping", {"2": "HIGH", "1": "MEDIUM", "0": "LOW"})
    return mapping.get(str(label), "LOW")


def _proba_to_priority(prob: float, thresholds: dict) -> str:
    """Map probability to priority string using threshold values."""
    if prob >= thresholds.get("high", 0.70):
        return "HIGH"
    if prob >= thresholds.get("medium", 0.40):
        return "MEDIUM"
    return "LOW"


# ---------------------------------------------------------------------------
# Prediction functions
# ---------------------------------------------------------------------------

def predict_single(
    feature_dict: dict,
    model=None,
    thresholds: dict | None = None,
    metadata: dict | None = None,
    model_path: str = DEFAULT_MODEL_PATH,
    thresholds_path: str = DEFAULT_THRESHOLDS_PATH,
    metadata_path: str = DEFAULT_METADATA_PATH,
) -> dict:
    """
    Predict risk for a single encounter.

    Parameters
    ----------
    feature_dict : dict mapping feature_name → value.
                   Must contain all features from FEATURE_COLUMNS.
    model, thresholds, metadata : pre-loaded objects (optional, for performance).

    Returns
    -------
    dict: encounter_id (if in feature_dict), risk_probability, priority, model_version
    """
    if model is None:
        model = load_model(model_path)
    if thresholds is None:
        thresholds = load_thresholds(thresholds_path)
    if metadata is None:
        metadata = load_metadata(metadata_path)

    feature_cols = metadata.get("feature_columns", FEATURE_COLUMNS)
    x = np.array([[feature_dict.get(c, 0) for c in feature_cols]])

    proba = model.predict_proba(x)[0]
    label = int(model.predict(x)[0])

    # Use class-1 probability for binary; max(proba) for multi-class
    if len(proba) == 2:
        risk_prob = float(proba[1])
        priority  = _proba_to_priority(risk_prob, thresholds)
    else:
        risk_prob = float(max(proba))
        priority  = _label_to_priority(label, thresholds)

    return {
        "encounter_id":    feature_dict.get("encounter_id", ""),
        "risk_probability": round(risk_prob, 4),
        "priority":         priority,
        "model_version":    metadata.get("model_version", "unknown"),
    }


def predict_batch(
    feature_df: pd.DataFrame,
    model=None,
    thresholds: dict | None = None,
    metadata: dict | None = None,
    model_path: str = DEFAULT_MODEL_PATH,
    thresholds_path: str = DEFAULT_THRESHOLDS_PATH,
    metadata_path: str = DEFAULT_METADATA_PATH,
) -> pd.DataFrame:
    """
    Predict risk for a batch of encounters.

    Parameters
    ----------
    feature_df : DataFrame with feature columns (encounter_id as index or column).

    Returns
    -------
    pd.DataFrame with columns: encounter_id, risk_probability, priority, model_version
    """
    if model is None:
        model = load_model(model_path)
    if thresholds is None:
        thresholds = load_thresholds(thresholds_path)
    if metadata is None:
        metadata = load_metadata(metadata_path)

    feature_cols = metadata.get("feature_columns", FEATURE_COLUMNS)

    # Build feature matrix
    available_cols = [c for c in feature_cols if c in feature_df.columns]
    X = feature_df[available_cols].fillna(0).values

    probas = model.predict_proba(X)
    labels = model.predict(X)

    if probas.shape[1] == 2:
        risk_probs = probas[:, 1]
        priorities = [_proba_to_priority(p, thresholds) for p in risk_probs]
    else:
        risk_probs = probas.max(axis=1)
        priorities = [_label_to_priority(int(l), thresholds) for l in labels]

    enc_ids = (
        feature_df.index.tolist()
        if feature_df.index.name == "encounter_id"
        else feature_df.get("encounter_id", pd.Series(range(len(feature_df)))).tolist()
    )

    return pd.DataFrame({
        "encounter_id":    enc_ids,
        "risk_probability": [round(float(p), 4) for p in risk_probs],
        "priority":         priorities,
        "model_version":    metadata.get("model_version", "unknown"),
    })
