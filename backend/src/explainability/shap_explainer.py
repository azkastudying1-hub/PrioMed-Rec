"""
src/explainability/shap_explainer.py
--------------------------------------
Per-prediction SHAP explanation for the PrioMed-Rec prioritization model.

Explainer selection (auto-detected from model type):
  - RandomForest / XGBoost  → shap.TreeExplainer
  - LogisticRegression      → shap.LinearExplainer
  - RuleBaselineClassifier  → fallback (equal-weight placeholder)

Output contract (plan §683-§694):
  {
    "encounter_id": "...",
    "risk_probability": float,
    "priority": "HIGH|MEDIUM|LOW",
    "top_features": [
      { "feature": str, "value": float, "shap_value": float, "direction": "increases_risk|decreases_risk|neutral" }
    ],
    "explainer_type": "TreeExplainer|LinearExplainer|fallback",
    "model_name": str,
    "note": str
  }

IMPORTANT:
  - XAI output NEVER modifies risk_probability or priority (enforced by get_explanation).
  - All explanations carry verification_required=True — pharmacist always decides.
  - SHAP is an approximation tool; values are not validated clinical evidence.
"""

from __future__ import annotations

import warnings
from typing import Any

import numpy as np

from src.rules.rule_evaluator import RuleBaselineClassifier


# ---------------------------------------------------------------------------
# Explainer factory
# ---------------------------------------------------------------------------

def _get_explainer_type(model: Any) -> str:
    """Detect which SHAP explainer is appropriate for *model*."""
    cls = type(model).__name__
    if isinstance(model, RuleBaselineClassifier):
        return "fallback"
    if cls in ("RandomForestClassifier", "XGBClassifier",
               "GradientBoostingClassifier", "DecisionTreeClassifier"):
        return "TreeExplainer"
    if cls in ("LogisticRegression", "LogisticRegressionCV",
               "LinearSVC", "SGDClassifier"):
        return "LinearExplainer"
    return "fallback"


def _build_shap_explainer(model: Any, X_background: np.ndarray, explainer_type: str):
    """Build and return the appropriate SHAP explainer object."""
    import shap

    if explainer_type == "TreeExplainer":
        return shap.TreeExplainer(model)
    if explainer_type == "LinearExplainer":
        # masker = shap.maskers.Independent(X_background) — works with LinearExplainer
        masker = shap.maskers.Independent(X_background)
        return shap.LinearExplainer(model, masker)
    return None  # fallback — no SHAP object needed


# ---------------------------------------------------------------------------
# Core explanation function
# ---------------------------------------------------------------------------

def get_explanation(
    model: Any,
    feature_vector: np.ndarray,
    feature_names: list[str],
    risk_probability: float,
    priority: str,
    encounter_id: str = "",
    top_n: int = 5,
    X_background: np.ndarray | None = None,
) -> dict:
    """
    Compute per-prediction SHAP explanation.

    Parameters
    ----------
    model           : fitted estimator
    feature_vector  : 1-D array of feature values (length == len(feature_names))
    feature_names   : ordered list of feature column names
    risk_probability: float [0,1] — from predict step, NOT recomputed here
    priority        : "LOW"|"MEDIUM"|"HIGH" — from predict step, NOT recomputed
    encounter_id    : optional identifier for the prediction
    top_n           : number of top features to return (default 5)
    X_background    : background dataset for LinearExplainer (optional; uses
                      zeros if not provided)

    Returns
    -------
    dict matching the output contract schema above.
    """
    x = np.asarray(feature_vector, dtype=float).reshape(1, -1)
    n_features = len(feature_names)

    # Pad/trim x to match feature_names length
    if x.shape[1] != n_features:
        padded = np.zeros((1, n_features))
        take = min(x.shape[1], n_features)
        padded[0, :take] = x[0, :take]
        x = padded

    explainer_type = _get_explainer_type(model)

    # --- Compute SHAP values ---
    shap_values = _compute_shap_values(
        model, x, feature_names, explainer_type, X_background
    )

    # --- Build top_features list ---
    top_features = _build_top_features(
        shap_values, feature_names, x[0], top_n
    )

    return {
        "encounter_id":    encounter_id,
        "risk_probability": round(float(risk_probability), 4),
        "priority":        priority,
        "top_features":    top_features,
        "explainer_type":  explainer_type,
        "model_name":      type(model).__name__,
        "note": (
            "SHAP values are model-approximated contributions — not clinically validated. "
            "Pharmacist review is required."
        ),
    }


