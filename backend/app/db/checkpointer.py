from langgraph.checkpoint.memory import InMemorySaver

from app.core.config import get_settings
from app.core.logging import get_logger

log = get_logger(__name__)

_saver = None
_pg_ctx = None


async def get_checkpointer():
    global _saver, _pg_ctx
    if _saver is not None:
        return _saver

    settings = get_settings()
    if settings.checkpointer != "postgres":
        _saver = InMemorySaver()
        return _saver

    # AsyncPostgresSaver 走 psycopg，不能复用 asyncpg 的 DSN
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

    dsn = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
    _pg_ctx = AsyncPostgresSaver.from_conn_string(dsn)
    _saver = await _pg_ctx.__aenter__()
    await _saver.setup()
    log.info("checkpointer ready backend=postgres")
    return _saver


async def close_checkpointer() -> None:
    global _saver, _pg_ctx
    if _pg_ctx is not None:
        await _pg_ctx.__aexit__(None, None, None)
    _saver = None
    _pg_ctx = None
