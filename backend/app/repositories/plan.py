from datetime import date
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    HealthFeedbackRecord,
    HealthPlan,
    HealthPlanVersion,
    PlanAdjustmentRecord,
    PlanTask,
    TaskCheckin,
    TrackingSummary,
)


async def plan_of(session: AsyncSession, user_id: UUID, plan_id: UUID) -> HealthPlan | None:
    return await session.scalar(select(HealthPlan).where(HealthPlan.id == plan_id, HealthPlan.user_id == user_id))


async def plans_of(session: AsyncSession, user_id: UUID, status: str | None = None) -> list[HealthPlan]:
    stmt = select(HealthPlan).where(HealthPlan.user_id == user_id)
    if status:
        stmt = stmt.where(HealthPlan.status == status)
    return list(await session.scalars(stmt.order_by(HealthPlan.created_at.desc())))


async def versions_of(session: AsyncSession, plan_id: UUID) -> list[HealthPlanVersion]:
    rows = await session.scalars(
        select(HealthPlanVersion).where(HealthPlanVersion.plan_id == plan_id).order_by(HealthPlanVersion.version_no)
    )
    return list(rows)


async def version_of(session: AsyncSession, plan_id: UUID, version_id: UUID) -> HealthPlanVersion | None:
    return await session.scalar(
        select(HealthPlanVersion).where(HealthPlanVersion.id == version_id, HealthPlanVersion.plan_id == plan_id)
    )


async def active_plan(session: AsyncSession, user_id: UUID) -> HealthPlan | None:
    return await session.scalar(
        select(HealthPlan)
        .where(HealthPlan.user_id == user_id, HealthPlan.status == "active")
        .order_by(HealthPlan.start_date.desc())
    )


async def next_version_no(session: AsyncSession, plan_id: UUID) -> int:
    current = await session.scalar(
        select(func.max(HealthPlanVersion.version_no)).where(HealthPlanVersion.plan_id == plan_id)
    )
    return int(current or 0) + 1


async def tasks_of(session: AsyncSession, version_id: UUID, start: date | None = None, end: date | None = None):
    stmt = select(PlanTask).where(PlanTask.plan_version_id == version_id)
    if start:
        stmt = stmt.where(PlanTask.scheduled_date >= start)
    if end:
        stmt = stmt.where(PlanTask.scheduled_date <= end)
    return list(await session.scalars(stmt.order_by(PlanTask.scheduled_date, PlanTask.scheduled_time)))


async def task_of(session: AsyncSession, user_id: UUID, task_id: UUID) -> PlanTask | None:
    return await session.scalar(
        select(PlanTask)
        .join(HealthPlanVersion, HealthPlanVersion.id == PlanTask.plan_version_id)
        .join(HealthPlan, HealthPlan.id == HealthPlanVersion.plan_id)
        .where(PlanTask.id == task_id, HealthPlan.user_id == user_id)
    )


async def task_with_plan(
    session: AsyncSession, user_id: UUID, task_id: UUID
) -> tuple[PlanTask, HealthPlan, HealthPlanVersion] | None:
    """任务连同所属计划与版本一起取。改日期要校验版本是不是当前版本，分开查容易漏。"""
    row = await session.execute(
        select(PlanTask, HealthPlan, HealthPlanVersion)
        .join(HealthPlanVersion, HealthPlanVersion.id == PlanTask.plan_version_id)
        .join(HealthPlan, HealthPlan.id == HealthPlanVersion.plan_id)
        .where(PlanTask.id == task_id, HealthPlan.user_id == user_id)
    )
    return row.first()


async def checkin_count_of_task(session: AsyncSession, task_id: UUID) -> int:
    total = await session.scalar(select(func.count()).select_from(TaskCheckin).where(TaskCheckin.task_id == task_id))
    return int(total or 0)


async def checkin_of(session: AsyncSession, task_id: UUID, checkin_date: date) -> TaskCheckin | None:
    return await session.scalar(
        select(TaskCheckin).where(TaskCheckin.task_id == task_id, TaskCheckin.checkin_date == checkin_date)
    )


async def checkin_count_of_version(session: AsyncSession, version_id: UUID) -> int:
    """按版本统计打卡数。任务 id 随版本生成，改期换版本会让旧打卡挂不到新任务上。"""
    total = await session.scalar(
        select(func.count())
        .select_from(TaskCheckin)
        .join(PlanTask, PlanTask.id == TaskCheckin.task_id)
        .where(PlanTask.plan_version_id == version_id)
    )
    return int(total or 0)


async def checkins_between(session: AsyncSession, user_id: UUID, start: date, end: date) -> list[TaskCheckin]:
    rows = await session.scalars(
        select(TaskCheckin).where(
            TaskCheckin.user_id == user_id,
            TaskCheckin.checkin_date >= start,
            TaskCheckin.checkin_date <= end,
        )
    )
    return list(rows)


async def feedbacks_between(session: AsyncSession, user_id: UUID, start: date, end: date) -> list[HealthFeedbackRecord]:
    rows = await session.scalars(
        select(HealthFeedbackRecord).where(HealthFeedbackRecord.user_id == user_id)
    )
    return [row for row in rows if start <= row.recorded_at.date() <= end]


async def latest_summary(session: AsyncSession, user_id: UUID, plan_id: UUID) -> TrackingSummary | None:
    return await session.scalar(
        select(TrackingSummary)
        .where(TrackingSummary.user_id == user_id, TrackingSummary.plan_id == plan_id)
        .order_by(TrackingSummary.created_at.desc())
    )


async def adjustment_log(session: AsyncSession, plan_id: UUID) -> list[PlanAdjustmentRecord]:
    rows = await session.scalars(
        select(PlanAdjustmentRecord)
        .where(PlanAdjustmentRecord.plan_id == plan_id)
        .order_by(PlanAdjustmentRecord.created_at.desc())
    )
    return list(rows)
