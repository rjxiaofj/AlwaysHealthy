from datetime import UTC, datetime, time as dtime, timedelta
from typing import NoReturn
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import runtime_config
from app.core.exceptions import AppError, Conflict, NotFound
from app.core.timeutil import BUSINESS_TZ, as_utc
from app.db.models import User
from app.repositories import admin as admin_repo
from app.repositories import chat as chat_repo
from app.repositories import security as security_repo
from app.schemas.admin import AdminUserOut

# 后台可管理的 Agent 清单：名字取自 app/agents/ 与 app/graph/main_graph.py 的节点注册，
# 这里只做状态展示，不加载或执行任何 agent 逻辑
AGENT_NAMES = [
    "supervisor",
    "emergency_router",
    "emergency_response",
    "data_collector",
    "profile_validator",
    "risk_assessment",
    "intervention",
    "plan",
    "health_tracking",
    "report",
]


def _audit_dict(row) -> dict:
    return {
        "id": str(row.id),
        "actor_user_id": str(row.actor_user_id) if row.actor_user_id else None,
        "action": row.action,
        "resource_type": row.resource_type,
        "resource_id": row.resource_id,
        "result": row.result,
        "request_id": row.request_id,
        "created_at": as_utc(row.created_at).isoformat(),
    }


async def list_users(
    session: AsyncSession,
    page: int,
    page_size: int,
    *,
    keyword: str | None = None,
    role: str | None = None,
    status: str | None = None,
) -> tuple[list[dict], int]:
    rows, total = await admin_repo.list_users(
        session, page, page_size, keyword=keyword, role=role, status=status
    )
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
        return AdminUserOut.model_validate(target).model_dump(mode="json")
    if target.role == "admin" and role == "user" and await admin_repo.count_admins(session) <= 1:
        await _reject(session, actor=actor, action=action, resource_type=resource_type,
                      resource_id=resource_id, request_id=request_id, error=Conflict("至少需要保留一个管理员"))

    target.role = role
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


async def set_status(
    session: AsyncSession,
    *,
    actor: User,
    target_id: UUID,
    status: str,
    request_id: str,
) -> dict:
    target = await admin_repo.user_of(session, target_id)
    action, resource_type, resource_id = "update_user_status", "user", str(target_id)
    if target is None:
        await _reject(session, actor=actor, action=action, resource_type=resource_type,
                      resource_id=resource_id, request_id=request_id, error=NotFound("账号不存在"))
    if target.id == actor.id:
        await _reject(session, actor=actor, action=action, resource_type=resource_type,
                      resource_id=resource_id, request_id=request_id, error=Conflict("不能停用自己的账号"))
    if target.status == status:
        return AdminUserOut.model_validate(target).model_dump(mode="json")

    target.status = status
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


async def delete_user(
    session: AsyncSession,
    *,
    actor: User,
    target_id: UUID,
    confirm_username: str,
    request_id: str,
) -> None:
    target = await admin_repo.user_of(session, target_id)
    action, resource_type, resource_id = "delete_user", "user", str(target_id)
    if target is None:
        await _reject(session, actor=actor, action=action, resource_type=resource_type,
                      resource_id=resource_id, request_id=request_id, error=NotFound("账号不存在"))
    if target.id == actor.id:
        await _reject(session, actor=actor, action=action, resource_type=resource_type,
                      resource_id=resource_id, request_id=request_id, error=Conflict("不能删除自己的账号"))
    if target.role == "admin" and await admin_repo.count_admins(session) <= 1:
        await _reject(session, actor=actor, action=action, resource_type=resource_type,
                      resource_id=resource_id, request_id=request_id, error=Conflict("至少需要保留一个管理员"))
    if confirm_username != target.username:
        await _reject(session, actor=actor, action=action, resource_type=resource_type,
                      resource_id=resource_id, request_id=request_id, error=Conflict("确认用户名不匹配，未删除"))

    # 硬删除：级联删掉该用户所有数据（外键 ondelete=CASCADE 已在模型里定义）
    await session.execute(delete(User).where(User.id == target_id))
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


async def list_audits(
    session: AsyncSession,
    page: int,
    page_size: int,
    *,
    action: str | None = None,
    actor_user_id: UUID | None = None,
    result: str | None = None,
) -> tuple[list[dict], int]:
    rows, total = await admin_repo.list_audits(
        session, page, page_size, action=action, actor_user_id=actor_user_id, result=result
    )
    return [_audit_dict(row) for row in rows], total


async def list_incidents(
    session: AsyncSession,
    limit: int,
    *,
    status: str | None = None,
    severity: str | None = None,
) -> list[dict]:
    rows = await security_repo.incidents_of(session, limit, status=status, severity=severity)
    return [security_repo.as_dict(row) for row in rows]


async def overview(session: AsyncSession) -> dict:
    now = datetime.now(UTC)
    day_start_utc = datetime.combine(
        as_utc(now).astimezone(BUSINESS_TZ).date(), dtime.min
    ).astimezone(UTC)
    return await admin_repo.overview_counts(session, day_start_utc)


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


def get_runtime() -> dict:
    return runtime_config.snapshot()


def set_runtime(*, actor: User, session: AsyncSession, payload, request_id: str) -> dict:
    changes: list[str] = []
    for field in ("llm_model", "llm_api_key", "embedding_backend"):
        value = getattr(payload, field)
        if value is not None:
            runtime_config.set_and_persist(field, value)
            changes.append(field)
    if changes:
        # 模型参数是敏感配置，审计只记「改了哪些字段」，绝不记 key 明文
        chat_repo.audit(
            session,
            actor_user_id=actor.id,
            action="update_runtime_config",
            resource_type="runtime_config",
            resource_id=",".join(changes),
            result="success",
            request_id=request_id,
        )
    return runtime_config.snapshot()


def agent_status(graph_service) -> list[dict]:
    """返回 Agent 清单的加载状态。graph_service 是运行时实例，存在即视为工作流已加载。"""
    loaded = graph_service is not None
    return [
        {"name": name, "loaded": loaded}
        for name in AGENT_NAMES
    ]


async def workflow_stats(session: AsyncSession) -> dict:
    from app.db.models import WorkflowRun

    rows = await session.execute(select(WorkflowRun.status))
    statuses = [row[0] for row in rows]
    return {s: statuses.count(s) for s in ("running", "waiting_user", "cancelled", "failed", "completed")}


def knowledge_status(retriever) -> dict:
    return {
        "chunks": getattr(retriever, "size", 0),
    }
