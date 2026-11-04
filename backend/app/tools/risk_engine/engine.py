from typing import Any

from app.tools.risk_engine.rule_loader import DIMENSIONS, Rule, load_all
from app.tools.risk_engine.rule_matcher import match_rule

LEVEL_ORDER = {"信息不足": 0, "低": 1, "中": 2, "高": 3}

# 维度判定所需的输入，缺这些就只能标记信息不足，不能默认低风险
REQUIRED_INPUTS: dict[str, tuple[str, ...]] = {
    "cardiovascular": ("age", "systolic_bp", "diastolic_bp"),
    "metabolic": ("bmi",),
    "sleep": ("sleep_hours",),
    "mental": ("phq2_score", "phq9_score", "stress_level"),
    "lifestyle": ("exercise_days", "sedentary_hours"),
}

INDICATOR_LABELS = {
    "age": "年龄",
    "bmi": "BMI",
    "waist_cm": "腰围",
    "systolic_bp": "收缩压",
    "diastolic_bp": "舒张压",
    "fasting_glucose": "空腹血糖",
    "hba1c": "糖化血红蛋白",
    "ldl_c": "低密度脂蛋白胆固醇",
    "hdl_c": "高密度脂蛋白胆固醇",
    "triglycerides": "甘油三酯",
    "sleep_hours": "平均睡眠时长",
    "sleep_latency_min": "入睡耗时",
    "apnea_suspected": "睡眠呼吸暂停表现",
    "daytime_sleepiness": "日间困倦",
    "phq2_score": "PHQ-2",
    "phq9_score": "PHQ-9",
    "stress_level": "压力感受",
    "function_impaired": "社会功能影响",
    "exercise_days": "每周运动天数",
    "sedentary_hours": "每日久坐时长",
    "smoking_status": "吸烟情况",
    "drinking_frequency": "饮酒频率",
}


class RiskEngine:
    def __init__(self, rules_dir=None):
        self.rule_version, self._rules = load_all(rules_dir) if rules_dir else load_all()

    @property
    def rules(self) -> dict[str, list[Rule]]:
        return self._rules

    def evaluate(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        dimensions: dict[str, Any] = {}
        for dimension in DIMENSIONS:
            dimensions[dimension] = self._evaluate_dimension(dimension, snapshot)

        overall = aggregate_level([d["level"] for d in dimensions.values()])
        urgency = "非紧急"
        if any(d["urgency"] == "需尽快就医" for d in dimensions.values()):
            urgency = "需尽快就医"

        return {
            "overall_level": overall,
            "urgency": urgency,
            "dimensions": dimensions,
            "rule_engine_version": self.rule_version,
        }

    def _evaluate_dimension(self, dimension: str, snapshot: dict[str, Any]) -> dict[str, Any]:
        matched: list[Rule] = [r for r in self._rules[dimension] if match_rule(r, snapshot)]
        missing = [key for key in REQUIRED_INPUTS[dimension] if snapshot.get(key) is None]

        if matched:
            level = max((r.risk_level for r in matched), key=lambda x: LEVEL_ORDER[x])
        elif missing:
            level = "信息不足"
        else:
            level = "低"

        risk_factors = [
            {
                "rule_id": rule.rule_id,
                "indicator": rule.indicator,
                "label": INDICATOR_LABELS.get(rule.indicator, rule.indicator),
                "value": snapshot.get(rule.indicator) if rule.operator != "all" else None,
                "unit": rule.unit,
                "message": rule.message,
                "risk_level": rule.risk_level,
            }
            for rule in matched
        ]

        sources: dict[str, dict[str, Any]] = {}
        for rule in matched:
            source = rule.source
            sources[source.get("source_id", rule.rule_id)] = {
                "source_id": source.get("source_id"),
                "title": source.get("title"),
                "version": source.get("version"),
                "page": source.get("page"),
            }

        limitations = []
        if missing:
            limitations.append(
                "缺少" + "、".join(INDICATOR_LABELS.get(m, m) for m in missing) + "，该维度判断不完整"
            )
        if dimension == "metabolic" and snapshot.get("fasting_glucose") is not None:
            if snapshot.get("glucose_fasting_confirmed") is not True:
                limitations.append("血糖未确认空腹状态，相关提示仅供参考")

        return {
            "dimension": dimension,
            "level": level,
            "risk_factors": risk_factors,
            "missing_data": [INDICATOR_LABELS.get(m, m) for m in missing],
            "missing_keys": missing,
            "explanation": "",
            "limitations": limitations,
            "evidence_sources": list(sources.values()),
            "actions": [a for rule in matched for a in rule.recommended_action],
            "urgency": "需尽快就医" if any(r.urgency == "需尽快就医" for r in matched) else "非紧急",
        }


def aggregate_level(levels: list[str]) -> str:
    # 已知的中高风险不因其他维度缺数据被拉低
    if "高" in levels:
        return "高"
    if "中" in levels:
        return "中"
    if levels and all(level == "低" for level in levels):
        return "低"
    return "信息不足"


_engine: RiskEngine | None = None


def get_engine() -> RiskEngine:
    global _engine
    if _engine is None:
        _engine = RiskEngine()
    return _engine
