from __future__ import annotations

import datetime
import json
import re

from app.core.config import settings
from app.nodes.state import AgentState, INTENT_OPTIONS
from app.nodes.utils import fallback_extract, normalize_query
from app.prompts.exam_agent import extractor_system_prompt
from app.services.modelscope import create_chat_completion
from src.exam_agent.services.events import emit_event


async def extract_query(state: AgentState) -> AgentState:
    question = state["question"]
    emit_event(state, "run.start", {"question": question}, status="running")
    year = datetime.date.today().year
    system_prompt = extractor_system_prompt(INTENT_OPTIONS)
    user_prompt = f"当前年份：{year}\n问题：{question}"
    try:
        result = await create_chat_completion(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            model=settings.model_default,
            temperature=0,
            top_p=1,
            stream=False,
        )
        payload_text = result["content"]
        json_match = re.search(r"\{.*\}", payload_text, re.DOTALL)
        if not json_match:
            raise ValueError("Extractor did not return JSON.")
        payload = json.loads(json_match.group(0))
        query = normalize_query(payload)
    except Exception:
        query = fallback_extract(question)
        emit_event(state, "trace.event", {"message": "Extractor fallback used."}, status="running")
    return {"query": query}
