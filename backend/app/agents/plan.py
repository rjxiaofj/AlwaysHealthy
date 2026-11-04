from datetime import date, timedelta
from typing import Any

TASK_TEMPLATES: dict[str, list[dict[str, Any]]] = {
    "cardiovascular": [
        {
            "title": "测量并记录血压",
            "category": "monitoring",
            "description": "静坐五分钟后测量，连续测两次取平均值",
            "scheduled_time": "08:00",
            "frequency": "daily",
            "duration_minutes": 5,
            "completion_criteria": "记录收缩压与舒张压两个数值",
            "checkin_type": "value",
        }
    ],
    "metabolic": [
        {
            "title": "记录三餐与含糖饮料",
            "category": "diet",
            "description": "只记录，不刻意节食，用于找出可调整的一餐",
            "scheduled_time": "20:30",
            "frequency": "daily",
            "duration_minutes": 5,
            "completion_criteria": "写出三餐主要内容与饮料份数",
            "checkin_type": "text",
        },
        {
            "title": "晨起称重",
            "category": "monitoring",
            "description": "排空后空腹，同一台秤",
            "scheduled_time": "07:00",
            "frequency": "every_other_day",
            "duration_minutes": 2,
            "completion_criteria": "记录体重数值",
            "checkin_type": "value",
        },
    ],
    "sleep": [
        {
            "title": "固定起床时间",
            "category": "sleep",
            "description": "比入睡时间更容易执行，先固定起床时间",
            "scheduled_time": "07:00",
            "frequency": "daily",
            "duration_minutes": 1,
            "completion_criteria": "起床时间与目标相差不超过三十分钟",
            "checkin_type": "boolean",
        },
        {
            "title": "睡前减少屏幕使用",
            "category": "sleep",
            "description": "睡前一小时停止刷手机与短视频",
            "scheduled_time": "22:00",
            "frequency": "daily",
            "duration_minutes": 60,
            "completion_criteria": "睡前最后一小时没有使用手机",
            "checkin_type": "boolean",
        },
    ],
    "mental": [
        {
            "title": "十分钟放松练习",
            "category": "mental",
            "description": "腹式呼吸或渐进式肌肉放松，选一种固定做",
            "scheduled_time": "21:00",
            "frequency": "daily",
            "duration_minutes": 10,
            "completion_criteria": "完成一次十分钟练习并记录主观紧张程度",
            "checkin_type": "boolean",
        },
        {
            "title": "记录情绪与压力来源",
            "category": "mental",
            "description": "写下当天最明显的一次情绪波动与触发事件",
            "scheduled_time": "21:30",
            "frequency": "daily",
            "duration_minutes": 5,
            "completion_criteria": "写下一件具体事件，不写笼统感受",
            "checkin_type": "text",
        },
    ],
    "lifestyle": [
        {
            "title": "快走二十分钟",
            "category": "exercise",
            "description": "能说话但略喘的强度，不追求配速",
            "scheduled_time": "19:00",
            "frequency": "every_other_day",
            "duration_minutes": 20,
            "completion_criteria": "连续快走不少于二十分钟",
            "checkin_type": "boolean",
        },
        {
            "title": "每餐增加一份蔬菜",
            "category": "diet",
            "description": "优先深色蔬菜，不额外增加烹调油",
            "scheduled_time": "12:00",
            "frequency": "daily",
            "duration_minutes": 1,
            "completion_criteria": "三餐中至少两餐有蔬菜",
            "checkin_type": "boolean",
        },
    ],
}


def _should_schedule(frequency: str, index: int) -> bool:
    if frequency == "daily":
        return True
    if frequency == "every_other_day":
        return index % 2 == 0
    if frequency == "weekly":
        return index % 7 == 0
    return False


def build(
    recommendations: list[dict[str, Any]],
    duration_days: int,
    start_date: date | None = None,
    goal: str | None = None,
    change_reason: str = "首次生成",
) -> dict[str, Any]:
    start = start_date or date.today()
    end = start + timedelta(days=duration_days - 1)

    dimensions: list[str] = []
    for item in recommendations:
        dimension = item["dimension"]
        if dimension in TASK_TEMPLATES and dimension not in dimensions:
            dimensions.append(dimension)

    # 每天最多三项，先保证能执行再谈覆盖度
    templates: list[dict[str, Any]] = []
    for dimension in dimensions:
        for template in TASK_TEMPLATES[dimension]:
            if len(templates) >= 3:
                break
            templates.append({**template, "dimension": dimension})

    tasks = []
    for index in range(duration_days):
        current = start + timedelta(days=index)
        for template in templates:
            if not _should_schedule(template["frequency"], index):
                continue
            tasks.append(
                {
                    "title": template["title"],
                    "category": template["category"],
                    "description": template["description"],
                    "scheduled_date": current,
                    "scheduled_time": template["scheduled_time"],
                    "frequency": template["frequency"],
                    "duration_minutes": template["duration_minutes"],
                    "completion_criteria": template["completion_criteria"],
                    "checkin_type": template["checkin_type"],
                }
            )

    cautions = ["未完成的任务不等于健康变差，先记录原因", "症状加重时停止计划并就医"]
    for item in recommendations:
        for caution in item.get("cautions", []):
            if caution not in cautions:
                cautions.append(caution)

    return {
        "title": f"{duration_days}天健康管理计划",
        "goal": goal or _default_goal(recommendations),
        "duration_days": duration_days,
        "start_date": start,
        "end_date": end,
        "tasks": tasks,
        "cautions": cautions,
        "basis": [
            {"title": source.get("title"), "version": source.get("version")}
            for item in recommendations
            for source in item.get("evidence_sources", [])
            if source.get("source_id")
        ][:6],
        "change_reason": change_reason,
    }


def _default_goal(recommendations: list[dict[str, Any]]) -> str:
    titles = [item["title"] for item in recommendations if item["priority"] != "low"]
    if not titles:
        return "保持现有作息，完成每日记录"
    return "先做到" + "、".join(titles[:2]) + "，形成可记录的日常"
