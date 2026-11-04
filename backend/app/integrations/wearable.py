"""可穿戴设备数据适配。

第一版不接厂商 SDK，只固定字段口径与落库路径，后续接入改这里。

设备读数默认质量状态是 pending。这类数据进指标表，但不参与评估快照：
消费级设备的估算值不能当成医疗检测结果，只有明确标记 verified 才进评估。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import HealthMetricRecord
from app.tools.metrics import METRIC_DEFS

QUALITY_VERIFIED = "verified"
QUALITY_PENDING = "pending"
QUALITY_REJECTED = "rejected"
QUALITY_STATUSES = (QUALITY_VERIFIED, QUALITY_PENDING, QUALITY_REJECTED)

SOURCE_WEARABLE = "wearable"


@dataclass(slots=True)
class WearableReading:
    source: str
    device_type: str
    metric_code: str
    value: float
    unit: str
    measured_at: datetime
    quality_status: str = QUALITY_PENDING

    def __post_init__(self) -> None:
        if self.metric_code not in METRIC_DEFS:
            raise ValueError(f"未登记的指标编码 {self.metric_code}")
        expected = METRIC_DEFS[self.metric_code].unit
        if self.unit != expected:
            raise ValueError(f"{self.metric_code} 单位应为 {expected}，收到 {self.unit}")
        if self.quality_status not in QUALITY_STATUSES:
            raise ValueError(f"未知的质量状态 {self.quality_status}")
        definition = METRIC_DEFS[self.metric_code]
        if not definition.low <= self.value <= definition.high:
            raise ValueError(f"{definition.label} 数值超出可接受范围")
        if self.measured_at.tzinfo is None:
            self.measured_at = self.measured_at.replace(tzinfo=UTC)


class WearableDataAdapter(ABC):
    """厂商适配基类。实现 fetch 即可，字段归一与落库由这里统一处理。"""

    source: str = "wearable"
    device_type: str = "unknown"

    @abstractmethod
    async def fetch(self, user_id: UUID) -> list[WearableReading]:
        """拉取该用户设备数据。真实实现里要做厂商鉴权与失败重试。"""

    def normalize(self, raw: dict) -> WearableReading:
        return WearableReading(
            source=raw.get("source") or self.source,
            device_type=raw.get("device_type") or self.device_type,
            metric_code=raw["metric_code"],
            value=float(raw["value"]),
            unit=raw["unit"],
            measured_at=raw["measured_at"],
            quality_status=raw.get("quality_status") or QUALITY_PENDING,
        )


async def ingest(session: AsyncSession, user_id: UUID, adapter: WearableDataAdapter) -> int:
    """写入适配器返回的读数，返回写入条数。"""
    readings = await adapter.fetch(user_id)
    for item in readings:
        session.add(
            HealthMetricRecord(
                user_id=user_id,
                metric_code=item.metric_code,
                value=item.value,
                unit=item.unit,
                measured_at=item.measured_at,
                measurement_context={
                    "device_type": item.device_type,
                    "quality_status": item.quality_status,
                    "source": item.source,
                },
                source_type=SOURCE_WEARABLE,
            )
        )
    if readings:
        await session.commit()
    return len(readings)
