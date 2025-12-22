# FastAPI LangGraph + ChromaDB Demo

Minimal FastAPI project pre-wired with a ChromaDB vector store, a LangGraph demo, and a RAGFlow + DeepSeek workflow.

## Quick start
1. (Optional) `python -m venv .venv && .\.venv\Scripts\activate`
2. Install deps: `pip install -r requirements.txt`
3. Copy env template: `cp .env.example .env` (adjust values if needed)
4. Run: `uvicorn main:app --reload --host 0.0.0.0 --port 8000`
5. Open Swagger UI at `http://localhost:8000/docs`

## Project layout
- `main.py` – FastAPI app factory, CORS, router wiring, Swagger config.
- `app/core/config.py` – Environment-driven settings via `pydantic-settings`.
- `app/core/chroma.py` – Cached ChromaDB HTTP client + FastAPI dependency.
- `app/api/routes/` – API routers (`health`, `vector_store`, `workflow`, `chat`).
- `app/workflows/langgraph_demo.py` – Small LangGraph demo graph.
- `app/workflows/ragflow_graph.py` – RAGFlow retrieval + LLM answering graph.
- `.env.example` – Template for local configuration.

## Endpoints
- `GET /api/health` – Liveness check.
- `POST /api/chroma/vectors` – Upsert a vector (expects `id`, `embedding`, optional `document`/`metadata`).
- `POST /api/chroma/vectors/query` – Nearest-neighbor search via embeddings.
- `POST /api/workflows/demo` – Runs the LangGraph demo, returning streamed steps and the final state.
- `POST /api/chat/completions` – Proxies ModelScope chat completion (DeepSeek R1/V3), persists the turn into ChromaDB.
- `POST /api/workflows/ragflow` – RAGFlow retrieval + DeepSeek generation. Retrieves KB hits from RAGFlow, then sends the contexts to the LLM for parsing.

## Environment
Set values in `.env` (defaults in the template):
- `APP_DEBUG`, `APP_HOST`, `APP_PORT`
- `APP_CHROMA_HOST`, `APP_CHROMA_PORT`, `APP_CHROMA_COLLECTION`
- `APP_MODELSCOPE_API_BASE`, `APP_MODELSCOPE_API_KEY`
- `APP_MODEL_DEFAULT` (e.g., `deepseek-ai/DeepSeek-V3.2`)
- `APP_RAGFLOW_API_BASE` (e.g., `http://localhost:9380/api`)
- `APP_RAGFLOW_API_KEY`
- `APP_RAGFLOW_TOP_K_DEFAULT` (default: `4`)
- `APP_RAGFLOW_KB_ID` optional fixed knowledge base id

## Working with LangGraph
- Add new graphs under `app/workflows/` and expose them through routers in `app/api/routes/`.
- `langgraph_demo` shows a basic uppercase + echo flow.
- `ragflow_graph` shows a simple RAG workflow:
  1) `retrieve_contexts` calls RAGFlow (`APP_RAGFLOW_API_BASE` + `/v1/knowledge_base/retrieval`) to fetch KB hits (Bearer auth via `APP_RAGFLOW_API_KEY`, optional `APP_RAGFLOW_KB_ID`).
  2) `generate_answer` sends the hits, history, and question to DeepSeek (via ModelScope) and returns `answer/reasoning/raw`.
  Example request:
  ```bash
  curl -X POST http://localhost:8000/api/workflows/ragflow \
    -H "Content-Type: application/json" \
    -d '{
      "question": "LangGraph 用法是什么？",
      "history": ["之前聊过 ChromaDB 怎么用"],
      "model": "deepseek-ai/DeepSeek-R1-0528",
      "top_k": 3
    }'
  ```
  Response fields: `contexts` (RAGFlow text list), `answer` (LLM reply), `reasoning` (DeepSeek R1 chain-of-thought when present), `raw` (full model payload).

## Dependency pins
See `requirements.txt` for the pinned versions. If you need the latest releases or release dates, run `pip index versions <package>` or check PyPI/changelogs before upgrading.
