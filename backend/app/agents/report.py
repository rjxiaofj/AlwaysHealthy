from datetime import datetime
from typing import Any

from app.agents.risk_assessment import DIMENSION_NAMES

DISCLAIMER = "本报告基于你自行提供的信息与已审核规则生成，仅供健康管理参考，不构成疾病诊断或治疗方案。"

LEVEL_TEXT = {"低": "低风险", "中": "需要关注", "高": "高风险", "信息不足": "信息不足"}


def build_assessment_report(
    snapshot: dict[str, Any],
    risk_result: dict[str, Any],
    recommendations: list[dict[str, Any]],
    plan_draft: dict[str, Any] | None,
) -> dict[str, Any]:
    sections: list[dict[str, Any]] = []

    basic = [
        f"年龄：{snapshot.get('age') or '未提供'}",
        f"性别：{'男' if snapshot.get('sex') == 'male' else '女' if snapshot.get('sex') == 'female' else '未提供'}",
        f"身高：{snapshot.get('height_cm') or '未提供'} cm，体重：{snapshot.get('weight_kg') or '未提供'} kg"
        if snapshot.get("height_cm")
        else "身高体重：未提供",
        f"BMI：{snapshot.get('bmi') or '未计算'}",
    ]
    sections.append({"heading": "基本信息", "paragraphs": basic, "items": []})

    items = []
    for dimension, data in risk_result["dimensions"].items():
        name = DIMENSION_NAMES.get(dimension, dimension)
        factors = "；".join(item["message"] for item in data.get("risk_factors", []))
        line = f"{name}：{LEVEL_TEXT.get(data['level'], data['level'])}"
        if factors:
            line += f"，依据：{factors}"
        items.append(line)
    sections.append({"heading": "五维评估结果", "paragraphs": [], "items": items})

    attention = []
    for dimension, data in risk_result["dimensions"].items():
        for item in data.get("risk_factors", []):
            attention.append(f"{DIMENSION_NAMES.get(dimension, dimension)}：{item['message']}")
    sections.append(
        {
            "heading": "需要关注的因素",
            "paragraphs": [] if attention else ["本次评估没有匹配到需要重点关注的因素。"],
            "items": attention,
        }
    )

    gaps = []
    for dimension, data in risk_result["dimensions"].items():
        if data.get("missing_data"):
            gaps.append(f"{DIMENSION_NAMES.get(dimension, dimension)}：缺少" + "、".join(data["missing_data"]))
        for limitation in data.get("limitations", []):
            if limitation not in gaps:
                gaps.append(limitation)
    sections.append(
        {
            "heading": "缺失数据与评估局限",
            "paragraphs": ["数据不足的维度不做推断，补齐后结论可能变化。"] if gaps else ["本次评估数据相对完整。"],
            "items": gaps,
        }
    )

    sources: list[str] = []
    for data in risk_result["dimensions"].values():
        for source in data.get("evidence_sources", []):
            label = f"{source.get('title')}（{source.get('version') or '版本未标注'}）"
            if label not in sources:
                sources.append(label)
    sections.append(
        {
            "heading": "医学依据",
            "paragraphs": [],
            "items": sources or ["本次未关联到可引用的资料条目"],
        }
    )

    rec_items = []
    for item in recommendations:
        rec_items.append(f"{item['title']}：" + "；".join(item.get("action_items", [])))
    sections.append({"heading": "个性化建议", "paragraphs": [], "items": rec_items})

    if plan_draft:
        plan_items = [
            f"计划周期：{plan_draft['duration_days']} 天，{plan_draft['start_date']} 至 {plan_draft['end_date']}",
            f"阶段目标：{plan_draft.get('goal', '')}",
            f"每日任务数：最多 3 项",
        ]
        sections.append({"heading": "健康管理计划", "paragraphs": [], "items": plan_items})

    return {
        "report_type": "assessment",
        "title": f"健康评估报告 {datetime.now():%Y-%m-%d}",
        "disclaimer": DISCLAIMER,
        "overall_level": risk_result.get("overall_level"),
        "urgency": risk_result.get("urgency"),
        "rule_engine_version": risk_result.get("rule_engine_version"),
        "knowledge_version": risk_result.get("knowledge_version"),
        "sections": sections,
    }


def build_tracking_report(summary: dict[str, Any], plan_title: str) -> dict[str, Any]:
    sections = [
        {
            "heading": "计划执行情况",
            "paragraphs": [
                f"计划：{plan_title}",
                f"统计区间：{summary['period_start']} 至 {summary['period_end']}",
                f"任务完成率：{summary['completion_rate']}%（{summary['task_completed']}/{summary['task_total']}）",
            ],
            "items": [],
        }
    ]
    metric_items = []
    for metric in summary.get("metrics", []):
        change = "无对比数据" if metric.change is None else f"变化 {metric.change}{metric.unit}"
        metric_items.append(
            f"{metric.label}：最新 {metric.latest}{metric.unit}，均值 {metric.average}{metric.unit}，{change}"
        )
    sections.append(
        {
            "heading": "健康指标变化",
            "paragraphs": [] if metric_items else ["本周期没有指标记录。"],
            "items": metric_items,
        }
    )
    sections.append(
        {
            "heading": "说明",
            "paragraphs": [
                "完成率反映执行情况，不代表健康改善程度。指标变化需要结合测量条件与更长周期观察。"
            ],
            "items": summary.get("notes", []),
        }
    )
    return {
        "report_type": "tracking",
        "title": f"阶段跟踪报告 {datetime.now():%Y-%m-%d}",
        "disclaimer": DISCLAIMER,
        "sections": sections,
    }
