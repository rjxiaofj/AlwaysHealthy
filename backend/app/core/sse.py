import json
from typing import Any

ALLOWED_EVENTS = {
    "run_started",
    "node_progress",
    "token",
    "confirmation_required",
    "heartbeat",
    "run_completed",
    "run_error",
}


class SSEEventMapper:
    """只允许白名单事件出去，HealthState 与提示词不进入响应。"""

    internal_keys = {"profile_snapshot", "messages", "prompt", "system_prompt", "tool_args"}

    @classmethod
    def format(cls, event: str, data: dict[str, Any]) -> str:
        if event not in ALLOWED_EVENTS:
            raise ValueError(f"未登记的 SSE 事件: {event}")
        payload = {key: value for key, value in data.items() if key not in cls.internal_keys}
        body = json.dumps(payload, ensure_ascii=False, default=str)
        return f"event: {event}\ndata: {body}\n\n"

    @classmethod
    def heartbeat(cls) -> str:
        return "event: heartbeat\ndata: {}\n\n"
