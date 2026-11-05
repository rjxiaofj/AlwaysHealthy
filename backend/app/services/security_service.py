from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.repositories import security as security_repo

log = get_logger(__name__)

LOGIN_FAILURE_WINDOW = timedelta(minutes=15)
LOGIN_FAILURE_THRESHOLD = 5


async def note_login_failure(session: AsyncSession, account: str) -> None:
    """登录失败后判断要不要记一条安全事件。

    连着错密码是最明确的一种攻击信号，越权 404 之类噪声太大不适合做采集点。
    同一账号在窗口内只留一条未处置事件，避免暴力破解期间每失败一次就刷一行。
    这里不提交事务，调用方原本就要为审计记录提交一次。
    """
    now = datetime.now(UTC)
    since = now - LOGIN_FAILURE_WINDOW
    # 本次失败的审计还没提交，先 flush 出去，否则统计永远差一条，阈值一辈子触发不了
    await session.flush()
    failures = await security_repo.count_login_failures(session, account, since)
    if failures < LOGIN_FAILURE_THRESHOLD:
        return

    existing = await security_repo.open_incident_for(
        session, security_repo.BRUTEFORCE, account, since
    )
    if existing is not None:
        return

    # description 里只写账号与次数，不写密码、不写来源凭据
    await security_repo.add_incident(
        session,
        incident_type=security_repo.BRUTEFORCE,
        severity="medium",
        description=f"account={account} failures={failures} window={LOGIN_FAILURE_WINDOW.seconds // 60}min",
        occurred_at=now,
    )
    log.warning("login brute force detected account=%s failures=%s", account, failures)


async def list_incidents(session: AsyncSession, limit: int = 20) -> list[dict[str, Any]]:
    rows = await security_repo.incidents_of(session, limit)
    return [security_repo.as_dict(row) for row in rows]
