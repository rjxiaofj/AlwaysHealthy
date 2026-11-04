from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFound
from app.db.models import HealthReport
from app.repositories import chat as chat_repo


async def save_report(
    session: AsyncSession,
    user_id: UUID,
    *,
    payload: dict[str, Any],
    assessment_id: UUID | None,
    tracking_summary_id: UUID | None = None,
) -> HealthReport:
    report = HealthReport(
        user_id=user_id,
        assessment_id=assessment_id,
        tracking_summary_id=tracking_summary_id,
        report_type=payload.get("report_type", "assessment"),
        title=payload.get("title", "健康评估报告"),
        content_snapshot=payload,
    )
    session.add(report)
    await session.commit()
    return report


async def list_reports(session: AsyncSession, user_id: UUID) -> list[dict[str, Any]]:
    rows = await chat_repo.reports_of(session, user_id)
    return [
        {
            "id": row.id,
            "report_type": row.report_type,
            "title": row.title,
            "created_at": row.created_at,
        }
        for row in rows
    ]


async def detail(session: AsyncSession, user_id: UUID, report_id: UUID) -> dict[str, Any]:
    row = await chat_repo.report_of(session, user_id, report_id)
    if row is None:
        raise NotFound("报告不存在")
    return {
        "id": row.id,
        "report_type": row.report_type,
        "title": row.title,
        "content": row.content_snapshot,
        "created_at": row.created_at,
    }


def to_markdown(report: dict[str, Any]) -> str:
    content = report["content"]
    lines = [f"# {report['title']}", "", f"生成时间：{report['created_at']:%Y-%m-%d %H:%M}", ""]
    lines.append(content.get("disclaimer", "本报告仅供健康管理参考，不构成诊断。"))
    lines.append("")
    for section in content.get("sections", []):
        lines.append(f"## {section['heading']}")
        lines.extend(section.get("paragraphs", []))
        if lines and lines[-1] != "":
            lines.append("")
        for item in section.get("items", []):
            lines.append(f"- {item}")
        lines.append("")
    return "\n".join(lines).strip() + "\n"
