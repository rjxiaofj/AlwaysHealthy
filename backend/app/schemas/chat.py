from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class ConversationIn(BaseModel):
    title: str | None = Field(default=None, max_length=64)


class ConversationOut(BaseModel):
    id: UUID
    title: str
    status: str
    created_at: datetime
    updated_at: datetime
    last_message: str | None = None


class MessageIn(BaseModel):
    content: str = Field(min_length=1, max_length=2000)


class MessageOut(BaseModel):
    id: UUID
    role: str
    content: str
    message_type: str
    meta: dict[str, Any]
    created_at: datetime


class RunOut(BaseModel):
    id: UUID
    status: str
    run_type: str
    started_at: datetime
    completed_at: datetime | None
    error_code: str | None
    meta: dict[str, Any]


class ResumeIn(BaseModel):
    approval_type: Literal["profile", "plan"]
    decision: Literal["approve", "modify", "reject"]
    business_id: UUID | None = None
    version_id: UUID | None = None
    feedback: str | None = Field(default=None, max_length=500)


class ReportOut(BaseModel):
    id: UUID
    report_type: str
    title: str
    content: dict[str, Any]
    created_at: datetime


class ReminderOut(BaseModel):
    id: UUID
    notification_type: str
    title: str
    content: str
    related_object_id: UUID | None
    read_at: datetime | None
    created_at: datetime


class FileOut(BaseModel):
    id: UUID
    original_filename: str
    mime_type: str
    file_size: int
    parse_status: str
    created_at: datetime


class ConsentIn(BaseModel):
    consent_type: str = Field(min_length=2, max_length=48)
    policy_version: str = Field(default="v1", max_length=16)
    granted: bool
