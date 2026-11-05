from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

Json = JSON().with_variant(JSONB(), "postgresql")


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    username: Mapped[str] = mapped_column(String(64), unique=True)
    email: Mapped[str | None] = mapped_column(String(128), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(16), default="user")
    status: Mapped[str] = mapped_column(String(16), default="active")
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class HealthProfile(Base, TimestampMixin):
    __tablename__ = "health_profiles"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    birth_date: Mapped[date | None] = mapped_column(Date)
    # 对话里只拿到年龄时记这里，birth_date 仍然留空，不反推具体生日
    age_years: Mapped[int | None] = mapped_column(Integer)
    sex: Mapped[str | None] = mapped_column(String(8))
    height_cm: Mapped[Decimal | None] = mapped_column(Numeric(5, 1))
    weight_kg: Mapped[Decimal | None] = mapped_column(Numeric(5, 1))
    waist_cm: Mapped[Decimal | None] = mapped_column(Numeric(5, 1))
    occupation: Mapped[str | None] = mapped_column(String(64))
    lifestyle: Mapped[dict[str, Any]] = mapped_column(Json, default=dict)
    profile_version: Mapped[int] = mapped_column(Integer, default=1)


class MedicalHistory(Base):
    __tablename__ = "medical_histories"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    history_type: Mapped[str] = mapped_column(String(16))
    condition_code: Mapped[str] = mapped_column(String(64))
    description: Mapped[str | None] = mapped_column(Text)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class HealthMetricRecord(Base):
    __tablename__ = "health_metric_records"
    __table_args__ = (Index("ix_metric_user_code_time", "user_id", "metric_code", "measured_at"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    metric_code: Mapped[str] = mapped_column(String(48))
    value: Mapped[Decimal] = mapped_column(Numeric(10, 3))
    unit: Mapped[str] = mapped_column(String(16))
    measured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    source_type: Mapped[str] = mapped_column(String(16), default="manual")
    measurement_context: Mapped[dict[str, Any]] = mapped_column(Json, default=dict)
    quality_status: Mapped[str] = mapped_column(String(16), default="valid")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class RiskAssessment(Base):
    __tablename__ = "risk_assessments"
    __table_args__ = (Index("ix_assessment_user_time", "user_id", "created_at"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    profile_version: Mapped[int] = mapped_column(Integer, default=1)
    profile_snapshot: Mapped[dict[str, Any]] = mapped_column(Json, default=dict)
    overall_level: Mapped[str] = mapped_column(String(16))
    urgency: Mapped[str] = mapped_column(String(16))
    rule_engine_version: Mapped[str] = mapped_column(String(32))
    knowledge_version: Mapped[str] = mapped_column(String(32))
    assessment_status: Mapped[str] = mapped_column(String(16), default="completed")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AssessmentDimensionResult(Base):
    __tablename__ = "assessment_dimension_results"
    __table_args__ = (UniqueConstraint("assessment_id", "dimension", name="uq_dimension_per_assessment"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    assessment_id: Mapped[UUID] = mapped_column(ForeignKey("risk_assessments.id", ondelete="CASCADE"), index=True)
    dimension: Mapped[str] = mapped_column(String(24))
    risk_level: Mapped[str] = mapped_column(String(16))
    risk_factors: Mapped[list[Any]] = mapped_column(Json, default=list)
    missing_data: Mapped[list[Any]] = mapped_column(Json, default=list)
    explanation: Mapped[str] = mapped_column(Text, default="")
    limitations: Mapped[list[Any]] = mapped_column(Json, default=list)


class AssessmentEvidence(Base):
    __tablename__ = "assessment_evidence"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    dimension_result_id: Mapped[UUID] = mapped_column(
        ForeignKey("assessment_dimension_results.id", ondelete="CASCADE"), index=True
    )
    source_id: Mapped[str] = mapped_column(String(64))
    chunk_id: Mapped[str] = mapped_column(String(96))
    page_number: Mapped[int | None] = mapped_column(Integer)
    evidence_excerpt: Mapped[str] = mapped_column(Text)


class KnowledgeSource(Base):
    __tablename__ = "knowledge_sources"

    source_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    title: Mapped[str] = mapped_column(String(255))
    issuing_org: Mapped[str] = mapped_column(String(128))
    document_type: Mapped[str] = mapped_column(String(32))
    version: Mapped[str] = mapped_column(String(32))
    publish_date: Mapped[date | None] = mapped_column(Date)
    effective_status: Mapped[str] = mapped_column(String(16), default="active")
    applicable_population: Mapped[str] = mapped_column(String(64), default="adult")
    dimensions: Mapped[list[Any]] = mapped_column(Json, default=list)
    original_url: Mapped[str | None] = mapped_column(String(512))
    import_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    checksum: Mapped[str] = mapped_column(String(64))
    license_note: Mapped[str | None] = mapped_column(String(255))


class InterventionRecommendation(Base):
    __tablename__ = "intervention_recommendations"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    assessment_id: Mapped[UUID] = mapped_column(ForeignKey("risk_assessments.id", ondelete="CASCADE"), index=True)
    dimension: Mapped[str] = mapped_column(String(24))
    category: Mapped[str] = mapped_column(String(32))
    priority: Mapped[str] = mapped_column(String(16))
    title: Mapped[str] = mapped_column(String(128))
    description: Mapped[str] = mapped_column(Text)
    action_items: Mapped[list[Any]] = mapped_column(Json, default=list)
    evidence_sources: Mapped[list[Any]] = mapped_column(Json, default=list)
    cautions: Mapped[list[Any]] = mapped_column(Json, default=list)
    requires_professional_consultation: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class HealthPlan(Base, TimestampMixin):
    __tablename__ = "health_plans"
    __table_args__ = (CheckConstraint("duration_days BETWEEN 7 AND 30", name="ck_plan_duration"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    assessment_id: Mapped[UUID | None] = mapped_column(ForeignKey("risk_assessments.id", ondelete="SET NULL"))
    title: Mapped[str] = mapped_column(String(128))
    duration_days: Mapped[int] = mapped_column(Integer)
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    current_version_id: Mapped[UUID | None] = mapped_column(Uuid)
    status: Mapped[str] = mapped_column(String(24), default="pending_review")


class HealthPlanVersion(Base):
    __tablename__ = "health_plan_versions"
    __table_args__ = (UniqueConstraint("plan_id", "version_no", name="uq_plan_version_no"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    plan_id: Mapped[UUID] = mapped_column(ForeignKey("health_plans.id", ondelete="CASCADE"), index=True)
    version_no: Mapped[int] = mapped_column(Integer)
    change_reason: Mapped[str | None] = mapped_column(Text)
    plan_content: Mapped[dict[str, Any]] = mapped_column(Json, default=dict)
    status: Mapped[str] = mapped_column(String(24), default="draft")
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PlanTask(Base):
    __tablename__ = "plan_tasks"
    __table_args__ = (Index("ix_task_version_date", "plan_version_id", "scheduled_date"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    plan_version_id: Mapped[UUID] = mapped_column(ForeignKey("health_plan_versions.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(128))
    category: Mapped[str] = mapped_column(String(32))
    description: Mapped[str | None] = mapped_column(Text)
    scheduled_date: Mapped[date] = mapped_column(Date)
    scheduled_time: Mapped[str | None] = mapped_column(String(8))
    frequency: Mapped[str | None] = mapped_column(String(32))
    duration_minutes: Mapped[int | None] = mapped_column(Integer)
    completion_criteria: Mapped[str] = mapped_column(String(255))
    checkin_type: Mapped[str] = mapped_column(String(16), default="boolean")
    reminder_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(16), default="pending")


class TaskCheckin(Base):
    __tablename__ = "task_checkins"
    __table_args__ = (UniqueConstraint("task_id", "checkin_date", name="uq_checkin_per_day"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    task_id: Mapped[UUID] = mapped_column(ForeignKey("plan_tasks.id", ondelete="CASCADE"))
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(16))
    feedback: Mapped[str | None] = mapped_column(Text)
    checkin_date: Mapped[date] = mapped_column(Date)
    checkin_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    idempotency_key: Mapped[str | None] = mapped_column(String(96))


class HealthFeedbackRecord(Base):
    __tablename__ = "health_feedback_records"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    plan_id: Mapped[UUID | None] = mapped_column(ForeignKey("health_plans.id", ondelete="SET NULL"))
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    mood_status: Mapped[str | None] = mapped_column(String(16))
    fatigue_level: Mapped[str | None] = mapped_column(String(16))
    physical_feeling: Mapped[str | None] = mapped_column(Text)
    execution_difficulty: Mapped[str | None] = mapped_column(String(32))
    additional_feedback: Mapped[str | None] = mapped_column(Text)


class TrackingSummary(Base):
    __tablename__ = "tracking_summaries"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    plan_id: Mapped[UUID] = mapped_column(ForeignKey("health_plans.id", ondelete="CASCADE"))
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)
    completion_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    metric_summary: Mapped[dict[str, Any]] = mapped_column(Json, default=dict)
    trend_summary: Mapped[dict[str, Any]] = mapped_column(Json, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PlanAdjustmentRecord(Base):
    __tablename__ = "plan_adjustment_records"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    plan_id: Mapped[UUID] = mapped_column(ForeignKey("health_plans.id", ondelete="CASCADE"), index=True)
    old_version_id: Mapped[UUID | None] = mapped_column(Uuid)
    new_version_id: Mapped[UUID | None] = mapped_column(Uuid)
    adjustment_reason: Mapped[str | None] = mapped_column(Text)
    user_feedback: Mapped[str | None] = mapped_column(Text)
    approval_status: Mapped[str] = mapped_column(String(16), default="pending")
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Conversation(Base, TimestampMixin):
    __tablename__ = "conversations"
    __table_args__ = (Index("ix_conversation_user_time", "user_id", "updated_at"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    thread_id: Mapped[str] = mapped_column(String(64), unique=True)
    title: Mapped[str] = mapped_column(String(128), default="新的健康对话")
    status: Mapped[str] = mapped_column(String(16), default="active")


class ConversationMessage(Base):
    __tablename__ = "conversation_messages"
    __table_args__ = (Index("ix_message_conversation_time", "conversation_id", "created_at"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    conversation_id: Mapped[UUID] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"))
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text)
    message_type: Mapped[str] = mapped_column(String(24), default="text")
    meta: Mapped[dict[str, Any]] = mapped_column(Json, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class WorkflowRun(Base):
    __tablename__ = "workflow_runs"
    __table_args__ = (Index("ix_run_conversation_time", "conversation_id", "started_at"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    conversation_id: Mapped[UUID] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"))
    thread_id: Mapped[str] = mapped_column(String(64))
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    run_type: Mapped[str] = mapped_column(String(24), default="message")
    status: Mapped[str] = mapped_column(String(16), default="running")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(48))
    meta: Mapped[dict[str, Any]] = mapped_column(Json, default=dict)


class HealthReport(Base):
    __tablename__ = "health_reports"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    assessment_id: Mapped[UUID | None] = mapped_column(Uuid)
    tracking_summary_id: Mapped[UUID | None] = mapped_column(Uuid)
    report_type: Mapped[str] = mapped_column(String(24))
    title: Mapped[str] = mapped_column(String(128))
    content_snapshot: Mapped[dict[str, Any]] = mapped_column(Json, default=dict)
    file_asset_id: Mapped[UUID | None] = mapped_column(Uuid)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class EmergencyEvent(Base):
    __tablename__ = "emergency_events"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    conversation_id: Mapped[UUID | None] = mapped_column(Uuid)
    run_id: Mapped[UUID | None] = mapped_column(Uuid)
    trigger_reason: Mapped[str] = mapped_column(String(255))
    matched_rules: Mapped[list[Any]] = mapped_column(Json, default=list)
    urgency: Mapped[str] = mapped_column(String(16), default="紧急")
    response_status: Mapped[str] = mapped_column(String(16), default="delivered")
    triggered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (Index("ix_notification_user_read", "user_id", "read_at", "created_at"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    notification_type: Mapped[str] = mapped_column(String(32))
    title: Mapped[str] = mapped_column(String(128))
    content: Mapped[str] = mapped_column(Text)
    related_object_id: Mapped[UUID | None] = mapped_column(Uuid)
    dedup_key: Mapped[str | None] = mapped_column(String(96), unique=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ConsentRecord(Base):
    __tablename__ = "consent_records"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    consent_type: Mapped[str] = mapped_column(String(48))
    policy_version: Mapped[str] = mapped_column(String(16))
    consent_status: Mapped[str] = mapped_column(String(16))
    consented_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class FileAsset(Base):
    __tablename__ = "file_assets"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    original_filename: Mapped[str] = mapped_column(String(255))
    stored_filename: Mapped[str] = mapped_column(String(128))
    storage_path: Mapped[str] = mapped_column(String(512))
    mime_type: Mapped[str] = mapped_column(String(64))
    file_size: Mapped[int] = mapped_column(BigInteger)
    checksum: Mapped[str] = mapped_column(String(64))
    scan_status: Mapped[str] = mapped_column(String(16), default="skipped")
    parse_status: Mapped[str] = mapped_column(String(16), default="pending")
    # 解析出的候选指标，用户确认前不进指标表
    parsed_payload: Mapped[dict[str, Any] | None] = mapped_column(Json)
    parse_message: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SecurityAuditLog(Base):
    __tablename__ = "security_audit_logs"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    actor_user_id: Mapped[UUID | None] = mapped_column(Uuid, index=True)
    action: Mapped[str] = mapped_column(String(48))
    resource_type: Mapped[str] = mapped_column(String(32))
    resource_id: Mapped[str | None] = mapped_column(String(64))
    result: Mapped[str] = mapped_column(String(16))
    request_id: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SecurityIncident(Base):
    __tablename__ = "security_incidents"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    incident_type: Mapped[str] = mapped_column(String(48))
    severity: Mapped[str] = mapped_column(String(16))
    description: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default="open")
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
