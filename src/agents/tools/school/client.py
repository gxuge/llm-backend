from __future__ import annotations

from contextvars import ContextVar
from typing import Any

import httpx

from src.app.core.config import settings


class SchoolConfigError(Exception):
    """学校后端配置缺失异常。"""


class SchoolApiError(Exception):
    """学校后端接口返回异常。"""


_access_token = ContextVar("school_access_token", default=None)


def set_access_token(token: str | None) -> None:
    """在当前协程上下文设置学校接口访问令牌。"""
    _access_token.set(token)


def _get_access_token() -> str | None:
    """读取当前协程上下文中的访问令牌。"""
    return _access_token.get()


def _get_base_url() -> str:
    """统一校验并返回学校后端基础地址。"""
    if not settings.school_api_base:
        raise SchoolConfigError("缺少 APP_SCHOOL_API_BASE，请在环境变量中配置学校后端基础地址。")
    return settings.school_api_base.rstrip("/")


def clean_params(params: dict[str, Any]) -> dict[str, Any]:
    """过滤值为 None 的参数，避免传递无效字段。"""
    return {key: value for key, value in params.items() if value is not None}


def _extract_error_message(payload: Any) -> str:
    """从后端统一返回体中提取错误信息。"""
    if isinstance(payload, dict):
        for key in ("message", "msg", "error"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return "学校后端返回失败。"


def _unwrap_result(payload: Any) -> Any:
    """
    统一解析 Jeecg Result 包装：
    - success=false 时抛出异常，优先使用 message/msg。
    - success=true 且包含 result 字段时返回 result。
    - 非标准结构时返回原始 payload。
    """
    if isinstance(payload, dict) and "success" in payload:
        if payload.get("success") is False:
            raise SchoolApiError(_extract_error_message(payload))
        if "result" in payload:
            return payload.get("result")
    return payload


async def request_school_api(
    path: str,
    *,
    method: str,
    params: dict[str, Any] | None = None,
) -> Any:
    """
    学校后端通用请求封装。
    - GET: 参数放 query string
    - POST: 参数放 JSON body
    """
    base_url = _get_base_url()
    timeout = settings.school_api_timeout
    url = f"{base_url}{path if path.startswith('/') else f'/{path}'}"

    headers: dict[str, str] = {}
    token = _get_access_token()
    if token:
        headers["X-Access-Token"] = token

    clean = clean_params(params or {})
    method_upper = method.strip().upper()
    async with httpx.AsyncClient(timeout=timeout) as client:
        if method_upper == "POST":
            response = await client.post(url, json=clean, headers=headers)
        else:
            response = await client.get(url, params=clean, headers=headers)

    try:
        payload = response.json()
    except Exception as exc:  # pragma: no cover - 防御式兜底
        raise SchoolApiError(f"学校后端返回非 JSON 内容: {response.text}") from exc

    if response.status_code >= 400:
        raise SchoolApiError(_extract_error_message(payload))

    return _unwrap_result(payload)
