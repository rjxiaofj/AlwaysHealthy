from typing import Any, Literal, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages
from typing_extensions import Annotated


class HealthState(TypedDict, total=False):
    messages: Annotated[list[AnyMessage], add_messages]
    user_id: str
    conversation_id: str
    user_intent: str
    workflow_status: Literal["running", "waiting_user", "completed", "failed"]
    current_stage: str
    reply: str

    profile_snapshot: dict[str, Any]
    profile_version: int
    collect_round: int
    missing_fields: list[str]
    validation_result: dict[str, Any]
    requires_confirmation: bool

    risk_result: dict[str, Any]
    recommendations: list[dict[str, Any]]
    plan_draft: dict[str, Any]
    plan_validation: dict[str, Any]
    plan_duration_days: int
    report_payload: dict[str, Any]
    sources: list[dict[str, Any]]

    pending_review: dict[str, Any]
    approval_status: str
    human_feedback: str

    emergency_triggered: bool
    emergency_reason: str
    matched_rules: list[str]
    urgency: Literal["紧急", "需尽快就医", "非紧急"]

    retry_count: int
    error_code: str
    error_message: str
