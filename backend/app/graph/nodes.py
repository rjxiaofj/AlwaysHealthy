from datetime import date
from typing import Any
from uuid import UUID

from langgraph.types import interrupt

from app.agents import data_collector, health_tracking, intervention, plan, report, risk_assessment, supervisor
from app.agents.emergency_response import render_emergency
from app.agents.emergency_router import get_router
from app.agents.profile_validator import validate as validate_profile
from app.core.exceptions import NotFound
from app.db.models import HealthPlan
from app.graph.deps import GraphDeps
from app.graph.state import HealthState
from app.repositories import plan as plan_repo
from app.services import assessment_service, profile_service, tracking_service
from app.tools import plan_validator


def _last_text(state: HealthState) -> str:
    messages = state.get("messages") or []
    if not messages:
        return ""
    content = getattr(messages[-1], "content", "")
    return content if isinstance(content, str) else str(content)


async def safety_node(state: HealthState, deps: GraphDeps) -> dict[str, Any]:
    hits = get_router().check(_last_text(state))
    if hits:
        return {
            "emergency_triggered": True,
            "emergency_reason": get_router().trigger_reason(hits),
            "matched_rules": [hit.rule_id for hit in hits],
            "urgency": "紧急",
            "workflow_status": "completed",
            "current_stage": "emergency",
            "reply": render_emergency(hits),
        }
    return {"emergency_triggered": False, "current_stage": "supervisor", "urgency": "非紧急"}


async def supervisor_node(state: HealthState, deps: GraphDeps) -> dict[str, Any]:
    text = _last_text(state)
    intent = supervisor.detect(text)
    update: dict[str, Any] = {
        "user_intent": supervisor.describe(intent),
        "current_stage": "supervisor",
    }
    if intent in ("assessment", "plan_adjust"):
        update["plan_duration_days"] = supervisor.plan_duration_from(text)
    return update


async def collect_node(state: HealthState, deps: GraphDeps) -> dict[str, Any]:
    user_id = UUID(state["user_id"])
    async with deps.session_factory() as session:
        snapshot, version = await profile_service.build_snapshot(session, user_id)

    extracted = data_collector.extract(_last_text(state))
    merged = data_collector.merge_into(snapshot, extracted)
    questions = data_collector.follow_up_questions(merged)
    reply = data_collector.describe_captured(extracted)
    if questions:
        reply += "还需要确认：" + "；".join(f"{q}" for q in questions) + "。"

    return {
        "profile_snapshot": merged,
        "profile_version": version,
        "collect_round": int(state.get("collect_round", 0)) + 1,
        "reply": reply,
        "current_stage": "data_collector",
    }


async def validate_node(state: HealthState, deps: GraphDeps) -> dict[str, Any]:
    snapshot = state.get("profile_snapshot", {})
    result = validate_profile(snapshot)

    if not result["ok"]:
        return {
            "validation_result": result,
            "missing_fields": result["missing_fields"],
            "workflow_status": "waiting_user",
            "requires_confirmation": False,
            "reply": "这部分数据暂时不能进入评估：" + "；".join(result["errors"]),
            "current_stage": "profile_validator",
        }

    needs_review = bool(result["assessable_dimensions"])
    reply = state.get("reply", "")
    if result["warnings"]:
        reply += "提醒：" + "；".join(result["warnings"]) + "。"

    return {
        "validation_result": result,
        "missing_fields": result["missing_fields"],
        "requires_confirmation": needs_review,
        "reply": reply,
        "current_stage": "profile_validator",
    }


async def review_profile_node(state: HealthState, deps: GraphDeps) -> dict[str, Any]:
    snapshot = state.get("profile_snapshot", {})
    decision = interrupt(
        {
            "approval_type": "profile",
            "summary": {
                "age": snapshot.get("age"),
                "sex": snapshot.get("sex"),
                "bmi": snapshot.get("bmi"),
                "systolic_bp": snapshot.get("systolic_bp"),
                "diastolic_bp": snapshot.get("diastolic_bp"),
                "missing_fields": state.get("missing_fields", []),
                "warnings": state.get("validation_result", {}).get("warnings", []),
            },
            "message": "请确认以上健康信息是否准确，确认后才会进入风险评估",
        }
    )
    payload = decision if isinstance(decision, dict) else {"decision": "approve"}
    action = payload.get("decision", "approve")
    if action == "reject":
        return {
            "approval_status": "reject",
            "workflow_status": "completed",
            "current_stage": "human_review",
            "reply": "已取消本次评估，没有生成评估记录。你可以补充信息后重新发起。",
        }
    return {
        "approval_status": action,
        "human_feedback": payload.get("feedback", ""),
        "current_stage": "human_review",
    }


async def assess_node(state: HealthState, deps: GraphDeps) -> dict[str, Any]:
    snapshot = dict(state.get("profile_snapshot", {}))
    feedback = state.get("human_feedback")
    result = await risk_assessment.assess(snapshot, deps.retriever, deps.llm, deps.use_llm)
    if feedback:
        for data in result["dimensions"].values():
            data.setdefault("limitations", []).append(f"用户补充说明：{feedback}")
    return {
        "risk_result": result,
        "urgency": result["urgency"],
        "current_stage": "risk_assessment",
    }


async def intervene_node(state: HealthState, deps: GraphDeps) -> dict[str, Any]:
    recommendations = intervention.build(state["risk_result"])
    return {"recommendations": recommendations, "current_stage": "intervention"}


async def plan_node(state: HealthState, deps: GraphDeps) -> dict[str, Any]:
    duration = int(state.get("plan_duration_days", 14))
    reason = state.get("human_feedback") or "首次生成"
    draft = plan.build(
        state.get("recommendations", []),
        duration,
        start_date=date.today(),
        goal=state.get("validation_result", {}).get("goal"),
        change_reason=reason,
    )
    return {"plan_draft": draft, "current_stage": "plan"}


