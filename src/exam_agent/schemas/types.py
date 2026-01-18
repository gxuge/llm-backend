from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

Intent = Literal["政策", "分数", "排名", "推荐", "学校信息", "混合"]


class QuerySpec(BaseModel):
    year: int | None = None
    school_name: str | None = None
    area_name: str | None = None
    score: int | None = None
    intent: Intent = "政策"
    school_type: int | None = None
    boarding_type: int | None = None
    score_type: int | None = None
    registered_residence_type: int | None = None
    accommodation_type: int | None = None


class Citation(BaseModel):
    title: str | None = None
    source: str | None = None
    snippet: str | None = None
    url: str | None = None


class TableColumn(BaseModel):
    field: str
    title: str


class TableSpec(BaseModel):
    type: str = "table"
    table_id: str = Field(default="table", alias="tableId")
    title: str = "Table"
    row_key: str = Field(default="id", alias="rowKey")
    columns: list[TableColumn] = Field(default_factory=list)
    rows: list[dict[str, Any]] = Field(default_factory=list)
    meta: dict[str, Any] | None = None


class ChartSpec(BaseModel):
    lib: str = "echarts"
    option: dict[str, Any]
