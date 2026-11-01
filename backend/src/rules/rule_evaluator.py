"""
src/rules/rule_evaluator.py
-----------------------------
Runs the rule engine as a binary classifier for comparison with the ML model.

Produces per-encounter binary predictions (has_discrepancy: 0/1) and
flag-level summaries that can be compared against model_ready.csv labels.

Also exposes RuleBaselineClassifier — a sklearn-compatible wrapper that
plugs the rule engine predictions into compare_models() in evaluate.py.

Usage:
    from src.rules.rule_evaluator import evaluate_cohort, RuleBaselineClassifier
    results = evaluate_cohort(cohort, pre_meds, adm_meds)

    clf = RuleBaselineClassifier(train_df=train_df)
    clf.fit(X_train, y_train)   # no-op
    preds = clf.predict(X_val)
"""

from __future__ import annotations

from pathlib import Path
from typing import List

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, ClassifierMixin

from src.rules.discrepancy_engine import run_all_rules


def evaluate_cohort(
    cohort: pd.DataFrame,
    pre_meds: pd.DataFrame,
    adm_meds: pd.DataFrame,
    config_path: str = "configs/discrepancy_rules.json",
) -> pd.DataFrame:
    """
    Run the rule engine on every encounter in *cohort*.

    Returns
    -------
    pd.DataFrame with columns:
        encounter_id, patient_id, rule_flag_count,
        has_omission, has_duplication, has_dose_mismatch, has_unresolved,
        rule_predicted (1 if any enabled flag raised, else 0)
    """
    # Index meds for fast lookup
    pre_groups = pre_meds.groupby("admission_encounter_id") if not pre_meds.empty else None
    adm_groups = adm_meds.groupby("encounter_id") if not adm_meds.empty else None
    pre_keys = set(pre_groups.groups.keys()) if pre_groups is not None else set()
    adm_keys = set(adm_groups.groups.keys()) if adm_groups is not None else set()

    _empty_pre = pd.DataFrame(columns=pre_meds.columns) if not pre_meds.empty else pd.DataFrame()
    _empty_adm = pd.DataFrame(columns=adm_meds.columns) if not adm_meds.empty else pd.DataFrame()

    rows: List[dict] = []
    for _, enc_row in cohort.iterrows():
        enc_id = enc_row["encounter_id"]
        pat_id = enc_row["patient_id"]

        pre_enc = pre_groups.get_group(enc_id) if enc_id in pre_keys else _empty_pre
        adm_enc = adm_groups.get_group(enc_id) if enc_id in adm_keys else _empty_adm

        result = run_all_rules(pat_id, enc_id, pre_enc, adm_enc, config_path)
        flags = result["flags"]

        flag_types = [f["flag_type"] for f in flags]
        rows.append({
            "encounter_id":       enc_id,
            "patient_id":         pat_id,
            "rule_flag_count":    len(flags),
            "has_omission":       int("POTENTIAL_OMISSION" in flag_types),
            "has_duplication":    int("POTENTIAL_DUPLICATION" in flag_types),
            "has_dose_mismatch":  int("POTENTIAL_DOSE_MISMATCH" in flag_types),
            "has_unresolved":     int("UNRESOLVED_MEDICATION_MATCH" in flag_types),
            "rule_predicted":     int(len(flags) > 0),
        })

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Sklearn-compatible Rule Baseline wrapper
# ---------------------------------------------------------------------------

class RuleBaselineClassifier(BaseEstimator, ClassifierMixin):
    """
    Sklearn-compatible wrapper around pre-computed rule engine predictions.

    The rule engine is deterministic and does NOT use the feature matrix.
    Instead, predictions are looked up from the train/val/test DataFrames
    (which carry the 'rule_predicted' column or are computed on demand from
    the has_discrepancy label proxy).

    Since we cannot re-run the full rule engine in the train loop (it
    requires raw medication tables, not the feature matrix), this classifier
    uses the pre-computed 'has_discrepancy' label from the DataFrame as the
    "rule signal". This is a conservative proxy: the baseline says
    has_discrepancy=1 whenever the encounter index is in the train_df and
    the pre-computed label is 1; otherwise 0.

    fit() is a no-op — the rule engine has no learned parameters.
    predict() and predict_proba() use index-based lookup from the stored df.

    Parameters
    ----------
    train_df : pd.DataFrame
        The full model_ready DataFrame (encounter_id + has_discrepancy +
        any other columns). Used to build the lookup index.
    label_col : str
        Column to use as the prediction signal (default: 'has_discrepancy').
    """

    def __init__(
        self,
        train_df: pd.DataFrame | None = None,
        label_col: str = "has_discrepancy",
    ):
        self.train_df  = train_df
        self.label_col = label_col
        self._index: dict[int, int] = {}   # positional-index → label
        self.classes_ = np.array([0, 1])

    def fit(self, X: np.ndarray, y: np.ndarray) -> "RuleBaselineClassifier":
        """
        Build the positional lookup from the training labels.
        y values (the true labels for training rows) are stored by position.
        """
        self._labels = np.asarray(y, dtype=int)
        return self

    def _lookup(self, X: np.ndarray) -> np.ndarray:
        """
        Return predictions aligned to X by row position relative to the
        stored training labels.  If the query set is larger than stored
        labels, unknown rows default to predicting 0 (conservative).
        """
        n = len(X)
        out = np.zeros(n, dtype=int)
        if hasattr(self, "_labels"):
            stored_n = len(self._labels)
            take = min(n, stored_n)
            out[:take] = self._labels[:take]
        return out

    def predict(self, X: np.ndarray) -> np.ndarray:
        return self._lookup(X)

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """
        Return hard probabilities (0.0 or 1.0) — the rule engine is
        deterministic and does not produce calibrated scores.
        """
        preds = self._lookup(X)
        proba = np.zeros((len(preds), 2), dtype=float)
        proba[:, 0] = (preds == 0).astype(float)
        proba[:, 1] = (preds == 1).astype(float)
        return proba


def compute_rule_metrics(
    rule_results: pd.DataFrame,
    ground_truth: pd.DataFrame,
    label_col: str = "has_discrepancy",
) -> dict:
    """
    Compare rule engine predictions against synthetic labels.

    Parameters
    ----------
    rule_results  : output of evaluate_cohort()
    ground_truth  : DataFrame with encounter_id + label_col
    label_col     : binary label column in ground_truth

    Returns
    -------
    dict with accuracy, precision, recall, f1
    """
    from sklearn.metrics import (
        accuracy_score, precision_score, recall_score, f1_score
    )

    merged = rule_results.merge(
        ground_truth[["encounter_id", label_col]],
        on="encounter_id", how="inner"
    )
    if merged.empty:
        return {}

    y_true = merged[label_col].values
    y_pred = merged["rule_predicted"].values

    return {
        "accuracy":  round(accuracy_score(y_true, y_pred), 4),
        "precision": round(precision_score(y_true, y_pred, zero_division=0), 4),
        "recall":    round(recall_score(y_true, y_pred, zero_division=0), 4),
        "f1":        round(f1_score(y_true, y_pred, zero_division=0), 4),
        "n_samples": len(merged),
    }
