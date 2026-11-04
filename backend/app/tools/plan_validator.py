from datetime import date
from typing import Any

FORBIDDEN = ("确诊", "处方", "剂量", "毫克", "mg", "停药", "换药", "加量")
MAX_TASKS_PER_DAY = 5
MIN_DURATION = 7
MAX_DURATION = 30


def validate(draft: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []

    duration = int(draft.get("duration_days", 0))
    if not MIN_DURATION <= duration <= MAX_DURATION:
        errors.append(f"计划周期 {duration} 天不在 7 到 30 天范围内")

    start = draft.get("start_date")
    end = draft.get("end_date")
    if not isinstance(start, date) or not isinstance(end, date):
        errors.append("计划起止日期缺失")
        return {"ok": False, "errors": errors, "warnings": warnings}
    if (end - start).days + 1 != duration:
        errors.append("起止日期与周期天数不一致")

    tasks = draft.get("tasks", [])
    if not tasks:
        errors.append("计划没有任务")

    per_day: dict[date, int] = {}
    for task in tasks:
        day = task.get("scheduled_date")
        if not isinstance(day, date) or not start <= day <= end:
            errors.append(f"任务「{task.get('title')}」日期不在计划周期内")
            continue
        per_day[day] = per_day.get(day, 0) + 1
        if not str(task.get("completion_criteria", "")).strip():
            errors.append(f"任务「{task.get('title')}」缺少完成标准")
        text = f"{task.get('title', '')}{task.get('description', '')}{task.get('completion_criteria', '')}"
        for word in FORBIDDEN:
            if word in text:
                errors.append(f"任务「{task.get('title')}」包含不允许的表述：{word}")

    for day, count in per_day.items():
        if count > MAX_TASKS_PER_DAY:
            warnings.append(f"{day.isoformat()} 安排了 {count} 项任务，执行负担偏高")

    return {"ok": not errors, "errors": errors, "warnings": warnings}
