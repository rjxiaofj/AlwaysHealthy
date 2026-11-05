from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from langchain_core.messages import HumanMessage
from langgraph.types import Command

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.models import Conversation, EmergencyEvent, WorkflowRun
from app.db.session import SessionLocal
from app.graph.deps import GraphDeps
from app.graph.main_graph import build_main_graph
from app.repositories import chat as chat_repo
from app.repositories import plan as plan_repo
from app.services import assessment_service, conversation_service, plan_service, report_service

log = get_logger(__name__)

NODE_LABELS = {
    "safety": "正在进行安全检查",
    "supervisor": "正在识别你的意图",
    "collect": "正在采集健康信息",
    "validate": "正在校验健康数据",
    "review_profile": "等待你确认健康信息",
    "assess": "正在进行健康风险评估",
    "intervene": "正在生成个性化建议",
    "plan": "正在制定健康管理计划",
    "validate_plan": "正在校验计划",
    "review_plan": "等待你确认计划",
    "final_check": "输出前安全复核",
    "report": "正在生成健康报告",
    "consult": "正在检索健康资料",
    "track": "正在分析执行情况",
    "report_query": "正在查询历史评估",
    "adjust": "正在调整计划",
    "finish_plan": "计划已确认",
    "emergency": "紧急响应",
}


@dataclass
class RunContext:
    run_id: UUID
    conversation: Conversation
    assessment_id: UUID | None = None
    plan_id: UUID | None = None
    plan_version_id: UUID | None = None
    report_id: UUID | None = None
    extra: dict[str, Any] = field(default_factory=dict)


