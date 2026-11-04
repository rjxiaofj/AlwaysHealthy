from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import Conflict, IllegalPlan, NotFound
from app.db.models import (
    HealthPlan,
    HealthPlanVersion,
    PlanAdjustmentRecord,
    PlanTask,
    TaskCheckin,
)
from app.repositories import plan as repo

MAX_DURATION = 30
MIN_DURATION = 7


async def persist_draft(
    session: AsyncSession,
    user_id: UUID,
    draft: dict[str, Any],
    assessment_id: UUID | None,
) -> HealthPlan:
    duration = int(draft["duration_days"])
    if not MIN_DURATION <= duration <= MAX_DURATION:
        raise IllegalPlan("计划周期必须在 7 到 30 天之间")
    start = draft["start_date"] if isinstance(draft["start_date"], date) else date.fromisoformat(draft["start_date"])

    plan = HealthPlan(
        user_id=user_id,
        assessment_id=assessment_id,
        title=draft["title"],
        duration_days=duration,
        start_date=start,
        end_date=start + timedelta(days=duration - 1),
        status="pending_review",
    )
    session.add(plan)
    await session.flush()

    version = HealthPlanVersion(
        plan_id=plan.id,
        version_no=1,
        change_reason="首次生成",
        plan_content={
            "goal": draft.get("goal", ""),
            "cautions": draft.get("cautions", []),
            "basis": draft.get("basis", []),
        },
        status="draft",
    )
    session.add(version)
    await session.flush()

    for item in draft.get("tasks", []):
        session.add(
            PlanTask(
                plan_version_id=version.id,
                title=item["title"],
                category=item.get("category", "lifestyle"),
                description=item.get("description"),
                scheduled_date=item["scheduled_date"],
                scheduled_time=item.get("scheduled_time"),
                frequency=item.get("frequency"),
                duration_minutes=item.get("duration_minutes"),
                completion_criteria=item["completion_criteria"],
                checkin_type=item.get("checkin_type", "boolean"),
            )
        )

    plan.current_version_id = version.id
    await session.commit()
    return plan


async def approve(session: AsyncSession, user_id: UUID, plan_id: UUID, version_id: UUID) -> HealthPlan:
    plan = await repo.plan_of(session, user_id, plan_id)
    if plan is None:
        raise NotFound("计划不存在")
    version = await repo.version_of(session, plan_id, version_id)
    if version is None:
        raise NotFound("计划版本不存在")
    if version.status not in ("draft", "pending_review"):
        raise Conflict("该版本已处理，不能重复确认")

    others = await session.scalars(
        select(HealthPlan).where(
            HealthPlan.user_id == user_id,
            HealthPlan.status == "active",
            HealthPlan.id != plan.id,
        )
    )
    for other in others:
        other.status = "superseded"

    if plan.current_version_id and plan.current_version_id != version.id:
        previous = await repo.version_of(session, plan.id, plan.current_version_id)
        if previous and previous.status == "active":
            previous.status = "superseded"

    now = datetime.now(UTC)
    version.status = "active"
    version.approved_at = now
    plan.current_version_id = version.id
    plan.status = "active"

    pending_adjust = await session.scalar(
        select(PlanAdjustmentRecord).where(
            PlanAdjustmentRecord.plan_id == plan.id,
            PlanAdjustmentRecord.new_version_id == version.id,
            PlanAdjustmentRecord.approval_status == "pending",
        )
    )
    if pending_adjust:
        pending_adjust.approval_status = "approved"
        pending_adjust.confirmed_at = now

    await session.commit()
    return plan


async def reject_version(session: AsyncSession, user_id: UUID, plan_id: UUID, version_id: UUID) -> None:
    plan = await repo.plan_of(session, user_id, plan_id)
    if plan is None:
        raise NotFound("计划不存在")
    version = await repo.version_of(session, plan_id, version_id)
    if version is None:
        raise NotFound("计划版本不存在")
    if version.status != "draft":
        raise Conflict("只有草稿版本可以拒绝")
    version.status = "cancelled"
    if plan.status == "pending_review":
        plan.status = "cancelled"
    await session.commit()


async def adjust(session: AsyncSession, user_id: UUID, plan_id: UUID, reason: str) -> HealthPlanVersion:
    plan = await repo.plan_of(session, user_id, plan_id)
    if plan is None:
        raise NotFound("计划不存在")
    if plan.status not in ("active", "pending_review"):
        raise Conflict("当前计划状态不允许调整")

    base = await repo.version_of(session, plan.id, plan.current_version_id) if plan.current_version_id else None
    version_no = await repo.next_version_no(session, plan.id)
    version = HealthPlanVersion(
        plan_id=plan.id,
        version_no=version_no,
        change_reason=reason,
        plan_content=base.plan_content if base else {},
        status="draft",
    )
    session.add(version)
    await session.flush()

    # 任务结构随版本复制，日期沿用当前周期，改期由后续调整接口处理
    if base:
        for task in await repo.tasks_of(session, base.id):
            session.add(
                PlanTask(
                    plan_version_id=version.id,
                    title=task.title,
                    category=task.category,
                    description=task.description,
                    scheduled_date=task.scheduled_date,
                    scheduled_time=task.scheduled_time,
                    frequency=task.frequency,
                    duration_minutes=task.duration_minutes,
                    completion_criteria=task.completion_criteria,
                    checkin_type=task.checkin_type,
                )
            )

    session.add(
        PlanAdjustmentRecord(
            plan_id=plan.id,
            old_version_id=base.id if base else None,
            new_version_id=version.id,
            adjustment_reason=reason,
            approval_status="pending",
        )
    )
    await session.commit()
    return version


