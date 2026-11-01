# Website runbook and architecture decision

## Supported application path

The supported user interface is the React/Vite web application in `web/`; Streamlit is no longer a runtime dependency. The browser communicates with FastAPI through `/api`, and FastAPI owns model inference, rule checks, BPMH, reviews, audit logging, and the SQLite-backed operational state.

```text
React/Vite UI -> /api reverse proxy -> FastAPI -> model + rule engine + SQLite runtime state
                                      -> optional LLM/Langflow fallback
```

Langflow is optional for narrative orchestration: direct FastAPI fallback remains available if Langflow or an LLM key is unavailable. This keeps the safety-critical review workflow available without an external LLM.

For the required Langflow import procedure and the IBM Bob-compatible MCP tools, see [LANGFLOW_AND_IBM_BOB.md](LANGFLOW_AND_IBM_BOB.md).

## Important current boundary

There are two ML tracks:

1. `models/` plus `src/models/` is the current model contract consumed by the FastAPI website.
2. `medrec_xgboost/` is an isolated admission-time XGBoost MVP with a broader dataset schema.

Do not copy its model file into `models/` or point FastAPI at it directly. Its features, target and calibration process differ from the legacy API contract. Integrate it only through a versioned inference adapter, API contract tests, and local clinical validation.

## Local development

Prerequisites: Python 3.10+ and Node.js 20+.

```powershell
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe scripts/validate_data_layout.py
.\.venv\Scripts\python.exe -m uvicorn api.main:app --host 127.0.0.1 --port 8000 --reload
```

In a second terminal:

```powershell
Set-Location web
npm ci
$env:VITE_DATA_MODE = "live"
npm run dev
```

Open `http://localhost:5173`. Verify `http://localhost:8000/health` and `http://localhost:8000/docs` first. Leave LLM API keys empty for a safe deterministic fallback; do not add secrets to source files.

## Docker deployment

```powershell
docker compose up --build
```

Open `http://localhost`. The web image is compiled with `VITE_DATA_MODE=live`. `/api/*` is reverse-proxied by Nginx to FastAPI. The API model/reference data stay inside the immutable image, while mutable SQLite/audit state persists in the `priomed_runtime` volume. Stop with `docker compose down`; add `-v` only when intentionally discarding operational state.

## Acceptance checks

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_api.py tests/test_model.py
Set-Location web; npm run build
```

Before clinical pilot: restrict CORS to deployed UI origins, require authenticated pharmacist identities, rotate any exposed keys, validate all real-data ingestion under hospital governance, validate calibration/thresholds locally, conduct prospective workflow testing, and monitor false negatives, alert burden and drift.

## MCP server

When launching the IBM Bob-compatible MCP server, always run it from the repository root so that `mcp_server.py` and `.venv` resolve correctly:

```powershell
Set-Location D:\Hacktiv8\priomed-rec
.\.venv\Scripts\python.exe .\mcp_server.py
```
