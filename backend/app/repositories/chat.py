from datetime import UTC, date, datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    Conversation,
    ConversationMessage,
    EmergencyEvent,
    FileAsset,
    HealthReport,
    Notification,
    SecurityAuditLog,
    WorkflowRun,
)


async def conversation_of(session: AsyncSession, user_id: UUID, conversation_id: UUID) -> Conversation | None:
    return await session.scalar(
        select(Conversation).where(Conversation.id == conversation_id, Conversation.user_id == user_id)
    )


async def run_of(session: AsyncSession, user_id: UUID, run_id: UUID) -> WorkflowRun | None:
    return await session.scalar(select(WorkflowRun).where(WorkflowRun.id == run_id, WorkflowRun.user_id == user_id))


async def conversations_of(session: AsyncSession, user_id: UUID) -> list[Conversation]:
    rows = await session.scalars(
        select(Conversation).where(Conversation.user_id == user_id).order_by(Conversation.updated_at.desc())
    )
    return list(rows)


async def messages_of(session: AsyncSession, conversation_id: UUID, limit: int) -> list[ConversationMessage]:
    rows = await session.scalars(
        select(ConversationMessage)
        .where(ConversationMessage.conversation_id == conversation_id)
        .order_by(ConversationMessage.created_at.desc())
        .limit(limit)
    )
    return list(reversed(list(rows)))


async def last_messages(session: AsyncSession, conversation_id: UUID, limit: int) -> list[ConversationMessage]:
    return await messages_of(session, conversation_id, limit)


async def reports_of(session: AsyncSession, user_id: UUID) -> list[HealthReport]:
    rows = await session.scalars(
        select(HealthReport).where(HealthReport.user_id == user_id).order_by(HealthReport.created_at.desc())
    )
    return list(rows)


async def report_of_summary(session: AsyncSession, user_id: UUID, summary_id: UUID) -> HealthReport | None:
    return await session.scalar(
        select(HealthReport).where(
            HealthReport.user_id == user_id,
            HealthReport.tracking_summary_id == summary_id,
        )
    )


async def report_of(session: AsyncSession, user_id: UUID, report_id: UUID) -> HealthReport | None:
    return await session.scalar(
        select(HealthReport).where(HealthReport.id == report_id, HealthReport.user_id == user_id)
    )


async def notifications_of(session: AsyncSession, user_id: UUID) -> list[Notification]:
    rows = await session.scalars(
        select(Notification).where(Notification.user_id == user_id).order_by(Notification.created_at.desc()).limit(50)
    )
    return list(rows)


async def unread_task_reminders(
    session: AsyncSession, user_id: UUID, task_ids: set[UUID], day: date
) -> list[Notification]:
    """取今天已打卡任务对应的未读提醒。键按生成时的口径拼，不用模糊匹配以免误伤别的日期。"""
    if not task_ids:
        return []
    keys = [f"task_due:{task_id}:{day.isoformat()}" for task_id in task_ids]
    rows = await session.scalars(
        select(Notification).where(
            Notification.user_id == user_id,
            Notification.notification_type == "task_due",
            Notification.dedup_key.in_(keys),
            Notification.read_at.is_(None),
        )
    )
    return list(rows)


async def notification_by_dedup(session: AsyncSession, dedup_key: str) -> Notification | None:
    return await session.scalar(select(Notification).where(Notification.dedup_key == dedup_key))


async def files_of(session: AsyncSession, user_id: UUID) -> list[FileAsset]:
    rows = await session.scalars(
        select(FileAsset).where(FileAsset.user_id == user_id).order_by(FileAsset.created_at.desc())
    )
    return list(rows)


async def file_of(session: AsyncSession, user_id: UUID, file_id: UUID) -> FileAsset | None:
    return await session.scalar(select(FileAsset).where(FileAsset.id == file_id, FileAsset.user_id == user_id))


async def runs_of_conversation(session: AsyncSession, conversation_id: UUID) -> list[WorkflowRun]:
    rows = await session.scalars(
        select(WorkflowRun)
        .where(WorkflowRun.conversation_id == conversation_id)
        .order_by(WorkflowRun.started_at.desc())
    )
    return list(rows)


# 一个会话同时只允许一条活 run：checkpointer 按 conversation.thread_id 只存一份
# 断点，两条活 run 会互相把对方的状态接错
LIVE_RUN_STATUSES = ("running", "waiting_user")


async def cancel_live_runs(session: AsyncSession, conversation_id: UUID) -> int:
    """新一轮开始前，把同会话还活着的旧 run 全部收成 cancelled。

    LangGraph 的 checkpointer 按 conversation.thread_id 只存一份断点，同会话所有
    run 共用它。只收 waiting_user 不够：旧 run 仍在 running 时用户又发一条消息，
    它晚一步走到 interrupt 会把自己写成 waiting_user，可那时 checkpointer 里的
    断点已经属于新一轮，resume 守卫会放行，把新状态接到旧 run 上。

    条件更新只碰活状态，completed/failed/cancelled 这些终态留作审计。
    """
    result = await session.execute(
        update(WorkflowRun)
        .where(
            WorkflowRun.conversation_id == conversation_id,
            WorkflowRun.status.in_(LIVE_RUN_STATUSES),
        )
        .values(status="cancelled", completed_at=datetime.now(UTC), error_code="SUPERSEDED"),
        execution_options={"synchronize_session": False},
    )
    return result.rowcount or 0


async def cancel_run(session: AsyncSession, run_id: UUID, code: str) -> bool:
    """断连/前置校验失败时把仍挂在 running 的 run 收口，终态一律不覆盖。"""
    result = await session.execute(
        update(WorkflowRun)
        .where(WorkflowRun.id == run_id, WorkflowRun.status == "running")
        .values(status="cancelled", completed_at=datetime.now(UTC), error_code=code),
        execution_options={"synchronize_session": False},
    )
    return bool(result.rowcount)


async def claim_resume(session: AsyncSession, run_id: UUID) -> bool:
    """原子抢占确认权：waiting_user -> running，只有一条请求能拿到。

    两个标签页同时点同一张确认卡片时，两边各自 SELECT 看到的都是 waiting_user，
    Python 里的 `run.status != "waiting_user"` 判断挡不住。把状态转移下推成带
    条件的 UPDATE，用 rowcount 判定谁抢到，抢不到的不能往同一 thread 打第二次 resume。
    """
    result = await session.execute(
        update(WorkflowRun)
        .where(WorkflowRun.id == run_id, WorkflowRun.status == "waiting_user")
        .values(status="running"),
        execution_options={"synchronize_session": False},
    )
    return bool(result.rowcount)


async def emergency_events_of(session: AsyncSession, user_id: UUID, limit: int = 20) -> list[EmergencyEvent]:
    rows = await session.scalars(
        select(EmergencyEvent)
        .where(EmergencyEvent.user_id == user_id)
        .order_by(EmergencyEvent.triggered_at.desc())
        .limit(limit)
    )
    return list(rows)


def audit(
    session: AsyncSession,
    *,
    actor_user_id: UUID | None,
    action: str,
    resource_type: str,
    resource_id: str | None,
    result: str,
    request_id: str | None,
) -> None:
    session.add(
        SecurityAuditLog(
            actor_user_id=actor_user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            result=result,
            request_id=request_id,
        )
    )
