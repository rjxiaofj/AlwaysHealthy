from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import admin_user, db_session, request_id
from app.core.response import ok, paged
from app.db.models import User
from app.schemas.admin import RolePatchIn
from app.services import admin_service

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users")
async def list_users(
    request: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user: User = Depends(admin_user),
    session: AsyncSession = Depends(db_session),
):
    items, total = await admin_service.list_users(session, page, page_size)
    return paged(request, items, total, page, page_size)


@router.patch("/users/{user_id}/role")
async def set_role(
    request: Request,
    user_id: UUID,
    payload: RolePatchIn,
    user: User = Depends(admin_user),
    session: AsyncSession = Depends(db_session),
):
    data = await admin_service.set_role(
        session,
        actor=user,
        target_id=user_id,
        role=payload.role,
        request_id=request_id(request),
    )
    return ok(request, data, "角色已更新")


@router.post("/incidents/{incident_id}/resolve")
async def resolve_incident(
    request: Request,
    incident_id: UUID,
    user: User = Depends(admin_user),
    session: AsyncSession = Depends(db_session),
):
    data = await admin_service.resolve_incident(
        session,
        actor=user,
        incident_id=incident_id,
        request_id=request_id(request),
    )
    return ok(request, data, "事件已处置")
