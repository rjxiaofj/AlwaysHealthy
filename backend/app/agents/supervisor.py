import re

from app.agents import data_collector

KEYWORDS = {
    "plan_adjust": ("调整计划", "改计划", "换计划", "计划太长", "计划太短", "重新制定"),
    "tracking": ("打卡", "任务", "执行情况", "跟踪", "完成情况", "今天要做什么"),
    "report": ("报告", "历史记录", "上次评估"),
    "assessment": ("评估", "体检", "风险", "检查一下", "帮我看看", "分析一下"),
}

INTENT_STAGE = {
    "assessment": "health_assessment",
    "tracking": "health_tracking",
    "report": "report_query",
    "plan_adjust": "plan_adjust",
    "consult": "consult",
}


def detect(text: str) -> str:
    for intent, words in KEYWORDS.items():
        if any(word in text for word in words):
            return intent
    # 用户直接报了一串身体数据时按评估处理，不必等他说出评估两个字
    if len(data_collector.extract(text)) >= 2:
        return "assessment"
    return "consult"


def describe(intent: str) -> str:
    return INTENT_STAGE.get(intent, "consult")


def plan_duration_from(text: str, default: int = 14) -> int:
    # 只认明确带天数的表达，避免把年龄、体重里的数字当周期
    for match in re.findall(r"(\d{1,2})\s*天", text):
        value = int(match)
        if 7 <= value <= 30:
            return value
    return default
