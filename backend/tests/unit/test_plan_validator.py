from datetime import date, timedelta

from app.tools import plan_validator


def build_draft(days=14, tasks_per_day=2, criteria="完成记录"):
    start = date(2026, 1, 1)
    tasks = []
    for index in range(days):
        for _ in range(tasks_per_day):
            tasks.append(
                {
                    "title": "记录血压",
                    "description": "静坐五分钟",
                    "scheduled_date": start + timedelta(days=index),
                    "completion_criteria": criteria,
                }
            )
    return {
        "duration_days": days,
        "start_date": start,
        "end_date": start + timedelta(days=days - 1),
        "tasks": tasks,
    }


def test_valid_draft_passes():
    assert plan_validator.validate(build_draft())["ok"] is True


def test_duration_below_seven_days_rejected():
    draft = build_draft(days=6)
    result = plan_validator.validate(draft)
    assert result["ok"] is False
    assert any("7 到 30" in item for item in result["errors"])


def test_duration_above_thirty_days_rejected():
    draft = build_draft(days=31)
    assert plan_validator.validate(draft)["ok"] is False


def test_task_outside_period_rejected():
    draft = build_draft(days=7)
    draft["tasks"][0]["scheduled_date"] = draft["end_date"] + timedelta(days=1)
    result = plan_validator.validate(draft)
    assert result["ok"] is False
    assert any("日期不在计划周期内" in item for item in result["errors"])


def test_missing_completion_criteria_rejected():
    draft = build_draft(days=7, criteria=" ")
    result = plan_validator.validate(draft)
    assert result["ok"] is False
    assert any("完成标准" in item for item in result["errors"])


def test_forbidden_medical_wording_rejected():
    draft = build_draft(days=7, criteria="按处方每天服用 20 毫克")
    result = plan_validator.validate(draft)
    assert result["ok"] is False
    assert any("不允许的表述" in item for item in result["errors"])


def test_too_many_tasks_warns():
    draft = build_draft(days=7, tasks_per_day=6)
    result = plan_validator.validate(draft)
    assert result["ok"] is True
    assert result["warnings"]


def test_empty_tasks_rejected():
    draft = build_draft(days=7)
    draft["tasks"] = []
    assert plan_validator.validate(draft)["ok"] is False
