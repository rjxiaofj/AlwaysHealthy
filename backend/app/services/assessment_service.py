from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    AssessmentDimensionResult,
    AssessmentEvidence,
    InterventionRecommendation,
    RiskAssessment,
)
from app.repositories import health as repo


async def save_assessment(
    session: AsyncSession,
    user_id: UUID,
    *,
    snapshot: dict[str, Any],
    profile_version: int,
    risk_result: dict[str, Any],
    recommendations: list[dict[str, Any]],
) -> RiskAssessment:
    assessment = RiskAssessment(
        user_id=user_id,
        profile_version=profile_version,
        profile_snapshot=snapshot,
        overall_level=risk_result["overall_level"],
        urgency=risk_result["urgency"],
        rule_engine_version=risk_result.get("rule_engine_version", "0"),
        knowledge_version=risk_result.get("knowledge_version", "0"),
        assessment_status="completed",
    )
    session.add(assessment)
    await session.flush()

    for dimension, data in risk_result["dimensions"].items():
        result = AssessmentDimensionResult(
            assessment_id=assessment.id,
            dimension=dimension,
            risk_level=data["level"],
            risk_factors=data.get("risk_factors", []),
            missing_data=data.get("missing_data", []),
            explanation=data.get("explanation", ""),
            limitations=data.get("limitations", []),
        )
        session.add(result)
        await session.flush()

        for evidence in data.get("evidences", []):
            session.add(
                AssessmentEvidence(
                    dimension_result_id=result.id,
                    source_id=evidence["source_id"],
                    chunk_id=evidence["chunk_id"],
                    page_number=evidence.get("page"),
                    evidence_excerpt=evidence["content"][:1000],
                )
            )

    for item in recommendations:
        session.add(
            InterventionRecommendation(
                assessment_id=assessment.id,
                dimension=item["dimension"],
                category=item["category"],
                priority=item["priority"],
                title=item["title"],
                description=item["description"],
                action_items=item.get("action_items", []),
                evidence_sources=item.get("evidence_sources", []),
                cautions=item.get("cautions", []),
                requires_professional_consultation=item.get("requires_professional_consultation", False),
            )
        )

    await session.commit()
    return assessment


async def detail(session: AsyncSession, user_id: UUID, assessment_id: UUID) -> dict[str, Any] | None:
    assessment = await repo.assessment_of(session, user_id, assessment_id)
    if assessment is None:
        return None
    dimensions = await repo.dimensions_of(session, assessment_id)
    evidence_map = await repo.evidence_of(session, [d.id for d in dimensions])
    recs = await repo.recommendations_of(session, assessment_id)

    dim_payload = []
    for dim in dimensions:
        sources = {}
        for item in evidence_map.get(dim.id, []):
            sources[item.source_id] = {
                "source_id": item.source_id,
                "title": item.source_id,
                "version": "",
                "page": item.page_number,
                "excerpt": item.evidence_excerpt,
            }
        dim_payload.append(
            {
                "dimension": dim.dimension,
                "level": dim.risk_level,
                "risk_factors": dim.risk_factors,
                "missing_data": dim.missing_data,
                "explanation": dim.explanation,
                "limitations": dim.limitations,
                "evidence_sources": list(sources.values()),
            }
        )

    return {
        "id": assessment.id,
        "overall_level": assessment.overall_level,
        "urgency": assessment.urgency,
        "rule_engine_version": assessment.rule_engine_version,
        "knowledge_version": assessment.knowledge_version,
        "created_at": assessment.created_at,
        "profile_version": assessment.profile_version,
        "dimensions": dim_payload,
        "recommendations": [
            {
                "id": rec.id,
                "dimension": rec.dimension,
                "category": rec.category,
                "priority": rec.priority,
                "title": rec.title,
                "description": rec.description,
                "action_items": rec.action_items,
                "cautions": rec.cautions,
                "requires_professional_consultation": rec.requires_professional_consultation,
            }
            for rec in recs
        ],
    }


async def list_latest(session: AsyncSession, user_id: UUID, limit: int = 20) -> list[dict[str, Any]]:
    rows = await session.scalars(
        select(RiskAssessment)
        .where(RiskAssessment.user_id == user_id)
        .order_by(RiskAssessment.created_at.desc())
        .limit(limit)
    )
    return [
        {
            "id": item.id,
            "overall_level": item.overall_level,
            "urgency": item.urgency,
            "created_at": item.created_at,
            "profile_version": item.profile_version,
        }
        for item in rows
    ]


async def latest_full(session: AsyncSession, user_id: UUID) -> dict[str, Any] | None:
    assessment = await session.scalar(
        select(RiskAssessment)
        .where(RiskAssessment.user_id == user_id)
        .order_by(RiskAssessment.created_at.desc())
        .limit(1)
    )
    if assessment is None:
        return None
    return await detail(session, user_id, assessment.id)
