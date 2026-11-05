"""to_print_html：报告打印友好版 HTML 的单元测试。

用户点「导出 PDF」实际是打开这个 HTML 用浏览器打印另存。这里测两件要命的事：
① 报告内容里的用户输入必须转义，不能变成可执行的标签（报告内容可能夹带用户填的
   身体感受、计划反馈等自由文本）；② 结构完整，有标题、免责声明、分节与条目。
"""
from datetime import UTC, datetime

from app.services.report_service import to_print_html


def _report(content: dict) -> dict:
    return {
        "id": "00000000-0000-0000-0000-000000000000",
        "report_type": "assessment",
        "title": "健康评估报告",
        "content": content,
        "created_at": datetime(2026, 11, 5, 12, 0, tzinfo=UTC),
    }


def test_escapes_user_content_to_prevent_tag_injection():
    # 报告里可能夹带用户输入，比如计划反馈「<script>alert(1)</script> 感觉不错」
    report = _report(
        {
            "disclaimer": "仅供参考",
            "overall_level": "中风险",
            "sections": [{"heading": "需要关注", "paragraphs": ["<script>alert(1)</script> 与 <b>加粗</b>"], "items": ["<img onerror=alert(1)>"]}],
        }
    )

    html = to_print_html(report)

    assert "<script>" not in html
    assert "<b>" not in html
    assert "<img" not in html
    # 转义后仍是可见文本，不是被吞掉
    assert "&lt;script&gt;" in html
    assert "&lt;b&gt;加粗&lt;/b&gt;" in html


def test_contains_title_meta_disclaimer_and_sections():
    report = _report(
        {
            "disclaimer": "本报告仅供健康管理参考",
            "overall_level": "中风险",
            "sections": [
                {"heading": "五维评估结果", "paragraphs": [], "items": ["血压：偏高", "体重：正常"]},
                {"heading": "个性化建议", "paragraphs": ["每周三次有氧运动"], "items": []},
            ],
        }
    )

    html = to_print_html(report)

    assert "<h1>健康评估报告</h1>" in html
    assert "生成时间：2026-11-05 12:00" in html
    assert "本报告仅供健康管理参考" in html
    assert "五维评估结果" in html
    assert "血压：偏高" in html
    assert "每周三次有氧运动" in html
    assert "中风险" in html


def test_empty_level_omits_badge():
    report = _report({"disclaimer": "", "sections": []})

    html = to_print_html(report)

    assert 'class="level"' not in html


def test_has_print_stylesheet_and_lang():
    report = _report({"disclaimer": "d", "sections": []})

    html = to_print_html(report)

    assert '@media print' in html
    assert 'lang="zh-CN"' in html
    assert "break-inside: avoid" in html


def test_items_become_list():
    report = _report({"disclaimer": "", "sections": [{"heading": "计划", "paragraphs": [], "items": ["任务一", "任务二"]}]})

    html = to_print_html(report)

    assert "<ul>" in html
    assert "<li>任务一</li>" in html
    assert "<li>任务二</li>" in html
