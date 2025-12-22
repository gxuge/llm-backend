from typing import Any
from typing_extensions import TypedDict

from langgraph.graph import END, StateGraph

from app.core.config import settings
from app.services.modelscope import create_chat_completion
from app.services.ragflow import RagflowClient, RagflowConfigError, RagflowRetrievalError, get_ragflow_client


class RagflowState(TypedDict, total=False):
    question: str
    history: list[str]
    contexts: list[str]
    model: str
    top_k: int
    answer: str
    reasoning: str | None
    raw: dict[str, Any] | None


async def retrieve_contexts(state: RagflowState) -> RagflowState:
    client: RagflowClient = get_ragflow_client()
    contexts = await client.retrieve(state["question"], top_k=state.get("top_k"))
    return {"contexts": contexts}


async def generate_answer(state: RagflowState) -> RagflowState:
    model = state.get("model") or settings.model_default
    contexts = state.get("contexts", [])
    history = state.get("history", [])

    context_block = "\n\n".join(contexts)
    history_block = "\n".join(history)

    prompt_parts = []
    if history_block:
        prompt_parts.append(f"历史对话:\n{history_block}")
    if context_block:
        prompt_parts.append(f"知识库命中文档:\n{context_block}")
    prompt_parts.append(f"用户问题:\n{state['question']}")

    messages = [
        {
            "role": "system",
            "content": (
                "你是一个基于知识库的助手。优先使用知识库内容回答问题，"
                "如果知识库无法覆盖，请直接说明而不是编造。"
            ),
        },
        {"role": "user", "content": "\n\n".join(prompt_parts)},
    ]

    result = await create_chat_completion(
        messages,
        model=model,
        temperature=settings.model_temperature_default,
        top_p=settings.model_top_p_default,
        presence_penalty=settings.model_presence_penalty_default,
        frequency_penalty=settings.model_frequency_penalty_default,
        max_tokens=settings.model_max_tokens_default,
        stream=False,
    )

    return {
        "model": model,
        "answer": result["content"],
        "reasoning": result.get("reasoning"),
        "raw": result.get("raw"),
    }


graph = StateGraph(RagflowState)
graph.add_node("retrieve_contexts", retrieve_contexts)
graph.add_node("generate_answer", generate_answer)
graph.add_edge("retrieve_contexts", "generate_answer")
graph.add_edge("generate_answer", END)
graph.set_entry_point("retrieve_contexts")

ragflow_workflow = graph.compile()
