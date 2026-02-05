# 学校工具
from __future__ import annotations

import datetime
from typing import Any

import httpx
from langchain_core.tools import tool

from src.app.core.config import settings

from contextvars import ContextVar

_access_token = ContextVar("school_access_token", default=None)

def set_access_token(token: str | None) -> None:
    _access_token.set(token)

def _get_access_token() -> str | None:
    return _access_token.get()



# school 工具异常
class SchoolConfigError(Exception):
    """school 后端配置缺失时抛出。"""


# school 接口错误
class SchoolApiError(Exception):
    """school 后端返回错误时抛出。"""



# 获取基础地址（不做鉴权）
# 获取基础地址（不做鉴权）
def _get_base_url() -> str:
    if not settings.school_api_base:
        raise SchoolConfigError("未配置 APP_SCHOOL_API_BASE，请在环境变量中指定 school 基础地址。")
    return settings.school_api_base.rstrip("/")


# 过滤掉 None 参数，避免无效查询
# 过滤 None 参数，避免无效查询
def _clean_params(params: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in params.items() if value is not None}


# 通用 GET 请求封装（无 token 认证）
# 通用 GET 封装（无 token 认证）
async def _get_json(path: str, *, params: dict[str, Any]) -> Any:
    base_url = _get_base_url()
    timeout = settings.school_api_timeout

    url = f"{base_url}{path if path.startswith('/') else f'/{path}'}"
    headers = {}
    token = _get_access_token()
    if token:
        headers["X-Access-Token"] = token

    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.get(url, params=params, headers=headers)
        if response.status_code == 405:
            response = await client.post(url, params=params, json=params, headers=headers)

    if response.status_code >= 400:
        raise SchoolApiError(f"school backend error {response.status_code}: {response.text}")

@tool("list_school_page")
# 学校分页列表
async def list_school_page(
    name: str | None = None,
    area_id: str | None = None,
    school_type: int | None = None,
    boarding_type: int | None = None,
    page_no: int | None = None,
    page_size: int | None = None,
) -> Any:
    """
    获取校园管理列表（/sys/school/list）。
    """
    # school_type: 0=公办普高, 1=民办普高, 2=中职, 3=综合
    # boarding_type: 0=到校, 1=走读, 2=其他
    params = _clean_params(
        {
            "name": name,
            "areaId": area_id,
            "schoolType": school_type,
            "boardingType": boarding_type,
            "pageNo": page_no,
            "pageSize": page_size,
        }
    )
    return await _get_json("/sys/school/list", params=params)


@tool("list_area_page")
# 区域分页列表
async def list_area_page(
    name: str | None = None,
    page_no: int | None = None,
    page_size: int | None = None,
) -> Any:
    """
    获取区域管理列表（/sys/area/list）。
    """
    params = _clean_params({"name": name, "pageNo": page_no, "pageSize": page_size})
    return await _get_json("/sys/area/list", params=params)


@tool("list_school_scores")
# 学校分数列表
async def list_school_scores(
    year: int | None = None,
    score_type: int | None = None,
    school_id: str | None = None,
    registered_residence_type: int | None = None,
    accommodation_type: int | None = None,
) -> Any:
    """
    获取学校分数列表（/sys/score/list）。
    使用场景：按年份、类型、学校、户籍类型、住宿类型过滤分数数据。
    """
    # score_type: 0=指标, 1=一批, 2=其他
    # registered_residence_type: 0=AC类, 1=D类, 2=综合
    # accommodation_type: 0=住校, 1=走读
    if year is None:
        year = datetime.date.today().year
    params = _clean_params(
        {
            "schoolId": school_id,
            "year": year,
            "type": score_type,
            "registeredResidenceType": registered_residence_type,
            "accommodationType": accommodation_type,
        }
    )
    return await _get_json("/sys/score/listByCondition", params=params)


@tool("list_school_rank_page")
# 学校排名分页
async def list_school_rank_page(
    school_id: str | None = None,
    year: int | None = None,
    page_no: int | None = None,
    page_size: int | None = None,
) -> Any:
    """
    获取学校排名分页列表（/sys/rank/list）。
    """
    params = _clean_params(
        {
            "schoolId": school_id,
            "year": year,
            "pageNo": page_no,
            "pageSize": page_size,
        }
    )
    return await _get_json("/sys/rank/list", params=params)


@tool("list_score_layer_page")
# 分数分层分页
async def list_score_layer_page(
    year: int | None = None,
    subject: int | None = None,
    page_no: int | None = None,
    page_size: int | None = None,
) -> Any:
    """
    获取分数层次分页列表（/sys/scoreLayer/list）。
    """
    if year is None:
        year = datetime.date.today().year
    params = _clean_params(
        {"year": year, "subject": subject, "pageNo": page_no, "pageSize": page_size}
    )
    return await _get_json("/sys/scoreLayer/list", params=params)


@tool("list_school_ranks")
# 学校排名列表（不分页）
async def list_school_ranks(
    school_id: str | None = None, year: int | None = None
) -> Any:
    """
    获取学校排名列表（/sys/rank/listAll）。
    使用场景：按学校或年份过滤不分页的排名数据。
    """
    params = _clean_params({"schoolId": school_id, "year": year})
    return await _get_json("/sys/rank/listAll", params=params)


@tool("list_schools")
# 学校列表（不分页）
async def list_schools(
    name: str | None = None,
    area_id: str | None = None,
    school_type: int | None = None,
    boarding_type: int | None = None,
) -> Any:
    """
    获取学校列表（/sys/school/listAll）。
    使用场景：前置过滤学校数据，为后续按 ID 查询或联动选择器提供选项。
    """
    # school_type: 0=公办普高, 1=民办普高, 2=中职, 3=综合
    # boarding_type: 0=到校, 1=走读, 2=其他
    params = _clean_params(
        {
            "name": name,
            "areaId": area_id,
            "schoolType": school_type,
            "boardingType": boarding_type,
        }
    )
    return await _get_json("/sys/school/listAll", params=params)


SCHOOL_TOOLS = [
    list_school_page,
    list_area_page,
    list_school_scores,
    list_school_rank_page,
    list_score_layer_page,
    list_school_ranks,
    list_schools,
]
