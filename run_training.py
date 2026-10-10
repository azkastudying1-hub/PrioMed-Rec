"""
run_training.py
----------------
Training entry point for PrioMed-Rec prioritization model (v2).

Labels: has_discrepancy — derived from Synthea longitudinal medication data
        (replaced v1 random proxy — see docs/DECISION_LOG.md LBL-001).

Models: RuleBaseline, LogisticRegression, RandomForest, XGBoost
Selection: multi-metric (primary: top_20pct_recall; tiebreaker: f1)
Eval:   Precision, Recall, F1, ROC-AUC, PR-AUC, Brier, confusion matrix,
        Top-K recall (5%, 10%, 20%) — simulates limited pharmacist capacity.

Usage:
    python run_training.py
"""

import json
from pathlib import Path

from src.models.train import train_all_models, save_best_model, MODEL_VERSION
from src.models.evaluate import compare_models, compute_metrics, select_best_model, final_test_report


def _print_topk(metrics: dict) -> None:
    """Pretty-print Top-K recall metrics (hackathon operational value metric)."""
    topk = metrics.get("top_k_recall", {})
    if topk:
        print("  Top-K Recall (pharmacist capacity simulation):")
        for k, v in topk.items():
            print(f"    {k}: {v:.4f}")


def main() -> None:
    print("=" * 65)
    print(f"PrioMed-Rec Model Training  [version={MODEL_VERSION}]")
    print("Label : has_discrepancy (binary 0/1) — longitudinal derivation v2")
    print("Select: multi-metric (primary=top_20pct_recall, tiebreaker=f1)")
    print("=" * 65)

    # ── 1. Train all models ────────────────────────────────────────────────
    result = train_all_models(
        model_ready_path="data/processed/model_ready.csv",
        target_col="has_discrepancy",
        seed=42,
    )

    models       = result["models"]
    X_val        = result["X_val"]
    y_val        = result["y_val"]
    X_test       = result["X_test"]
    y_test       = result["y_test"]
    feature_cols = result["feature_cols"]

    # ── 2. Full metric comparison on validation set ────────────────────────
    print("\n[evaluate] Validation set — full metric comparison:")
    val_rows = []
    for name, model in models.items():
        m = compute_metrics(model, X_val, y_val, model_name=name,
                            top_k_fractions=[0.05, 0.10, 0.20])
        topk = m.get("top_k_recall", {})
        val_rows.append({
            "model":            name,
            "split":            "validation",
            "accuracy":         m["accuracy"],
            "precision":        m["precision"],
            "recall":           m["recall"],
            "f1":               m["f1"],
            "roc_auc":          m.get("roc_auc"),
            "pr_auc":           m.get("pr_auc"),
            "brier":            m.get("brier"),
            "top_5pct_recall":  topk.get("top_5pct_recall"),
            "top_10pct_recall": topk.get("top_10pct_recall"),
            "top_20pct_recall": topk.get("top_20pct_recall"),
        })

    import pandas as pd
    val_comparison = pd.DataFrame(val_rows)

    display_cols = ["model", "precision", "recall", "f1",
                    "roc_auc", "pr_auc", "brier",
                    "top_10pct_recall", "top_20pct_recall"]
    print(val_comparison[[c for c in display_cols if c in val_comparison.columns]].to_string(index=False))

    # ── 3. Multi-metric model selection ───────────────────────────────────
    best_name  = select_best_model(val_comparison)
    best_model = models[best_name]
    print(f"\n[select] Best model: {best_name}")

    # ── 4. Final test-set evaluation (one time only) ───────────────────────
    test_metrics = final_test_report(best_model, X_test, y_test, best_name)

    print(f"\n[evaluate] Test set results — {best_name}:")
    scalar_keys = [k for k in test_metrics if k not in ("confusion_matrix", "top_k_recall")]
    for k in scalar_keys:
        print(f"  {k}: {test_metrics[k]}")
    _print_topk(test_metrics)
    if "confusion_matrix" in test_metrics:
        print(f"  confusion_matrix: {test_metrics['confusion_matrix']}")

    # ── 5. Save best model + metadata ─────────────────────────────────────
    save_best_model(
        model=best_model,
        model_name=best_name,
        feature_cols=feature_cols,
        out_dir="models",
    )

    # ── 6. Save eval_report.json ───────────────────────────────────────────
    eval_report = {
        "model_version":     MODEL_VERSION,
        "best_model":        best_name,
        "target":            "has_discrepancy",
        "label_version":     "labels-2.0.0",
        "label_strategy":    "longitudinal_synthea_derivation",
        "selection_metric":  "top_20pct_recall (primary), f1 (tiebreaker)",
        "note": (
            "Labels are controlled synthetic engineering targets derived from "
            "Synthea longitudinal medication data. They are NOT clinical ground truth. "
            "Software correctness ≠ ML validity ≠ clinical validation."
        ),
        "validation":        val_comparison.to_dict(orient="records"),
        "test":              test_metrics,
    }
    eval_path = Path("models/eval_report.json")
    with open(eval_path, "w") as fh:
        json.dump(eval_report, fh, indent=2, default=str)
    print(f"\n[train] Eval report saved: {eval_path}")

    # ── 7. Summary ────────────────────────────────────────────────────────
    print("\n" + "=" * 65)
    print("[done] Training complete.")
    print(f"  Model version : {MODEL_VERSION}")
    print(f"  Best model    : {best_name}")
    print(f"  Test ROC-AUC  : {test_metrics.get('roc_auc', 'N/A')}")
    print(f"  Test F1       : {test_metrics.get('f1', 'N/A')}")
    topk = test_metrics.get("top_k_recall", {})
    print(f"  Top-20% recall: {topk.get('top_20pct_recall', 'N/A')}")
    print("=" * 65)
    print()
    print("IMPORTANT: These metrics reflect performance on SYNTHETIC labels.")
    print("ROC-AUC > 0.50 confirms structural signal (not random proxy).")
    print("This is NOT clinical validation. Do not claim clinical accuracy.")


if __name__ == "__main__":
    main()
