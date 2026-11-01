# Langflow and IBM Bob integration

This implementation follows the Blueprint v4 philosophy:

> AI decides **who first**. Rules surface **what to check**. The pharmacist decides **what to do**.

## Langflow

The website calls Langflow through `/langflow`, which Vite proxies in development and Nginx proxies in Docker. If it is unavailable, the website safely falls back to FastAPI; the clinical review workflow remains usable.

First-time setup is required because mounting a JSON file does not import it into Langflow automatically:

1. Start FastAPI and Langflow (`docker compose up --build`, or run both locally).
2. Open `http://localhost:7860`.
3. Import `langflow/priomedrec_orchestrator.json` and `langflow/priomedrec_review.json`.
4. Confirm their IDs match `.env`: `ab69172c-78ec-45bd-85cd-83ddbcb6cc50` and `e903f5fc-3a3e-4cd3-9773-dca76018f5a6`. If Langflow generates different IDs, update `VITE_LANGFLOW_ORCHESTRATOR_FLOW_ID` and `VITE_LANGFLOW_REVIEW_FLOW_ID` before rebuilding the web app.
5. Configure the flow's FastAPI endpoint to reach the API service. In Docker this is `http://api:8000`; locally use `http://localhost:8000`.

Never allow a Langflow/LLM node to set priorities, mutate prescriptions, or bypass the pharmacist review endpoint.

## IBM Bob / MCP

`mcp_server.py` is a genuine stdio MCP server; `mcp_settings.json` registers it with an IBM Bob-compatible MCP client. It offers exactly three auditable tools:

- `rank_admission_risk` → FastAPI model batch-priority endpoint.
- `detect_medication_discrepancy` → FastAPI analysis endpoint (rules plus verification-required results).
- `record_pharmacist_review` → FastAPI audit endpoint.

Start FastAPI first, then configure IBM Bob to load [mcp_settings.json](../mcp_settings.json). Start the server from the repository root:

```powershell
Set-Location D:\Hacktiv8\priomed-rec
.\.venv\Scripts\python.exe .\mcp_server.py
```

The MCP tool server contains no model and makes no clinical decision by itself; it always delegates to the API.

## Data use

The running legacy API uses the existing Synthea-derived cohort, medication timelines, processed feature matrix, reference drug-risk lookup, interaction knowledge file, and model artefacts. `medrec_xgboost` remains an isolated candidate model until an adapter and local validation are completed; it must not silently replace the active model.
