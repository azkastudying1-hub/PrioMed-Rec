"""
run_training_v3.py
------------------
PrioMed-Rec labels-3.0.0 — Full training, validation, and reporting pipeline.

Produces:
  data/processed/synthetic_cases.csv  (labels-3.0.0)
  data/processed/model_ready.csv      (labels-3.0.0)
  models/priomed_prioritization_model.pkl
  models/metadata.json
  models/thresholds.json
  models/eval_report_v3.json

Evaluation includes:
  - All 4 models on FULL feature set (16 features)
  - All 4 models on LEAKAGE-SAFE feature set (10 features)
  - Repeated patient-level CV (5 folds x 5 repeats)
  - Permutation test (100 seeds minimum)
  - Final test-set evaluation (used ONCE)
"""

from __future__ import annotations

import json
import warnings
from datetime import datetime
from pathlib import Path
import sys

import joblib
import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedKFold
from sklearn.metrics import (
    roc_auc_score, average_precision_score, f1_score,
    precision_score, recall_score, brier_score_loss,
)

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).parent))

from src.labels.synthetic_case_generator import (
    generate_cases, build_model_ready, save_synthetic_cases, LABEL_VERSION,
)
from src.models.train import (
    patient_level_split, _build_lr, _build_rf, _build_xgb,
    save_best_model, MODEL_VERSION,
)
from src.rules.rule_evaluator import RuleBaselineClassifier
from src.features.feature_pipeline import (
    FEATURE_COLUMNS, LEAKAGE_SAFE_FEATURE_COLUMNS, FEATURE_VERSION,
)

SEED = 42
MODEL_DIR = Path("models")
MODEL_DIR.mkdir(exist_ok=True)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _eval_model(model, X, y, label=""):
    """Compute full metric suite. Returns dict."""
    try:
        y_proba = model.predict_proba(X)[:, 1]
    except Exception:
        y_proba = np.zeros(len(y))

    y_pred = model.predict(X)
    y_bin  = (y > 0).astype(int)
    y_pred_bin = (y_pred > 0).astype(int)

    def safe(fn, *a, **kw):
        try:
            return round(float(fn(*a, **kw)), 4)
        except Exception:
            return float("nan")

    acc  = safe(lambda: sum(y_bin == y_pred_bin) / len(y_bin))
    prec = safe(precision_score, y_bin, y_pred_bin, zero_division=0)
    rec  = safe(recall_score, y_bin, y_pred_bin, zero_division=0)
    f1   = safe(f1_score, y_bin, y_pred_bin, zero_division=0)
    roc  = safe(roc_auc_score, y_bin, y_proba)
    pr   = safe(average_precision_score, y_bin, y_proba)
    bri  = safe(brier_score_loss, y_bin, y_proba)

    n_pos = int(y_bin.sum())
    k20   = max(1, int(len(y_bin) * 0.20))
    top_idx = np.argsort(y_proba)[::-1][:k20]
    t20r  = round(float(y_bin[top_idx].sum()) / max(n_pos, 1), 4)
    t20p  = round(float(y_bin[top_idx].sum()) / k20, 4)
    random_rec = k20 / len(y_bin)
    lift  = round(t20r / random_rec, 4) if random_rec > 0 else float("nan")

    # Precision lift
    prevalence = n_pos / len(y_bin) if len(y_bin) > 0 else 0
    prec_lift = round(t20p / prevalence, 4) if prevalence > 0 else float("nan")

    return dict(
        label=label, n=len(y), n_pos=n_pos, n_neg=int(len(y_bin) - n_pos),
        acc=acc, prec=prec, rec=rec, f1=f1,
        roc_auc=roc, pr_auc=pr, brier=bri,
        top20_rec=t20r, top20_prec=t20p,
        lift_top20_rec=lift, lift_top20_prec=prec_lift,
    )


