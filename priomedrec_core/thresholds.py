"""Single source of truth for ML probability thresholds.

The runtime model metadata owns the numbers; these defaults must only be used
when no threshold file is available (for example inside a minimal container).
"""
from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path

DEFAULT_HIGH = 0.70
DEFAULT_MEDIUM = 0.40


def _candidate_paths() -> list[Path]:
    configured = os.getenv("PMR_THRESHOLDS_PATH", "").strip()
    paths: list[Path] = [Path(configured)] if configured else []
    here = Path(__file__).resolve()
    paths.extend(
        [
            Path.cwd() / "models" / "thresholds.json",
            here.parent.parent / "models" / "thresholds.json",
            Path("/app/models/thresholds.json"),
        ]
    )
    return paths


@lru_cache(maxsize=1)
def load_thresholds() -> tuple[float, float, str]:
    for path in _candidate_paths():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        high = float(payload.get("high", DEFAULT_HIGH))
        medium = float(payload.get("medium", DEFAULT_MEDIUM))
        version = str(payload.get("threshold_version", "thresholds-unknown"))
        if 0.0 <= medium < high <= 1.0:
            return high, medium, version
    return DEFAULT_HIGH, DEFAULT_MEDIUM, "thresholds-default"


def high_threshold() -> float:
    return load_thresholds()[0]


def medium_threshold() -> float:
    return load_thresholds()[1]


def threshold_version() -> str:
    return load_thresholds()[2]
