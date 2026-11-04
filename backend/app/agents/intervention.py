from typing import Any

from app.agents.risk_assessment import DIMENSION_NAMES

CATEGORY = {
    "cardiovascular": "健康指标自我监测",
    "metabolic": "饮食管理",
    "sleep": "睡眠管理",
    "mental": "压力与心理健康管理",
    "lifestyle": "身体活动与运动",
}

BASE_CAUTIONS = [
    "平台不提供诊断与处方，服药方案以医生意见为准",
    "指标出现明显异常或伴随不适时优先就医，不继续按计划观察",
]


def build(risk_result: dict[str, Any]) -> list[dict[str, Any]]:
    recommendations: list[dict[str, Any]] = []

    for dimension, data in risk_result["dimensions"].items():
        level = data["level"]
        if level not in ("中", "高"):
            continue
        actions = []
        for action in data.get("actions", []):
            if action not in actions:
                actions.append(action)
        if not actions:
            continue

        recommendations.append(
            {
                "dimension": dimension,
                "category": CATEGORY[dimension],
                "priority": "high" if level == "高" else "medium",
                "title": f"{DIMENSION_NAMES[dimension]}改善建议",
                "description": data.get("explanation", ""),
                "action_items": actions[:4],
                "evidence_sources": data.get("evidence_sources", []),
                "cautions": list(BASE_CAUTIONS) + list(data.get("limitations", [])),
                "requires_professional_consultation": level == "高" or data.get("urgency") == "需尽快就医",
            }
        )

    if not recommendations:
        recommendations.append(
            {
                "dimension": "lifestyle",
                "category": "身体活动与运动",
                "priority": "low",
                "title": "保持当前习惯",
                "description": "当前数据没有触发需要重点关注的规则，维持现有作息与活动量即可，重点是持续记录。",
                "action_items": ["每周至少记录三次体重或血压", "保持每周一百五十分钟中等强度活动"],
                "evidence_sources": [],
                "cautions": ["数据缺失的维度补齐后结论可能变化"],
                "requires_professional_consultation": False,
            }
        )

    return recommendations