async def revise_draft(
    session: AsyncSession,
    user_id: UUID,
    plan_id: UUID,
    draft: dict[str, Any],
    reason: str,
) -> HealthPlanVersion:
    """用户要求修改时生成新版本草稿，旧版本保持原状态，不覆盖历史。"""
    plan = await repo.plan_of(session, user_id, plan_id)
    if plan is None:
        raise NotFound("计划不存在")

    version_no = await repo.next_version_no(session, plan.id)
    version = HealthPlanVersion(
        plan_id=plan.id,
        version_no=version_no,
        change_reason=reason[:200],
        plan_content={
            "goal": draft.get("goal", ""),
            "cautions": draft.get("cautions", []),
            "basis": draft.get("basis", []),
        },
        status="draft",
    )
    session.add(version)
    await session.flush()

    for item in draft.get("tasks", []):
        session.add(
            PlanTask(
                plan_version_id=version.id,
                title=item["title"],
                category=item.get("category", "lifestyle"),
                description=item.get("description"),
                scheduled_date=item["scheduled_date"],
                scheduled_time=item.get("scheduled_time"),
                frequency=item.get("frequency"),
                duration_minutes=item.get("duration_minutes"),
                completion_criteria=item["completion_criteria"],
                checkin_type=item.get("checkin_type", "boolean"),
            )
        )
    await session.commit()
    return version


async def checkin(session: AsyncSession, user_id: UUID, task_id: UUID, payload) -> TaskCheckin:
    task = await repo.task_of(session, user_id, task_id)
    if task is None:
        raise NotFound("任务不存在")

    plan = await session.scalar(
        select(HealthPlan)
        .join(HealthPlanVersion, HealthPlanVersion.plan_id == HealthPlan.id)
        .where(HealthPlanVersion.id == task.plan_version_id, HealthPlan.user_id == user_id)
    )
    if plan is None or plan.status != "active" or plan.current_version_id != task.plan_version_id:
        raise Conflict("计划未生效或该任务属于历史版本，不能打卡")

    checkin_date = payload.checkin_date or date.today()
    if not plan.start_date <= checkin_date <= plan.end_date:
        raise IllegalPlan("打卡日期不在计划周期内")

    record = await repo.checkin_of(session, task_id, checkin_date)
    if record:
        # 同一天重复提交按更新处理，不新增记录
        record.status = payload.status
        record.feedback = payload.feedback
        record.checkin_at = datetime.now(UTC)
    else:
        record = TaskCheckin(
            task_id=task_id,
            user_id=user_id,
            status=payload.status,
            feedback=payload.feedback,
            checkin_date=checkin_date,
            idempotency_key=payload.idempotency_key,
        )
        session.add(record)
    task.status = payload.status
    await session.commit()
    return record


async def patch_task(session: AsyncSession, user_id: UUID, task_id: UUID, payload) -> PlanTask:
    task = await repo.task_of(session, user_id, task_id)
    if task is None:
        raise NotFound("任务不存在")
    if payload.scheduled_time is not None:
        task.scheduled_time = payload.scheduled_time
    if payload.reminder_enabled is not None:
        task.reminder_enabled = payload.reminder_enabled
    await session.commit()
    return task


async def close_expired(session: AsyncSession, user_id: UUID) -> None:
    expired = await session.scalars(
        select(HealthPlan).where(
            HealthPlan.user_id == user_id,
            HealthPlan.status == "active",
            HealthPlan.end_date < date.today(),
        )
    )
    changed = False
    for plan in expired:
        plan.status = "completed"
        changed = True
    if changed:
        await session.commit()


async def detail(session: AsyncSession, user_id: UUID, plan_id: UUID) -> dict[str, Any]:
    await close_expired(session, user_id)
    plan = await repo.plan_of(session, user_id, plan_id)
    if plan is None:
        raise NotFound("计划不存在")

    versions = await repo.versions_of(session, plan.id)
    tasks = await repo.tasks_of(session, plan.current_version_id) if plan.current_version_id else []
    checkins = await repo.checkins_between(session, user_id, plan.start_date, plan.end_date)
    status_map = {item.task_id: item.status for item in checkins}

    return {
        "id": plan.id,
        "title": plan.title,
        "duration_days": plan.duration_days,
        "start_date": plan.start_date,
        "end_date": plan.end_date,
        "status": plan.status,
        "current_version_id": plan.current_version_id,
        "assessment_id": plan.assessment_id,
        "created_at": plan.created_at,
        "tasks": [
            {
                "id": task.id,
                "title": task.title,
                "category": task.category,
                "description": task.description,
                "scheduled_date": task.scheduled_date,
                "scheduled_time": task.scheduled_time,
                "frequency": task.frequency,
                "duration_minutes": task.duration_minutes,
                "completion_criteria": task.completion_criteria,
                "checkin_type": task.checkin_type,
                "status": task.status,
                "checkin_status": status_map.get(task.id),
            }
            for task in tasks
        ],
        "versions": [
            {
                "id": version.id,
                "version_no": version.version_no,
                "status": version.status,
                "change_reason": version.change_reason,
                "created_at": version.created_at,
                "content": version.plan_content,
            }
            for version in versions
        ],
    }


async def list_plans(session: AsyncSession, user_id: UUID) -> list[dict[str, Any]]:
    await close_expired(session, user_id)
    plans = await repo.plans_of(session, user_id)
    return [
        {
            "id": plan.id,
            "title": plan.title,
            "duration_days": plan.duration_days,
            "start_date": plan.start_date,
            "end_date": plan.end_date,
            "status": plan.status,
            "created_at": plan.created_at,
            "current_version_id": plan.current_version_id,
        }
        for plan in plans
    ]
