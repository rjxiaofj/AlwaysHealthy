from functools import partial
from typing import Any

from langgraph.graph import END, START, StateGraph

from app.agents.emergency_response import render_emergency
from app.agents.emergency_router import get_router
from app.graph import nodes
from app.graph.deps import GraphDeps
from app.graph.state import HealthState


async def final_check_node(state: HealthState, deps: GraphDeps) -> dict[str, Any]:
    messages = state.get("messages") or []
    text = " ".join(getattr(item, "content", "") for item in messages[-2:])
    text += " " + (state.get("human_feedback") or "")
    hits = get_router().check(text)
    if hits:
        return {
            "emergency_triggered": True,
            "emergency_reason": get_router().trigger_reason(hits),
            "matched_rules": [hit.rule_id for hit in hits],
            "urgency": "紧急",
            "reply": render_emergency(hits),
            "workflow_status": "completed",
            "current_stage": "final_safety_check",
        }
    return {"current_stage": "final_safety_check"}


def route_after_safety(state: HealthState) -> str:
    return "emergency" if state.get("emergency_triggered") else "supervisor"


def route_intent(state: HealthState) -> str:
    intent = state.get("user_intent")
    mapping = {
        "health_assessment": "collect",
        "consult": "consult",
        "health_tracking": "track",
        "report_query": "report_query",
        "plan_adjust": "adjust",
    }
    return mapping.get(intent, "consult")


def route_after_validate(state: HealthState) -> str:
    if state.get("workflow_status") == "waiting_user":
        return "blocked"
    if state.get("requires_confirmation"):
        return "review"
    return "assess"


def route_after_profile_review(state: HealthState) -> str:
    return "blocked" if state.get("approval_status") == "reject" else "assess"


def route_after_adjust(state: HealthState) -> str:
    return "validate_plan" if state.get("plan_draft") else "blocked"


def route_after_plan_validation(state: HealthState) -> str:
    return "blocked" if state.get("workflow_status") == "failed" else "review_plan"


def route_after_plan_review(state: HealthState) -> str:
    status = state.get("approval_status")
    if status == "reject":
        return "blocked"
    if status == "modify":
        # 修改多轮仍不通过时不再循环，让用户先看到当前结果
        return "plan" if int(state.get("retry_count", 0)) < 2 else "finish_plan"
    if not state.get("risk_result"):
        return "finish_plan"
    return "final_check"


def route_after_final_check(state: HealthState) -> str:
    return "emergency" if state.get("emergency_triggered") else "report"


def build_main_graph(deps: GraphDeps, checkpointer=None):
    graph = StateGraph(HealthState)

    graph.add_node("safety", partial(nodes.safety_node, deps=deps))
    graph.add_node("supervisor", partial(nodes.supervisor_node, deps=deps))
    graph.add_node("emergency", partial(nodes.emergency_node, deps=deps))
    graph.add_node("collect", partial(nodes.collect_node, deps=deps))
    graph.add_node("validate", partial(nodes.validate_node, deps=deps))
    graph.add_node("review_profile", partial(nodes.review_profile_node, deps=deps))
    graph.add_node("assess", partial(nodes.assess_node, deps=deps))
    graph.add_node("intervene", partial(nodes.intervene_node, deps=deps))
    graph.add_node("plan", partial(nodes.plan_node, deps=deps))
    graph.add_node("validate_plan", partial(nodes.validate_plan_node, deps=deps))
    graph.add_node("review_plan", partial(nodes.review_plan_node, deps=deps))
    graph.add_node("final_check", partial(final_check_node, deps=deps))
    graph.add_node("report", partial(nodes.report_node, deps=deps))
    graph.add_node("consult", partial(nodes.consult_node, deps=deps))
    graph.add_node("track", partial(nodes.track_node, deps=deps))
    graph.add_node("report_query", partial(nodes.report_query_node, deps=deps))
    graph.add_node("adjust", partial(nodes.adjust_node, deps=deps))
    graph.add_node("finish_plan", partial(nodes.finish_plan_node, deps=deps))

    graph.add_edge(START, "safety")
    graph.add_conditional_edges("safety", route_after_safety, {"emergency": "emergency", "supervisor": "supervisor"})
    graph.add_conditional_edges(
        "supervisor",
        route_intent,
        {
            "collect": "collect",
            "consult": "consult",
            "track": "track",
            "report_query": "report_query",
            "adjust": "adjust",
        },
    )
    graph.add_edge("collect", "validate")
    graph.add_conditional_edges(
        "validate",
        route_after_validate,
        {"blocked": END, "review": "review_profile", "assess": "assess"},
    )
    graph.add_conditional_edges(
        "review_profile",
        route_after_profile_review,
        {"blocked": END, "assess": "assess"},
    )
    graph.add_edge("assess", "intervene")
    graph.add_edge("intervene", "plan")
    graph.add_edge("plan", "validate_plan")
    graph.add_conditional_edges(
        "validate_plan",
        route_after_plan_validation,
        {"blocked": END, "review_plan": "review_plan"},
    )
    graph.add_conditional_edges(
        "review_plan",
        route_after_plan_review,
        {"blocked": END, "plan": "plan", "final_check": "final_check", "finish_plan": "finish_plan"},
    )
    graph.add_conditional_edges(
        "final_check",
        route_after_final_check,
        {"emergency": "emergency", "report": "report"},
    )
    graph.add_conditional_edges(
        "adjust",
        route_after_adjust,
        {"validate_plan": "validate_plan", "blocked": END},
    )
    graph.add_edge("finish_plan", END)
    graph.add_edge("report", END)
    graph.add_edge("consult", END)
    graph.add_edge("track", END)
    graph.add_edge("report_query", END)
    graph.add_edge("emergency", END)

    return graph.compile(checkpointer=checkpointer)
