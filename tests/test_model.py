"""
tests/test_model.py
--------------------
Unit tests for Sub-Task 7: model training, evaluation, and prediction.

Uses small synthetic data — no I/O from large CSV files.

Run: pytest tests/test_model.py -v
"""

import json
import pytest
import numpy as np
import pandas as pd
import joblib
from pathlib import Path

from src.models.train import patient_level_split, MODEL_VERSION
from src.models.evaluate import compute_metrics, compare_models, select_best_model
from src.models.predict import (
    load_model, load_thresholds, load_metadata,
    predict_single, predict_batch,
    _proba_to_priority, _label_to_priority,
)
from src.features.feature_pipeline import FEATURE_COLUMNS


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_model_ready(n: int = 100, n_patients: int = 20, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    patient_ids = [f"PAT-{i:03}" for i in range(n_patients)]
    enc_patient = rng.choice(patient_ids, size=n)
    features = rng.random((n, len(FEATURE_COLUMNS)))
    df = pd.DataFrame(features, columns=FEATURE_COLUMNS)
    df["encounter_id"] = [f"ENC-{i:04}" for i in range(n)]
    df["patient_id"]   = enc_patient
    df["review_priority"]  = rng.integers(0, 3, size=n)
    df["has_discrepancy"]  = rng.integers(0, 2, size=n)
    return df


# ---------------------------------------------------------------------------
# Patient-level split
# ---------------------------------------------------------------------------

class TestPatientLevelSplit:

    def test_no_patient_overlap_train_test(self):
        """No patient_id must appear in both train and test."""
        df = _make_model_ready(200, n_patients=40)
        train, val, test = patient_level_split(df, seed=42)
        train_pats = set(train["patient_id"])
        val_pats   = set(val["patient_id"])
        test_pats  = set(test["patient_id"])
        assert train_pats.isdisjoint(test_pats), "Patient leak: train ∩ test != empty"
        assert train_pats.isdisjoint(val_pats),  "Patient leak: train ∩ val != empty"
        assert val_pats.isdisjoint(test_pats),   "Patient leak: val ∩ test != empty"

    def test_all_rows_accounted_for(self):
        """Train + val + test must cover all rows."""
        df = _make_model_ready(200, n_patients=40)
        train, val, test = patient_level_split(df, seed=42)
        assert len(train) + len(val) + len(test) == len(df)

    def test_reproducible(self):
        """Same seed → same split."""
        df = _make_model_ready(200, n_patients=40)
        t1, v1, te1 = patient_level_split(df, seed=7)
        t2, v2, te2 = patient_level_split(df, seed=7)
        assert list(t1["encounter_id"]) == list(t2["encounter_id"])

    def test_different_seeds_differ(self):
        df = _make_model_ready(200, n_patients=40)
        t1, _, _ = patient_level_split(df, seed=1)
        t2, _, _ = patient_level_split(df, seed=99)
        # Very unlikely (but not impossible) to be identical
        # Use patient sets as comparison
        assert set(t1["patient_id"]) != set(t2["patient_id"])


# ---------------------------------------------------------------------------
# evaluate
# ---------------------------------------------------------------------------

class TestComputeMetrics:

    def _dummy_model(self):
        """A trivial model that always predicts class 1."""
        from sklearn.dummy import DummyClassifier
        m = DummyClassifier(strategy="most_frequent")
        m.fit(np.zeros((10, 3)), np.ones(10))
        return m

    def test_metric_keys_present(self):
        from sklearn.ensemble import RandomForestClassifier
        X = np.random.rand(50, 4)
        y = np.random.randint(0, 2, 50)
        m = RandomForestClassifier(n_estimators=5, random_state=0)
        m.fit(X, y)
        metrics = compute_metrics(m, X, y)
        for key in ["accuracy", "precision", "recall", "f1", "roc_auc"]:
            assert key in metrics

    def test_accuracy_in_0_1(self):
        from sklearn.ensemble import RandomForestClassifier
        X = np.random.rand(50, 4)
        y = np.random.randint(0, 2, 50)
        m = RandomForestClassifier(n_estimators=5, random_state=0)
        m.fit(X, y)
        metrics = compute_metrics(m, X, y)
        assert 0.0 <= metrics["accuracy"] <= 1.0

    def test_compare_models_returns_dataframe(self):
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.linear_model import LogisticRegression
        X = np.random.rand(100, 4)
        y = np.random.randint(0, 2, 100)
        models = {
            "RF": RandomForestClassifier(n_estimators=5, random_state=0).fit(X, y),
            "LR": LogisticRegression(max_iter=100, random_state=0).fit(X, y),
        }
        comp = compare_models(models, X, y)
        assert isinstance(comp, pd.DataFrame)
        assert "model" in comp.columns
        assert len(comp) == 2


# ---------------------------------------------------------------------------
# predict
# ---------------------------------------------------------------------------

class TestPredict:

    def test_proba_to_priority_high(self):
        thresh = {"high": 0.70, "medium": 0.40}
        assert _proba_to_priority(0.85, thresh) == "HIGH"

    def test_proba_to_priority_medium(self):
        thresh = {"high": 0.70, "medium": 0.40}
        assert _proba_to_priority(0.55, thresh) == "MEDIUM"

    def test_proba_to_priority_low(self):
        thresh = {"high": 0.70, "medium": 0.40}
        assert _proba_to_priority(0.20, thresh) == "LOW"

    def test_label_to_priority_mapping(self):
        thresh = {"mapping": {"2": "HIGH", "1": "MEDIUM", "0": "LOW"}}
        assert _label_to_priority(2, thresh) == "HIGH"
        assert _label_to_priority(1, thresh) == "MEDIUM"
        assert _label_to_priority(0, thresh) == "LOW"

    def test_predict_single_schema(self):
        """predict_single must return required output schema."""
        model = load_model()
        thresholds = load_thresholds()
        metadata   = load_metadata()
        feature_dict = {col: 0 for col in FEATURE_COLUMNS}
        feature_dict["age"] = 65
        feature_dict["polypharmacy_flag"] = 1
        result = predict_single(feature_dict, model=model,
                                thresholds=thresholds, metadata=metadata)
        assert "risk_probability" in result
        assert "priority" in result
        assert "model_version" in result
        assert result["priority"] in {"LOW", "MEDIUM", "HIGH"}
        assert 0.0 <= result["risk_probability"] <= 1.0

    def test_predict_batch_schema(self):
        """predict_batch must return DataFrame with required columns."""
        model      = load_model()
        thresholds = load_thresholds()
        metadata   = load_metadata()
        df = pd.DataFrame([{col: 0 for col in FEATURE_COLUMNS}] * 5)
        df.index.name = "encounter_id"
        result = predict_batch(df, model=model, thresholds=thresholds, metadata=metadata)
        assert isinstance(result, pd.DataFrame)
        for col in ["risk_probability", "priority", "model_version"]:
            assert col in result.columns
        assert result["priority"].isin({"LOW", "MEDIUM", "HIGH"}).all()

    def test_risk_probability_range(self):
        """risk_probability must always be in [0.0, 1.0]."""
        model      = load_model()
        thresholds = load_thresholds()
        metadata   = load_metadata()
        feature_dict = {col: np.random.rand() * 10 for col in FEATURE_COLUMNS}
        result = predict_single(feature_dict, model=model,
                                thresholds=thresholds, metadata=metadata)
        assert 0.0 <= result["risk_probability"] <= 1.0

    def test_model_version_in_output(self):
        model    = load_model()
        metadata = load_metadata()
        feature_dict = {col: 0 for col in FEATURE_COLUMNS}
        result = predict_single(feature_dict, model=model, metadata=metadata)
        assert result["model_version"] == metadata["model_version"]


# ---------------------------------------------------------------------------
# Metadata and thresholds integrity
# ---------------------------------------------------------------------------

class TestModelArtifacts:

    def test_metadata_keys_present(self):
        metadata = load_metadata()
        for key in ["model_version", "feature_version", "feature_columns", "training_date"]:
            assert key in metadata

    def test_thresholds_keys_present(self):
        thresh = load_thresholds()
        assert "high" in thresh
        assert "medium" in thresh
        assert 0.0 < thresh["medium"] < thresh["high"] < 1.0

    def test_model_pkl_exists(self):
        assert Path("models/priomed_prioritization_model.pkl").exists()

    def test_model_version_format(self):
        assert MODEL_VERSION.startswith("model-")


# ---------------------------------------------------------------------------
# Sub-Task 8: SHAP Explainability tests
# ---------------------------------------------------------------------------

class TestSHAPExplainer:

    def _trained_rf(self):
        from sklearn.ensemble import RandomForestClassifier
        X = np.random.default_rng(0).random((60, len(FEATURE_COLUMNS)))
        y = np.random.default_rng(0).integers(0, 2, 60)
        m = RandomForestClassifier(n_estimators=5, random_state=0)
        m.fit(X, y)
        return m, X

    def test_explanation_schema_keys(self):
        """Output must have all required schema fields."""
        from src.explainability.shap_explainer import get_explanation
        model, X = self._trained_rf()
        feat = X[0]
        result = get_explanation(
            model=model,
            feature_vector=feat,
            feature_names=FEATURE_COLUMNS,
            risk_probability=0.75,
            priority="HIGH",
            encounter_id="ENC-0001",
            top_n=5,
        )
        for key in ["encounter_id", "risk_probability", "priority",
                    "top_features", "explainer_type", "model_name", "note"]:
            assert key in result, f"Missing key: {key}"

    def test_risk_probability_unchanged(self):
        """get_explanation must NOT modify risk_probability."""
        from src.explainability.shap_explainer import get_explanation
        model, X = self._trained_rf()
        original_prob = 0.82
        result = get_explanation(
            model=model,
            feature_vector=X[0],
            feature_names=FEATURE_COLUMNS,
            risk_probability=original_prob,
            priority="HIGH",
        )
        assert result["risk_probability"] == round(original_prob, 4)

    def test_priority_unchanged(self):
        """get_explanation must NOT modify priority."""
        from src.explainability.shap_explainer import get_explanation
        model, X = self._trained_rf()
        result = get_explanation(
            model=model,
            feature_vector=X[0],
            feature_names=FEATURE_COLUMNS,
            risk_probability=0.50,
            priority="MEDIUM",
        )
        assert result["priority"] == "MEDIUM"

    def test_top_n_features_count(self):
        """top_features must return exactly top_n entries (or fewer if n_features < top_n)."""
        from src.explainability.shap_explainer import get_explanation
        model, X = self._trained_rf()
        result = get_explanation(
            model=model,
            feature_vector=X[0],
            feature_names=FEATURE_COLUMNS,
            risk_probability=0.60,
            priority="MEDIUM",
            top_n=5,
        )
        assert len(result["top_features"]) <= 5

    def test_top_features_schema(self):
        """Each top_feature entry must have required fields."""
        from src.explainability.shap_explainer import get_explanation
        model, X = self._trained_rf()
        result = get_explanation(
            model=model,
            feature_vector=X[0],
            feature_names=FEATURE_COLUMNS,
            risk_probability=0.60,
            priority="MEDIUM",
        )
        for feat in result["top_features"]:
            assert "feature" in feat
            assert "value" in feat
            assert "shap_value" in feat
            assert "direction" in feat
            assert feat["direction"] in {"increases_risk", "decreases_risk", "neutral"}

    def test_direction_field_consistency(self):
        """direction must be consistent with sign of shap_value."""
        from src.explainability.shap_explainer import get_explanation
        model, X = self._trained_rf()
        result = get_explanation(
            model=model,
            feature_vector=X[0],
            feature_names=FEATURE_COLUMNS,
            risk_probability=0.60,
            priority="MEDIUM",
        )
        for feat in result["top_features"]:
            sv = feat["shap_value"]
            direction = feat["direction"]
            if sv > 0:
                assert direction == "increases_risk"
            elif sv < 0:
                assert direction == "decreases_risk"
            else:
                assert direction == "neutral"

    def test_rule_baseline_fallback(self):
        """RuleBaselineClassifier must use fallback explainer without error."""
        from src.explainability.shap_explainer import get_explanation
        from src.rules.rule_evaluator import RuleBaselineClassifier
        import numpy as np
        X = np.zeros((5, len(FEATURE_COLUMNS)))
        y = np.array([1, 0, 1, 1, 0])
        rb = RuleBaselineClassifier()
        rb.fit(X, y)
        result = get_explanation(
            model=rb,
            feature_vector=X[0],
            feature_names=FEATURE_COLUMNS,
            risk_probability=0.50,
            priority="MEDIUM",
        )
        assert result["explainer_type"] == "fallback"
        assert "top_features" in result

    def test_logistic_regression_explainer(self):
        """LogisticRegression must use LinearExplainer without error."""
        from src.explainability.shap_explainer import get_explanation
        from sklearn.linear_model import LogisticRegression
        X = np.random.default_rng(1).random((60, len(FEATURE_COLUMNS)))
        y = np.random.default_rng(1).integers(0, 2, 60)
        lr = LogisticRegression(max_iter=200, random_state=0)
        lr.fit(X, y)
        result = get_explanation(
            model=lr,
            feature_vector=X[0],
            feature_names=FEATURE_COLUMNS,
            risk_probability=0.55,
            priority="MEDIUM",
            X_background=X,
        )
        assert result["explainer_type"] == "LinearExplainer"
        assert len(result["top_features"]) <= 5


# ---------------------------------------------------------------------------
# Multi-metric model selection (Sub-Task 7 revised)
# ---------------------------------------------------------------------------

class TestMultiMetricSelection:
    """Tests for select_best_model() using multi-metric criteria."""

    def _make_comparison_df(self) -> "pd.DataFrame":
        import pandas as pd
        return pd.DataFrame([
            {"model": "RuleBaseline",        "f1": 0.60, "roc_auc": 0.55,
             "pr_auc": 0.58, "brier": 0.40, "top_20pct_recall": 0.20},
            {"model": "LogisticRegression",  "f1": 0.65, "roc_auc": 0.71,
             "pr_auc": 0.66, "brier": 0.23, "top_20pct_recall": 0.24},
            {"model": "RandomForest",        "f1": 0.79, "roc_auc": 0.72,
             "pr_auc": 0.65, "brier": 0.18, "top_20pct_recall": 0.26},
            {"model": "XGBoost",             "f1": 0.77, "roc_auc": 0.70,
             "pr_auc": 0.64, "brier": 0.19, "top_20pct_recall": 0.24},
        ])

    def test_selects_best_top20pct_recall(self):
        """Model with highest top_20pct_recall should be selected (primary criterion)."""
        df = self._make_comparison_df()
        best = select_best_model(df)
        assert best == "RandomForest"

    def test_tiebreaker_uses_f1(self):
        """When top_20pct_recall is tied within 0.02, f1 decides."""
        import pandas as pd
        df = pd.DataFrame([
            {"model": "ModelA", "f1": 0.70, "roc_auc": 0.72, "top_20pct_recall": 0.25},
            {"model": "ModelB", "f1": 0.75, "roc_auc": 0.71, "top_20pct_recall": 0.25},
        ])
        best = select_best_model(df)
        assert best == "ModelB"  # higher f1 within tie zone

    def test_fallback_to_roc_auc_if_no_topk(self):
        """If top_20pct_recall is absent, fall back to roc_auc."""
        import pandas as pd
        df = pd.DataFrame([
            {"model": "ModelA", "f1": 0.65, "roc_auc": 0.70},
            {"model": "ModelB", "f1": 0.60, "roc_auc": 0.75},
        ])
        best = select_best_model(df)
        assert best == "ModelB"


class TestEvalReportTopK:
    """Tests that eval_report.json contains required metrics (labels-3.0.0 schema)."""

    def test_eval_report_exists(self):
        assert Path("models/eval_report.json").exists()

    def test_eval_report_has_test_leakage_safe(self):
        """labels-3.0.0 eval_report uses test_leakage_safe instead of 'test'."""
        with open("models/eval_report.json") as f:
            report = json.load(f)
        assert "test_leakage_safe" in report, (
            "eval_report.json must contain test_leakage_safe (labels-3.0.0 schema)"
        )

    def test_eval_report_top_k_has_20pct(self):
        """Each model result in test_leakage_safe must have top20_rec."""
        with open("models/eval_report.json") as f:
            report = json.load(f)
        test_results = report.get("test_leakage_safe", [])
        assert len(test_results) > 0
        for r in test_results:
            assert "top20_rec" in r, f"Missing top20_rec in result: {r.get('label')}"

    def test_eval_report_has_all_required_metrics(self):
        with open("models/eval_report.json") as f:
            report = json.load(f)
        test_results = report.get("test_leakage_safe", [])
        assert len(test_results) > 0
        required = ["prec", "rec", "f1", "roc_auc", "pr_auc", "brier", "top20_rec"]
        for r in test_results:
            for m in required:
                assert m in r, f"Missing metric '{m}' in eval_report result: {r.get('label')}"

    def test_eval_report_label_version_is_v3(self):
        with open("models/eval_report.json") as f:
            report = json.load(f)
        assert report.get("label_version") == "labels-3.0.0"

    def test_eval_report_selection_metric_is_multicriterion(self):
        with open("models/eval_report.json") as f:
            report = json.load(f)
        sel = report.get("selection_metric", "")
        assert "top_20" in sel.lower(), f"selection_metric should mention top_20: {sel}"

    def test_eval_report_roc_auc_above_random(self):
        """With longitudinal labels-3.0.0, leakage-safe ROC-AUC must exceed 0.60."""
        with open("models/eval_report.json") as f:
            report = json.load(f)
        test_results = report.get("test_leakage_safe", [])
        rocs = [r.get("roc_auc", 0.0) for r in test_results
                if r.get("label", "").startswith("RandomForest")]
        assert len(rocs) > 0, "No RandomForest result in test_leakage_safe"
        assert float(rocs[0]) > 0.60, (
            f"Safe-feature ROC-AUC {rocs[0]} <= 0.60 — unexpected loss of signal"
        )

    def test_model_version_is_v3(self):
        with open("models/eval_report.json") as f:
            report = json.load(f)
        assert report.get("model_version") == "model-0.3.0"


# ---------------------------------------------------------------------------
# Inference Guard tests (labels-3.0.0 / features-0.3.0)
# ---------------------------------------------------------------------------

class TestInferenceGuard:
    """Tests for the runtime inference guard that enforces safe feature policy."""

    SAFE_FEATURES = [
        "age", "age_65_plus", "gender_encoded",
        "polypharmacy_flag", "high_alert_flag", "high_alert_count",
        "active_condition_count", "prior_encounter_count",
        "allergy_count", "has_drug_allergy",
    ]
    FORBIDDEN = [
        "discontinued_medication_count", "new_medication_count",
        "total_medication_count", "pre_admission_medication_count",
        "admission_medication_count", "potential_duplicate_candidates",
    ]

    def _make_manifest(self) -> dict:
        return {
            "version": "features-0.3.0",
            "label_version": "labels-3.0.0",
            "safe_features": self.SAFE_FEATURES,
            "forbidden_features": self.FORBIDDEN,
            "feature_provenance": {},
        }

    def _safe_input(self) -> dict:
        return {f: 1.0 for f in self.SAFE_FEATURES}

    def test_guard_accepts_safe_features(self):
        """Valid safe-feature dict must pass without error."""
        from src.models.inference_guard import InferenceGuard
        guard = InferenceGuard(self._make_manifest())
        result = guard.validate_and_extract(self._safe_input())
        assert result.shape == (len(self.SAFE_FEATURES),)

    def test_guard_rejects_forbidden_feature(self):
        """Any forbidden feature in input must raise InferenceGuardError."""
        from src.models.inference_guard import InferenceGuard, InferenceGuardError
        guard = InferenceGuard(self._make_manifest())
        bad_input = self._safe_input()
        bad_input["discontinued_medication_count"] = 3.0   # forbidden
        with pytest.raises(InferenceGuardError, match="FORBIDDEN"):
            guard.validate_and_extract(bad_input)

    def test_guard_rejects_all_forbidden_features(self):
        """Every forbidden feature must trigger InferenceGuardError individually."""
        from src.models.inference_guard import InferenceGuard, InferenceGuardError
        guard = InferenceGuard(self._make_manifest())
        for forbidden in self.FORBIDDEN:
            bad_input = self._safe_input()
            bad_input[forbidden] = 0.0
            with pytest.raises(InferenceGuardError):
                guard.validate_and_extract(bad_input)

    def test_guard_rejects_missing_safe_feature(self):
        """Missing safe feature must raise InferenceGuardError."""
        from src.models.inference_guard import InferenceGuard, InferenceGuardError
        guard = InferenceGuard(self._make_manifest())
        incomplete = {f: 1.0 for f in self.SAFE_FEATURES[:-2]}  # drop last 2
        with pytest.raises(InferenceGuardError, match="MISSING"):
            guard.validate_and_extract(incomplete)

    def test_guard_output_order_matches_manifest(self):
        """Output array values must be in manifest feature order."""
        from src.models.inference_guard import InferenceGuard
        guard = InferenceGuard(self._make_manifest())
        inp = {f: float(i) for i, f in enumerate(self.SAFE_FEATURES)}
        result = guard.validate_and_extract(inp)
        expected = np.array([float(i) for i in range(len(self.SAFE_FEATURES))])
        np.testing.assert_array_equal(result, expected)

    def test_guard_validates_dataframe(self):
        """validate_dataframe must accept a clean DataFrame."""
        from src.models.inference_guard import InferenceGuard
        guard = InferenceGuard(self._make_manifest())
        df = pd.DataFrame([self._safe_input()])
        result = guard.validate_dataframe(df)
        assert result.shape == (1, len(self.SAFE_FEATURES))

    def test_guard_dataframe_rejects_forbidden(self):
        """validate_dataframe must reject forbidden columns."""
        from src.models.inference_guard import InferenceGuard, InferenceGuardError
        guard = InferenceGuard(self._make_manifest())
        df = pd.DataFrame([self._safe_input()])
        df["discontinued_medication_count"] = 0
        with pytest.raises(InferenceGuardError, match="FORBIDDEN"):
            guard.validate_dataframe(df)

    def test_guard_load_from_file(self):
        """InferenceGuard.load() must read manifest from saved JSON."""
        from src.models.inference_guard import InferenceGuard
        guard = InferenceGuard.load("models/feature_manifest.json")
        assert "features-0.3.0" in guard.version or "features" in guard.version
        assert len(guard.safe_features) > 0
        assert len(guard.forbidden_features) > 0

    def test_guard_file_safe_features_match_expected(self):
        """Saved manifest safe_features must contain all expected leakage-safe features."""
        from src.models.inference_guard import InferenceGuard
        guard = InferenceGuard.load("models/feature_manifest.json")
        for f in ["age", "active_condition_count", "high_alert_flag"]:
            assert f in guard.safe_features, f"{f} must be in safe_features"

    def test_guard_file_forbidden_features_match_expected(self):
        """Saved manifest must forbid the label-adjacent features."""
        from src.models.inference_guard import InferenceGuard
        guard = InferenceGuard.load("models/feature_manifest.json")
        for f in ["discontinued_medication_count", "new_medication_count",
                  "potential_duplicate_candidates"]:
            assert f in guard.forbidden_features, f"{f} must be in forbidden_features"
