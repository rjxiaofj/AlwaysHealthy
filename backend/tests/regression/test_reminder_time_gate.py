"""_time_passed：任务是否已到设定时间，决定「待完成」提醒该不该现在催。

背景：任务带了 scheduled_time（如 08:00 测血压、22:00 睡前少屏幕）。早上六点就把
晚上的任务当成「待完成」顶上来，既不准也烦人。到点了才催。
"""
from datetime import datetime, timezone, timedelta

from app.services.reminder_service import _time_passed

TZ = timezone(timedelta(hours=8))


def _at(hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 11, 5, hour, minute, tzinfo=TZ)


def test_no_scheduled_time_always_passed():
    assert _time_passed(None, _at(6, 0)) is True
    assert _time_passed("", _at(6, 0)) is True


def test_before_scheduled_time_not_passed():
    # 晚上 22:00 的任务，早上 6 点不该催
    assert _time_passed("22:00", _at(6, 0)) is False


def test_at_or_after_scheduled_time_passed():
    assert _time_passed("08:00", _at(8, 0)) is True
    assert _time_passed("08:00", _at(8, 30)) is True
    assert _time_passed("08:00", _at(23, 0)) is True


def test_minute_boundary_is_inclusive():
    # 08:00 的任务，08:00 整就该算到点（不是 08:01 才到）
    assert _time_passed("08:00", _at(8, 0)) is True


def test_malformed_time_falls_back_to_passed():
    # 存了坏格式的时间不该卡住提醒，退回到「按已到点处理」
    assert _time_passed("25:00", _at(12, 0)) is True
    assert _time_passed("abc", _at(12, 0)) is True
