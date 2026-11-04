from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.db.models import HealthMetricRecord
from app.integrations.wearable import (
    QUALITY_PENDING,
    QUALITY_VERIFIED,
    WearableDataAdapter,
    WearableReading,
    ingest,
)
from app.repositories.health import _counting_for_assessment


class FakeAdapter(WearableDataAdapter):
    source = "fake"
    device_type = "smartwatch"

    async def fetch(self, user_id):
        return []


class FixedAdapter(WearableDataAdapter):
    source = "fake"
    device_type = "smartwatch"

    def __init__(self, readings):
        self._readings = readings

    async def fetch(self, user_id):
        return self._readings


def reading(**overrides) -> WearableReading:
    payload = {
        "source": "fake",
        "device_type": "smartwatch",
        "metric_code": "heart_rate",
        "value": 68,
        "unit": "bpm",
        "measured_at": datetime(2026, 11, 4, 8, 30, tzinfo=UTC),
    }
    payload.update(overrides)
    return WearableReading(**payload)


def test_normalize_fills_default_source_and_pending_status():
    item = FakeAdapter().normalize(
        {
            "metric_code": "heart_rate",
            "value": 72,
            "unit": "bpm",
            "measured_at": datetime(2026, 11, 4, 8, 30, tzinfo=UTC),
        }
    )
    assert item.source == "fake"
    assert item.device_type == "smartwatch"
    assert item.quality_status == QUALITY_PENDING


def test_unit_must_match_metric_definition():
    with pytest.raises(ValueError):
        reading(metric_code="weight_kg", value=70, unit="bpm")


def test_unknown_metric_rejected():
    with pytest.raises(ValueError):
        reading(metric_code="blood_type", value=1, unit="bpm")


def test_value_out_of_range_rejected():
    with pytest.raises(ValueError):
        reading(metric_code="heart_rate", value=400, unit="bpm")


def metric_row(source_type: str, quality: str | None) -> HealthMetricRecord:
    context = {"quality_status": quality} if quality else {}
    return HealthMetricRecord(
        id=uuid4(),
        user_id=uuid4(),
        metric_code="heart_rate",
        value=68,
        unit="bpm",
        measured_at=datetime(2026, 11, 4, 8, 30, tzinfo=UTC),
        source_type=source_type,
        measurement_context=context,
    )


def test_pending_wearable_reading_excluded_from_assessment():
    row = metric_row("wearable", QUALITY_PENDING)
    assert _counting_for_assessment(row) is False


def test_verified_wearable_reading_counts():
    row = metric_row("wearable", QUALITY_VERIFIED)
    assert _counting_for_assessment(row) is True


def test_manual_reading_always_counts():
    row = metric_row("manual", None)
    assert _counting_for_assessment(row) is True


async def test_ingest_skips_repeated_readings(session):
    user_id = uuid4()
    adapter = FixedAdapter([reading(metric_code="heart_rate", value=68, unit="bpm")])

    first = await ingest(session, user_id, adapter)
    second = await ingest(session, user_id, adapter)

    # 设备重发同一时间窗的数据不应重复入库
    assert first == 1
    assert second == 0
