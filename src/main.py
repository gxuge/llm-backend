# ??????????????????
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from src.app.api.routes import health, internal_runs, workflow
from src.app.core.config import settings
from src.app.services.run_store import RedisUnavailableError


def create_app() -> FastAPI:
    """应用入口：初始化 FastAPI、CORS 与路由。"""
    app = FastAPI(
        title=settings.app_name,
        debug=settings.debug,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router, prefix="/api")
    app.include_router(workflow.router, prefix="/api/workflows")
    app.include_router(internal_runs.router)

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        # 统一 HTTP 异常输出，避免过多堆栈信息
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"message": exc.detail, "code": exc.status_code}},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        # 参数校验错误：仅返回简明字段
        return JSONResponse(
            status_code=422,
            content={"error": {"message": "Validation error", "details": exc.errors()}},
        )

    @app.exception_handler(RedisUnavailableError)
    async def redis_unavailable_handler(request: Request, exc: RedisUnavailableError):
        return JSONResponse(
            status_code=503,
            content={"error": {"message": "Redis unavailable", "code": "REDIS_UNAVAILABLE"}},
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        # 兜底异常：对外隐藏具体堆栈
        return JSONResponse(
            status_code=500,
            content={"error": {"message": "Internal server error"}},
        )

    return app


app = create_app()


@app.get("/", include_in_schema=False)
def root() -> dict[str, str]:
    """健康页：给出应用状态与文档入口。"""
    return {"message": f"{settings.app_name} is up", "docs": "/docs"}
