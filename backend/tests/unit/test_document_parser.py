import io
from pathlib import Path

from pypdf import PdfWriter

from app.services import document_parser


def codes(fields) -> dict[str, float]:
    return {item.metric_code: item.value for item in fields}


def test_bp_pair_line() -> None:
    result = codes(document_parser.parse_text("血压 138/88 mmHg"))
    assert result == {"systolic_bp": 138.0, "diastolic_bp": 88.0}


def test_bp_separate_lines() -> None:
    result = codes(document_parser.parse_text("收缩压：150\n舒张压：95"))
    assert result == {"systolic_bp": 150.0, "diastolic_bp": 95.0}


def test_bp_pair_wins_over_lonely_numbers() -> None:
    text = "本次血压 132/84，历史收缩压 150"
    result = codes(document_parser.parse_text(text))
    # 同一编码只取第一次命中，合并写法的值排在前
    assert result["systolic_bp"] == 132.0
    assert result["diastolic_bp"] == 84.0


def test_mgdl_converted_to_mmol() -> None:
    text = "空腹血糖 140 mg/dL  甘油三酯 204 mg/dL  低密度脂蛋白 158 mg/dL  高密度脂蛋白 42 mg/dL"
    result = codes(document_parser.parse_text(text))
    assert result["fasting_glucose"] == 7.78
    assert result["triglycerides"] == 2.3
    assert result["ldl_c"] == 4.09
    assert result["hdl_c"] == 1.09


def test_mmol_left_alone() -> None:
    result = codes(document_parser.parse_text("低密度脂蛋白 4.10 mmol/L"))
    assert result["ldl_c"] == 4.1


def test_out_of_range_dropped() -> None:
    result = document_parser.parse_text("心率 999  体重 3  腰围 500")
    assert result == []


def test_unknown_metric_ignored() -> None:
    # 总胆固醇不在指标表里，识别到也不出现在结果里，避免给出无法落库的字段
    result = document_parser.parse_text("总胆固醇 6.2 mmol/L")
    assert result == []


def test_empty_text() -> None:
    assert document_parser.parse_text("本报告仅供参考") == []


def test_image_is_unsupported(tmp_path: Path) -> None:
    path = tmp_path / "a.png"
    path.write_bytes(b"\x89PNG\r\n\x1a\n")
    outcome = document_parser.parse_document(path, "image/png")
    assert outcome.status == "unsupported"
    assert outcome.fields == []
    assert "图片" in outcome.message


def test_pdf_without_text_layer(tmp_path: Path) -> None:
    path = tmp_path / "blank.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=595, height=842)
    buffer = io.BytesIO()
    writer.write(buffer)
    path.write_bytes(buffer.getvalue())

    outcome = document_parser.parse_document(path, "application/pdf")
    assert outcome.status == "unsupported"
    assert "文字层" in outcome.message


def test_broken_pdf_reports_failed(tmp_path: Path) -> None:
    path = tmp_path / "broken.pdf"
    path.write_bytes(b"%PDF-1.4\nthis is not a real pdf")
    outcome = document_parser.parse_document(path, "application/pdf")
    assert outcome.status == "failed"
    assert outcome.fields == []
