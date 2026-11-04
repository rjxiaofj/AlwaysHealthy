import os
import uuid
from pathlib import Path

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_alwayshealthy.db"
os.environ["CHECKPOINTER"] = "memory"
os.environ["ENV"] = "dev"
os.environ["KNOWLEDGE_DIR"] = str(Path(__file__).resolve().parents[2] / "knowledge")
os.environ["STORAGE_DIR"] = "./test_storage"
os.environ["JWT_SECRET"] = "test-secret-key-that-is-long-enough-for-hs256"

import httpx
import pytest_asyncio

from app.main import app


@pytest_asyncio.fixture
async def client():
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
            yield http


@pytest_asyncio.fixture
async def auth(client):
    username = f"u{uuid.uuid4().hex[:10]}"
    response = await client.post("/api/v1/auth/register", json={"username": username, "password": "demo12345"})
    data = response.json()["data"]
    return {"Authorization": f"Bearer {data['access_token']}", "username": username}
