"""
src/models/train.py
--------------------
Patient-level train/validation/test split and model training.

CRITICAL — Patient-level split (Sub-Task 7 Acceptance Criterion):
  All encounters belonging to the same patient must be in the same split.
  This prevents information leakage between encounters of the same patient.

Models trained (in order):
  1. Rule Baseline    — RuleBaselineClassifier from src/rules/rule_evaluator.py
  2. Logistic Regression
  3. Random Forest
  4. XGBoost

Model selection is based on validation set performance — the test set
is used ONLY for the final report (one time).

Target: has_discrepancy (binary 0/1) — independent from ML features.
        Labels come from synthetic_case_generator.py mutation sampling.
        NOT review_priority (which was derived from feature columns → leakage).
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Tuple

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from xgboost import XGBClassifier

from src.features.feature_pipeline import FEATURE_COLUMNS, FEATURE_VERSION
from src.rules.rule_evaluator import RuleBaselineClassifier

MODEL_DIR = Path("models")
MODEL_VERSION = "model-0.3.0"

# Patient-level split ratios
TRAIN_RATIO = 0.70
VAL_RATIO   = 0.15
TEST_RATIO  = 0.15


# ---------------------------------------------------------------------------
# Patient-level split
# ---------------------------------------------------------------------------

def patient_level_split(
    df: pd.DataFrame,
    patient_col: str = "patient_id",
    seed: int = 42,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Split *df* so that all rows belonging to the same patient_id land in
    the same partition (train / val / test).

    Returns
    -------
    (train_df, val_df, test_df)
    """
    rng = np.random.default_rng(seed)
    patients = list(df[patient_col].unique())
    rng.shuffle(patients)

    n = len(patients)
    n_train = int(n * TRAIN_RATIO)
    n_val   = int(n * VAL_RATIO)

    train_pats = set(patients[:n_train])
    val_pats   = set(patients[n_train:n_train + n_val])
    test_pats  = set(patients[n_train + n_val:])

    train = df[df[patient_col].isin(train_pats)].copy()
    val   = df[df[patient_col].isin(val_pats)].copy()
    test  = df[df[patient_col].isin(test_pats)].copy()

    return train, val, test


# ---------------------------------------------------------------------------
# Model builders
# ---------------------------------------------------------------------------

def _build_lr(seed: int = 42) -> LogisticRegression:
    return LogisticRegression(
        max_iter=1000, random_state=seed, class_weight="balanced", C=1.0
    )


def _build_rf(seed: int = 42) -> RandomForestClassifier:
    return RandomForestClassifier(
        n_estimators=200, max_depth=8, min_samples_leaf=5,
        class_weight="balanced", random_state=seed, n_jobs=-1
    )


def _build_xgb(seed: int = 42, scale_pos_weight: float = 1.0) -> XGBClassifier:
    """
    Binary XGBoost classifier.

    scale_pos_weight handles class imbalance: set to
    (n_negative / n_positive) so minority class gets more weight.
    For has_discrepancy: class-0 is minority (23.7%) → weight > 1.
    """
    return XGBClassifier(
        n_estimators=300, max_depth=6, learning_rate=0.05,
        subsample=0.8, colsample_bytree=0.8,
        scale_pos_weight=scale_pos_weight,
        eval_metric="logloss", random_state=seed, n_jobs=-1,
    )


# ---------------------------------------------------------------------------
# Training entry point
# ---------------------------------------------------------------------------

