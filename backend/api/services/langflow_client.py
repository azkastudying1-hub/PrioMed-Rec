"""Bounded Langflow REST client; no browser code uses this client."""
from __future__ import annotations

import asyncio
import os
import time
from dataclasses import dataclass
from typing import Any

import httpx


class LangflowUnavailable(RuntimeError):
    """Raised for a bounded, auditable handoff to the local fallback."""


@dataclass
class CircuitBreaker:
    failures: int = 0
    opened_at: float | None = None

    def allow(self) -> bool:
        if self.opened_at is None:
            return True
        if time.monotonic() - self.opened_at >= float(os.getenv("LANGFLOW_CIRCUIT_RESET_SECONDS", "60")):
            self.failures, self.opened_at = 0, None
            return True
        return False

    def success(self) -> None:
        self.failures, self.opened_at = 0, None

    def failure(self) -> None:
        self.failures += 1
        if self.failures >= int(os.getenv("LANGFLOW_CIRCUIT_FAILS", "3")):
            self.opened_at = time.monotonic()


class LangflowClient:
    def __init__(self, base_url: str | None = None, api_key: str | None = None, flow_id: str | None = None) -> None:
        self.base_url = (base_url or os.getenv("LANGFLOW_BASE_URL") or os.getenv("LANGFLOW_URL", "http://langflow:7860")).rstrip("/")
        self.api_key = api_key if api_key is not None else os.getenv("LANGFLOW_API_KEY", "")
        self.flow_id = flow_id or os.getenv("LANGFLOW_MASTER_FLOW_ID", "")
        self.breaker = CircuitBreaker()

    async def run_master(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.flow_id:
            raise LangflowUnavailable("LANGFLOW_MASTER_FLOW_ID belum dikonfigurasi")
        if not self.api_key:
            raise LangflowUnavailable("LANGFLOW_API_KEY belum dikonfigurasi")
        if not self.breaker.allow():
            raise LangflowUnavailable("circuit breaker Langflow terbuka")
        timeout = float(os.getenv("LANGFLOW_TIMEOUT_SECONDS", "25"))
        headers = {"x-api-key": self.api_key}
        request = {"input_value": __import__("json").dumps(payload), "output_type": "chat", "input_type": "chat"}
        error: Exception | None = None
        for attempt in range(2):
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.post(f"{self.base_url}/api/v1/run/{self.flow_id}", headers=headers, json=request)
                response.raise_for_status()
                body = response.json()
                self.breaker.success()
                return self._extract_result(body)
            except (httpx.HTTPError, ValueError, KeyError) as exc:
                error = exc
                if attempt == 0:
                    await asyncio.sleep(0.1)
        self.breaker.failure()
        raise LangflowUnavailable(f"Langflow gagal: {type(error).__name__}") from error

    @staticmethod
    def _extract_result(body: dict[str, Any]) -> dict[str, Any]:
        # PMR Result Packager returns JSON text through standard v1 chat output.
        outputs = body.get("outputs", [])
        if outputs:
            message = outputs[0].get("outputs", [{}])[0].get("results", {}).get("message", {}).get("text")
            if isinstance(message, str):
                parsed = __import__("json").loads(message)
                if isinstance(parsed, dict):
                    return parsed
        if isinstance(body.get("result"), dict):
            return body["result"]
        raise ValueError("Keluaran Langflow tidak memuat result JSON terstruktur")