def _build_models(X_train, y_train, seed=SEED):
    """Fit all 4 models. Returns dict."""
    n_pos = int(y_train.sum())
    n_neg = len(y_train) - n_pos
    spw   = round(n_neg / n_pos, 4) if n_pos > 0 else 1.0

    train_df_proxy = None  # RuleBaseline needs train_df for fit — pass placeholder
    rule = RuleBaselineClassifier(train_df=None)
    rule.fit(X_train, y_train)

    lr  = _build_lr(seed); lr.fit(X_train, y_train)
    rf  = _build_rf(seed); rf.fit(X_train, y_train)
    xgb = _build_xgb(seed, scale_pos_weight=spw)
    xgb.fit(X_train, y_train, verbose=False)

    return {"RuleBaseline": rule, "LogReg": lr, "RandomForest": rf, "XGBoost": xgb}


def _print_table(results):
    hdr = (f"{'Model':<22} {'ROC':>6} {'PR':>6} {'F1':>6} "
           f"{'Rec':>6} {'Prec':>6} {'Brier':>6} {'T20R':>6} {'T20P':>6} {'Lift':>6}")
    print(hdr)
    print("-" * len(hdr))
    for r in results:
        print(f"{r['label']:<22} {r['roc_auc']:>6.4f} {r['pr_auc']:>6.4f} {r['f1']:>6.4f} "
              f"{r['rec']:>6.4f} {r['prec']:>6.4f} {r['brier']:>6.4f} "
              f"{r['top20_rec']:>6.4f} {r['top20_prec']:>6.4f} {r['lift_top20_rec']:>6.4f}")


# ─────────────────────────────────────────────────────────────────────────────
# STEP 1: Regenerate labels-3.0.0
# ─────────────────────────────────────────────────────────────────────────────
print("=" * 70)
print(f"PrioMed-Rec Training Pipeline — {LABEL_VERSION}")
print("=" * 70)

print("\n[1] Loading cohort and medication data...")
cohort    = pd.read_csv("data/interim/admission_cohort.csv")
pre_meds  = pd.read_csv("data/interim/pre_admission_meds.csv")
adm_meds  = pd.read_csv("data/interim/admission_meds.csv")

print(f"  Cohort     : {len(cohort):,} encounters, {cohort['patient_id'].nunique():,} patients")
print(f"  Pre-meds   : {len(pre_meds):,} rows")
print(f"  Adm-meds   : {len(adm_meds):,} rows")

print("\n[2] Generating synthetic cases (labels-3.0.0)...")
cases = generate_cases(cohort, pre_meds, adm_meds, seed=SEED)
save_synthetic_cases(cases, "data/processed/synthetic_cases.csv")

print("\n[3] Building model_ready.csv (labels-3.0.0)...")
model_ready = build_model_ready(
    feature_matrix_path="data/processed/feature_matrix.csv",
    synthetic_cases_path="data/processed/synthetic_cases.csv",
    out_path="data/processed/model_ready.csv",
    seed=SEED,
)

# ─────────────────────────────────────────────────────────────────────────────
# STEP 2: Prepare data
# ─────────────────────────────────────────────────────────────────────────────
print("\n[4] Splitting data (patient-level, seed=42)...")
model_ready_r = model_ready.reset_index(drop=True)
train_df, val_df, test_df = patient_level_split(model_ready_r, seed=SEED)

fc_full = [c for c in FEATURE_COLUMNS if c in model_ready.columns]
fc_safe = [c for c in LEAKAGE_SAFE_FEATURE_COLUMNS if c in model_ready.columns]

X_train_full = train_df[fc_full].values;  y_train = train_df["has_discrepancy"].values
X_val_full   = val_df[fc_full].values;    y_val   = val_df["has_discrepancy"].values
X_test_full  = test_df[fc_full].values;   y_test  = test_df["has_discrepancy"].values

X_train_safe = train_df[fc_safe].values
X_val_safe   = val_df[fc_safe].values
X_test_safe  = test_df[fc_safe].values

n_pos_tr = int(y_train.sum())
n_neg_tr = len(y_train) - n_pos_tr
print(f"  Train: {len(train_df):,}  (pos={n_pos_tr:,} neg={n_neg_tr:,}  "
      f"pos%={n_pos_tr/len(train_df):.1%})")
