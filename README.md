# FastAPI LangGraph Demo

Minimal FastAPI project pre-wired with a LangGraph demo and a RAGFlow + DeepSeek workflow.

## Quick start
1. (Optional) `python -m venv .venv && .\.venv\Scripts\activate`
2. Install deps: `pip install -r requirements.txt`
3. Copy env template: `cp .env.example .env` (adjust values if needed)
4. Run: `uvicorn main:app --reload --host 0.0.0.0 --port 8000`
5. Open Swagger UI at `http://localhost:8000/docs`

## Project layout
- `main.py` - FastAPI app factory, CORS, router wiring, Swagger config.
- `app/core/config.py` - Environment-driven settings via `pydantic-settings`.
- `app/api/routes/` - API routers (`health`, `workflow`, `internal_runs`).
- `app/workflows/langgraph_demo.py` - Small LangGraph demo graph.
- `app/workflows/ragflow_graph.py` - RAGFlow retrieval + LLM answering graph.
- `.env.example` - Template for local configuration.

## Endpoints
- `GET /api/health` - Liveness check.
- `POST /api/workflows/demo` - Runs the LangGraph demo, returning streamed steps and the final state.
- `POST /api/workflows/ragflow` - RAGFlow retrieval + DeepSeek generation.
- `POST /internal/runs` - Start workflow run (internal).
- `GET /internal/runs/events?runId=...` - Stream SSE events (internal).
- `GET /internal/runs/result?runId=...` - Fetch run summary (internal).

## Environment
Set values in `.env` (defaults in the template):
- `APP_DEBUG`, `APP_HOST`, `APP_PORT`
- `APP_MODELSCOPE_API_BASE`, `APP_MODELSCOPE_API_KEY`
- `APP_MODEL_DEFAULT` (e.g., `deepseek-ai/DeepSeek-V3.2`)
- `APP_RAGFLOW_API_BASE` (e.g., `http://localhost:9380/api`)
- `APP_RAGFLOW_API_KEY`
- `APP_RAGFLOW_TOP_K_DEFAULT` (default: `4`)
- `APP_RAGFLOW_KB_ID` optional fixed knowledge base id
- `APP_RAGFLOW_DATASET_IDS` optional dataset ids for retrieval
- `APP_RAGFLOW_RERANK_ID` optional rerank id for retrieval

## Working with LangGraph
- Add new graphs under `app/workflows/` and expose them through routers in `app/api/routes/`.
- `langgraph_demo` shows a basic uppercase + echo flow.
- `ragflow_graph` shows a simple RAG workflow.

Example request:
```bash
curl -X POST http://localhost:8000/api/workflows/ragflow \
  -H "Content-Type: application/json" \
  -d '{
    "question": "LangGraph 用法是什么？",
    "history": ["之前聊过 RAGFlow 怎么用"],
    "model": "deepseek-ai/DeepSeek-R1-0528",
    "top_k": 3
  }'
```

Response fields: `contexts` (RAGFlow text list), `answer` (LLM reply), `reasoning` (DeepSeek R1 chain-of-thought when present), `raw` (full model payload).

## Dependency pins
See `requirements.txt` for the pinned versions. If you need the latest releases or release dates, run `pip index versions <package>` or check PyPI/changelogs before upgrading.