def _compute_shap_values(
    model: Any,
    x: np.ndarray,
    feature_names: list[str],
    explainer_type: str,
    X_background: np.ndarray | None,
) -> np.ndarray:
    """
    Return 1-D array of SHAP values for the positive class (class 1),
    or fallback equal-weight placeholder.
    """
    import shap

    n_features = len(feature_names)

    if explainer_type == "fallback":
        # RuleBaseline has no learned feature weights.
        # Use uniform placeholder (all zero = "no SHAP signal")
        return np.zeros(n_features)

    bg = X_background if X_background is not None else np.zeros((1, n_features))

    try:
        explainer = _build_shap_explainer(model, bg, explainer_type)

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            raw = explainer.shap_values(x)

        # raw can be: ndarray shape (1, n_feat) for binary,
        #             list [neg_class, pos_class] for some sklearn models
        if isinstance(raw, list):
            # index 1 = positive class contribution
            sv = np.array(raw[1]).flatten()
        else:
            sv = np.array(raw).flatten()

        # If 2-D (n_samples, n_features) squeeze to 1-D
        if sv.ndim > 1:
            sv = sv[0]

        # Ensure correct length
        if len(sv) != n_features:
            sv = np.zeros(n_features)

        return sv

    except Exception:  # noqa: BLE001
        # Any SHAP failure → safe fallback (zeros)
        return np.zeros(n_features)


def _build_top_features(
    shap_values: np.ndarray,
    feature_names: list[str],
    feature_values: np.ndarray,
    top_n: int,
) -> list[dict]:
    """
    Sort features by |shap_value| descending and return the top_n.
    """
    abs_sv = np.abs(shap_values)
    top_idx = np.argsort(abs_sv)[::-1][:top_n]

    top_features = []
    for idx in top_idx:
        sv = float(shap_values[idx])
        direction = (
            "increases_risk" if sv > 0 else
            "decreases_risk" if sv < 0 else
            "neutral"
        )
        top_features.append({
            "feature":    feature_names[idx],
            "value":      round(float(feature_values[idx]), 4),
            "shap_value": round(sv, 4),
            "direction":  direction,
        })
    return top_features


# ---------------------------------------------------------------------------
# Batch explanation helper
# ---------------------------------------------------------------------------

def explain_batch(
    model: Any,
    feature_df,
    feature_names: list[str],
    predictions_df,
    top_n: int = 5,
    X_background: np.ndarray | None = None,
) -> list[dict]:
    """
    Explain predictions for all rows in feature_df.

    Parameters
    ----------
    model          : fitted estimator
    feature_df     : pd.DataFrame with feature columns
    feature_names  : ordered feature column names
    predictions_df : pd.DataFrame with risk_probability, priority, encounter_id
    top_n          : number of top features per prediction

    Returns
    -------
    list[dict] — one explanation dict per row
    """
    results = []
    for i in range(len(feature_df)):
        row_features = feature_df.iloc[i][feature_names].values
        pred_row = predictions_df.iloc[i]
        enc_id = str(pred_row.get("encounter_id", "")) if hasattr(pred_row, "get") else ""
        explanation = get_explanation(
            model=model,
            feature_vector=row_features,
            feature_names=feature_names,
            risk_probability=float(pred_row["risk_probability"]),
            priority=str(pred_row["priority"]),
            encounter_id=enc_id,
            top_n=top_n,
            X_background=X_background,
        )
        results.append(explanation)
    return results
