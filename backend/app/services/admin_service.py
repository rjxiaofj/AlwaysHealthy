from datetime import UTC, datetime
from typing import NoReturn
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError, Conflict, NotFound
from app.db.models import User
from app.repositories import admin as admin_repo
from app.repositories import chat as chat_repo
from app.repositories import security as security_repo
from app.schemas.admin import AdminUserOut


async def list_users(session: AsyncSession, page: int, page_size: int) -> tuple[list[dict], int]:
    rows, total = await admin_repo.list_users(session, page, page_size)
    return [AdminUserOut.model_validate(row).model_dump(mode="json") for row in rows], total


async def _reject(
    session: AsyncSession,
    *,
    actor: User,
    action: str,
    resource_type: str,
    resource_id: str,
    request_id: str,
    error: AppError,
) -> NoReturn:
    """拒绝也要留痕。异常抛出后事务会被丢弃，所以审计必须先自己提交。"""
    chat_repo.audit(
        session,
        actor_user_id=actor.id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        result="fail",
        request_id=request_id,
    )
    await session.commit()
    raise error


async def set_role(
    session: AsyncSession,
    *,
    actor: User,
    target_id: UUID,
    role: str,
    request_id: str,
) -> dict:
    target = await admin_repo.user_of(session, target_id)
    action, resource_type, resource_id = "update_user_role", "user", str(target_id)
    if target is None:
        await _reject(session, actor=actor, action=action, resource_type=resource_type,
                      resource_id=resource_id, request_id=request_id, error=NotFound("账号不存在"))
    if target.id == actor.id:
        await _reject(session, actor=actor, action=action, resource_type=resource_type,
                      resource_id=resource_id, request_id=request_id, error=Conflict("不能修改自己的角色"))
    if target.role == role:
        # 没有状态变化就不写审计，也避免重复点按钮刷出一片记录
        return AdminUserOut.model_validate(target).model_dump(mode="json")
    if target.role == "admin" and role == "user" and await admin_repo.count_admins(session) <= 1:
        await _reject(session, actor=actor, action=action, resource_type=resource_type,
                      resource_id=resource_id, request_id=request_id, error=Conflict("至少需要保留一个管理员"))

    target.role = role
    # 响应先组装再提交，提交后不再回读 ORM 对象：异步会话里的隐式 IO 会报 MissingGreenlet
    payload = AdminUserOut.model_validate(target).model_dump(mode="json")
    chat_repo.audit(
        session,
        actor_user_id=actor.id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        result="success",
        request_id=request_id,
    )
    await session.commit()
    return payload


async def resolve_incident(
    session: AsyncSession,
    *,
    actor: User,
    incident_id: UUID,
    request_id: str,
) -> dict:
    incident = await security_repo.incident_of(session, incident_id)
    action, resource_type, resource_id = "resolve_incident", "security_incident", str(incident_id)
    if incident is None:
        await _reject(session, actor=actor, action=action, resource_type=resource_type,
                      resource_id=resource_id, request_id=request_id, error=NotFound("安全事件不存在"))
    if incident.status == "resolved":
        return security_repo.as_dict(incident)
    if incident.status != "open":
        await _reject(session, actor=actor, action=action, resource_type=resource_type,
                      resource_id=resource_id, request_id=request_id, error=Conflict("该事件状态不能处置"))

    incident.status = "resolved"
    incident.resolved_at = datetime.now(UTC)
    payload = security_repo.as_dict(incident)
    chat_repo.audit(
        session,
        actor_user_id=actor.id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        result="success",
        request_id=request_id,
    )
    await session.commit()
    return payload
