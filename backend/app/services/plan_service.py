from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.timeutil import business_today
from app.core.exceptions import Conflict, IllegalPlan, InvalidHealthData, NotFound
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
                reminder_enabled=True,
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
        # 计划被顶替时版本状态要一起收敛，否则详情页会显示一个已失效的 active 版本
        if other.current_version_id:
            stale = await repo.version_of(session, other.id, other.current_version_id)
            if stale and stale.status == "active":
                stale.status = "superseded"

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


async def reject_version(session: AsyncSession, user_id: UUID, plan_id: UUID, version_id: UUID) -> str:
    """否掉一个草稿版本。两种来源不同处理：

    初次计划的草稿被否，计划本身也不成立，直接取消；调整产生的草稿被否，
    只作废这一版，计划继续用原来的生效版本，用户不会因为试了一次调整丢掉整个计划。
    """
    plan = await repo.plan_of(session, user_id, plan_id)
    if plan is None:
        raise NotFound("计划不存在")
    version = await repo.version_of(session, plan_id, version_id)
    if version is None:
        raise NotFound("计划版本不存在")
    if version.status != "draft":
        raise Conflict("只有草稿版本可以拒绝")

    pending_adjust = await session.scalar(
        select(PlanAdjustmentRecord).where(
            PlanAdjustmentRecord.plan_id == plan.id,
            PlanAdjustmentRecord.new_version_id == version.id,
            PlanAdjustmentRecord.approval_status == "pending",
        )
    )
    version.status = "cancelled"
    if pending_adjust:
        pending_adjust.approval_status = "rejected"
        pending_adjust.confirmed_at = datetime.now(UTC)
        await session.commit()
        return "调整已作废，计划仍是原来的版本"

    if plan.status == "pending_review":
        plan.status = "cancelled"
    await session.commit()
    return "计划已取消"


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
                    # 沿用原任务的开关，调整版本不该把用户关掉的提醒又打开
                    reminder_enabled=task.reminder_enabled,
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


