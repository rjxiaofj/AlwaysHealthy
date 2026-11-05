from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user, db_session
from app.core.exceptions import Conflict
from app.core.response import ok, paged
from app.db.models import HealthMetricRecord, User
from app.repositories import health as repo
from app.repositories import plan as plan_repo
from app.schemas.tracking import FeedbackIn, MetricIn, ReassessmentIn
from app.services import tracking_service

router = APIRouter(tags=["tracking"])


@router.post("/tracking/metrics")
async def add_metric(
    request: Request,
    payload: MetricIn,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(db_session),
):
    record = await tracking_service.add_metric(session, user.id, payload)
    return ok(request, {"id": str(record.id), "measured_at": record.measured_at})


@router.get("/tracking/metrics")
async def list_metrics(
    request: Request,
    codes: str | None = Query(default=None, description="逗号分隔的指标编码"),
    days: int = Query(default=90, ge=1, le=365),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    user: User = Depends(current_user),
    session: AsyncSession = Depends(db_session),
):
    code_list = [item for item in (codes or "").split(",") if item] or None
    rows = await tracking_service.list_metrics(session, user.id, code_list, days, limit=page * page_size)
    total = await repo.count_rows(session, HealthMetricRecord, HealthMetricRecord.user_id == user.id)
    return paged(request, rows[(page - 1) * page_size :], total, page, page_size)


@router.post("/tracking/feedback")
async def add_feedback(
    request: Request,
    payload: FeedbackIn,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(db_session),
):
    record = await tracking_service.add_feedback(session, user.id, payload)
    return ok(request, {"id": str(record.id)})


@router.get("/tracking/feedback")
async def list_feedback(
    request: Request,
    days: int = Query(default=30, ge=1, le=365),
    user: User = Depends(current_user),
    session: AsyncSession = Depends(db_session),
):
    return ok(request, await tracking_service.list_feedback(session, user.id, days))


@router.get("/tracking/summary")
async def tracking_summary(
    request: Request,
    plan_id: UUID | None = None,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(db_session),
):
    if plan_id is None:
        active = await plan_repo.active_plan(session, user.id)
        if active is None:
            raise Conflict("当前没有生效中的计划")
        plan_id = active.id
    return ok(request, await tracking_service.summary(session, user.id, plan_id))


@router.get("/tracking/trends")
async def tracking_trends(
    request: Request,
    codes: str | None = Query(default=None),
    days: int = Query(default=30, ge=1, le=365),
    user: User = Depends(current_user),
    session: AsyncSession = Depends(db_session),
):
    code_list = [item for item in (codes or "").split(",") if item]
    if not code_list:
        code_list = ["systolic_bp", "diastolic_bp", "weight_kg", "sleep_hours", "fasting_glucose"]
    return ok(request, [item.model_dump() for item in await tracking_service.trends(session, user.id, code_list, days)])


@router.post("/tracking/reassessment")
async def reassessment(
    request: Request,
    payload: ReassessmentIn,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(db_session),
):
    await tracking_service.reassessment_request(session, user.id, payload.reason)
    return ok(request, None, "重新评估诉求已登记")
