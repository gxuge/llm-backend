import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.config import settings
from app.workflows.langgraph_demo import workflow
from app.workflows.ragflow_graph import ragflow_workflow
from app.services.ragflow import RagflowConfigError, RagflowRetrievalError

router = APIRouter(tags=["LangGraph"])
logger = logging.getLogger(__name__)


class WorkflowRequest(BaseModel):
    message: str = Field(..., description="User message to feed into the graph")
    history: list[str] = Field(default_factory=list, description="Past turns")


@router.post("/demo", summary="Run LangGraph demo workflow")
def run_demo(payload: WorkflowRequest) -> dict:
    events = []
    for step in workflow.stream({"message": payload.message, "history": payload.history}):
        events.append(step)

    # `invoke` gives the final state after the compiled graph runs once.
    final_state = workflow.invoke({"message": payload.message, "history": payload.history})
    return {"events": events, "final_state": final_state}


class RagflowWorkflowRequest(BaseModel):
    question: str = Field(..., description="用户问题，将用于检索 RAGFlow 知识库")
    history: list[str] = Field(default_factory=list, description="可选的历史对话轮次")
    model: str | None = Field(
        None, description="使用的模型名称，默认走 APP_MODEL_DEFAULT/DeepSeek"
    )
    top_k: int | None = Field(
        None, gt=0, description="覆盖默认的 RAGFlow top_k (APP_RAGFLOW_TOP_K_DEFAULT)"
    )


class RagflowWorkflowResponse(BaseModel):
    model: str
    contexts: list[str]
    answer: str
    reasoning: str | None = None
    raw: dict[str, Any] | None = None


@router.post(
    "/ragflow",
    summary="Query RAGFlow KB then answer with LLM via LangGraph",
    response_model=RagflowWorkflowResponse,
)
async def run_ragflow_workflow(payload: RagflowWorkflowRequest) -> RagflowWorkflowResponse:
    initial_state = {
        "question": payload.question,
        "history": payload.history,
        "model": payload.model or settings.model_default,
    }
    if payload.top_k:
        initial_state["top_k"] = payload.top_k

    try:
        final_state = await ragflow_workflow.ainvoke(initial_state)
    except (RagflowConfigError, RagflowRetrievalError) as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    except Exception as exc:  # pragma: no cover
        logger.exception("Unhandled ragflow workflow error")
        raise HTTPException(status_code=500, detail="Unexpected ragflow workflow error") from exc

    return RagflowWorkflowResponse(
        model=final_state.get("model") or settings.model_default,
        contexts=final_state.get("contexts", []),
        answer=final_state.get("answer", ""),
        reasoning=final_state.get("reasoning"),
        raw=final_state.get("raw"),
    )
