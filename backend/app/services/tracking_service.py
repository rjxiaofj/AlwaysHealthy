from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.report import build_tracking_report
from app.core.exceptions import Conflict, NotFound
from app.core.logging import get_logger
from app.core.timeutil import as_utc
from app.db.models import HealthFeedbackRecord, HealthMetricRecord, PlanTask, TrackingSummary
from app.repositories import chat as chat_repo
from app.repositories import health as health_repo
from app.repositories import plan as plan_repo
from app.schemas.tracking import MetricIn, TrendOut, TrendPoint
from app.services import report_service
from app.tools.metrics import METRIC_DEFS

log = get_logger(__name__)


async def add_metric(session: AsyncSession, user_id: UUID, payload: MetricIn) -> HealthMetricRecord:
    # 时间有效性在 MetricIn 里校验，这里只负责落库
    definition = METRIC_DEFS[payload.metric_code]
    record = HealthMetricRecord(
        user_id=user_id,
        metric_code=payload.metric_code,
        value=payload.value,
        unit=definition.unit,
        measured_at=payload.measured_at,
        measurement_context=payload.context,
        source_type=payload.context.get("source_type", "manual"),
    )
    session.add(record)
    await session.commit()
    return record


async def list_metrics(
    session: AsyncSession,
    user_id: UUID,
    codes: list[str] | None,
    days: int,
    limit: int = 200,
) -> list[dict[str, Any]]:
    rows = await health_repo.metrics_of(session, user_id, codes, limit)
    since = datetime.now(UTC) - timedelta(days=days)
    return [
        {
            "id": row.id,
            "metric_code": row.metric_code,
            "label": METRIC_DEFS[row.metric_code].label if row.metric_code in METRIC_DEFS else row.metric_code,
            "value": float(row.value),
            "unit": row.unit,
            "measured_at": row.measured_at,
            "source_type": row.source_type,
            "context": row.measurement_context,
        }
        for row in rows
        if as_utc(row.measured_at) >= since
    ]


async def add_feedback(session: AsyncSession, user_id: UUID, payload) -> HealthFeedbackRecord:
    record = HealthFeedbackRecord(
        user_id=user_id,
        plan_id=payload.plan_id,
        mood_status=payload.mood_status,
        fatigue_level=payload.fatigue_level,
        physical_feeling=payload.physical_feeling,
        execution_difficulty=payload.execution_difficulty,
        additional_feedback=payload.additional_feedback,
    )
    session.add(record)
    await session.commit()
    return record


def _aggregate(code: str, points: list[tuple[datetime, float]]) -> TrendOut:
    values = [value for _, value in points]
    latest = values[-1] if values else None
    return TrendOut(
        metric_code=code,
        label=METRIC_DEFS[code].label,
        unit=METRIC_DEFS[code].unit,
        points=[TrendPoint(measured_at=ts, value=value) for ts, value in points],
        latest=latest,
        average=round(sum(values) / len(values), 2) if values else None,
        minimum=min(values) if values else None,
        maximum=max(values) if values else None,
        change=round(values[-1] - values[0], 2) if len(values) > 1 else None,
    )


async def trends(session: AsyncSession, user_id: UUID, codes: list[str], days: int) -> list[TrendOut]:
    rows = await health_repo.metrics_of(session, user_id, codes, 1000)
    since = datetime.now(UTC) - timedelta(days=days)
    grouped: dict[str, list[tuple[datetime, float]]] = {code: [] for code in codes}
    for row in sorted(rows, key=lambda item: item.measured_at):
        if as_utc(row.measured_at) < since:
            continue
        grouped.setdefault(row.metric_code, []).append((as_utc(row.measured_at), float(row.value)))
    return [_aggregate(code, values) for code, values in grouped.items() if values]


async def summary(session: AsyncSession, user_id: UUID, plan_id: UUID) -> dict[str, Any]:
    plan = await plan_repo.plan_of(session, user_id, plan_id)
    if plan is None:
        raise NotFound("计划不存在")

    today = date.today()
    period_end = min(today, plan.end_date)
    tasks = await plan_repo.tasks_of(session, plan.current_version_id) if plan.current_version_id else []
    period_tasks: list[PlanTask] = [task for task in tasks if task.scheduled_date <= period_end]
    checkins = await plan_repo.checkins_between(session, user_id, plan.start_date, period_end)
    done = [item for item in checkins if item.status == "completed"]
    rate = round(len(done) / len(period_tasks) * 100, 1) if period_tasks else 0.0

    metrics = await trends(session, user_id, list(METRIC_DEFS.keys()), max(plan.duration_days, 7))
    notes = []
    if period_tasks and rate < 60:
        notes.append("完成率偏低，先确认任务是否为执行条件受限，不建议直接归因于身体变差")
    if plan.end_date < today:
        notes.append("计划周期已结束，是否重新评估由你决定")
    if not metrics:
        notes.append("周期内没有健康指标记录，趋势部分无法判断")

    return {
        "period_start": plan.start_date,
        "period_end": period_end,
        "completion_rate": rate,
        "task_total": len(period_tasks),
        "task_completed": len(done),
        "metrics": metrics,
        "notes": notes,
    }


