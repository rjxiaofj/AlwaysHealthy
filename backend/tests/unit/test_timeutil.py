from datetime import UTC, date, datetime, timedelta, timezone

from app.core.timeutil import BUSINESS_TZ, business_today, to_business_date


def test_utc_still_yesterday_but_business_day_is_today() -> None:
    # 2026-11-04T17:30Z 等于东八区 11-05 凌晨 1:30
    moment = datetime(2026, 11, 4, 17, 30, tzinfo=UTC)

    assert moment.date() == date(2026, 11, 4)
    assert to_business_date(moment) == date(2026, 11, 5)


def test_late_evening_does_not_jump_to_next_day() -> None:
    # 东八区 23:30 还是当天，不能被算成第二天
    moment = datetime(2026, 11, 5, 15, 30, tzinfo=UTC)

    assert to_business_date(moment) == date(2026, 11, 5)


def test_naive_datetime_is_treated_as_utc() -> None:
    # sqlite 取回的是不带时区的时间，按 UTC 解释，不能当成本地时间再加八小时
    assert to_business_date(datetime(2026, 11, 4, 17, 30)) == date(2026, 11, 5)


def test_other_timezone_input_is_converted_not_reinterpreted() -> None:
    other = datetime(2026, 11, 5, 9, 0, tzinfo=timezone(timedelta(hours=-5)))

    # 东五区 11-05 09:00 等于 UTC 14:00，等于东八区 22:00，仍是 11-05
    assert to_business_date(other) == date(2026, 11, 5)


def test_business_today_accepts_injected_clock() -> None:
    assert business_today(datetime(2026, 12, 31, 16, 30, tzinfo=UTC)) == date(2027, 1, 1)


def test_business_today_returns_business_date_of_now() -> None:
    # 不允许跟服务器本地日期绑定：容器里是 UTC，这里是东八区
    assert business_today() == datetime.now(BUSINESS_TZ).date()
