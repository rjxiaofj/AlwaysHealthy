from collections.abc import AsyncIterator
from uuid import UUID

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import Forbidden, Unauthorized
from app.core.security import decode_access_token
from app.db.models import User
from app.db.session import get_session
from app.repositories import health as repo

bearer = HTTPBearer(auto_error=False)


async def db_session() -> AsyncIterator[AsyncSession]:
    async for session in get_session():
        yield session


async def current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    session: AsyncSession = Depends(db_session),
) -> User:
    if credentials is None:
        raise Unauthorized("请先登录")
    payload = decode_access_token(credentials.credentials)
    user_id = payload.get("sub")
    if not user_id:
        raise Unauthorized("令牌缺少用户标识")
    user = await repo.get_user(session, UUID(user_id))
    if user is None or user.status != "active":
        raise Unauthorized("用户不存在或已停用")
    return user


async def admin_user(user: User = Depends(current_user)) -> User:
    if user.role != "admin":
        raise Forbidden("需要管理员权限")
    return user


def request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "")
