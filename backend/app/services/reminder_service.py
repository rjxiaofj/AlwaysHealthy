from datetime import date
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Notification
from app.repositories import chat as chat_repo
from app.repositories import plan as plan_repo
from app.services import tracking_service


async def sync(session: AsyncSession, user_id: UUID) -> None:
    """提醒在用户访问时生成，平台没有后台调度进程。"""
    plan = await plan_repo.active_plan(session, user_id)
    if plan is None or plan.current_version_id is None:
        return

    today = date.today()
    tasks = await plan_repo.tasks_of(session, plan.current_version_id, today, today)
    checkins = await plan_repo.checkins_between(session, user_id, today, today)
    checked = {item.task_id for item in checkins}

    created: list[Notification] = []
    for task in tasks:
        if task.id in checked:
            continue
        # 任务级提醒可以关掉，计划级的两条提醒不受单个开关影响
        if not task.reminder_enabled:
            continue
        key = f"task_due:{task.id}:{today.isoformat()}"
        if await chat_repo.notification_by_dedup(session, key):
            continue
        created.append(
            Notification(
                user_id=user_id,
                notification_type="task_due",
                title="今日任务待完成",
                content=f"{task.title}，完成标准：{task.completion_criteria}",
                related_object_id=task.id,
                dedup_key=key,
            )
        )

    overdue = await tracking_service.unfinished_before(session, user_id, today)
    if overdue:
        key = f"task_overdue:{plan.id}:{today.isoformat()}"
        if not await chat_repo.notification_by_dedup(session, key):
            created.append(
                Notification(
                    user_id=user_id,
                    notification_type="task_overdue",
                    title="有任务未记录",
                    content=f"本周期已有 {overdue} 项任务没有打卡记录，可以在计划页补充或说明原因",
                    related_object_id=plan.id,
                    dedup_key=key,
                )
            )

    if (plan.end_date - today).days <= 1:
        key = f"plan_end:{plan.id}:{today.isoformat()}"
        if not await chat_repo.notification_by_dedup(session, key):
            created.append(
                Notification(
                    user_id=user_id,
                    notification_type="plan_end",
                    title="计划即将结束",
                    content="当前计划周期即将结束，是否重新评估由你决定，系统不会自动创建",
                    related_object_id=plan.id,
                    dedup_key=key,
                )
            )

    for item in created:
        session.add(item)
    if created:
        await session.commit()


async def list_reminders(session: AsyncSession, user_id: UUID) -> list[dict]:
    await sync(session, user_id)
    rows = await chat_repo.notifications_of(session, user_id)
    return [
        {
            "id": row.id,
            "notification_type": row.notification_type,
            "title": row.title,
            "content": row.content,
            "related_object_id": row.related_object_id,
            "read_at": row.read_at,
            "created_at": row.created_at,
        }
        for row in rows
    ]