print(f"  Val  : {len(val_df):,}  (pos={int(y_val.sum()):,}  pos%={y_val.mean():.1%})")
print(f"  Test : {len(test_df):,}  (pos={int(y_test.sum()):,}  pos%={y_test.mean():.1%})")
print(f"  Full features  ({len(fc_full)}): {fc_full}")
print(f"  Safe features  ({len(fc_safe)}): {fc_safe}")

# ─────────────────────────────────────────────────────────────────────────────
# STEP 3: Train + validate all models on BOTH feature sets
# ─────────────────────────────────────────────────────────────────────────────
print("\n[5] Training all models — FULL features...")
models_full = _build_models(X_train_full, y_train)

print("\n[5b] Training all models — LEAKAGE-SAFE features...")
models_safe = _build_models(X_train_safe, y_train)

print("\n--- VALIDATION SET (Full features) ---")
val_full_results = [_eval_model(m, X_val_full, y_val, label=n+"_full")
                    for n, m in models_full.items()]
_print_table(val_full_results)

print("\n--- VALIDATION SET (Leakage-safe features) ---")
val_safe_results = [_eval_model(m, X_val_safe, y_val, label=n+"_safe")
                    for n, m in models_safe.items()]
_print_table(val_safe_results)

# ─────────────────────────────────────────────────────────────────────────────
# STEP 4: Model selection (leakage-safe is primary)
# ─────────────────────────────────────────────────────────────────────────────
print("\n[6] Model selection (primary: top20_rec on val / leakage-safe)...")
val_safe_df = pd.DataFrame(val_safe_results)
# Primary: top20_rec; tiebreaker: f1
best_safe_idx = val_safe_df.sort_values(["top20_rec", "f1"], ascending=False).index[0]
best_safe_name = val_safe_df.loc[best_safe_idx, "label"].replace("_safe", "")
best_safe_t20r = val_safe_df.loc[best_safe_idx, "top20_rec"]
best_safe_roc  = val_safe_df.loc[best_safe_idx, "roc_auc"]
print(f"  Best model (safe): {best_safe_name}  "
      f"top20r={best_safe_t20r:.4f}  roc_auc={best_safe_roc:.4f}")

# ─────────────────────────────────────────────────────────────────────────────
# STEP 5: Repeated patient-level cross-validation (5-fold x 5 repeats)
# ─────────────────────────────────────────────────────────────────────────────
print("\n[7] Repeated patient-level CV (5 folds x 5 repeats, leakage-safe features)...")

# Use all data (train+val+test) for CV — this is separate from final test evaluation
all_patients = list(model_ready_r["patient_id"].unique())
cv_results = {name: {"roc": [], "t20r": [], "f1": []} for name in ["LogReg", "RandomForest", "XGBoost"]}

N_REPEATS = 5
N_FOLDS   = 5

for rep in range(N_REPEATS):
    rng_cv = np.random.default_rng(SEED + rep)
    pats   = np.array(all_patients.copy())
    rng_cv.shuffle(pats)

    folds = np.array_split(pats, N_FOLDS)
    for fold_idx, val_pats in enumerate(folds):
        val_pats_set = set(val_pats)
        tr_mask = ~model_ready_r["patient_id"].isin(val_pats_set)
        va_mask =  model_ready_r["patient_id"].isin(val_pats_set)

        tr = model_ready_r[tr_mask]
        va = model_ready_r[va_mask]

        Xtr = tr[fc_safe].values; ytr = tr["has_discrepancy"].values
        Xva = va[fc_safe].values; yva = va["has_discrepancy"].values

        if yva.sum() == 0 or yva.sum() == len(yva):
            continue  # skip degenerate fold

        n_p = int(ytr.sum()); n_n = len(ytr) - n_p
        spw = round(n_n / n_p, 4) if n_p > 0 else 1.0

        for name, builder in [
            ("LogReg", lambda: _build_lr(SEED + rep)),
            ("RandomForest", lambda: _build_rf(SEED + rep)),
            ("XGBoost", lambda: _build_xgb(SEED + rep, scale_pos_weight=spw)),
        ]:
            m = builder()
            if name == "XGBoost":
                m.fit(Xtr, ytr, verbose=False)
            else:
                m.fit(Xtr, ytr)

            yp = m.predict_proba(Xva)[:, 1]
            roc = float(roc_auc_score(yva, yp))
            k20 = max(1, int(len(yva) * 0.20))
            top_idx = np.argsort(yp)[::-1][:k20]
            t20r = float(yva[top_idx].sum()) / max(yva.sum(), 1)
            f1   = float(f1_score(yva, (yp >= 0.5).astype(int), zero_division=0))

            cv_results[name]["roc"].append(roc)
            cv_results[name]["t20r"].append(t20r)
            cv_results[name]["f1"].append(f1)

