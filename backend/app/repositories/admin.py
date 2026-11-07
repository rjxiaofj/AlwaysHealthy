from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import SecurityAuditLog, SecurityIncident, User


async def list_users(
    session: AsyncSession,
    page: int,
    page_size: int,
    *,
    keyword: str | None = None,
    role: str | None = None,
    status: str | None = None,
) -> tuple[list[User], int]:
    query = select(User)
    if keyword:
        query = query.where(User.username.ilike(f"%{keyword}%"))
    if role:
        query = query.where(User.role == role)
    if status:
        query = query.where(User.status == status)
    total = int(
        await session.scalar(select(func.count()).select_from(query.subquery())) or 0
    )
    rows = await session.scalars(
        query.order_by(User.created_at.asc(), User.username.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(rows), total


async def user_of(session: AsyncSession, user_id: UUID) -> User | None:
    return await session.get(User, user_id)


async def count_admins(session: AsyncSession) -> int:
    # 降权前必须确认还有别的 admin，否则库里一个管理员都不剩，后台再也进不去
    return int(
        await session.scalar(select(func.count()).select_from(User).where(User.role == "admin")) or 0
    )


async def list_audits(
    session: AsyncSession,
    page: int,
    page_size: int,
    *,
    action: str | None = None,
    actor_user_id: UUID | None = None,
    result: str | None = None,
) -> tuple[list[SecurityAuditLog], int]:
    query = select(SecurityAuditLog)
    if action:
        query = query.where(SecurityAuditLog.action == action)
    if actor_user_id:
        query = query.where(SecurityAuditLog.actor_user_id == actor_user_id)
    if result:
        query = query.where(SecurityAuditLog.result == result)
    total = int(
        await session.scalar(select(func.count()).select_from(query.subquery())) or 0
    )
    rows = await session.scalars(
        query.order_by(SecurityAuditLog.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(rows), total


async def analytics_counts(session: AsyncSession, since: datetime, top_actions: int = 8) -> dict:
    """管理后台可视化用的聚合数据。

    时间序列不在 SQL 里按天分组：SQLite 的 date() 与 Postgres 的 date() 对带时区的
    timestamptz 语义不同，同一份 SQL 会在两个库上切出不同的日界。这里只取原始时间戳，
    由服务层按业务时区归日，跨库行为一致。
    """
    from app.db.models import WorkflowRun

    by_role = {
        str(row[0]): int(row[1])
        for row in await session.execute(select(User.role, func.count()).group_by(User.role))
    }
    by_status = {
        str(row[0]): int(row[1])
        for row in await session.execute(select(User.status, func.count()).group_by(User.status))
    }
    new_user_times = list(
        await session.scalars(select(User.created_at).where(User.created_at >= since))
    )
    login_fail_times = list(
        await session.scalars(
            select(SecurityAuditLog.created_at).where(
                SecurityAuditLog.action == "login",
                SecurityAuditLog.result == "fail",
                SecurityAuditLog.created_at >= since,
            )
        )
    )
    top = [
        {"action": str(row[0]), "count": int(row[1])}
        for row in await session.execute(
            select(SecurityAuditLog.action, func.count().label("n"))
            .group_by(SecurityAuditLog.action)
            .order_by(func.count().desc(), SecurityAuditLog.action.asc())
            .limit(top_actions)
        )
    ]
    by_severity = {
        str(row[0] or "unknown"): int(row[1])
        for row in await session.execute(
            select(SecurityIncident.severity, func.count()).group_by(SecurityIncident.severity)
        )
    }
    workflow = {
        str(row[0]): int(row[1])
        for row in await session.execute(
            select(WorkflowRun.status, func.count()).group_by(WorkflowRun.status)
        )
    }
    return {
        "by_role": by_role,
        "by_status": by_status,
        "new_user_times": new_user_times,
        "login_fail_times": login_fail_times,
        "top_actions": top,
        "by_severity": by_severity,
        "workflow": workflow,
    }


async def overview_counts(session: AsyncSession, day_start: datetime) -> dict[str, int]:
    user_total = int(await session.scalar(select(func.count()).select_from(User)) or 0)
    admin_total = int(
        await session.scalar(select(func.count()).select_from(User).where(User.role == "admin")) or 0
    )
    open_incidents = int(
        await session.scalar(
            select(func.count()).select_from(SecurityIncident).where(SecurityIncident.status == "open")
        )
        or 0
    )
    login_fail_today = int(
        await session.scalar(
            select(func.count())
            .select_from(SecurityAuditLog)
            .where(
                SecurityAuditLog.action == "login",
                SecurityAuditLog.result == "fail",
                SecurityAuditLog.created_at >= day_start,
            )
        )
        or 0
    )
    new_users_today = int(
        await session.scalar(
            select(func.count()).select_from(User).where(User.created_at >= day_start)
        )
        or 0
    )
    return {
        "user_total": user_total,
        "admin_total": admin_total,
        "open_incidents": open_incidents,
        "login_fail_today": login_fail_today,
        "new_users_today": new_users_today,
    }
