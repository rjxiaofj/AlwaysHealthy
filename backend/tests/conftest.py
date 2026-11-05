import os
import uuid
from pathlib import Path

# 库文件按绝对路径给，别用相对路径：从仓库根跑 pytest 时 ./test_alwayshealthy.db
# 会落在根目录，而这里的删除语句删的是 backend 下那个，两个路径对不上就等于没清库，
# 上一轮留下的用户名会在下一轮注册时报 409
_DB_FILE = Path(__file__).resolve().parents[1] / "test_alwayshealthy.db"

os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_DB_FILE.as_posix()}"
os.environ["CHECKPOINTER"] = "memory"
os.environ["ENV"] = "dev"
os.environ["KNOWLEDGE_DIR"] = str(Path(__file__).resolve().parents[2] / "knowledge")
os.environ["STORAGE_DIR"] = "./test_storage"
os.environ["JWT_SECRET"] = "test-secret-key-that-is-long-enough-for-hs256"

# 本机 backend/.env 里有真实模型密钥（跑演示时填的），不挡住的话整个测试全会真的去调
# DeepSeek：一轮从三十秒变成九分钟、每次烧掉几毛额度，断言还随模型输出飘。CI 上 .env
# 不入库所以密钥本来就是空的，这里显式清掉，两边跑的是同一条「模型不可用」的确定路径
os.environ["LLM_API_KEY"] = ""

# init_models 只建缺失的表，不会给已有表补列。每次测试从空库起，避免模型改了还跑旧结构
if _DB_FILE.exists():
    _DB_FILE.unlink()

import httpx
import pytest_asyncio

from app.db.session import SessionLocal
from app.main import app


@pytest_asyncio.fixture
async def client():
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
            yield http


@pytest_asyncio.fixture
async def session():
    """直接查库的会话，用于断言审计这类没有查询接口的落库结果。"""
    async with app.router.lifespan_context(app):
        async with SessionLocal() as db:
            yield db


@pytest_asyncio.fixture
async def auth(client):
    username = f"u{uuid.uuid4().hex[:10]}"
    response = await client.post("/api/v1/auth/register", json={"username": username, "password": "demo12345"})
    data = response.json()["data"]
    return {"Authorization": f"Bearer {data['access_token']}", "username": username}
