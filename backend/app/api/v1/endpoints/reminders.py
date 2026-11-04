from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user, db_session
from app.core.exceptions import NotFound
from app.core.response import ok
from app.db.models import Notification, User
from app.services import reminder_service

router = APIRouter(tags=["reminder"])


@router.get("/reminders")
async def list_reminders(
    request: Request,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(db_session),
):
    return ok(request, await reminder_service.list_reminders(session, user.id))


@router.post("/reminders/{reminder_id}/read")
async def read_reminder(
    reminder_id: UUID,
    request: Request,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(db_session),
):
    target = await session.get(Notification, reminder_id)
    if target is None or target.user_id != user.id:
        raise NotFound("提醒不存在")
    if target.read_at is None:
        target.read_at = datetime.now(UTC)
        await session.commit()
    return ok(request, None, "已标记已读")
