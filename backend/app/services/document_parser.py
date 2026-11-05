import re
from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader

from app.core.logging import get_logger
from app.tools.metrics import METRIC_DEFS

log = get_logger(__name__)

# 演示环境够用，超大报告不做分片解析
MAX_PAGES = 30
MAX_TEXT_CHARS = 200_000

# 报告里的血脂血糖常用 mg/dL，换算成 METRIC_DEFS 约定的单位需要除以这个系数
UNIT_DIVISORS = {
    "fasting_glucose": 18.0,
    "ldl_c": 38.67,
    "hdl_c": 38.67,
    "triglycerides": 88.57,
}

UNIT_WINDOW = 16


@dataclass(frozen=True)
class Rule:
    metric_code: str
    patterns: tuple[str, ...]


# 只认常见检验单写法。数值后面必须能落到取值区间，否则当作误匹配丢掉
RULES: tuple[Rule, ...] = (
    Rule("systolic_bp", (r"收缩压\D{0,6}(\d{2,3})",)),
    Rule("diastolic_bp", (r"舒张压\D{0,6}(\d{2,3})",)),
    Rule("heart_rate", (r"(?:静息)?心率\D{0,6}(\d{2,3})",)),
    Rule("weight_kg", (r"体重\D{0,6}(\d{2,3}(?:\.\d)?)",)),
    Rule("waist_cm", (r"腰围\D{0,6}(\d{2,3}(?:\.\d)?)",)),
    Rule("fasting_glucose", (r"空腹血糖\D{0,6}(\d{1,3}(?:\.\d{1,2})?)", r"血糖\D{0,6}(\d{1,3}(?:\.\d{1,2})?)")),
    Rule("hba1c", (r"糖化血红蛋白\D{0,6}(\d{1,2}(?:\.\d{1,2})?)",)),
    Rule("ldl_c", (r"低密度脂蛋白\D{0,6}(\d{1,3}(?:\.\d{1,2})?)",)),
    Rule("hdl_c", (r"高密度脂蛋白\D{0,6}(\d{1,3}(?:\.\d{1,2})?)",)),
    Rule("triglycerides", (r"甘油三酯\D{0,6}(\d{1,3}(?:\.\d{1,2})?)",)),
)

# 血压常写成一行两个数，单独认一次
BLOOD_PRESSURE_PAIR = r"血压\D{0,6}(\d{2,3})\s*/\s*(\d{2,3})"


@dataclass(frozen=True)
class ExtractedField:
    metric_code: str
    value: float
    raw: str


@dataclass
class ParseOutcome:
    status: str
    fields: list[ExtractedField]
    message: str


def _to_float(text: str) -> float | None:
    try:
        return float(text)
    except ValueError:
        return None


def _normalize(code: str, value: float, window: str) -> float | None:
    # 血糖血脂按 mg/dL 记时数值会大一个量级，靠命中位置后面的单位判断
    if "mg/dl" in window.lower() and code in UNIT_DIVISORS:
        return value / UNIT_DIVISORS[code]
    return value


def _in_range(code: str, value: float) -> bool:
    definition = METRIC_DEFS.get(code)
    if definition is None:
        return False
    return definition.low <= value <= definition.high


def _accept(
    code: str,
    value: float,
    raw: str,
    position: int,
    found: dict[str, tuple[int, "ExtractedField"]],
) -> None:
    if not _in_range(code, value):
        return
    # 体检单靠前的是本次结果，后面的多为历史对比列，同编码取位置最靠前的一条
    current = found.get(code)
    if current is not None and current[0] <= position:
        return
    found[code] = (position, ExtractedField(metric_code=code, value=round(value, 2), raw=raw.strip()))


def parse_text(text: str) -> list[ExtractedField]:
    """从纯文本里抽候选指标。同一编码按原文位置取第一条，其余由用户核对原文后决定。"""
    found: dict[str, tuple[int, ExtractedField]] = {}

    for rule in RULES:
        for pattern in rule.patterns:
            match = re.search(pattern, text)
            if match is None:
                continue
            value = _to_float(match.group(1))
            if value is None:
                continue
            window = text[match.end() : match.end() + UNIT_WINDOW]
            value = _normalize(rule.metric_code, value, window)
            if value is not None:
                _accept(rule.metric_code, value, match.group(0), match.start(), found)
            break

    pair = re.search(BLOOD_PRESSURE_PAIR, text)
    if pair is not None:
        systolic = _to_float(pair.group(1))
        diastolic = _to_float(pair.group(2))
        if systolic is not None:
            _accept("systolic_bp", systolic, pair.group(0), pair.start(), found)
        if diastolic is not None:
            _accept("diastolic_bp", diastolic, pair.group(0), pair.start(), found)

    ordered = sorted(found.values(), key=lambda item: item[0])
    return [field for _, field in ordered]


def extract_pdf_text(path: Path) -> tuple[str, int]:
    reader = PdfReader(str(path))
    pages = reader.pages[:MAX_PAGES]
    chunks: list[str] = []
    for page in pages:
        chunks.append(page.extract_text() or "")
        if sum(len(chunk) for chunk in chunks) > MAX_TEXT_CHARS:
            break
    return "\n".join(chunks), len(reader.pages)


def parse_document(path: Path, mime_type: str) -> ParseOutcome:
    if mime_type != "application/pdf":
        # 没有 OCR 能力，图片只保存不解析，不假装读过
        return ParseOutcome("unsupported", [], "图片资料暂不支持文字识别，仅保存原件")

    try:
        text, page_count = extract_pdf_text(path)
    except Exception as exc:
        log.warning("pdf extract failed path=%s err=%s", path.name, exc)
        return ParseOutcome("failed", [], "文件无法解析，可能已损坏或加密")

    if not text.strip():
        return ParseOutcome("unsupported", [], "没有可读取的文字层，可能是扫描件")

    fields = parse_text(text)
    if not fields:
        return ParseOutcome("parsed", [], f"读取 {page_count} 页，未发现可识别的指标")

    return ParseOutcome("parsed", fields, f"读取 {page_count} 页，识别出 {len(fields)} 项指标")
