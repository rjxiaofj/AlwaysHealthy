from datetime import date, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    AssessmentDimensionResult,
    AssessmentEvidence,
    Conversation,
    ConversationMessage,
    HealthMetricRecord,
    HealthProfile,
    InterventionRecommendation,
    MedicalHistory,
    PlanTask,
    RefreshToken,
    RiskAssessment,
    TaskCheckin,
    User,
    WorkflowRun,
)
from app.integrations.wearable import QUALITY_VERIFIED, SOURCE_WEARABLE


async def get_user(session: AsyncSession, user_id: UUID) -> User | None:
    return await session.get(User, user_id)


async def get_user_by_username(session: AsyncSession, username: str) -> User | None:
    return await session.scalar(select(User).where(User.username == username))


async def add_refresh_token(session: AsyncSession, token: RefreshToken) -> None:
    session.add(token)


async def find_refresh_token(session: AsyncSession, token_hash: str) -> RefreshToken | None:
    return await session.scalar(select(RefreshToken).where(RefreshToken.token_hash == token_hash))


async def profile_of(session: AsyncSession, user_id: UUID) -> HealthProfile | None:
    return await session.scalar(select(HealthProfile).where(HealthProfile.user_id == user_id))


async def histories_of(session: AsyncSession, user_id: UUID) -> list[MedicalHistory]:
    rows = await session.scalars(
        select(MedicalHistory).where(MedicalHistory.user_id == user_id).order_by(MedicalHistory.recorded_at.desc())
    )
    return list(rows)


async def metrics_of(session: AsyncSession, user_id: UUID, codes: list[str] | None, limit: int) -> list[HealthMetricRecord]:
    stmt = select(HealthMetricRecord).where(HealthMetricRecord.user_id == user_id)
    if codes:
        stmt = stmt.where(HealthMetricRecord.metric_code.in_(codes))
    stmt = stmt.order_by(HealthMetricRecord.measured_at.desc()).limit(limit)
    return list(await session.scalars(stmt))


async def latest_metrics(session: AsyncSession, user_id: UUID, codes: tuple[str, ...]) -> dict[str, HealthMetricRecord]:
    rows = await session.scalars(
        select(HealthMetricRecord)
        .where(HealthMetricRecord.user_id == user_id, HealthMetricRecord.metric_code.in_(codes))
        .order_by(HealthMetricRecord.measured_at.desc())
    )
    latest: dict[str, HealthMetricRecord] = {}
    for row in rows:
        if not _counting_for_assessment(row):
            continue
        latest.setdefault(row.metric_code, row)
    return latest


def _counting_for_assessment(row: HealthMetricRecord) -> bool:
    """设备读数只有标记 verified 才进评估快照。

    否则第一次拉取手环就会把估算心率替换掉用户手动录入的血压记录。
    """
    if row.source_type != SOURCE_WEARABLE:
        return True
    return (row.measurement_context or {}).get("quality_status") == QUALITY_VERIFIED


async def assessment_of(session: AsyncSession, user_id: UUID, assessment_id: UUID) -> RiskAssessment | None:
    return await session.scalar(
        select(RiskAssessment).where(RiskAssessment.id == assessment_id, RiskAssessment.user_id == user_id)
    )


async def dimensions_of(session: AsyncSession, assessment_id: UUID) -> list[AssessmentDimensionResult]:
    rows = await session.scalars(
        select(AssessmentDimensionResult).where(AssessmentDimensionResult.assessment_id == assessment_id)
    )
    return list(rows)


async def evidence_of(session: AsyncSession, dimension_result_ids: list[UUID]) -> dict[UUID, list[AssessmentEvidence]]:
    if not dimension_result_ids:
        return {}
    rows = await session.scalars(
        select(AssessmentEvidence).where(AssessmentEvidence.dimension_result_id.in_(dimension_result_ids))
    )
    grouped: dict[UUID, list[AssessmentEvidence]] = {}
    for row in rows:
        grouped.setdefault(row.dimension_result_id, []).append(row)
    return grouped


async def recommendations_of(session: AsyncSession, assessment_id: UUID) -> list[InterventionRecommendation]:
    rows = await session.scalars(
        select(InterventionRecommendation).where(InterventionRecommendation.assessment_id == assessment_id)
    )
    return list(rows)


async def tasks_of_version(session: AsyncSession, version_id: UUID) -> list[PlanTask]:
    rows = await session.scalars(
        select(PlanTask).where(PlanTask.plan_version_id == version_id).order_by(PlanTask.scheduled_date, PlanTask.id)
    )
    return list(rows)


async def checkins_of_user(session: AsyncSession, user_id: UUID, since: date | None = None) -> list[TaskCheckin]:
    stmt = select(TaskCheckin).where(TaskCheckin.user_id == user_id)
    if since:
        stmt = stmt.where(TaskCheckin.checkin_date >= since)
    return list(await session.scalars(stmt))


async def count_rows(session: AsyncSession, model, *conditions) -> int:
    return int(await session.scalar(select(func.count()).select_from(model).where(*conditions)) or 0)
