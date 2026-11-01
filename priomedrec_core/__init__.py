"""Pure deterministic domain logic shared by FastAPI and Langflow adapters.

This package deliberately imports neither FastAPI nor Langflow.  Clinical
findings remain deterministic and all output is decision support only.
"""

from .contracts import AnalysisInput, AnalysisResult
from .pipeline import run_full, run_phase_a, run_phase_b
from .queue_config import QueueConfig, DEFAULT_CONFIG, SlaThreshold
from .queue_engine import (
    compute_queue_score,
    apply_ml_quota,
    apply_hysteresis,
    batch_rescore,
    determine_next_due_at,
    sort_queue,
    compute_ml_percentiles,
    compute_tier_from_ml_score,
    compute_tier_source,
)
from .queue_transitions import (
    admit,
    bpmh_submit,
    discharge,
    cancel,
    transfer,
    park_dpjp,
    unpark_dpjp,
    expire_claim,
    lab_critical,
    order_change,
)

__all__ = [
    "AnalysisInput", "AnalysisResult", "run_phase_a", "run_phase_b", "run_full",
    # Queue engine
    "QueueConfig", "DEFAULT_CONFIG", "SlaThreshold",
    "compute_queue_score", "apply_ml_quota", "apply_hysteresis",
    "batch_rescore", "determine_next_due_at", "sort_queue",
    "compute_ml_percentiles", "compute_tier_from_ml_score", "compute_tier_source",
    # Queue transitions
    "admit", "bpmh_submit", "discharge", "cancel",
    "transfer", "park_dpjp", "unpark_dpjp", "expire_claim",
    "lab_critical", "order_change",
]
