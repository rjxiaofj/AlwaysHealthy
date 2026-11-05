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


def _escape(value: Any) -> str:
    # 报告内容可能夹带用户输入，进 HTML 前转义，别让一段文字变成可执行的标签
    text = str(value)
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def to_print_html(report: dict[str, Any]) -> str:
    """把报告渲染成独立的、打印友好的 HTML。

    用户在浏览器里打开这个页面，用系统的「打印 → 另存为 PDF」就能拿到排版干净的
    PDF，不必在后端引 weasyprint/reportlab 这类重依赖。样式全部内联，无外部资源，
    离线也能打印。
    """
    content = report["content"]
    level = content.get("overall_level")
    sections_html: list[str] = []
    for section in content.get("sections", []):
        paragraphs = "".join(f"<p>{_escape(line)}</p>" for line in section.get("paragraphs", []))
        items = "".join(f"<li>{_escape(item)}</li>" for item in section.get("items", []))
        items_html = f"<ul>{items}</ul>" if items else ""
        sections_html.append(
            f"<section><h2>{_escape(section['heading'])}</h2>{paragraphs}{items_html}</section>"
        )

    disclaimer = _escape(content.get("disclaimer", "本报告仅供健康管理参考，不构成诊断。"))
    level_html = f'<span class="level">{_escape(level)}</span>' if level else ""

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_escape(report['title'])}</title>
<style>
  :root {{ color-scheme: light; }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; padding: 40px 48px;
    font-family: -apple-system, "Segoe UI", "Microsoft YaHei", sans-serif;
    color: #1f2937; line-height: 1.7; font-size: 14px;
    max-width: 820px; margin: 0 auto;
  }}
  header {{ border-bottom: 2px solid #e5e7eb; padding-bottom: 16px; margin-bottom: 24px; }}
  h1 {{ font-size: 24px; margin: 0 0 8px; }}
  .meta {{ color: #6b7280; font-size: 13px; }}
  .level {{
    display: inline-block; margin-top: 8px; padding: 2px 10px;
    border-radius: 999px; background: #f3f4f6; color: #374151; font-size: 13px;
  }}
  .disclaimer {{ color: #6b7280; font-size: 12px; margin: 0 0 24px; }}
  section {{ margin-bottom: 22px; }}
  h2 {{ font-size: 16px; margin: 0 0 8px; color: #111827; }}
  p {{ margin: 4px 0; }}
  ul {{ margin: 6px 0; padding-left: 20px; }}
  li {{ margin: 3px 0; }}
  @media print {{
    body {{ padding: 0; }}
    section {{ break-inside: avoid; }}
  }}
</style>
</head>
<body>
  <header>
    <h1>{_escape(report['title'])}</h1>
    <div class="meta">生成时间：{report['created_at']:%Y-%m-%d %H:%M}</div>
    {level_html}
  </header>
  <p class="disclaimer">{disclaimer}</p>
  {"".join(sections_html)}
</body>
</html>
"""
