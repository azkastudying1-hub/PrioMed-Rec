"""
src/models/inference_guard.py
------------------------------
Runtime inference guard for PrioMed-Rec.

Enforces that:
  (1) Only features listed in feature_manifest.json safe_features are accepted
  (2) Any forbidden feature in the input raises InferenceGuardError
  (3) Feature order/schema must match the manifest exactly
  (4) Missing features raises InferenceGuardError

This guard is the enforcement layer for the leakage-safe feature policy.
It must be called before every inference call.

Usage:
    from src.models.inference_guard import InferenceGuard, InferenceGuardError
    guard = InferenceGuard.load("models/feature_manifest.json")
    X_safe = guard.validate_and_extract(feature_dict)   # raises on violation
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


class InferenceGuardError(ValueError):
    """Raised when inference input violates the feature manifest."""


class InferenceGuard:
    """
    Validates that inference inputs comply with the leakage-safe feature manifest.

    Rules:
      - Input may only contain features listed in `safe_features`
      - Any feature in `forbidden_features` → InferenceGuardError
      - Missing safe features → InferenceGuardError (no silent defaults)
      - Feature order in output always matches manifest order
    """

    def __init__(self, manifest: dict):
        self.version         = manifest.get("version", "unknown")
        self.label_version   = manifest.get("label_version", "unknown")
        self.safe_features   = list(manifest["safe_features"])
        self.forbidden_features = list(manifest.get("forbidden_features", []))
        self.provenance      = manifest.get("feature_provenance", {})

    @classmethod
    def load(cls, manifest_path: str = "models/feature_manifest.json") -> "InferenceGuard":
        """Load manifest from JSON file."""
        with open(manifest_path, encoding="utf-8") as fh:
            manifest = json.load(fh)
        return cls(manifest)

    def validate_and_extract(
        self,
        features: dict | pd.Series | pd.DataFrame,
    ) -> np.ndarray:
        """
        Validate feature input and return numpy array in manifest order.

        Parameters
        ----------
        features : dict, pd.Series, or single-row pd.DataFrame

        Returns
        -------
        np.ndarray of shape (n_safe_features,) or (1, n_safe_features)

        Raises
        ------
        InferenceGuardError if any forbidden feature is present,
        or any required safe feature is missing.
        """
        if isinstance(features, pd.DataFrame):
            if len(features) != 1:
                raise InferenceGuardError(
                    f"validate_and_extract expects a single-row DataFrame; got {len(features)} rows."
                )
            features = features.iloc[0].to_dict()
        elif isinstance(features, pd.Series):
            features = features.to_dict()

        present_keys = set(features.keys())

        # Check for forbidden features
        violations = present_keys & set(self.forbidden_features)
        if violations:
            raise InferenceGuardError(
                f"InferenceGuard: FORBIDDEN features detected: {sorted(violations)}. "
                f"These features are label-adjacent and must not be used for inference. "
                f"See docs/feature_provenance.md for rationale."
            )

        # Check for missing safe features
        missing = [f for f in self.safe_features if f not in present_keys]
        if missing:
            raise InferenceGuardError(
                f"InferenceGuard: MISSING safe features: {missing}. "
                f"All safe_features must be present."
            )

        # Extract in canonical order
        values = [float(features[f]) for f in self.safe_features]
        return np.array(values, dtype=float)

    def validate_dataframe(self, df: pd.DataFrame) -> np.ndarray:
        """
        Validate a multi-row DataFrame and return safe feature matrix.

        Parameters
        ----------
        df : pd.DataFrame with any set of columns

        Returns
        -------
        np.ndarray of shape (n_rows, n_safe_features)
        """
        present_cols = set(df.columns)

        violations = present_cols & set(self.forbidden_features)
        if violations:
            raise InferenceGuardError(
                f"InferenceGuard: FORBIDDEN columns in DataFrame: {sorted(violations)}. "
                f"Remove these columns before calling inference."
            )

        missing = [f for f in self.safe_features if f not in present_cols]
        if missing:
            raise InferenceGuardError(
                f"InferenceGuard: MISSING safe columns in DataFrame: {missing}."
            )

        return df[self.safe_features].values.astype(float)

    def describe(self) -> str:
        lines = [
            f"InferenceGuard v{self.version} (label_version={self.label_version})",
            f"  Safe features ({len(self.safe_features)}): {self.safe_features}",
            f"  Forbidden features ({len(self.forbidden_features)}): {self.forbidden_features}",
        ]
        return "\n".join(lines)
