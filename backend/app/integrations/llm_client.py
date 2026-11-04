import asyncio
from typing import Any

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger

log = get_logger(__name__)


class LLMUnavailable(RuntimeError):
    pass


class LLMClient:
    def __init__(self) -> None:
        settings = get_settings()
        self.base_url = settings.llm_base_url.rstrip("/")
        self.api_key = settings.llm_api_key
        self.model = settings.llm_model
        self.timeout = settings.llm_timeout_seconds

    @property
    def ready(self) -> bool:
        return bool(self.api_key)

    async def complete(self, system: str, user: str, temperature: float = 0.3) -> str:
        if not self.ready:
            raise LLMUnavailable("未配置模型密钥")
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
            "stream": False,
        }
        headers = {"Authorization": f"Bearer {self.api_key}"}

        last_error: Exception | None = None
        for attempt in range(2):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    resp = await client.post(f"{self.base_url}/chat/completions", json=payload, headers=headers)
                if resp.status_code >= 500:
                    raise LLMUnavailable(f"模型服务返回 {resp.status_code}")
                resp.raise_for_status()
                data = resp.json()
                return data["choices"][0]["message"]["content"].strip()
            except (httpx.HTTPError, KeyError, IndexError, LLMUnavailable) as exc:
                last_error = exc
                if attempt == 0:
                    await asyncio.sleep(0.8)
        log.warning("llm call failed: %s", last_error)
        raise LLMUnavailable(str(last_error))

    async def try_complete(self, system: str, user: str, temperature: float = 0.3) -> str | None:
        # 模型不可用时返回 None，由调用方回落到确定性文案，安全流程不依赖模型
        try:
            return await self.complete(system, user, temperature)
        except LLMUnavailable:
            return None


_client: LLMClient | None = None


def get_llm() -> LLMClient:
    global _client
    if _client is None:
        _client = LLMClient()
    return _client
