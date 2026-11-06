"""运行时可变配置：让后台能在不重启的情况下改模型参数并热生效。

为什么单独建这一层：`Settings` 是 `@lru_cache` 缓存、启动时读一次 `.env` 的只读快照。
后台要「在线改 llm_model / llm_api_key / embedding_backend 并立即生效」，得有一个可变的内存态，
再持久化到磁盘让重启后仍生效。持久化不用 `.env`——compose 的 env 注入会覆盖它，改文件也不触发重载；
这里写独立 JSON，由 `load_overrides()` 在启动后覆盖那三个字段。

改 `llm_api_key` / `llm_model` 由 LLMClient 直接读这里的新值；改 `embedding_backend` 则让
retriever 单例重建（关键词 <-> 向量是两套索引，不能混用）。
"""

import json
import threading
from pathlib import Path

from app.core.config import get_settings
from app.core.logging import get_logger

log = get_logger(__name__)

# 只允许后台在线改这三个字段，其余配置仍只读，避免把整份 Settings 变成可写面
RUNTIME_KEYS = ("llm_model", "llm_api_key", "embedding_backend")

_RUNTIME_FILE = Path(__file__).resolve().parents[2] / "runtime_config.json"
_lock = threading.Lock()
_overrides: dict[str, str] = {}


def _load_from_disk() -> dict[str, str]:
    if not _RUNTIME_FILE.exists():
        return {}
    try:
        data = json.loads(_RUNTIME_FILE.read_text(encoding="utf-8"))
        return {k: str(v) for k, v in data.items() if k in RUNTIME_KEYS}
    except (json.JSONDecodeError, OSError) as exc:
        log.warning("runtime_config.json 读不了，按未覆盖处理: %s", exc)
        return {}


def load_overrides() -> None:
    """启动时调用一次，把磁盘上的覆盖值读进内存。"""
    global _overrides
    with _lock:
        _overrides = _load_from_disk()


def get(key: str, fallback: str = "") -> str:
    with _lock:
        return _overrides.get(key, fallback)


def set_and_persist(key: str, value: str) -> None:
    if key not in RUNTIME_KEYS:
        raise ValueError(f"不支持的运行时配置项: {key}")
    with _lock:
        _overrides[key] = value
        snapshot = dict(_overrides)
    _RUNTIME_FILE.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")


def snapshot() -> dict[str, str]:
    """返回当前生效的运行时配置。llm_api_key 明文回显给管理员（需求明确要求），
    但不允许把这份快照写进日志或审计。"""
    settings = get_settings()
    with _lock:
        return {
            "llm_model": _overrides.get("llm_model", settings.llm_model),
            "llm_api_key": _overrides.get("llm_api_key", settings.llm_api_key),
            "embedding_backend": _overrides.get("embedding_backend", settings.embedding_backend),
        }
