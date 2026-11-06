import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.v1.router import api_router, health_router
from app.core.config import get_settings
from app.core.exceptions import AppError
from app.core.logging import get_logger, setup_logging
from app.core import runtime_config
from app.db.checkpointer import close_checkpointer, get_checkpointer
from app.db.session import SessionLocal, init_models
from app.graph.deps import GraphDeps
from app.integrations.llm_client import get_llm
from app.services import knowledge_service
from app.services.graph_service import GraphService
from app.tools.knowledge_base.retriever import get_retriever

settings = get_settings()
log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    if settings.env == "dev":
        await init_models()

    # 后台在线改过的模型参数在这里覆盖进内存，重启后仍生效
    runtime_config.load_overrides()

    retriever = get_retriever()
    llm = get_llm()
    checkpointer = await get_checkpointer()
    deps = GraphDeps(
        session_factory=SessionLocal,
        retriever=retriever,
        llm=llm,
        use_llm=bool(settings.llm_api_key),
    )
    app.state.retriever = retriever
    app.state.llm = llm
    app.state.graph_service = GraphService(deps, checkpointer)
    async with SessionLocal() as session:
        synced = await knowledge_service.sync_sources(session)
    log.info(
        "app ready retriever_chunks=%s checkpointer=%s knowledge_synced=%s",
        getattr(retriever, "size", 0),
        settings.checkpointer,
        synced,
    )

    yield

    await close_checkpointer()


app = FastAPI(title=settings.app_name, lifespan=lifespan, docs_url="/api/docs", openapi_url="/api/openapi.json")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def attach_request_id(request: Request, call_next):
    request.state.request_id = f"req_{uuid.uuid4().hex[:16]}"
    response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.request_id
    return response


@app.exception_handler(AppError)
async def handle_app_error(request: Request, exc: AppError):
    return exc.to_response(getattr(request.state, "request_id", ""))


@app.exception_handler(RequestValidationError)
async def handle_validation_error(request: Request, exc: RequestValidationError):
    fields = [".".join(str(part) for part in item["loc"][1:]) for item in exc.errors()]
    return JSONResponse(
        status_code=422,
        content={
            "code": "INVALID_HEALTH_DATA",
            "message": "请求参数不符合要求: " + "、".join(fields),
            "data": {"fields": fields},
            "request_id": getattr(request.state, "request_id", ""),
        },
    )


@app.exception_handler(Exception)
async def handle_unexpected(request: Request, exc: Exception):
    log.exception("unhandled error request_id=%s", getattr(request.state, "request_id", ""))
    return JSONResponse(
        status_code=500,
        content={
            "code": "INTERNAL_ERROR",
            "message": "服务器处理失败，请稍后重试",
            "data": None,
            "request_id": getattr(request.state, "request_id", ""),
        },
    )


app.include_router(api_router, prefix=settings.api_prefix)
app.include_router(health_router)

dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if dist.exists():
    if (dist / "assets").exists():
        # Vite 给产物加了内容哈希，文件名变了 hash 就变，可以放心让浏览器长缓存。
        # 用子类给 assets 加 immutable 长缓存头；index.html 由下方 spa_fallback 加 no-cache，
        # 两边配合才能做到「改代码 → index 取最新 hash → 旧 hash 资源不再被引用」
        class _HashedStaticFiles(StaticFiles):
            async def __call__(self, scope, receive, send):
                async def wrapped_send(message):
                    if message["type"] == "http.response.start":
                        message.setdefault("headers", []).append(
                            (b"cache-control", b"public, max-age=31536000, immutable")
                        )
                    await send(message)

                await super().__call__(scope, receive, wrapped_send)

        app.mount("/assets", _HashedStaticFiles(directory=dist / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str):
        if full_path.startswith(("api/", "health/")):
            return JSONResponse(status_code=404, content={"code": "RESOURCE_NOT_FOUND", "message": "接口不存在"})
        candidate = (dist / full_path).resolve()
        if full_path and candidate.is_file() and dist.resolve() in candidate.parents:
            return FileResponse(candidate)
        # index.html 不能缓存：它引用了带 hash 的 js/css，缓存住旧 index 就会一直跳到旧资源，
        # 部署更新后用户不手动强刷就看不到新界面。assets 走上面 StaticFiles + 内容哈希，
        # 这里只对入口 html 加 no-cache，让浏览器每次取最新的 hash
        return FileResponse(
            dist / "index.html",
            headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
        )
