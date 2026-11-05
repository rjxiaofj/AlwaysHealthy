from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents import plan as plan_agent
from app.api.deps import current_user, db_session
from app.core.exceptions import Conflict, IllegalPlan
from app.core.response import ok
from app.db.models import User
from app.schemas.plan import CheckinIn, PlanAdjustIn, PlanApproveIn, PlanGenerateIn, PlanShiftIn, TaskPatchIn
from app.services import assessment_service, plan_service
from app.tools import plan_validator

router = APIRouter(tags=["plan"])


@router.post("/plans/generate")
async def generate_plan(
    request: Request,
    payload: PlanGenerateIn,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(db_session),
):
    latest = await assessment_service.latest_full(session, user.id)
    if latest is None:
        raise Conflict("没有可用的评估记录，先完成一次评估")
    if not 7 <= payload.duration_days <= 30:
        raise IllegalPlan("计划周期必须在 7 到 30 天之间")

    draft = plan_agent.build(
        latest["recommendations"],
        payload.duration_days,
        start_date=payload.start_date or date.today(),
        goal=payload.goal,
    )
    validation = plan_validator.validate(draft)
    if not validation["ok"]:
        raise IllegalPlan("；".join(validation["errors"]))

    plan = await plan_service.persist_draft(session, user.id, draft, latest["id"])
    detail = await plan_service.detail(session, user.id, plan.id)
    return ok(request, detail)


@router.get("/plans")
async def list_plans(
    request: Request,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(db_session),
):
    return ok(request, await plan_service.list_plans(session, user.id))


@router.get("/plans/{plan_id}")
async def plan_detail(
    plan_id: UUID,
    request: Request,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(db_session),
):
    return ok(request, await plan_service.detail(session, user.id, plan_id))


@router.post("/plans/{plan_id}/approve")
async def approve_plan(
    plan_id: UUID,
    payload: PlanApproveIn,
    request: Request,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(db_session),
):
    await plan_service.approve(session, user.id, plan_id, payload.version_id)
    return ok(request, await plan_service.detail(session, user.id, plan_id))


@router.post("/plans/{plan_id}/adjust")
async def adjust_plan(
    plan_id: UUID,
    payload: PlanAdjustIn,
    request: Request,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(db_session),
):
    version = await plan_service.adjust(session, user.id, plan_id, payload.reason)
    return ok(request, {"version_id": str(version.id), "version_no": version.version_no})


@router.post("/plans/{plan_id}/shift")
async def shift_plan(
    plan_id: UUID,
    payload: PlanShiftIn,
    request: Request,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(db_session),
):
    await plan_service.shift(session, user.id, plan_id, payload.start_date, payload.reason or "")
    return ok(request, await plan_service.detail(session, user.id, plan_id))


@router.post("/plans/{plan_id}/cancel")
async def cancel_plan(
    plan_id: UUID,
    request: Request,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(db_session),
):
    await plan_service.cancel(session, user.id, plan_id)
    return ok(request, None, "计划已取消")


@router.get("/plans/{plan_id}/versions")
async def plan_versions(
    plan_id: UUID,
    request: Request,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(db_session),
):
    detail = await plan_service.detail(session, user.id, plan_id)
    return ok(request, detail["versions"])


@router.get("/plans/{plan_id}/tasks")
async def plan_tasks(
    plan_id: UUID,
    request: Request,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(db_session),
):
    detail = await plan_service.detail(session, user.id, plan_id)
    return ok(request, detail["tasks"])


@router.post("/tasks/{task_id}/checkins")
async def submit_checkin(
    task_id: UUID,
    payload: CheckinIn,
    request: Request,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(db_session),
):
    record = await plan_service.checkin(session, user.id, task_id, payload)
    return ok(
        request,
        {
            "id": str(record.id),
            "task_id": str(record.task_id),
            "status": record.status,
            "feedback": record.feedback,
            "checkin_date": record.checkin_date,
            "checkin_at": record.checkin_at,
        },
    )


@router.patch("/tasks/{task_id}")
async def patch_task(
    task_id: UUID,
    payload: TaskPatchIn,
    request: Request,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(db_session),
):
    task = await plan_service.patch_task(session, user.id, task_id, payload)
    return ok(
        request,
        {
            "id": str(task.id),
            "scheduled_date": task.scheduled_date,
            "scheduled_time": task.scheduled_time,
            "reminder_enabled": task.reminder_enabled,
        },
    )