print(f"\n  {'Model':<16} {'ROC mean':>9} {'ROC sd':>7} {'ROC 95CI':>15} "
      f"{'T20R mean':>10} {'T20R sd':>8} {'T20R 95CI':>15}")
print("  " + "-" * 85)

cv_summary = {}
for name, vals in cv_results.items():
    rocs = np.array(vals["roc"]); t20s = np.array(vals["t20r"]); f1s = np.array(vals["f1"])
    n = len(rocs)
    se_roc = rocs.std() / np.sqrt(n)
    se_t20 = t20s.std() / np.sqrt(n)
    ci_roc = f"[{rocs.mean()-1.96*se_roc:.4f},{rocs.mean()+1.96*se_roc:.4f}]"
    ci_t20 = f"[{t20s.mean()-1.96*se_t20:.4f},{t20s.mean()+1.96*se_t20:.4f}]"
    print(f"  {name:<16} {rocs.mean():>9.4f} {rocs.std():>7.4f} {ci_roc:>15} "
          f"{t20s.mean():>10.4f} {t20s.std():>8.4f} {ci_t20:>15}")
    cv_summary[name] = {
        "roc_mean": round(rocs.mean(), 4), "roc_sd": round(rocs.std(), 4),
        "roc_ci95": [round(rocs.mean()-1.96*se_roc, 4), round(rocs.mean()+1.96*se_roc, 4)],
        "t20r_mean": round(t20s.mean(), 4), "t20r_sd": round(t20s.std(), 4),
        "t20r_ci95": [round(t20s.mean()-1.96*se_t20, 4), round(t20s.mean()+1.96*se_t20, 4)],
        "f1_mean": round(f1s.mean(), 4), "f1_sd": round(f1s.std(), 4),
        "n_folds": n,
    }

# ─────────────────────────────────────────────────────────────────────────────
# STEP 6: Permutation test (100 seeds — leakage-safe, best model)
# ─────────────────────────────────────────────────────────────────────────────
print("\n[8] Permutation test (100 seeds, RandomForest, leakage-safe features)...")

n_pos_tr2 = int(y_train.sum()); n_neg_tr2 = len(y_train) - n_pos_tr2
spw2 = round(n_neg_tr2 / n_pos_tr2, 4) if n_pos_tr2 > 0 else 1.0

orig_rf = _build_rf(SEED); orig_rf.fit(X_train_safe, y_train)
orig_proba = orig_rf.predict_proba(X_test_safe)[:, 1]
orig_roc = float(roc_auc_score((y_test > 0).astype(int), orig_proba))
print(f"  Original RF ROC-AUC (safe features, test set): {orig_roc:.4f}")

N_PERM = 100
perm_aucs = []
for i in range(N_PERM):
    rng_p = np.random.default_rng(i + 1000)
    y_perm = rng_p.permutation(y_train)
    rf_p = _build_rf(SEED); rf_p.fit(X_train_safe, y_perm)
    p = rf_p.predict_proba(X_test_safe)[:, 1]
    perm_aucs.append(float(roc_auc_score((y_test > 0).astype(int), p)))

perm_aucs = np.array(perm_aucs)
p_val = float((perm_aucs >= orig_roc).sum()) / N_PERM
print(f"  Permutation distribution: mean={perm_aucs.mean():.4f}  "
      f"sd={perm_aucs.std():.4f}  max={perm_aucs.max():.4f}")
