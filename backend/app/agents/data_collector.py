import re
from typing import Any

from app.tools.risk_engine.engine import INDICATOR_LABELS

# 只抽取能落到结构化字段的表达，抽不到就问，不猜
_RULES: list[tuple[str, re.Pattern[str], Any]] = [
    ("age", re.compile(r"(\d{1,2})\s*岁"), int),
    ("height_cm", re.compile(r"身高\s*(\d{2,3}(?:\.\d)?)\s*(?:cm|厘米|公分)?"), float),
    ("weight_kg", re.compile(r"体重\s*(\d{2,3}(?:\.\d)?)(?!\d)\s*(?!斤)(?:kg|公斤|千克)?"), float),
    ("waist_cm", re.compile(r"腰围\s*(\d{2,3}(?:\.\d)?)\s*(?:cm|厘米)?"), float),
    ("sleep_hours", re.compile(r"(?:睡|睡眠)\s*(\d{1,2}(?:\.\d)?)\s*(?:个)?小时"), float),
    ("sleep_latency_min", re.compile(r"入睡\s*(?:要|需要)?\s*(\d{1,3})\s*分钟"), int),
    ("exercise_days", re.compile(r"每周\s*(?:运动|锻炼)\s*(\d)\s*天"), int),
    ("sedentary_hours", re.compile(r"久坐\s*(\d{1,2}(?:\.\d)?)\s*小时"), float),
    ("sugary_drinks_daily", re.compile(r"含糖饮料\s*(\d)\s*杯"), int),
    ("vegetable_servings", re.compile(r"蔬菜\s*(\d)\s*份"), int),
    ("phq9_score", re.compile(r"PHQ-?9\s*(?:得分|总分)?\s*(\d{1,2})", re.I), int),
    ("phq2_score", re.compile(r"PHQ-?2\s*(?:得分|总分)?\s*(\d{1,2})", re.I), int),
]

_BP = re.compile(r"(?:血压|高压)\s*(\d{2,3})\s*[/／]\s*(\d{2,3})")
_GLUCOSE = re.compile(r"(?:空腹血糖|血糖)\s*(\d{1,2}(?:\.\d)?)")

_SEX = re.compile(r"(?:^|[，,、；;\s])(男|女)(?:[，,、；;\s。]|$)")

TRUE_WORDS = {
    "salt_intake_high": ("口味重", "吃得咸", "高盐"),
    "apnea_suspected": ("打鼾", "憋醒", "呼吸暂停"),
    "stress_level": ("压力大", "很焦虑", "焦虑得", "紧张得睡不着"),
    "function_impaired": ("影响工作", "影响学习", "上不了班", "没法集中"),
    "activity_restricted": ("医生不让运动", "医生限制活动"),
}


def extract(text: str) -> dict[str, Any]:
    found: dict[str, Any] = {}

    for key, pattern, caster in _RULES:
        match = pattern.search(text)
        if match:
            found[key] = caster(match.group(1))

    bp = _BP.search(text)
    if bp:
        found["systolic_bp"] = int(bp.group(1))
        found["diastolic_bp"] = int(bp.group(2))

    glucose = _GLUCOSE.search(text)
    if glucose:
        found["fasting_glucose"] = float(glucose.group(1))
        found["glucose_fasting_confirmed"] = "空腹" in text

    if "斤" in text and "weight_kg" not in found:
        jin = re.search(r"体重\s*(\d{2,3})\s*斤", text)
        if jin:
            found["weight_kg"] = round(int(jin.group(1)) / 2, 1)

    sex = _SEX.search(text)
    if sex:
        found["sex"] = "male" if sex.group(1) == "男" else "female"

    if "不吸烟" in text or "不抽烟" in text or "从不吸烟" in text:
        found["smoking_status"] = "never"
    elif "戒烟" in text or "戒了" in text:
        found["smoking_status"] = "former"
    elif "吸烟" in text or "抽烟" in text or "一天一包" in text:
        found["smoking_status"] = "current"

    if "不喝酒" in text or "不饮酒" in text:
        found["drinking_frequency"] = "never"
    elif any(word in text for word in ("每天喝酒", "每天饮酒", "天天喝")):
        found["drinking_frequency"] = "daily"
    elif "偶尔喝" in text or "应酬" in text:
        found["drinking_frequency"] = "occasional"

    for key, words in TRUE_WORDS.items():
        if any(word in text for word in words):
            found[key] = "high" if key == "stress_level" else True

    if "白天困" in text or "白天嗜睡" in text or "总想睡" in text:
        found["daytime_sleepiness"] = "high"

    return found


def merge_into(snapshot: dict[str, Any], extracted: dict[str, Any]) -> dict[str, Any]:
    merged = dict(snapshot)
    for key, value in extracted.items():
        if value is not None:
            merged[key] = value
    if merged.get("height_cm") and merged.get("weight_kg"):
        meters = merged["height_cm"] / 100
        merged["bmi"] = round(merged["weight_kg"] / (meters * meters), 1)
    return merged


FOLLOW_UP_ORDER = (
    ("age", "你的年龄是多少"),
    ("sex", "方便告诉我性别吗"),
    ("height_cm", "身高和体重分别是多少"),
    ("weight_kg", "身高和体重分别是多少"),
    ("sleep_hours", "最近平均每天睡几个小时"),
    ("exercise_days", "每周有几天在运动"),
    ("sedentary_hours", "每天大概坐多久"),
    ("systolic_bp", "如果有最近一次血压读数，请按 120/80 的格式告诉我"),
    ("fasting_glucose", "最近有没有空腹血糖化验结果"),
)


def follow_up_questions(snapshot: dict[str, Any], limit: int = 3) -> list[str]:
    asked: list[str] = []
    for key, question in FOLLOW_UP_ORDER:
        if snapshot.get(key) is None and question not in asked:
            asked.append(question)
        if len(asked) >= limit:
            break
    return asked


def describe_captured(extracted: dict[str, Any]) -> str:
    if not extracted:
        return "这一轮没有提取到可结构化的健康数据。"
    parts = []
    for key, value in extracted.items():
        label = INDICATOR_LABELS.get(key, key)
        if isinstance(value, bool):
            value = "是" if value else "否"
        parts.append(f"{label} {value}")
    return "已记录：" + "，".join(parts) + "。"