async def reassessment_request(session: AsyncSession, user_id: UUID, reason: str) -> None:
    # 重新评估只登记诉求，实际评估由用户主动发起，避免后台自动创建记录。
    # 审计的 result 列只有 16 个字符，装不下原因，只记状态；原因本身没有后续分析价值
    chat_repo.audit(
        session,
        actor_user_id=user_id,
        action="reassessment_request",
        resource_type="health_profile",
        resource_id=str(user_id),
        result="requested",
        request_id=None,
    )
    await session.commit()
    log.info("reassessment requested user=%s reason=%s", user_id, reason[:60])


async def generate_report(session: AsyncSession, user_id: UUID, plan_id: UUID) -> dict[str, Any]:
    """把周期总结落库并生成阶段跟踪报告。同一计划的同一周期只出一份。"""
    plan = await plan_repo.plan_of(session, user_id, plan_id)
    if plan is None:
        raise NotFound("计划不存在")
    if plan.status not in ("active", "completed"):
        raise Conflict("当前计划状态不能生成周期报告")

    today = date.today()
    if plan.end_date > today:
        raise Conflict(f"周期到 {plan.end_date} 才结束，现在出报告统计不完整")

    existing = await plan_repo.summary_of_period(session, user_id, plan.id, plan.end_date)
    if existing is not None:
        report = await chat_repo.report_of_summary(session, user_id, existing.id)
        if report is not None:
            return await report_service.detail(session, user_id, report.id)

    data = await summary(session, user_id, plan.id)
    row = TrackingSummary(
        user_id=user_id,
        plan_id=plan.id,
        period_start=data["period_start"],
        period_end=plan.end_date,
        completion_rate=Decimal(str(data["completion_rate"])),
        metric_summary={"metrics": [item.model_dump(mode="json") for item in data["metrics"]]},
        trend_summary={"notes": data["notes"]},
    )
    session.add(row)
    try:
        await session.flush()
    except IntegrityError:
        # 双击并发时另一边已经写了同一周期，回滚后按已有记录返回
        await session.rollback()
        existing = await plan_repo.summary_of_period(session, user_id, plan_id, plan.end_date)
        report = await chat_repo.report_of_summary(session, user_id, existing.id) if existing else None
        if report is None:
            raise Conflict("周期报告正在生成，刷新后再看")
        return await report_service.detail(session, user_id, report.id)

    payload = build_tracking_report(data, plan.title)
    report = await report_service.save_report(
        session,
        user_id,
        payload=payload,
        assessment_id=None,
        tracking_summary_id=row.id,
    )
    return await report_service.detail(session, user_id, report.id)


async def today_tasks(session: AsyncSession, user_id: UUID) -> list[dict[str, Any]]:
    plan = await plan_repo.active_plan(session, user_id)
    if plan is None or plan.current_version_id is None:
        return []
    today = date.today()
    tasks = await plan_repo.tasks_of(session, plan.current_version_id, today, today)
    checkins = await plan_repo.checkins_between(session, user_id, today, today)
    status_map = {item.task_id: item.status for item in checkins}
    return [
        {
            "id": task.id,
            "title": task.title,
            "category": task.category,
            "scheduled_time": task.scheduled_time,
            "completion_criteria": task.completion_criteria,
            "status": status_map.get(task.id, "pending"),
        }
        for task in tasks
    ]


async def unfinished_before(session: AsyncSession, user_id: UUID, before: date) -> int:
    plan = await plan_repo.active_plan(session, user_id)
    if plan is None or plan.current_version_id is None:
        return 0
    tasks = await plan_repo.tasks_of(session, plan.current_version_id, plan.start_date, before)
    checkins = await plan_repo.checkins_between(session, user_id, plan.start_date, before)
    done_ids = {item.task_id for item in checkins}
    return len([task for task in tasks if task.id not in done_ids])


async def latest_metric_map(session: AsyncSession, user_id: UUID) -> dict[str, float]:
    rows = await session.scalars(
        select(HealthMetricRecord)
        .where(HealthMetricRecord.user_id == user_id)
        .order_by(HealthMetricRecord.measured_at.desc())
    )
    latest: dict[str, float] = {}
    for row in rows:
        latest.setdefault(row.metric_code, float(row.value))
    return latest