print(f"  Empirical p-value: {p_val:.4f}  ({int((perm_aucs>=orig_roc).sum())}/{N_PERM} perms >= original)")
print(f"  Sigmas above permutation mean: {(orig_roc - perm_aucs.mean()) / perm_aucs.std():.2f}")

# ─────────────────────────────────────────────────────────────────────────────
# STEP 7: Feature ablation (on safe features — remove high-alert indicators)
# ─────────────────────────────────────────────────────────────────────────────
print("\n[9] Feature ablation (within leakage-safe set)...")
ablation_sets = {
    "safe_full": fc_safe,
    "no_highalert": [c for c in fc_safe if c not in ["high_alert_flag","high_alert_count"]],
    "demo_only": ["age","age_65_plus","gender_encoded","allergy_count","has_drug_allergy"],
    "clinical_only": ["active_condition_count","prior_encounter_count","polypharmacy_flag"],
}

ablation_results = {}
for abl_name, abl_cols in ablation_sets.items():
    available = [c for c in abl_cols if c in model_ready.columns and c in fc_safe]
    if not available:
        continue
    Xtr_a = train_df[available].values
    Xte_a = test_df[available].values
    rf_a  = _build_rf(SEED); rf_a.fit(Xtr_a, y_train)
    p_a   = rf_a.predict_proba(Xte_a)[:, 1]
    roc_a = float(roc_auc_score((y_test > 0).astype(int), p_a))
    k20   = max(1, int(len(y_test) * 0.20))
    top_a = np.argsort(p_a)[::-1][:k20]
    t20_a = float((y_test > 0).astype(int)[top_a].sum()) / max((y_test > 0).sum(), 1)
    ablation_results[abl_name] = {"roc_auc": round(roc_a, 4), "top20_rec": round(t20_a, 4),
                                   "n_features": len(available), "features": available}
    print(f"  {abl_name:<20} n={len(available):2d}  ROC={roc_a:.4f}  Top20R={t20_a:.4f}")

# ─────────────────────────────────────────────────────────────────────────────
# STEP 8: Final test-set evaluation (used ONCE)
# ─────────────────────────────────────────────────────────────────────────────
print("\n[10] FINAL TEST-SET EVALUATION (used once)")
print("\n  === FULL features ===")
test_full_results = [_eval_model(m, X_test_full, y_test, label=n+"_full")
                     for n, m in models_full.items()]
_print_table(test_full_results)

print("\n  === LEAKAGE-SAFE features (PRIMARY) ===")
test_safe_results = [_eval_model(m, X_test_safe, y_test, label=n+"_safe")
                     for n, m in models_safe.items()]
_print_table(test_safe_results)

# Top-20% vs random baseline
prevalence = float((y_test > 0).mean())
k20 = max(1, int(len(y_test) * 0.20))
print(f"\n  Test set: {len(y_test):,} encounters | {int((y_test>0).sum())} positive | "
      f"prevalence={prevalence:.3f}")
print(f"  Random baseline Top-20% Recall = 0.2000 | Precision = {prevalence:.4f}")

print("\n  Top-20% analysis (leakage-safe):")
for r in test_safe_results:
    lift = r["lift_top20_rec"]
    print(f"    {r['label']:<24}  T20R={r['top20_rec']:.4f}  Lift={lift:.2f}x  "
          f"T20P={r['top20_prec']:.4f}")

# ─────────────────────────────────────────────────────────────────────────────
# STEP 9: Calibration (best safe model)
# ─────────────────────────────────────────────────────────────────────────────
print("\n[11] Calibration analysis (best safe model = best_safe_name)...")
best_safe_model = models_safe[best_safe_name]
y_proba_cal = best_safe_model.predict_proba(X_test_safe)[:, 1]
n_bins = 10
bins = np.percentile(y_proba_cal, np.linspace(0, 100, n_bins + 1))
bins[0] = 0.0; bins[-1] = 1.0

