from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents import intervention, risk_assessment
from app.agents.profile_validator import validate as validate_profile
from app.api.deps import current_user, db_session
from app.core.config import get_settings
from app.core.exceptions import InvalidHealthData, NotFound
from app.core.response import ok, paged
from app.db.models import RiskAssessment, User
from app.repositories import health as repo
from app.services import assessment_service, profile_service

router = APIRouter(tags=["assessment"])


@router.post("/assessments")
async def create_assessment(
    request: Request,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(db_session),
):
    snapshot, version = await profile_service.build_snapshot(session, user.id)
    validation = validate_profile(snapshot)
    if not validation["ok"]:
        raise InvalidHealthData("；".join(validation["errors"]), detail={"errors": validation["errors"]})

    risk = await risk_assessment.assess(
        snapshot,
        request.app.state.retriever,
        request.app.state.llm,
        use_llm=bool(get_settings().llm_api_key),
    )
    recommendations = intervention.build(risk)
    assessment = await assessment_service.save_assessment(
        session,
        user.id,
        snapshot=snapshot,
        profile_version=version,
        risk_result=risk,
        recommendations=recommendations,
    )
    detail = await assessment_service.detail(session, user.id, assessment.id)
    return ok(request, detail)


@router.get("/assessments")
async def list_assessments(
    request: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=50),
    user: User = Depends(current_user),
    session: AsyncSession = Depends(db_session),
):
    rows = await assessment_service.list_latest(session, user.id, limit=page * page_size)
    total = await repo.count_rows(session, RiskAssessment, RiskAssessment.user_id == user.id)
    items = rows[(page - 1) * page_size : page * page_size]
    return paged(request, items, total, page, page_size)


@router.get("/assessments/latest")
async def latest_assessment(
    request: Request,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(db_session),
):
    detail = await assessment_service.latest_full(session, user.id)
    return ok(request, detail)


@router.get("/assessments/{assessment_id}")
async def assessment_detail(
    assessment_id: UUID,
    request: Request,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(db_session),
):
    detail = await assessment_service.detail(session, user.id, assessment_id)
    if detail is None:
        raise NotFound("评估记录不存在")
    return ok(request, detail)


@router.get("/assessments/{assessment_id}/evidence")
async def assessment_evidence(
    assessment_id: UUID,
    request: Request,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(db_session),
):
    detail = await assessment_service.detail(session, user.id, assessment_id)
    if detail is None:
        raise NotFound("评估记录不存在")
    return ok(request, [{"dimension": item["dimension"], "sources": item["evidence_sources"]} for item in detail["dimensions"]])
