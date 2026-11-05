from uuid import UUID

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user, db_session
from app.core.response import ok
from app.db.models import User
from app.services import report_service

router = APIRouter(tags=["report"])


@router.get("/reports")
async def list_reports(
    request: Request,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(db_session),
):
    return ok(request, await report_service.list_reports(session, user.id))


@router.get("/reports/{report_id}")
async def report_detail(
    report_id: UUID,
    request: Request,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(db_session),
):
    return ok(request, await report_service.detail(session, user.id, report_id))


@router.get("/reports/{report_id}/export")
async def export_report(
    report_id: UUID,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(db_session),
):
    report = await report_service.detail(session, user.id, report_id)
    markdown = report_service.to_markdown(report)
    return Response(
        content=markdown.encode("utf-8"),
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="report-{report_id}.md"'},
    )


@router.get("/reports/{report_id}/print")
async def print_report(
    report_id: UUID,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(db_session),
):
    """打印友好版：返回独立 HTML，浏览器「打印 → 另存为 PDF」即可导出 PDF。"""
    report = await report_service.detail(session, user.id, report_id)
    html = report_service.to_print_html(report)
    return Response(content=html.encode("utf-8"), media_type="text/html; charset=utf-8")