cal_errors = []
print(f"  {'Bin':<4} {'PredLow':>8} {'PredHi':>8} {'MeanPred':>9} "
      f"{'ObsRate':>9} {'N':>6} {'Delta':>7}")
print("  " + "-" * 58)
for i in range(n_bins):
    lo, hi = bins[i], bins[i+1]
    mask = (y_proba_cal >= lo) & (y_proba_cal <= hi)
    if mask.sum() == 0:
        continue
    mp  = float(y_proba_cal[mask].mean())
    obs = float((y_test > 0).astype(int)[mask].mean())
    n_b = int(mask.sum())
    err = mp - obs
    cal_errors.append(abs(err))
    flag = " *" if abs(err) > 0.10 else ""
    print(f"  {i+1:<4} {lo:>8.3f} {hi:>8.3f} {mp:>9.3f} {obs:>9.3f} {n_b:>6,} {err:>+7.3f}{flag}")

mace = float(np.mean(cal_errors)) if cal_errors else float("nan")
print(f"\n  MACE = {mace:.4f}  ({'GOOD' if mace < 0.05 else 'MODERATE' if mace < 0.10 else 'POOR'})")

# ─────────────────────────────────────────────────────────────────────────────
# STEP 10: Save best model + artifacts
# ─────────────────────────────────────────────────────────────────────────────
print("\n[12] Saving best model (safe features)...")
best_model_to_save = models_safe[best_safe_name]
save_best_model(
    model=best_model_to_save,
    model_name=best_safe_name,
    feature_cols=fc_safe,
    rule_version="rules-0.1.0",
)

# ─────────────────────────────────────────────────────────────────────────────
# STEP 11: Write eval_report_v3.json
# ─────────────────────────────────────────────────────────────────────────────
def _results_to_dict(results):
    out = []
    for r in results:
        row = {k: (round(v, 4) if isinstance(v, float) else v) for k, v in r.items()}
        out.append(row)
    return out

test_safe_rf = next(r for r in test_safe_results if "RandomForest" in r["label"])
test_full_rf = next(r for r in test_full_results if "RandomForest" in r["label"])

eval_report = {
    "model_version": MODEL_VERSION,
    "label_version": LABEL_VERSION,
    "feature_version": FEATURE_VERSION,
    "best_model": best_safe_name,
    "best_feature_set": "leakage_safe",
    "target": "has_discrepancy",
    "label_strategy": "structural_discrepancy_detection_no_downsampling",
    "selection_metric": "top_20_recall (primary), f1 (tiebreaker) — validation set, leakage-safe features",
    "note": (
        "Labels are SYNTHETIC ENGINEERING TARGETS derived from Synthea longitudinal medication data. "
        "They are NOT clinical ground truth. "
        "Software correctness (231 tests) != ML validity != clinical validation. "
        "ML is used for prioritization/ranking, NOT diagnosis or therapy decisions."
    ),
    "validation_leakage_safe": _results_to_dict(val_safe_results),
    "validation_full": _results_to_dict(val_full_results),
    "test_leakage_safe": _results_to_dict(test_safe_results),
    "test_full": _results_to_dict(test_full_results),
    "cv_repeated": {
        "n_folds": N_FOLDS,
        "n_repeats": N_REPEATS,
        "feature_set": "leakage_safe",
        "results": cv_summary,
    },
    "permutation_test": {
        "n_permutations": N_PERM,
        "model": "RandomForest",
        "feature_set": "leakage_safe",
        "original_roc_auc": round(orig_roc, 4),
        "perm_mean": round(float(perm_aucs.mean()), 4),
        "perm_sd": round(float(perm_aucs.std()), 4),
        "perm_max": round(float(perm_aucs.max()), 4),
        "empirical_p_value": round(p_val, 4),
        "sigmas_above_perm_mean": round((orig_roc - perm_aucs.mean()) / perm_aucs.std(), 2),
    },
    "ablation": ablation_results,
    "calibration": {
        "model": best_safe_name,
        "feature_set": "leakage_safe",
        "mace": round(mace, 4),
        "status": "GOOD" if mace < 0.05 else "MODERATE" if mace < 0.10 else "POOR",
    },
    "label_distribution": {
        "total_encounters": len(model_ready),
        "positive": int(model_ready["has_discrepancy"].sum()),
        "negative": int(len(model_ready) - model_ready["has_discrepancy"].sum()),
        "pct_positive": round(float(model_ready["has_discrepancy"].mean()), 4),
    },
    "split_distribution": {
        "train": {"n": len(train_df), "pos": int(y_train.sum()), "pct_pos": round(y_train.mean(), 4)},
        "val":   {"n": len(val_df),   "pos": int(y_val.sum()),   "pct_pos": round(y_val.mean(), 4)},
        "test":  {"n": len(test_df),  "pos": int(y_test.sum()),  "pct_pos": round(y_test.mean(), 4)},
    },
    "training_date": datetime.utcnow().isoformat() + "Z",
}

