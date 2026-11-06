from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AdminUserOut(BaseModel):
    """管理列表的字段白名单，别把 User 整个 model_dump 出去。"""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    username: str
    email: str | None
    role: str
    status: str
    created_at: datetime
    last_login_at: datetime | None


class RolePatchIn(BaseModel):
    role: Literal["user", "admin"]
