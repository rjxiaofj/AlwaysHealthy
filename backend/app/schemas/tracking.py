from datetime import date, datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.tools.metrics import METRIC_DEFS


class MetricIn(BaseModel):
    metric_code: str
    value: float
    measured_at: datetime
    context: dict[str, Any] = Field(default_factory=dict)

    @field_validator("metric_code")
    @classmethod
    def known_metric(cls, value: str) -> str:
        if value not in METRIC_DEFS:
            raise ValueError("未知的指标编码")
        return value

    @field_validator("value")
    @classmethod
    def sane_value(cls, value: float, info) -> float:
        code = info.data.get("metric_code")
        definition = METRIC_DEFS.get(code)
        if definition and not (definition.low <= value <= definition.high):
            raise ValueError(f"{definition.label} 数值超出可接受范围")
        return value


class MetricOut(BaseModel):
    id: UUID
    metric_code: str
    label: str
    value: float
    unit: str
    measured_at: datetime
    source_type: str
    context: dict[str, Any]


class FeedbackIn(BaseModel):
    plan_id: UUID | None = None
    mood_status: Literal["good", "fair", "low"] | None = None
    fatigue_level: Literal["low", "medium", "high"] | None = None
    physical_feeling: str | None = Field(default=None, max_length=500)
    execution_difficulty: str | None = Field(default=None, max_length=200)
    additional_feedback: str | None = Field(default=None, max_length=500)


class TrendPoint(BaseModel):
    measured_at: datetime
    value: float


class TrendOut(BaseModel):
    metric_code: str
    label: str
    unit: str
    points: list[TrendPoint]
    latest: float | None
    average: float | None
    minimum: float | None
    maximum: float | None
    change: float | None


class SummaryOut(BaseModel):
    period_start: date
    period_end: date
    completion_rate: float
    task_total: int
    task_completed: int
    metrics: list[TrendOut]
    notes: list[str]


class ReassessmentIn(BaseModel):
    reason: str = Field(min_length=2, max_length=200)
