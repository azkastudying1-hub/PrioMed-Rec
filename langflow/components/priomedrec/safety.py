# langflow/components/priomedrec/safety.py
from langflow.custom import CustomComponent
from langflow.field_typing import Text

class SafetyGuardrailComponent(CustomComponent):
    display_name = "PrioMed Safety Guardrail"
    description  = "Memvalidasi output AI terhadap safety constraints klinis."
    name         = "PrioMedSafety"

    def build_config(self):
        return {
            "analysis_result": {
                "display_name": "Analysis Result (JSON)",
                "type": "str",
                "required": True,
            },
        }

    def build(self, analysis_result: str) -> Text:
        """
        Menjalankan guardrail checks pada hasil analisis.
        Stub ini harus diimplementasikan penuh sebelum production.
        """
        import json, httpx, os
        api_url = os.getenv("PRIOMEDREC_API_URL", "http://api:8000")
        payload = json.loads(analysis_result)
        response = httpx.post(
            f"{api_url}/internal/guardrail-check",
            json=payload,
            timeout=15.0,
        )
        response.raise_for_status()
        return str(response.json())
