from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import admin_user, db_session, request_id
from app.core.response import ok, paged
from app.db.models import User
from app.schemas.admin import RolePatchIn, RuntimePatchIn, StatusPatchIn
from app.services import admin_service

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/overview")
async def overview(
    request: Request,
    user: User = Depends(admin_user),
    session: AsyncSession = Depends(db_session),
):
    return ok(request, await admin_service.overview(session))


@router.get("/users")
async def list_users(
    request: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    keyword: str | None = Query(default=None),
    role: str | None = Query(default=None),
    status: str | None = Query(default=None),
    user: User = Depends(admin_user),
    session: AsyncSession = Depends(db_session),
):
    items, total = await admin_service.list_users(
        session, page, page_size, keyword=keyword, role=role, status=status
    )
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
        session, actor=user, target_id=user_id, role=payload.role, request_id=request_id(request)
    )
    return ok(request, data, "角色已更新")


@router.patch("/users/{user_id}/status")
async def set_status(
    request: Request,
    user_id: UUID,
    payload: StatusPatchIn,
    user: User = Depends(admin_user),
    session: AsyncSession = Depends(db_session),
):
    data = await admin_service.set_status(
        session, actor=user, target_id=user_id, status=payload.status, request_id=request_id(request)
    )
    return ok(request, data, "账号状态已更新")


@router.delete("/users/{user_id}")
async def delete_user(
    request: Request,
    user_id: UUID,
    confirm_username: str = Query(...),
    user: User = Depends(admin_user),
    session: AsyncSession = Depends(db_session),
):
    await admin_service.delete_user(
        session,
        actor=user,
        target_id=user_id,
        confirm_username=confirm_username,
        request_id=request_id(request),
    )
    return ok(request, None, "账号已删除")


@router.get("/audit-logs")
async def list_audits(
    request: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    action: str | None = Query(default=None),
    actor_user_id: UUID | None = Query(default=None),
    result: str | None = Query(default=None),
    user: User = Depends(admin_user),
    session: AsyncSession = Depends(db_session),
):
    items, total = await admin_service.list_audits(
        session, page, page_size, action=action, actor_user_id=actor_user_id, result=result
    )
    return paged(request, items, total, page, page_size)


@router.get("/incidents")
async def list_incidents(
    request: Request,
    limit: int = Query(default=20, ge=1, le=100),
    status: str | None = Query(default=None),
    severity: str | None = Query(default=None),
    user: User = Depends(admin_user),
    session: AsyncSession = Depends(db_session),
):
    return ok(
        request,
        await admin_service.list_incidents(session, limit, status=status, severity=severity),
    )


@router.post("/incidents/{incident_id}/resolve")
async def resolve_incident(
    request: Request,
    incident_id: UUID,
    user: User = Depends(admin_user),
    session: AsyncSession = Depends(db_session),
):
    data = await admin_service.resolve_incident(
        session, actor=user, incident_id=incident_id, request_id=request_id(request)
    )
    return ok(request, data, "事件已处置")


@router.get("/runtime")
async def get_runtime(
    request: Request,
    user: User = Depends(admin_user),
):
    return ok(request, admin_service.get_runtime())


@router.patch("/runtime")
async def set_runtime(
    request: Request,
    payload: RuntimePatchIn,
    user: User = Depends(admin_user),
    session: AsyncSession = Depends(db_session),
):
    data = admin_service.set_runtime(
        actor=user, session=session, payload=payload, request_id=request_id(request)
    )
    await session.commit()
    return ok(request, data, "运行配置已更新")


@router.get("/agents")
async def list_agents(
    request: Request,
    user: User = Depends(admin_user),
):
    graph_service = getattr(request.app.state, "graph_service", None)
    return ok(request, admin_service.agent_status(graph_service))


@router.get("/workflow-stats")
async def workflow_stats(
    request: Request,
    user: User = Depends(admin_user),
    session: AsyncSession = Depends(db_session),
):
    return ok(request, await admin_service.workflow_stats(session))


@router.get("/knowledge")
async def knowledge_status(
    request: Request,
    user: User = Depends(admin_user),
):
    retriever = getattr(request.app.state, "retriever", None)
    return ok(request, admin_service.knowledge_status(retriever))
