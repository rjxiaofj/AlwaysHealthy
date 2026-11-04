from datetime import UTC, datetime


def as_utc(value: datetime) -> datetime:
    # sqlite 不保存时区，取回的是 naive 时间，比较前统一按 UTC 处理
    return value if value.tzinfo else value.replace(tzinfo=UTC)
