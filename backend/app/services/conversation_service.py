import secrets
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFound
from app.db.models import Conversation, ConversationMessage
from app.repositories import chat as repo


async def create(session: AsyncSession, user_id: UUID, title: str | None) -> Conversation:
    conversation = Conversation(
        user_id=user_id,
        thread_id=f"th_{secrets.token_hex(12)}",
        title=title or "新的健康对话",
    )
    session.add(conversation)
    await session.commit()
    return conversation


async def list_conversations(session: AsyncSession, user_id: UUID) -> list[dict]:
    rows = await repo.conversations_of(session, user_id)
    payload = []
    for row in rows:
        messages = await repo.last_messages(session, row.id, 1)
        payload.append(
            {
                "id": row.id,
                "title": row.title,
                "status": row.status,
                "created_at": row.created_at,
                "updated_at": row.updated_at,
                "last_message": messages[-1].content[:60] if messages else None,
            }
        )
    return payload


async def get_conversation(session: AsyncSession, user_id: UUID, conversation_id: UUID) -> Conversation:
    conversation = await repo.conversation_of(session, user_id, conversation_id)
    if conversation is None:
        raise NotFound("会话不存在")
    return conversation


async def messages(session: AsyncSession, user_id: UUID, conversation_id: UUID) -> list[dict]:
    await get_conversation(session, user_id, conversation_id)
    rows = await repo.messages_of(session, conversation_id, 200)
    return [
        {
            "id": row.id,
            "role": row.role,
            "content": row.content,
            "message_type": row.message_type,
            "meta": row.meta,
            "created_at": row.created_at,
        }
        for row in rows
    ]


async def add_message(
    session: AsyncSession,
    conversation: Conversation,
    role: str,
    content: str,
    message_type: str = "text",
    meta: dict | None = None,
) -> ConversationMessage:
    message = ConversationMessage(
        conversation_id=conversation.id,
        user_id=conversation.user_id,
        role=role,
        content=content,
        message_type=message_type,
        meta=meta or {},
    )
    session.add(message)
    await session.flush()
    return message
