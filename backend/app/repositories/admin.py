from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User


async def list_users(session: AsyncSession, page: int, page_size: int) -> tuple[list[User], int]:
    total = int(await session.scalar(select(func.count()).select_from(User)) or 0)
    rows = await session.scalars(
        select(User)
        .order_by(User.created_at.asc(), User.username.asc())
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
