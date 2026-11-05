from datetime import date, datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class PlanGenerateIn(BaseModel):
    duration_days: int = Field(default=14, ge=7, le=30)
    start_date: date | None = None
    assessment_id: UUID | None = None
    goal: str | None = None


class TaskOut(BaseModel):
    id: UUID
    title: str
    category: str
    description: str | None
    scheduled_date: date
    scheduled_time: str | None
    frequency: str | None
    duration_minutes: int | None
    completion_criteria: str
    checkin_type: str
    reminder_enabled: bool = False
    status: str
    checkin_status: str | None = None


class VersionOut(BaseModel):
    id: UUID
    version_no: int
    status: str
    change_reason: str | None
    created_at: datetime
    content: dict[str, Any] = {}


class AdjustmentOut(BaseModel):
    version_id: UUID | None
    reason: str | None
    status: str
    created_at: datetime
    feedback: str | None


class PendingTaskOut(BaseModel):
    id: UUID
    title: str
    scheduled_date: date
    scheduled_time: str | None
    duration_minutes: int | None


class PendingVersionOut(BaseModel):
    id: UUID
    version_no: int
    change_reason: str | None
    tasks: list[PendingTaskOut] = []


class PlanOut(BaseModel):
    id: UUID
    title: str
    duration_days: int
    start_date: date
    end_date: date
    status: str
    current_version_id: UUID | None
    assessment_id: UUID | None
    created_at: datetime
    adjustment: AdjustmentOut | None = None
    pending_version: PendingVersionOut | None = None
    tasks: list[TaskOut] = []
    versions: list[VersionOut] = []


class PlanApproveIn(BaseModel):
    version_id: UUID


class PlanAdjustIn(BaseModel):
    reason: str = Field(min_length=2, max_length=200)


class PlanShiftIn(BaseModel):
    start_date: date
    reason: str | None = Field(default=None, max_length=200)


class AdjustmentFeedbackIn(BaseModel):
    version_id: UUID
    feedback: str = Field(min_length=2, max_length=200)


class CheckinIn(BaseModel):
    status: Literal["completed", "partial", "missed", "skipped"]
    feedback: str | None = Field(default=None, max_length=500)
    checkin_date: date | None = None
    idempotency_key: str | None = None


class CheckinOut(BaseModel):
    id: UUID
    task_id: UUID
    status: str
    feedback: str | None
    checkin_date: date
    checkin_at: datetime


class TaskPatchIn(BaseModel):
    scheduled_date: date | None = None
    scheduled_time: str | None = Field(default=None, pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    reminder_enabled: bool | None = None
