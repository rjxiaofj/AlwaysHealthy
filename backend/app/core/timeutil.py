from datetime import UTC, date, datetime, timedelta, timezone


def as_utc(value: datetime) -> datetime:
    # sqlite 不保存时区，取回的是 naive 时间，比较前统一按 UTC 处理
    return value if value.tzinfo else value.replace(tzinfo=UTC)


# 业务日期按东八区算。容器默认 UTC，早上 0 点到 8 点这段时间服务器还停在前一天，
# 「今日任务」「今日提醒」「打卡日期」会整体错一天。中国没有夏令时，固定 +8 就够，
# 也不依赖镜像里有没有 tzdata
BUSINESS_TZ = timezone(timedelta(hours=8))


def to_business_date(moment: datetime) -> date:
    return as_utc(moment).astimezone(BUSINESS_TZ).date()


def business_today(now: datetime | None = None) -> date:
    return to_business_date(now or datetime.now(UTC))