def train_all_models(
    model_ready_path: str = "data/processed/model_ready.csv",
    target_col: str = "has_discrepancy",
    seed: int = 42,
) -> dict:
    """
    Load model_ready.csv, split by patient, train all 4 models,
    and return the trained models + split data.

    Target: has_discrepancy (binary 0/1).
    Previous default 'review_priority' caused target leakage (F1=1.0)
    because it was derived directly from the same feature columns.

    Parameters
    ----------
    model_ready_path : path to model_ready.csv
    target_col : default 'has_discrepancy' — independent binary label
    seed : random seed

    Returns
    -------
    dict with keys:
        models, X_train, X_val, X_test, y_train, y_val, y_test,
        train_df, val_df, test_df, feature_cols, target_col
    """
    print(f"[train] Loading {model_ready_path}")
    df = pd.read_csv(model_ready_path, index_col="encounter_id")

    # Patient_id column must exist (join from cohort)
    if "patient_id" not in df.columns:
        raise ValueError("model_ready.csv must contain 'patient_id' column")

    feature_cols = [c for c in FEATURE_COLUMNS if c in df.columns]
    print(f"[train] Using {len(feature_cols)} features, target={target_col}")

    # Patient-level split
    df_reset = df.reset_index()
    train_df, val_df, test_df = patient_level_split(df_reset, seed=seed)
    print(f"[train] Split — Train: {len(train_df):,} | Val: {len(val_df):,} | Test: {len(test_df):,}")

    X_train = train_df[feature_cols].values
    y_train = train_df[target_col].values
    X_val   = val_df[feature_cols].values
    y_val   = val_df[target_col].values
    X_test  = test_df[feature_cols].values
    y_test  = test_df[target_col].values

    # Class imbalance weight for XGBoost binary
    # has_discrepancy=1 is majority (76.3%), class-0 is minority → weight > 1
    n_pos = int(y_train.sum())
    n_neg = len(y_train) - n_pos
    spw = round(n_neg / n_pos, 4) if n_pos > 0 else 1.0
    print(f"[train] Class distribution — pos(1): {n_pos:,} | neg(0): {n_neg:,} | scale_pos_weight={spw}")

    models = {}

    # 1. Rule Baseline (sklearn wrapper — no training data needed)
    print("[train] Building Rule Baseline...")
    rule_baseline = RuleBaselineClassifier(train_df=train_df)
    rule_baseline.fit(X_train, y_train)
    models["RuleBaseline"] = rule_baseline

    # 2. Logistic Regression
    print("[train] Training Logistic Regression...")
    lr = _build_lr(seed)
    lr.fit(X_train, y_train)
    models["LogisticRegression"] = lr

    # 3. Random Forest
    print("[train] Training Random Forest...")
    rf = _build_rf(seed)
    rf.fit(X_train, y_train)
    models["RandomForest"] = rf

    # 4. XGBoost (with class-imbalance weight for minority class 0)
    print("[train] Training XGBoost...")
    xgb = _build_xgb(seed, scale_pos_weight=spw)
    xgb.fit(X_train, y_train, verbose=False)
    models["XGBoost"] = xgb

    return {
        "models": models,
        "X_train": X_train, "y_train": y_train,
        "X_val":   X_val,   "y_val":   y_val,
        "X_test":  X_test,  "y_test":  y_test,
        "train_df": train_df, "val_df": val_df, "test_df": test_df,
        "feature_cols": feature_cols,
        "target_col": target_col,
    }


def save_best_model(
    model,
    model_name: str,
    feature_cols: list[str],
    rule_version: str = "rules-0.1.0",
    out_dir: str = "models",
) -> None:
    """Save model .pkl + metadata.json + thresholds.json."""
    out = Path(out_dir)
    out.mkdir(exist_ok=True)

    pkl_path = out / "priomed_prioritization_model.pkl"
    joblib.dump(model, pkl_path)

    metadata = {
        "model_version":   MODEL_VERSION,
        "model_name":      model_name,
        "feature_version": FEATURE_VERSION,
        "rule_version":    rule_version,
        "feature_columns": feature_cols,
        "training_date":   datetime.utcnow().isoformat() + "Z",
        "note": (
            "Trained on synthetic Synthea data. Labels are engineered proxies. "
            "Not validated for clinical use."
        ),
    }
    with open(out / "metadata.json", "w") as fh:
        json.dump(metadata, fh, indent=2)

    thresholds = {
        "threshold_version": "thresholds-0.1.0",
        "high":   0.70,
        "medium": 0.40,
        "mapping": {
            "2": "HIGH",
            "1": "MEDIUM",
            "0": "LOW",
        },
        "note": "Thresholds are provisional — set by project team, not clinically validated.",
    }
    with open(out / "thresholds.json", "w") as fh:
        json.dump(thresholds, fh, indent=2)

    print(f"[train] Model saved: {pkl_path}")
    print(f"[train] Metadata:    {out / 'metadata.json'}")
    print(f"[train] Thresholds:  {out / 'thresholds.json'}")