async def validate_plan_node(state: HealthState, deps: GraphDeps) -> dict[str, Any]:
    result = plan_validator.validate(state.get("plan_draft", {}))
    if not result["ok"]:
        return {
            "plan_validation": result,
            "workflow_status": "failed",
            "error_code": "INVALID_PLAN",
            "error_message": "；".join(result["errors"]),
            "reply": "计划没有通过校验，未生效：" + "；".join(result["errors"]),
            "current_stage": "plan_validator",
        }
    return {"plan_validation": result, "current_stage": "plan_validator"}


async def review_plan_node(state: HealthState, deps: GraphDeps) -> dict[str, Any]:
    draft = state.get("plan_draft", {})
    decision = interrupt(
        {
            "approval_type": "plan",
            "summary": {
                "title": draft.get("title"),
                "duration_days": draft.get("duration_days"),
                "goal": draft.get("goal"),
                "task_count": len(draft.get("tasks", [])),
                "warnings": state.get("plan_validation", {}).get("warnings", []),
            },
            "message": "计划需要你确认后才会生效，确认前可以要求修改",
        }
    )
    payload = decision if isinstance(decision, dict) else {"decision": "approve"}
    action = payload.get("decision", "approve")
    if action == "reject":
        return {
            "approval_status": "reject",
            "workflow_status": "completed",
            "current_stage": "human_review",
            "reply": "已放弃这份计划，没有写入生效版本。",
        }
    if action == "modify":
        return {
            "approval_status": "modify",
            "human_feedback": payload.get("feedback", "用户要求调整"),
            "retry_count": int(state.get("retry_count", 0)) + 1,
            "current_stage": "human_review",
        }
    return {"approval_status": "approve", "current_stage": "human_review"}


async def report_node(state: HealthState, deps: GraphDeps) -> dict[str, Any]:
    risk = state.get("risk_result", {})
    payload = report.build_assessment_report(
        state.get("profile_snapshot", {}),
        risk,
        state.get("recommendations", []),
        state.get("plan_draft"),
    )
    level = risk.get("overall_level", "信息不足")
    reply = (
        f"评估完成，总体风险提示为{level}。"
        "五个维度的具体依据、缺失数据和医学来源已经写入报告，计划等待你在计划页确认。"
    )
    if risk.get("urgency") == "需尽快就医":
        reply = "评估中有需要尽快就医的提示，请先看报告中的对应维度，再决定是否启用计划。" + reply

    return {
        "report_payload": payload,
        "reply": reply,
        "workflow_status": "completed",
        "current_stage": "report",
    }


async def consult_node(state: HealthState, deps: GraphDeps) -> dict[str, Any]:
    result = await risk_assessment.consult(_last_text(state), deps.retriever, deps.llm)
    return {
        "reply": result["answer"],
        "sources": result["sources"],
        "workflow_status": "completed",
        "current_stage": "consult",
    }


async def track_node(state: HealthState, deps: GraphDeps) -> dict[str, Any]:
    user_id = UUID(state["user_id"])
    async with deps.session_factory() as session:
        active = await plan_repo.active_plan(session, user_id)
        if active is None:
            return {
                "reply": "当前没有生效中的计划。可以先完成一次评估，再到计划页生成计划。",
                "workflow_status": "completed",
                "current_stage": "health_tracking",
            }
        summary = await tracking_service.summary(session, user_id, active.id)

    return {
        "reply": health_tracking.narrate(summary),
        "workflow_status": "completed",
        "current_stage": "health_tracking",
    }


async def report_query_node(state: HealthState, deps: GraphDeps) -> dict[str, Any]:
    user_id = UUID(state["user_id"])
    async with deps.session_factory() as session:
        latest = await assessment_service.latest_full(session, user_id)

    if not latest:
        reply = "还没有评估记录。先在对话里描述你的基本情况，我会走一次完整评估。"
    else:
        reply = (
            f"最近一次评估在 {latest['created_at']:%Y-%m-%d %H:%M}，总体提示为{latest['overall_level']}。"
            "完整报告和医学依据在报告页，历史记录不会被后续档案修改覆盖。"
        )
    return {"reply": reply, "workflow_status": "completed", "current_stage": "report_query"}


async def adjust_node(state: HealthState, deps: GraphDeps) -> dict[str, Any]:
    user_id = UUID(state["user_id"])
    async with deps.session_factory() as session:
        latest = await assessment_service.latest_full(session, user_id)

    if not latest or not latest.get("recommendations"):
        return {
            "reply": "还没有可用的评估结论。先做一次评估，再调整计划。",
            "workflow_status": "completed",
            "current_stage": "plan_adjust",
        }

    recommendations = [
        {**item, "evidence_sources": [], "cautions": item.get("cautions", [])}
        for item in latest["recommendations"]
    ]
    draft = plan.build(
        recommendations,
        int(state.get("plan_duration_days", 14)),
        start_date=date.today(),
        change_reason=_last_text(state)[:120] or "用户要求调整",
    )
    return {
        "recommendations": recommendations,
        "plan_draft": draft,
        "current_stage": "plan_adjust",
    }


async def emergency_node(state: HealthState, deps: GraphDeps) -> dict[str, Any]:
    return {"workflow_status": "completed", "current_stage": "emergency"}


async def finish_plan_node(state: HealthState, deps: GraphDeps) -> dict[str, Any]:
    return {
        "reply": "计划已确认，可以在计划页查看每日任务并打卡。",
        "workflow_status": "completed",
        "current_stage": "plan_confirmed",
    }
