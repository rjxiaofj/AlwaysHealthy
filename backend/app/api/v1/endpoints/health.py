from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import admin_user, db_session
from app.core.config import get_settings
from app.core.response import ok
from app.db.models import User
from app.tools.knowledge_base import retriever as retriever_module

router = APIRouter(tags=["health"])


@router.get("/health/live")
async def live():
    return {"status": "ok"}


@router.get("/health/ready")
async def ready(session: AsyncSession = Depends(db_session)):
    checks = {"database": "down", "knowledge": "down"}
    try:
        await session.execute(text("SELECT 1"))
        checks["database"] = "up"
    except Exception:
        return JSONResponse(status_code=503, content={"status": "degraded", "checks": checks})

    retriever = None
    try:
        retriever = retriever_module.get_retriever()
        checks["knowledge"] = "up" if getattr(retriever, "size", 0) > 0 else "empty"
    except Exception:
        checks["knowledge"] = "down"

    status_code = 200 if checks["database"] == "up" and checks["knowledge"] == "up" else 503
    return JSONResponse(status_code=status_code, content={"status": "ok" if status_code == 200 else "degraded", "checks": checks})


@router.get("/health/services")
async def services(request: Request, user: User = Depends(admin_user)):
    settings = get_settings()
    return ok(
        request,
        {
            "checkpointer": settings.checkpointer,
            "embedding_backend": settings.embedding_backend,
            "llm_configured": bool(settings.llm_api_key),
            "graph_loaded": getattr(request.app.state, "graph_service", None) is not None,
        },
    )
