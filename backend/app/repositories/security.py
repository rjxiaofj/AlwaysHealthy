from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.timeutil import as_utc
from app.db.models import SecurityAuditLog, SecurityIncident

LOGIN_ACTION = "login"
LOGIN_FAILED_RESULT = "fail"
BRUTEFORCE = "login_bruteforce"


async def count_login_failures(session: AsyncSession, account: str, since: datetime) -> int:
    total = await session.scalar(
        select(func.count())
        .select_from(SecurityAuditLog)
        .where(
            SecurityAuditLog.action == LOGIN_ACTION,
            SecurityAuditLog.result == LOGIN_FAILED_RESULT,
            SecurityAuditLog.resource_id == account,
            SecurityAuditLog.created_at >= since,
        )
    )
    return int(total or 0)


async def open_incident_for(
    session: AsyncSession, incident_type: str, account: str, since: datetime
) -> SecurityIncident | None:
    """同一个账号在窗口内只留一条未处置事件。

    description 以 account=<用户名> 开头，用前缀匹配而不是模糊匹配，
    避免 demo 与 demo2 这种前缀相同的账号互相吃掉对方的事件。
    """
    return await session.scalar(
        select(SecurityIncident).where(
            SecurityIncident.incident_type == incident_type,
            SecurityIncident.status == "open",
            SecurityIncident.occurred_at >= since,
            # autoescape 会把账号里的下划线与百分号转义掉，
            # 否则 demo_user_1 的前缀能匹配到 demoXuserY1，两个账号的事件会互相吞
            SecurityIncident.description.startswith(f"account={account} ", autoescape=True),
        )
    )


async def add_incident(
    session: AsyncSession,
    incident_type: str,
    severity: str,
    description: str,
    occurred_at: datetime,
) -> SecurityIncident:
    incident = SecurityIncident(
        incident_type=incident_type,
        severity=severity,
        description=description,
        status="open",
        occurred_at=occurred_at,
    )
    session.add(incident)
    return incident


async def incidents_of(session: AsyncSession, limit: int = 20) -> list[SecurityIncident]:
    rows = await session.scalars(
        select(SecurityIncident).order_by(SecurityIncident.occurred_at.desc()).limit(limit)
    )
    return list(rows)


async def incident_of(session: AsyncSession, incident_id: UUID) -> SecurityIncident | None:
    return await session.get(SecurityIncident, incident_id)


def as_dict(row: SecurityIncident) -> dict[str, object]:
    # sqlite 存不下时区：刚写的行是 aware、从库里读回的是 naive。统一转成带 +00:00 的
    # ISO 串，否则同一条事件在「处置响应」和「事件列表」里字符串长得不一样
    return {
        "id": str(row.id),
        "incident_type": row.incident_type,
        "severity": row.severity,
        "description": row.description,
        "status": row.status,
        "occurred_at": as_utc(row.occurred_at).isoformat() if row.occurred_at else None,
        "resolved_at": as_utc(row.resolved_at).isoformat() if row.resolved_at else None,
    }
