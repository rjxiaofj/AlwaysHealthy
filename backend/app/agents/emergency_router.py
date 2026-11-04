from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

EMERGENCY_FILE = Path(__file__).resolve().parents[1] / "tools" / "risk_engine" / "rules" / "emergency.yaml"


@dataclass(frozen=True)
class EmergencyHit:
    rule_id: str
    category: str
    message: str


class EmergencyRouter:
    def __init__(self, path: Path = EMERGENCY_FILE):
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        self.version = str(raw.get("version", "0"))
        self._signals: list[dict[str, Any]] = raw.get("signals", [])

    def check(self, text: str) -> list[EmergencyHit]:
        normalized = "".join(text.lower().split())
        if not normalized:
            return []
        hits = []
        for signal in self._signals:
            for pattern in signal.get("patterns", []):
                if pattern.lower().replace(" ", "") in normalized:
                    hits.append(
                        EmergencyHit(
                            rule_id=signal["rule_id"],
                            category=signal.get("category", "其他"),
                            message=signal.get("message", pattern),
                        )
                    )
                    break
        return hits

    def trigger_reason(self, hits: list[EmergencyHit]) -> str:
        return "；".join(hit.message for hit in hits)


_router: EmergencyRouter | None = None


def get_router() -> EmergencyRouter:
    global _router
    if _router is None:
        _router = EmergencyRouter()
    return _router
