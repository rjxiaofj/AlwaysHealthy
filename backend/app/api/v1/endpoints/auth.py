from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user, db_session
from app.core.response import ok
from app.db.models import User
from app.schemas.health import LoginIn, RefreshIn, RegisterIn, UserOut
from app.schemas.chat import ConsentIn
from app.services import auth_service

router = APIRouter(tags=["auth"])


@router.post("/auth/register")
async def register(request: Request, payload: RegisterIn, session: AsyncSession = Depends(db_session)):
    tokens = await auth_service.register(session, payload)
    return ok(request, tokens.model_dump())


@router.post("/auth/login")
async def login(request: Request, payload: LoginIn, session: AsyncSession = Depends(db_session)):
    tokens = await auth_service.login(session, payload)
    return ok(request, tokens.model_dump())


@router.post("/auth/refresh")
async def refresh(request: Request, payload: RefreshIn, session: AsyncSession = Depends(db_session)):
    tokens = await auth_service.refresh(session, payload.refresh_token)
    return ok(request, tokens.model_dump())


@router.post("/auth/logout")
async def logout(request: Request, payload: RefreshIn, session: AsyncSession = Depends(db_session)):
    await auth_service.logout(session, payload.refresh_token)
    return ok(request, None, "已退出")


@router.get("/users/me")
async def me(request: Request, user: User = Depends(current_user)):
    return ok(request, UserOut.model_validate(user).model_dump(mode="json"))
