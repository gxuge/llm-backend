from fastapi import APIRouter

# 仅保留 workflow 路由入口，具体工作流已按要求移除。
router = APIRouter(tags=["LangGraph"])
