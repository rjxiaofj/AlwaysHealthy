from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.timeutil import business_now, business_today
from app.db.models import Notification
from app.repositories import chat as chat_repo
from app.repositories import plan as plan_repo
from app.services import tracking_service


def _time_passed(scheduled_time: str | None, now) -> bool:
    """任务没有设定时间，或当前时刻已经过了设定时间，才值得催「待完成」。

    早上六点就把「晚上八点半记录饮食」当成待完成催，既不准也烦人。scheduled_time
    是 HH:MM 字符串，与 business_now 的东八区时刻比较。
    """
    if not scheduled_time:
        return True
    try:
        hour, minute = (int(part) for part in scheduled_time.split(":"))
    except (ValueError, AttributeError):
        return True
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return True
    return now.hour > hour or (now.hour == hour and now.minute >= minute)


async def sync(session: AsyncSession, user_id: UUID) -> None:
    """提醒在用户访问时生成，平台没有后台调度进程。"""
    plan = await plan_repo.active_plan(session, user_id)
    if plan is None or plan.current_version_id is None:
        return

    today = business_today()
    now = business_now()
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
        # 还没到设定时间不催：晚上八点半的记录，早上六点不该当作「待完成」顶上来
        if not _time_passed(task.scheduled_time, now):
            continue
        key = f"task_due:{task.id}:{today.isoformat()}"
        if await chat_repo.notification_by_dedup(session, key):
            continue
        time_hint = f"（设定时间 {task.scheduled_time}）" if task.scheduled_time else ""
        created.append(
            Notification(
                user_id=user_id,
                notification_type="task_due",
                title="今日任务待完成",
                content=f"{task.title}{time_hint}，完成标准：{task.completion_criteria}",
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

    cleared = await chat_repo.unread_task_reminders(session, user_id, checked, today)
    for row in cleared:
        # 任务已完成，待完成提醒不再留在未读里；保留行，提醒页还能查到这条通知
        row.read_at = datetime.now(UTC)

    for item in created:
        session.add(item)
    if created or cleared:
        try:
            await session.commit()
        except IntegrityError:
            # 两个访问同时进来时，另一边可能已经写入同一批 dedup_key，放弃本次写入即可
            await session.rollback()


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
