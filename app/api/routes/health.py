# ??????????????????
from fastapi import APIRouter

router = APIRouter(tags=["Health"])


@router.get("/health", summary="Health check")
def healthcheck() -> dict[str, str]:
    # 统一健康检查入口
    return {"status": "ok"}
