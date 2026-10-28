from __future__ import annotations

import json
from typing import Any

from lfx.custom import Component
from lfx.io import MultilineInput, Output
from lfx.schema import Data


class PMRJsonComponent(Component):
    """Small, reviewable adapter base for structured deterministic nodes."""

    inputs = [MultilineInput(name="payload_json", display_name="Payload JSON", value="{}")]
    outputs = [Output(name="result", display_name="Hasil terverifikasi", method="run")]

    def payload(self) -> dict[str, Any]:
        try:
            value = json.loads(self.payload_json or "{}")
        except json.JSONDecodeError as exc:
            raise ValueError("payload_json harus JSON object yang valid") from exc
        if not isinstance(value, dict):
            raise ValueError("payload_json harus JSON object")
        return value

    def result_data(self, value: dict[str, Any]) -> Data:
        self.status = value
        return Data(data=value)
