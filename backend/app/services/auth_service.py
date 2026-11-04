from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadCredentials, Unauthorized, UserExists
from app.core.security import (
    create_access_token,
    create_refresh_token,
    digest_token,
    hash_password,
    verify_password,
)
from app.core.timeutil import as_utc
from app.db.models import RefreshToken, User
from app.repositories import chat as chat_repo
from app.repositories import health as repo
from app.schemas.health import LoginIn, RegisterIn, TokenOut


async def _issue(session: AsyncSession, user: User) -> TokenOut:
    access, expires_in = create_access_token(str(user.id), user.role)
    raw_refresh, token_hash, expires_at = create_refresh_token()
    session.add(RefreshToken(user_id=user.id, token_hash=token_hash, expires_at=expires_at))
    await session.commit()
    return TokenOut(
        access_token=access,
        refresh_token=raw_refresh,
        expires_in=expires_in,
        user_id=user.id,
        username=user.username,
        role=user.role,
    )


async def register(session: AsyncSession, payload: RegisterIn) -> TokenOut:
    if await repo.get_user_by_username(session, payload.username):
        raise UserExists("用户名已被占用")
    user = User(
        username=payload.username,
        email=payload.email,
        password_hash=hash_password(payload.password),
    )
    session.add(user)
    await session.flush()
    return await _issue(session, user)


async def login(session: AsyncSession, payload: LoginIn, request_id: str | None = None) -> TokenOut:
    user = await repo.get_user_by_username(session, payload.username)
    # 用户不存在与密码错误返回同一错误，避免枚举账号
    if user is None or not verify_password(payload.password, user.password_hash):
        chat_repo.audit(
            session,
            actor_user_id=None,
            action="login",
            resource_type="user",
            resource_id=payload.username[:64],
            result="fail",
            request_id=request_id,
        )
        # 失败分支要单独提交，异常抛出后事务会被丢弃
        await session.commit()
        raise BadCredentials("用户名或密码不正确")
    if user.status != "active":
        raise Unauthorized("账号已停用")
    chat_repo.audit(
        session,
        actor_user_id=user.id,
        action="login",
        resource_type="user",
        resource_id=str(user.id),
        result="success",
        request_id=request_id,
    )
    user.last_login_at = datetime.now(UTC)
    return await _issue(session, user)


async def refresh(session: AsyncSession, raw_token: str, request_id: str | None = None) -> TokenOut:
    record = await repo.find_refresh_token(session, digest_token(raw_token))
    now = datetime.now(UTC)
    if record is None or record.revoked_at is not None or as_utc(record.expires_at) <= now:
        # 已轮换的令牌被再次使用通常意味着凭证泄露，留痕
        chat_repo.audit(
            session,
            actor_user_id=record.user_id if record else None,
            action="token_refresh",
            resource_type="refresh_token",
            resource_id=str(record.id) if record else None,
            result="fail",
            request_id=request_id,
        )
        await session.commit()
        raise Unauthorized("刷新令牌无效")
    user = await repo.get_user(session, record.user_id)
    if user is None or user.status != "active":
        raise Unauthorized("账号不可用")
    # 轮换：旧令牌立即失效，重复使用会被当成失效凭证
    record.revoked_at = now
    return await _issue(session, user)


async def logout(session: AsyncSession, raw_token: str, request_id: str | None = None) -> None:
    record = await repo.find_refresh_token(session, digest_token(raw_token))
    if record and record.revoked_at is None:
        record.revoked_at = datetime.now(UTC)
    chat_repo.audit(
        session,
        actor_user_id=record.user_id if record else None,
        action="logout",
        resource_type="refresh_token",
        resource_id=str(record.id) if record else None,
        result="success" if record else "ignored",
        request_id=request_id,
    )
    await session.commit()


async def current_user(session: AsyncSession, user_id: UUID) -> User:
    user = await repo.get_user(session, user_id)
    if user is None or user.status != "active":
        raise Unauthorized("用户不存在")
    return user
