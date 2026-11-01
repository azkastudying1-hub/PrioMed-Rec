"""
src/models/evaluate.py
-----------------------
Comprehensive model evaluation per TRIPOD+AI guidelines.

Metrics: accuracy, precision, recall, F1, ROC-AUC, PR-AUC,
         Brier score, calibration, confusion matrix, Top-K recall.

All metrics are computed on the VALIDATION set for model selection.
The test set is used ONLY in final_test_report().
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    roc_auc_score, average_precision_score,
    brier_score_loss, confusion_matrix,
)


# ---------------------------------------------------------------------------
# Core metrics
# ---------------------------------------------------------------------------

def compute_metrics(
    model,
    X: np.ndarray,
    y_true: np.ndarray,
    model_name: str = "model",
    top_k_fractions: list[float] | None = None,
) -> dict[str, Any]:
    """
    Compute the full evaluation suite for a model on dataset (X, y_true).

    Parameters
    ----------
    model : fitted sklearn/xgboost estimator
    X     : feature matrix
    y_true: ground-truth labels (binary 0/1 or ordinal 0/1/2)
    model_name : label for output dict
    top_k_fractions : fractions of the dataset to evaluate Top-K recall
                      (e.g. [0.10, 0.20] = top 10% and 20%)

    Returns
    -------
    dict with all metric values
    """
    if top_k_fractions is None:
        top_k_fractions = [0.05, 0.10, 0.20]

    y_pred_proba = model.predict_proba(X)
    y_pred = model.predict(X)

    # For binary AUC: use class-1 probability
    if y_pred_proba.shape[1] == 2:
        y_score = y_pred_proba[:, 1]
    else:
        # Multi-class: macro OvR
        y_score = y_pred_proba

    # Binary metrics (treat >0 as positive for ordinal)
    y_bin = (y_true > 0).astype(int)
    y_pred_bin = (y_pred > 0).astype(int)

    metrics: dict[str, Any] = {
        "model_name":  model_name,
        "n_samples":   len(y_true),
        "accuracy":    round(float(accuracy_score(y_true, y_pred)), 4),
        "precision":   round(float(precision_score(y_bin, y_pred_bin, zero_division=0)), 4),
        "recall":      round(float(recall_score(y_bin, y_pred_bin, zero_division=0)), 4),
        "f1":          round(float(f1_score(y_bin, y_pred_bin, zero_division=0)), 4),
    }

    # ROC-AUC
    try:
        if y_pred_proba.shape[1] == 2:
            metrics["roc_auc"] = round(float(roc_auc_score(y_bin, y_score)), 4)
            metrics["pr_auc"]  = round(float(average_precision_score(y_bin, y_score)), 4)
            metrics["brier"]   = round(float(brier_score_loss(y_bin, y_score)), 4)
        else:
            metrics["roc_auc"] = round(float(roc_auc_score(
                y_true, y_score, multi_class="ovr", average="macro"
            )), 4)
            metrics["pr_auc"]  = None
            metrics["brier"]   = None
    except Exception:  # noqa: BLE001
        metrics["roc_auc"] = None
        metrics["pr_auc"]  = None
        metrics["brier"]   = None

    # Confusion matrix
    metrics["confusion_matrix"] = confusion_matrix(y_true, y_pred).tolist()

    # Top-K recall (simulate pharmacist capacity)
    if y_pred_proba.shape[1] == 2:
        topk = {}
        high_priority = (y_true > 0).astype(int)
        scores = y_score
        for frac in top_k_fractions:
            k = max(1, int(len(y_true) * frac))
            top_k_idx = np.argsort(scores)[::-1][:k]
            topk[f"top_{int(frac*100)}pct_recall"] = round(
                float(high_priority[top_k_idx].sum() / max(high_priority.sum(), 1)), 4
            )
        metrics["top_k_recall"] = topk

    return metrics


def compare_models(
    models: dict,
    X: np.ndarray,
    y_true: np.ndarray,
    split_name: str = "validation",
) -> pd.DataFrame:
    """
    Run compute_metrics for all models and return a comparison DataFrame.
    """
    rows = []
    for name, model in models.items():
        m = compute_metrics(model, X, y_true, model_name=name)
        rows.append({
            "model":     name,
            "split":     split_name,
            "accuracy":  m["accuracy"],
            "precision": m["precision"],
            "recall":    m["recall"],
            "f1":        m["f1"],
            "roc_auc":   m.get("roc_auc"),
            "pr_auc":    m.get("pr_auc"),
            "brier":     m.get("brier"),
        })
    return pd.DataFrame(rows)


def select_best_model(comparison_df: pd.DataFrame) -> str:
    """
    Select best model using multi-metric evidence per revised spec (§8, §9).

    Primary criterion : top_20pct_recall (operational value under limited
                        pharmacist capacity — key hackathon metric)
    Tiebreaker (±0.02): f1
    Fallback           : roc_auc if top_k recall unavailable

    Selection rationale is printed to stdout and must be recorded in
    docs/DECISION_LOG.md.
    """
    df = comparison_df.copy()

    # Prefer top_20pct_recall as primary operational metric
    if "top_20pct_recall" in df.columns:
        primary = "top_20pct_recall"
    elif "roc_auc" in df.columns:
        primary = "roc_auc"
    else:
        primary = "f1"

    valid = df.dropna(subset=[primary])
    if valid.empty:
        valid = df
        primary = "f1"

    best_primary = valid[primary].max()
    # Candidates within 0.02 of best (tie zone)
    candidates = valid[valid[primary] >= best_primary - 0.02]

    # Break ties using f1
    if "f1" in candidates.columns:
        best_row = candidates.loc[candidates["f1"].idxmax()]
    else:
        best_row = candidates.loc[candidates[primary].idxmax()]

    print(
        f"[evaluate] Multi-metric selection — primary={primary}: "
        f"{best_row['model']} ({best_row[primary]:.4f})"
    )
    if "f1" in best_row:
        print(f"[evaluate]   F1={best_row.get('f1', 'N/A'):.4f}  "
              f"ROC-AUC={best_row.get('roc_auc', 'N/A')}  "
              f"PR-AUC={best_row.get('pr_auc', 'N/A')}")
    return best_row["model"]


def final_test_report(
    model,
    X_test: np.ndarray,
    y_test: np.ndarray,
    model_name: str,
) -> dict:
    """
    Compute metrics on the TEST set. Call this exactly ONCE after model selection.
    """
    print(f"[evaluate] Running final test evaluation for {model_name}…")
    metrics = compute_metrics(model, X_test, y_test, model_name=model_name)
    metrics["split"] = "test"
    return metrics
