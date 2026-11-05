from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user, db_session
from app.core.response import ok
from app.db.models import User
from app.services import knowledge_service

router = APIRouter(tags=["knowledge"])


@router.get("/knowledge/sources")
async def list_sources(
    request: Request,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(db_session),
):
    return ok(request, await knowledge_service.list_sources(session))
