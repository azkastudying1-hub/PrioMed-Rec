"""Pure deterministic domain logic shared by FastAPI and Langflow adapters.

This package deliberately imports neither FastAPI nor Langflow.  Clinical
findings remain deterministic and all output is decision support only.
"""

from .contracts import AnalysisInput, AnalysisResult
from .pipeline import run_full, run_phase_a, run_phase_b

__all__ = ["AnalysisInput", "AnalysisResult", "run_phase_a", "run_phase_b", "run_full"]