async def shift(
    session: AsyncSession,
    user_id: UUID,
    plan_id: UUID,
    new_start: date,
    reason: str,
) -> HealthPlanVersion:
    """整体平移计划日期。只在计划没开始、当前版本没打卡时允许。"""
    plan = await repo.plan_of(session, user_id, plan_id)
    if plan is None:
        raise NotFound("计划不存在")
    if plan.status not in ("active", "pending_review"):
        raise Conflict("当前计划状态不允许改期")

    today = business_today()
    if new_start < today:
        raise InvalidHealthData("新的开始日期不能早于今天")
    if plan.start_date < today:
        # 已经开始就有打卡和已完成任务，整体挪会把这些记录对到不存在的任务上
        raise Conflict("计划已经开始，不能整体改期，请逐条调整任务日期")

    delta = (new_start - plan.start_date).days
    if delta == 0:
        raise InvalidHealthData("新的开始日期与当前一致")

    base = await repo.version_of(session, plan.id, plan.current_version_id) if plan.current_version_id else None
    if base is not None and await repo.checkin_count_of_version(session, base.id) > 0:
        raise Conflict("当前版本已有打卡记录，不能整体改期")

    note = reason.strip()[:200] if reason and reason.strip() else f"整体改期 {delta} 天"
    version_no = await repo.next_version_no(session, plan.id)
    version = HealthPlanVersion(
        plan_id=plan.id,
        version_no=version_no,
        change_reason=note,
        plan_content=base.plan_content if base else {},
        status="active",
    )
    session.add(version)
    await session.flush()

    if base:
        for task in await repo.tasks_of(session, base.id):
            session.add(
                PlanTask(
                    plan_version_id=version.id,
                    title=task.title,
                    category=task.category,
                    description=task.description,
                    scheduled_date=task.scheduled_date + timedelta(days=delta),
                    scheduled_time=task.scheduled_time,
                    frequency=task.frequency,
                    duration_minutes=task.duration_minutes,
                    completion_criteria=task.completion_criteria,
                    checkin_type=task.checkin_type,
                    # 沿用原任务的开关，调整版本不该把用户关掉的提醒又打开
                    reminder_enabled=task.reminder_enabled,
                )
            )
        base.status = "superseded"

    plan.start_date = new_start
    plan.end_date = plan.end_date + timedelta(days=delta)
    plan.current_version_id = version.id

    session.add(
        PlanAdjustmentRecord(
            plan_id=plan.id,
            old_version_id=base.id if base else None,
            new_version_id=version.id,
            adjustment_reason=note,
            approval_status="approved",
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
                reminder_enabled=True,
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

    checkin_date = payload.checkin_date or business_today()
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
    # 改日期要连带校验版本与周期，先把任务连同计划取出来，只改时间与开关时也用同一份
    found = await repo.task_with_plan(session, user_id, task_id)
    if found is None:
        raise NotFound("任务不存在")
    task, plan, version = found
    if payload.scheduled_date is not None and payload.scheduled_date != task.scheduled_date:
        if plan.current_version_id != version.id:
            raise Conflict("旧版本任务不能再调整，请到当前版本操作")
        if plan.status not in ("active", "pending_review"):
            raise Conflict("当前计划状态不允许调整任务")
        if payload.scheduled_date < business_today():
            raise InvalidHealthData("不能把任务改到已经过去的日期")
        if not plan.start_date <= payload.scheduled_date <= plan.end_date:
            raise InvalidHealthData("任务日期要落在计划周期内")
        if await repo.checkin_count_of_task(session, task.id) > 0:
            # 打卡按任务 id 加打卡日期唯一，日期挪走会让已完成记录对到一个空日子上
            raise Conflict("任务已有打卡记录，不能再改日期")
        task.scheduled_date = payload.scheduled_date
    # 时间允许清空：字段不出现才是「不改」，显式传 null 表示把时间去掉。
    # 用 is not None 判断的话，清空请求会被当成没传，任务时间永远删不掉
    if "scheduled_time" in payload.model_fields_set:
        task.scheduled_time = payload.scheduled_time
    if payload.reminder_enabled is not None:
        task.reminder_enabled = payload.reminder_enabled
    await session.commit()
    return task


async def cancel(session: AsyncSession, user_id: UUID, plan_id: UUID) -> None:
    """取消计划。只改计划状态，任务与打卡记录都留着，历史还能查。"""
    plan = await repo.plan_of(session, user_id, plan_id)
    if plan is None:
        raise NotFound("计划不存在")
    if plan.status in ("completed", "superseded"):
        raise Conflict("该计划已结束")
    plan.status = "cancelled"
    await session.commit()


async def close_expired(session: AsyncSession, user_id: UUID) -> None:
    expired = await session.scalars(
        select(HealthPlan).where(
            HealthPlan.user_id == user_id,
            HealthPlan.status == "active",
            HealthPlan.end_date < business_today(),
        )
    )
    changed = False
    for plan in expired:
        plan.status = "completed"
        changed = True
    if changed:
        await session.commit()


async def remove_draft_task(
    session: AsyncSession,
    user_id: UUID,
    plan_id: UUID,
    version_id: UUID,
    task_id: UUID,
) -> None:
    """在待确认版本里删掉一条任务。

    调整版本沿用原任务结构，用户说「任务太多」只能靠删。删的是草稿里的新行，
    原版本任务与打卡都不动，所以不会影响已经完成的记录。
    """
    plan = await repo.plan_of(session, user_id, plan_id)
    if plan is None:
        raise NotFound("计划不存在")
    version = await repo.version_of(session, plan.id, version_id)
    if version is None:
        raise NotFound("计划版本不存在")
    if version.status != "draft":
        raise Conflict("只有待确认的版本可以删任务")

    tasks = await repo.tasks_of(session, version.id)
    target = next((item for item in tasks if item.id == task_id), None)
    if target is None:
        raise NotFound("任务不存在")
    if len(tasks) <= 1:
        raise Conflict("至少保留一项任务，否则确认后计划没有内容")

    await session.delete(target)
    await session.commit()


async def _approved_adjustment(session: AsyncSession, plan: HealthPlan) -> PlanAdjustmentRecord | None:
    """当前版本由调整产生且已生效时返回那条记录。改期也会换版本，但改期不写调整记录。"""
    if plan.current_version_id is None:
        return None
    for record in await repo.adjustment_log(session, plan.id):
        if record.new_version_id == plan.current_version_id and record.approval_status == "approved":
            return record
    return None


async def submit_adjustment_feedback(
    session: AsyncSession,
    user_id: UUID,
    plan_id: UUID,
    version_id: UUID,
    feedback: str,
) -> dict[str, Any]:
    """调整生效后收一句用户反馈。

    只收当前版本，历史调整不再回头补，否则同一条记录会混进不同时期的判断。
    同一条记录重复提交直接覆盖，不追加。
    """
    plan = await repo.plan_of(session, user_id, plan_id)
    if plan is None:
        raise NotFound("计划不存在")
    if plan.current_version_id != version_id:
        raise Conflict("只能对当前生效的版本反馈")

    record = await _approved_adjustment(session, plan)
    if record is None:
        raise Conflict("这个版本不是调整产生的，没有可反馈的记录")

    text = feedback.strip()
    if len(text) < 2:
        raise InvalidHealthData("反馈内容太短")
    record.user_feedback = text[:200]
    await session.commit()
    return {
        "version_id": record.new_version_id,
        "feedback": record.user_feedback,
    }


async def detail(session: AsyncSession, user_id: UUID, plan_id: UUID) -> dict[str, Any]:
    await close_expired(session, user_id)
    plan = await repo.plan_of(session, user_id, plan_id)
    if plan is None:
        raise NotFound("计划不存在")

    versions = await repo.versions_of(session, plan.id)
    tasks = await repo.tasks_of(session, plan.current_version_id) if plan.current_version_id else []
    draft = next((item for item in versions if item.status == "draft"), None)
    draft_tasks = await repo.tasks_of(session, draft.id) if draft else []
    checkins = await repo.checkins_between(session, user_id, plan.start_date, plan.end_date)
    status_map = {item.task_id: item.status for item in checkins}
    adjustment_record = await _approved_adjustment(session, plan)
    adjustment = (
        {
            "version_id": adjustment_record.new_version_id,
            "reason": adjustment_record.adjustment_reason,
            "status": adjustment_record.approval_status,
            "created_at": adjustment_record.created_at,
            "feedback": adjustment_record.user_feedback,
        }
        if adjustment_record
        else None
    )

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
        "adjustment": adjustment,
        "pending_version": (
            {
                "id": draft.id,
                "version_no": draft.version_no,
                "change_reason": draft.change_reason,
                "tasks": [
                    {
                        "id": task.id,
                        "title": task.title,
                        "scheduled_date": task.scheduled_date,
                        "scheduled_time": task.scheduled_time,
                        "duration_minutes": task.duration_minutes,
                    }
                    for task in draft_tasks
                ],
            }
            if draft
            else None
        ),
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
                "reminder_enabled": task.reminder_enabled,
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
