from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user, db_session
from app.core.response import ok
from app.db.models import User
from app.schemas.chat import ConsentIn
from app.services import consent_service

router = APIRouter(tags=["consent"])


@router.post("/consents")
async def grant_consent(
    request: Request,
    payload: ConsentIn,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(db_session),
):
    row = await consent_service.record(session, user.id, payload)
    return ok(request, {"id": str(row.id), "consent_status": row.consent_status})


@router.get("/consents")
async def list_consents(
    request: Request,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(db_session),
):
    return ok(request, await consent_service.list_records(session, user.id))
