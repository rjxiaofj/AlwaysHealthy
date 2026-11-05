from datetime import date, datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class RegisterIn(BaseModel):
    username: str = Field(min_length=3, max_length=32, pattern=r"^[A-Za-z0-9_]+$")
    password: str = Field(min_length=8, max_length=64)
    email: str | None = None


class LoginIn(BaseModel):
    username: str
    password: str


class RefreshIn(BaseModel):
    refresh_token: str


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    expires_in: int
    user_id: UUID
    username: str
    role: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    username: str
    email: str | None
    role: str
    status: str
    created_at: datetime
    last_login_at: datetime | None


class ProfilePatch(BaseModel):
    birth_date: date | None = None
    sex: Literal["male", "female"] | None = None
    height_cm: float | None = Field(default=None, ge=80, le=250)
    weight_kg: float | None = Field(default=None, ge=25, le=300)
    waist_cm: float | None = Field(default=None, ge=40, le=200)
    occupation: str | None = None
    lifestyle: dict[str, Any] | None = None


class MedicalHistoryIn(BaseModel):
    history_type: Literal["personal", "family", "allergy"]
    condition_code: str = Field(min_length=1, max_length=64)
    description: str | None = None


class MedicalHistoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    history_type: str
    condition_code: str
    description: str | None
    recorded_at: datetime


class ProfileOut(BaseModel):
    id: UUID
    birth_date: date | None
    age: int | None
    # 只在对话里报到年龄时写这一列，birth_date 仍留空。前端据它提示「补一下生日」
    age_years: int | None = None
    sex: str | None
    height_cm: float | None
    weight_kg: float | None
    bmi: float | None
    waist_cm: float | None
    occupation: str | None
    lifestyle: dict[str, Any]
    profile_version: int
    medical_histories: list[MedicalHistoryOut] = []


class RiskFactorOut(BaseModel):
    rule_id: str
    indicator: str
    label: str
    value: Any = None
    unit: str = ""
    message: str
    risk_level: str


class SourceOut(BaseModel):
    source_id: str | None = None
    title: str | None = None
    version: str | None = None
    page: int | None = None


class DimensionOut(BaseModel):
    dimension: str
    level: str
    risk_factors: list[RiskFactorOut] = []
    missing_data: list[str] = []
    explanation: str = ""
    limitations: list[str] = []
    evidence_sources: list[SourceOut] = []


class AssessmentIn(BaseModel):
    note: str | None = None


class AssessmentOut(BaseModel):
    id: UUID
    overall_level: str
    urgency: str
    rule_engine_version: str
    knowledge_version: str
    created_at: datetime
    profile_version: int
    dimensions: list[DimensionOut] = []
    recommendations: list[dict[str, Any]] = []


class ApplyExtractedIn(BaseModel):
    metric_codes: list[str] = Field(min_length=1, max_length=20)

    @field_validator("metric_codes")
    @classmethod
    def _dedupe(cls, value: list[str]) -> list[str]:
        # 重复编码只会让跳过计数变大，这里直接收掉
        seen: list[str] = []
        for code in value:
            if code not in seen:
                seen.append(code)
        return seen
