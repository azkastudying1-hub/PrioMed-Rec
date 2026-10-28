# Audit Langflow — LF-001

**Tanggal:** 2026-10-29
**Status:** baseline kode; runtime belum dapat diverifikasi karena Docker daemon/Compose tidak tersedia pada host audit.
**Sumber:** `PRIOMEDREC_LANGFLOW_MAXIMIZATION_PLAN.md` mengalahkan rencana lama untuk topik Langflow.

## Ringkasan

Kondisi belum Langflow-first. Dua flow JSON lama memakai HTTP client menuju FastAPI, sedangkan pipeline klinis dan keselamatan berada di `src/` serta `api/services/`. Hanya narasi melalui flow lama yang tampak di kanvas: sekitar **1 dari 10 langkah (≈10%)**. `web/src/api/langflow.ts` telah memenuhi S7 dengan hanya memanggil FastAPI `/api/v1/ai/*`.

## Peta pipeline aktual

| # | Langkah | Pelaksana/bukti | Terlihat di Langflow | Target |
|---:|---|---|:---:|---|
| 1 | Fitur + InferenceGuard | `src/features/*`, `src/models/inference_guard.py` | Tidak | Flow 01 extractor + guard |
| 2 | Skor ML + SHAP | `api/services/prioritization_service.py`, `src/models/predict.py`, `src/explainability/shap_explainer.py` | Tidak | Flow 01 scorer + SHAP |
| 3 | Prioritas final | `api/services/priority_service.py` | Tidak | Flow 00 composer |
| 4 | Normalisasi obat | `api/services/normalizer_service.py` | Tidak | Flow 02 normalizer |
| 5 | Diskrepansi | `src/rules/discrepancy_engine.py`, `api/services/discrepancy_service.py` | Tidak | Flow 02 rules |
| 6 | Safety/DDI/alergi/severity | `src/rules/safety_flags_engine.py`, `api/routes/interactions.py`, `configs/allergy_rules.json` | Tidak | Flow 02 parallel components |
| 7 | SBAR/narasi | `api/routes/v1/ai.py`, `api/services/llm_chain_service.py` | Sebagian | Flow 03 |
| 8 | Guardrail | `api/services/guardrail_service.py`, `src/llm/validators/output_validator.py` | Tidak | Flow 03 + verifier API |
| 9 | Review + audit | `api/routes/v1/review.py`, `api/services/audit_service.py`, `api/services/case_state_service.py` | Tidak | Flow 05 HITL/API audit |
| 10 | Copilot | `web/src/components/CopilotDrawer.tsx`, `api/routes/v1/ai.py` | Tidak | Flow 04 Agent/tools/KB |

## Flow, frontend, dan MCP

| Artefak | Kondisi | Gap |
|---|---|---|
| `langflow/priomedrec_orchestrator.json` | chat→HTTP FastAPI→prompt→LLM; metadata `lf_version: 1.11.5` | Bukan master/Fase A-B, tidak ada paritas/relay trace |
| `langflow/priomedrec_review.json` | chat review melalui HTTP FastAPI | Bukan Human Input checkpoint/tool approval |
| `web/src/api/langflow.ts` | browser→FastAPI gateway | Pertahankan; jangan panggil Langflow langsung |
| `mcp_server.py`, `mcp_settings.json` | MCP stdio→FastAPI; write draft-only | Belum Bob↔Langflow dua arah |

Tidak ada `priomedrec_core`, `langflow/components/priomedrec`, atau flow target `00`–`06`. Audit hash-chain, HITL/high-alert hard stop, guardrail sembilan cek, normalizer, ML/InferenceGuard, rules/safety, dan priority composer harus tetap deterministik dan menjadi sumber tunggal sebelum diekspos sebagai node.
