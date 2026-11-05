from datetime import date
from uuid import UUID

from sqlalchemy import select
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


async def emergency_events_of(session: AsyncSession, user_id: UUID) -> list[EmergencyEvent]:
    rows = await session.scalars(
        select(EmergencyEvent).where(EmergencyEvent.user_id == user_id).order_by(EmergencyEvent.triggered_at.desc())
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