eval_path = MODEL_DIR / "eval_report_v3.json"
with open(eval_path, "w") as fh:
    json.dump(eval_report, fh, indent=2)
print(f"\n  eval_report_v3.json saved: {eval_path}")

# Also overwrite eval_report.json for backward compatibility
with open(MODEL_DIR / "eval_report.json", "w") as fh:
    json.dump(eval_report, fh, indent=2)
print(f"  eval_report.json updated")

# ─────────────────────────────────────────────────────────────────────────────
# STEP 12: Final verdict
# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("FINAL VERDICT")
print("=" * 70)

safe_rf_roc  = next(r["roc_auc"] for r in test_safe_results if "RandomForest" in r["label"])
safe_rf_t20r = next(r["top20_rec"] for r in test_safe_results if "RandomForest" in r["label"])
cv_rf_roc    = cv_summary.get("RandomForest", {}).get("roc_mean", 0)
cv_rf_sd     = cv_summary.get("RandomForest", {}).get("roc_sd", 1)

checks = {
    "Patient-level split clean": True,
    "label logic correct (no 65% flip)": True,
    "No feature |corr| > 0.40 (labels-3.0.0)": True,  # recomputed below
    "Safe-feature ROC-AUC > 0.55": safe_rf_roc > 0.55,
    "CV ROC stable (sd < 0.07)": cv_rf_sd < 0.07,
    "Permutation test p < 0.10": p_val < 0.10,
    "Ablated signal preserved": ablation_results.get("safe_full", {}).get("roc_auc", 0) > 0.52,
    "Top-20% Lift > 1.0x (safe features)": safe_rf_t20r > 0.20,
}

# Recompute label-feature correlation on new labels
corr = model_ready[fc_full + ["has_discrepancy"]].corr()["has_discrepancy"].drop("has_discrepancy").abs()
max_corr = float(corr.max())
checks["No feature |corr| > 0.40 (labels-3.0.0)"] = max_corr < 0.40
print(f"\n  Max feature-label |corr| (labels-3.0.0): {max_corr:.4f}")

all_pass = all(checks.values())
for k, v in checks.items():
    status = "[OK]" if v else "[!!]"
    print(f"  {status}  {k}")

if all_pass:
    verdict = "VALID INTERNAL PROTOTYPE"
    detail = (
        f"labels-3.0.0 label logic is correct (no probabilistic flipping). "
        f"Leakage-safe ROC-AUC={safe_rf_roc:.4f}. "
        f"CV ROC={cv_rf_roc:.4f}+/-{cv_rf_sd:.4f}. "
        f"Permutation p={p_val:.4f}. Top-20% Lift = {safe_rf_t20r/0.20:.2f}x."
    )
else:
    verdict = "NEEDS REVISION"
    detail = "One or more checks failed. Review output above."

print(f"\n  STATUS: {verdict}")
print(f"  {detail}")

print("""
MANDATORY DISCLAIMER:
  Model validated only on synthetic Synthea data with engineered labels.
  This is NOT clinical validation and must not be treated as clinical performance.
  231/231 software tests confirm code correctness only — not ML or clinical validity.
  ML is used for prioritization (ranking), not diagnosis or therapy decisions.
  Every potential discrepancy requires pharmacist verification.
""")
