# langflow/components/priomedrec/audit.py
from langflow.custom import CustomComponent
from langflow.field_typing import Text

class AuditLogComponent(CustomComponent):
    display_name = "PrioMed Audit Log"
    description  = "Mencatat audit trail untuk semua keputusan AI ke backend."
    name         = "PrioMedAudit"

    def build_config(self):
        return {
            "event_type": {
                "display_name": "Event Type",
                "type": "str",
                "required": True,
            },
            "payload": {
                "display_name": "Payload (JSON)",
                "type": "str",
                "required": True,
            },
        }

    def build(self, event_type: str, payload: str) -> Text:
        """
        Mengirim audit event ke backend PrioMed-Rec.
        Stub ini harus diimplementasikan penuh sebelum production.
        """
        import json, httpx, os
        api_url = os.getenv("PRIOMEDREC_API_URL", "http://api:8000")
        data    = {"event_type": event_type, "payload": json.loads(payload)}
        response = httpx.post(
            f"{api_url}/internal/audit",
            json=data,
            timeout=10.0,
        )
        response.raise_for_status()
        return f"Audit logged: {event_type}"