class GraphService:
    def __init__(self, deps: GraphDeps, checkpointer=None):
        self.graph = build_main_graph(deps, checkpointer)
        self.settings = get_settings()

    def _config(self, thread_id: str) -> dict[str, Any]:
        return {"configurable": {"thread_id": thread_id}, "recursion_limit": 30}

    async def start_run(self, user_id: UUID, conversation_id: UUID, content: str):
        async with SessionLocal() as session:
            conversation = await conversation_service.get_conversation(session, user_id, conversation_id)
            await conversation_service.add_message(session, conversation, "user", content)
            run = WorkflowRun(
                conversation_id=conversation.id,
                thread_id=conversation.thread_id,
                user_id=user_id,
                run_type="message",
                status="running",
            )
            session.add(run)
            conversation.updated_at = datetime.now(UTC)
            await session.commit()
            ctx = RunContext(run_id=run.id, conversation=conversation)

        state_in = {
            "messages": [HumanMessage(content=content)],
            "user_id": str(user_id),
            "conversation_id": str(conversation_id),
            "workflow_status": "running",
            "retry_count": 0,
            "emergency_triggered": False,
        }
        yield ("run_started", {"run_id": str(ctx.run_id), "conversation_id": str(conversation_id)})
        async for event in self._stream(state_in, ctx, resume=False):
            yield event

    async def resume_run(self, user_id: UUID, run_id: UUID, payload):
        async with SessionLocal() as session:
            run = await chat_repo.run_of(session, user_id, run_id)
            if run is None:
                return
            conversation = await conversation_service.get_conversation(session, user_id, run.conversation_id)
            if payload.approval_type == "plan" and payload.decision == "approve":
                if not payload.business_id or not payload.version_id:
                    return
                await plan_service.approve(session, user_id, payload.business_id, payload.version_id)
            elif payload.approval_type == "plan" and payload.decision == "reject":
                if payload.business_id and payload.version_id:
                    await plan_service.reject_version(session, user_id, payload.business_id, payload.version_id)
            meta = run.meta or {}
            ctx = RunContext(
                run_id=run.id,
                conversation=conversation,
                assessment_id=UUID(meta["assessment_id"]) if meta.get("assessment_id") else None,
                plan_id=UUID(meta["plan_id"]) if meta.get("plan_id") else None,
                plan_version_id=UUID(meta["plan_version_id"]) if meta.get("plan_version_id") else None,
            )
            run.status = "running"
            await session.commit()

        decision = {"decision": payload.decision, "feedback": payload.feedback or ""}
        yield ("run_started", {"run_id": str(run_id), "conversation_id": str(ctx.conversation.id)})
        async for event in self._stream(Command(resume=decision), ctx, resume=True):
            yield event

    async def _stream(self, graph_input, ctx: RunContext, resume: bool):
        config = self._config(ctx.conversation.thread_id)
        interrupted: dict[str, Any] | None = None
        reply = ""
        try:
            async for chunk in self.graph.astream(graph_input, config=config, stream_mode="updates"):
                for node, update in chunk.items():
                    if node == "__interrupt__":
                        payload = update[0].value if isinstance(update, (list, tuple)) else getattr(update, "value", {})
                        interrupted = payload if isinstance(payload, dict) else {"raw": str(payload)}
                        continue
                    if node.startswith("__"):
                        continue
                    await self._persist_node(ctx, node, update or {})
                    if isinstance(update, dict) and update.get("reply"):
                        reply = update["reply"]
                    yield (
                        "node_progress",
                        {
                            "run_id": str(ctx.run_id),
                            "node": node,
                            "status": "completed",
                            "message": NODE_LABELS.get(node, node),
                        },
                    )
        except Exception as exc:
            log.exception("graph run failed run_id=%s", ctx.run_id)
            await self._fail(ctx, str(exc))
            yield ("run_error", {"run_id": str(ctx.run_id), "code": "GRAPH_EXECUTION_ERROR", "message": "工作流执行失败，请稍后重试"})
            return

        snapshot = await self.graph.aget_state(config)
        values = dict(snapshot.values or {})
        # 这一段里有没有节点产出新 reply。state 里的 reply 是整条链上最后一次写进去的值，
        # 恢复运行后如果这一段没有新 reply，它就是上一步的旧文案
        fresh_reply = reply
        reply = values.get("reply") or reply

        if interrupted is not None:
            payload = await self._enrich_interrupt(ctx, interrupted)
            yield ("confirmation_required", payload)
            # 计划确认这一段（assess → intervene → plan → plan_validator）没有任何节点写 reply，
            # 沿用 state 里的旧值会把 data_collector 那句「已记录：年龄 39…」再存一条，
            # 聊天里就出现两条一模一样的消息。没有新 reply 时用这次 interrupt 自带的阶段提示
            text = fresh_reply or payload.get("message") or ""
            await self._mark_waiting(ctx, values, text)
            return

        if reply:
            yield ("token", {"content": reply})
        await self._finish(ctx, values, reply)
        yield ("run_completed", {"run_id": str(ctx.run_id), "status": values.get("workflow_status", "completed")})

    async def _persist_node(self, ctx: RunContext, node: str, update: dict[str, Any]) -> None:
        if node == "intervene" or node == "assess":
            return
        async with SessionLocal() as session:
            if node == "collect":
                await self._save_profile(session, ctx, update)
            elif node == "plan":
                await self._save_plan(session, ctx, update.get("plan_draft") or {})
            elif node == "report":
                await self._save_report(session, ctx, update.get("report_payload") or {})
            elif node == "safety" and update.get("emergency_triggered"):
                await self._save_emergency(session, ctx, update)
            await session.commit()

    async def _save_profile(self, session, ctx: RunContext, update: dict[str, Any]) -> None:
        from app.db.models import HealthProfile
        from app.repositories import health as health_repo

        snapshot = update.get("profile_snapshot") or {}
        if not snapshot:
            return
        profile = await health_repo.profile_of(session, ctx.conversation.user_id)
        if profile is None:
            profile = HealthProfile(user_id=ctx.conversation.user_id, lifestyle={})
            session.add(profile)
            await session.flush()

        changed = False
        for field in ("sex", "height_cm", "weight_kg", "waist_cm"):
            value = snapshot.get(field)
            if value is not None and getattr(profile, field) != value:
                setattr(profile, field, value)
                changed = True
        if snapshot.get("age") and not profile.birth_date and profile.age_years != int(snapshot["age"]):
            profile.age_years = int(snapshot["age"])
            changed = True

        lifestyle = dict(profile.lifestyle or {})
        for key in (
            "sleep_hours",
            "sleep_latency_min",
            "apnea_suspected",
            "daytime_sleepiness",
            "phq2_score",
            "phq9_score",
            "stress_level",
            "function_impaired",
            "exercise_days",
            "sedentary_hours",
            "smoking_status",
            "drinking_frequency",
            "salt_intake_high",
            "sugary_drinks_daily",
            "vegetable_servings",
        ):
            if snapshot.get(key) is not None and lifestyle.get(key) != snapshot[key]:
                lifestyle[key] = snapshot[key]
                changed = True
        profile.lifestyle = lifestyle
        if changed:
            profile.profile_version = (profile.profile_version or 1) + 1

    async def _save_plan(self, session, ctx: RunContext, draft: dict[str, Any]) -> None:
        if not draft:
            return
        if ctx.plan_id is None:
            plan = await plan_service.persist_draft(session, ctx.conversation.user_id, draft, ctx.assessment_id)
            ctx.plan_id = plan.id
            ctx.plan_version_id = plan.current_version_id
            return
        # 已存在计划时是用户要求修改，生成新版本而不是再建一份计划
        version = await plan_service.revise_draft(
            session,
            ctx.conversation.user_id,
            ctx.plan_id,
            draft,
            draft.get("change_reason") or "用户要求调整",
        )
        ctx.plan_version_id = version.id

    async def _save_report(self, session, ctx: RunContext, payload: dict[str, Any]) -> None:
        if not payload or ctx.report_id is not None:
            return
        report = await report_service.save_report(
            session,
            ctx.conversation.user_id,
            payload=payload,
            assessment_id=ctx.assessment_id,
        )
        ctx.report_id = report.id

    async def _save_emergency(self, session, ctx: RunContext, update: dict[str, Any]) -> None:
        session.add(
            EmergencyEvent(
                user_id=ctx.conversation.user_id,
                conversation_id=ctx.conversation.id,
                run_id=ctx.run_id,
                trigger_reason=(update.get("emergency_reason") or "")[:255],
                matched_rules=update.get("matched_rules", []),
                urgency="紧急",
            )
        )

    async def _save_assessment(self, session, ctx: RunContext, values: dict[str, Any]) -> None:
        if ctx.assessment_id or not values.get("risk_result"):
            return
        assessment = await assessment_service.save_assessment(
            session,
            ctx.conversation.user_id,
            snapshot=values.get("profile_snapshot", {}),
            profile_version=int(values.get("profile_version", 1)),
            risk_result=values["risk_result"],
            recommendations=values.get("recommendations", []),
        )
        ctx.assessment_id = assessment.id

    async def _enrich_interrupt(self, ctx: RunContext, payload: dict[str, Any]) -> dict[str, Any]:
        async with SessionLocal() as session:
            current = await self.graph.aget_state(self._config(ctx.conversation.thread_id))
            values = dict(current.values or {})
            await self._save_assessment(session, ctx, values)
            if values.get("plan_draft") and ctx.plan_id is None:
                ctx.plan_id, ctx.plan_version_id = await self._persist_plan_for_interrupt(session, ctx, values)
            elif ctx.plan_id and ctx.assessment_id:
                plan = await plan_repo.plan_of(session, ctx.conversation.user_id, ctx.plan_id)
                if plan and plan.assessment_id is None:
                    plan.assessment_id = ctx.assessment_id
            await session.commit()

        enriched = {
            "run_id": str(ctx.run_id),
            "approval_type": payload.get("approval_type"),
            "message": payload.get("message", ""),
            "summary": payload.get("summary", {}),
            "assessment_id": str(ctx.assessment_id) if ctx.assessment_id else None,
            "plan_id": str(ctx.plan_id) if ctx.plan_id else None,
            "plan_version_id": str(ctx.plan_version_id) if ctx.plan_version_id else None,
        }
        return enriched

    async def _persist_plan_for_interrupt(self, session, ctx: RunContext, values: dict[str, Any]):
        plan = await plan_service.persist_draft(
            session,
            ctx.conversation.user_id,
            values["plan_draft"],
            ctx.assessment_id,
        )
        return plan.id, plan.current_version_id

    async def _mark_waiting(self, ctx: RunContext, values: dict[str, Any], reply: str) -> None:
        async with SessionLocal() as session:
            run = await session.get(WorkflowRun, ctx.run_id)
            if run:
                run.status = "waiting_user"
                run.meta = {
                    **(run.meta or {}),
                    "stage": values.get("current_stage", ""),
                    "assessment_id": str(ctx.assessment_id) if ctx.assessment_id else None,
                    "plan_id": str(ctx.plan_id) if ctx.plan_id else None,
                    "plan_version_id": str(ctx.plan_version_id) if ctx.plan_version_id else None,
                }
            if reply:
                await conversation_service.add_message(
                    session,
                    ctx.conversation,
                    "assistant",
                    reply,
                    message_type="confirm",
                    meta={"stage": values.get("current_stage", "")},
                )
            await session.commit()

    async def _finish(self, ctx: RunContext, values: dict[str, Any], reply: str) -> None:
        async with SessionLocal() as session:
            await self._save_assessment(session, ctx, values)
            run = await session.get(WorkflowRun, ctx.run_id)
            if run:
                run.status = "completed" if values.get("workflow_status") != "failed" else "failed"
                run.completed_at = datetime.now(UTC)
                run.error_code = values.get("error_code")
                run.meta = {
                    **(run.meta or {}),
                    "stage": values.get("current_stage", ""),
                    "intent": values.get("user_intent", ""),
                    "assessment_id": str(ctx.assessment_id) if ctx.assessment_id else None,
                    "plan_id": str(ctx.plan_id) if ctx.plan_id else None,
                }
            conversation = await session.get(Conversation, ctx.conversation.id)
            if conversation:
                conversation.updated_at = datetime.now(UTC)
            if reply:
                await conversation_service.add_message(
                    session,
                    ctx.conversation,
                    "assistant",
                    reply,
                    message_type="emergency" if values.get("emergency_triggered") else "text",
                    meta={
                        "stage": values.get("current_stage", ""),
                        "sources": values.get("sources", []),
                        "overall_level": (values.get("risk_result") or {}).get("overall_level"),
                    },
                )
            await session.commit()

    async def _fail(self, ctx: RunContext, message: str) -> None:
        async with SessionLocal() as session:
            run = await session.get(WorkflowRun, ctx.run_id)
            if run:
                run.status = "failed"
                run.error_code = "GRAPH_EXECUTION_ERROR"
                run.completed_at = datetime.now(UTC)
                run.meta = {**(run.meta or {}), "error": message[:200]}
            await session.commit()
