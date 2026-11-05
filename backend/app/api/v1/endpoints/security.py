from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import admin_user, db_session
from app.core.response import ok
from app.db.models import User
from app.services import security_service

router = APIRouter(tags=["security"])


@router.get("/security/incidents")
async def list_incidents(
    request: Request,
    limit: int = 20,
    user: User = Depends(admin_user),
    session: AsyncSession = Depends(db_session),
):
    return ok(request, await security_service.list_incidents(session, max(1, min(limit, 100))))
