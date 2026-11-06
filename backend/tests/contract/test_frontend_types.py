"""前端 `types.ts` 与后端响应契约的一致性守卫。

为什么需要这层：`ProfileOut` 曾经漏了 `age_years`，`get_profile` 明明传了这个值，
pydantic 默认的 `extra='ignore'` 把它静默丢掉，于是前端 `Profile` 接口上写着这个字段、
实际永远是 `undefined`，个人中心一直不显示年龄。`vue-tsc` 查的是类型声明，`pytest` 查的是
后端自己，两边各自都绿，错在两者之间。

所以这里不去猜运行时形状，直接比字段名：前端声明过的字段，后端模型必须有。
只查一个方向——后端多给的字段前端用不上，不算问题；少给的才是（AG-04 就是这一类）。

`types.ts` 里有一部分接口对应的是 service 拼出来的 dict，没有 pydantic 模型，
静态比不了，放在 `NO_MODEL` 里写明原因，另有几条在下面对真实响应取一次键来对。
"""

from datetime import date, datetime, time
from decimal import Decimal
from enum import Enum
from pathlib import Path
import re
from types import UnionType
from typing import Annotated, Any, Literal, Union, get_args, get_origin
from uuid import UUID

import pytest
from pydantic import BaseModel

from app.schemas.chat import ConversationOut, FileOut, MessageOut, ReminderOut, ReportOut, RunOut
from app.schemas.health import (
    AssessmentOut,
    DimensionOut,
    MedicalHistoryOut,
    ProfileOut,
    ProfilePatch,
    RiskFactorOut,
    SourceOut,
    TokenOut,
    UserOut,
)
from app.schemas.plan import AdjustmentOut, PendingTaskOut, PendingVersionOut, PlanOut, TaskOut, VersionOut
from app.schemas.tracking import SummaryOut, TrendOut, TrendPoint
from tests.helpers import activate_plan

TYPES_FILE = Path(__file__).resolve().parents[3] / "frontend" / "src" / "api" / "types.ts"


# ---------------------------------------------------------------- types.ts 解析


def _strip_comments(text: str) -> str:
    return "\n".join(line.split("//", 1)[0] for line in text.splitlines())


def _block_body(text: str, open_index: int) -> str:
    """从 `{` 所在下标开始配对，返回大括号之间的内容。"""
    depth = 0
    for index in range(open_index, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return text[open_index + 1 : index]
    raise AssertionError("types.ts 的大括号没配平，解析器要跟着改")


def _top_level_fields(body: str) -> dict[str, tuple[str, bool]]:
    """只取最外层的 `key:` / `key?:`，返回 {字段名: (类型文本, 是否可选)}。

    嵌套对象（`ReportDetail.content`）里的键属于后端自己拼的 dict，不在这里比，
    靠 `depth` 跳过——一行进入嵌套后 depth 就不为 0，直到对应的大括号关上。
    """
    fields: dict[str, tuple[str, bool]] = {}
    depth = 0
    for raw in body.splitlines():
        line = raw.strip()
        if depth == 0:
            match = re.match(r"([A-Za-z_]\w*)(\??)\s*:\s*(.*)$", line)
            if match:
                fields[match.group(1)] = (match.group(3).strip(), bool(match.group(2)))
        depth += line.count("{") - line.count("}")
    return fields


def _parse_types_file() -> tuple[dict[str, dict[str, tuple[str, bool]]], set[str]]:
    """返回 (接口字段表, 泛型接口名集合)。"""
    text = _strip_comments(TYPES_FILE.read_text(encoding="utf-8"))
    interfaces: dict[str, dict[str, tuple[str, bool]]] = {}
    generics: set[str] = set()
    for match in re.finditer(r"export interface\s+([A-Za-z_]\w*)\s*(<[^>]*>)?\s*\{", text):
        name = match.group(1)
        if match.group(2) is not None:
            # 泛型接口（ApiEnvelope<T>、PageData<T>）在外面套一层，没有对应的后端模型
            generics.add(name)
            continue
        interfaces[name] = _top_level_fields(_block_body(text, match.end() - 1))
    return interfaces, generics


INTERFACES, GENERIC_INTERFACES = _parse_types_file()

MAPPED: dict[str, type[BaseModel]] = {
    "UserInfo": UserOut,
    "TokenPayload": TokenOut,
    "Profile": ProfileOut,
    "ProfilePatchBody": ProfilePatch,
    "MedicalHistory": MedicalHistoryOut,
    "RiskFactor": RiskFactorOut,
    "EvidenceSource": SourceOut,
    "Dimension": DimensionOut,
    "Assessment": AssessmentOut,
    "Task": TaskOut,
    "PlanVersion": VersionOut,
    "PlanAdjustment": AdjustmentOut,
    "PlanPendingTask": PendingTaskOut,
    "PlanPendingVersion": PendingVersionOut,
    "Plan": PlanOut,
    "Conversation": ConversationOut,
    "ChatMessage": MessageOut,
    "RunInfo": RunOut,
    "ReportDetail": ReportOut,
    "Reminder": ReminderOut,
    "FileItem": FileOut,
    "Trend": TrendOut,
    "MetricPoint": TrendPoint,
    "TrackingSummary": SummaryOut,
}

# 这几个是请求体：值是前端发出去的，类型比对的方向要反过来（见 test_frontend_type_width_matches_model）
REQUEST_INTERFACES = {"ProfilePatchBody"}


NO_MODEL: dict[str, str] = {
    "AssessmentSummary": "assessment_service.list_latest 拼 dict，运行时见 test_assessment_summary_keys",
    "PlanSummary": "plan_service.list_plans 拼 dict，运行时见 test_plan_summary_keys",
    "ReportSummary": "GET /reports 由 report_service 拼 dict",
    "ReportSection": "ReportDetail.content 的内部结构，后端按报告类型拼 dict",
    "KnowledgeSource": "knowledge_repo.as_dict 拼的，运行时另有用例",
    "Recommendation": "AssessmentOut.recommendations 是 list[dict]",
    "FeedbackRecord": "tracking_service.list_feedback 拼 dict，运行时另有用例",
    "ConsentRecord": "consent_service.list_records 拼 dict，运行时另有用例",
    "EmergencyEvent": "profiles 端点拼 dict，触发条件见 tests/api/test_emergency_events.py",
    "ExtractedDocument": "file_service 拼 dict，需要上传 PDF，见 tests/api/test_document_extract.py",
    "ExtractedField": "同上",
    "ConfirmationPayload": "SSE 事件里的确认卡片，不经过模型序列化",
    "ServiceStatus": "GET /health/services 在端点里直接拼 dict，运行时见 test_admin_service_status_keys",
    "SecurityIncident": "security_repo.as_dict 拼 dict，运行时见 test_security_incident_keys",
}


# ---------------------------------------------------------------- 静态：字段名


def test_types_file_is_found():
    assert TYPES_FILE.exists(), f"找不到 {TYPES_FILE}，前端目录结构变了，解析路径要跟着改"
    assert len(INTERFACES) > 20, "解析出来的接口数量不对，解析器可能被 types.ts 的写法绊住了"


@pytest.mark.parametrize("interface", sorted(MAPPED))
def test_frontend_fields_exist_in_model(interface: str):
    model = MAPPED[interface]
    declared = INTERFACES.get(interface)
    assert declared is not None, f"types.ts 里已经没有 {interface}，映射表要跟着删"

    missing = sorted(set(declared) - set(model.model_fields))
    assert not missing, (
        f"{interface} 声明了 {missing}，但 {model.__name__} 没有这些字段。"
        "前端拿到的会是 undefined，tsc 与 pytest 都不会报错"
    )


def test_every_interface_is_accounted_for():
    """新增一个前端接口时必须做一次决定：映射到模型，或者写明为什么比不了。"""
    unknown = sorted(set(INTERFACES) - set(MAPPED) - set(NO_MODEL))
    assert not unknown, f"types.ts 新增了 {unknown}，请加进 MAPPED 或 NO_MODEL 并写清原因"

    stale = sorted((set(MAPPED) | set(NO_MODEL)) - set(INTERFACES) - GENERIC_INTERFACES)
    assert not stale, f"{stale} 已经从 types.ts 删掉了，这张表要跟着清"


def _allows_none(annotation) -> bool:
    """模型字段的注解里有没有 None。`Any` 和没写注解的都不算。"""
    if annotation is Any or annotation is None:
        return False
    if annotation is type(None):
        return True
    return any(getattr(item, "__name__", "") == "NoneType" for item in get_args(annotation))


# 前端写的是结构性类型，以下这些跟「能不能是 null」无关，跳过
_SKIP_TS_TYPES = ("Record<", "{", "unknown", "any", "Any")


@pytest.mark.parametrize("interface", sorted(MAPPED))
def test_frontend_allows_null_when_model_can(interface: str):
    """模型可能是 None 的字段，前端必须写 `| null`。

    反过来的错（前端写了 `| null`、模型永远不给 null）只是声明松一点，不会崩；
    这个方向才会崩——模板里写 `item.title.length`，拿到 null 就是运行时错误。
    """
    model = MAPPED[interface]
    declared = INTERFACES.get(interface) or {}
    violations: list[str] = []

    for name, (type_text, optional) in declared.items():
        field = model.model_fields.get(name)
        if field is None or not _allows_none(field.annotation):
            continue
        if optional or "null" in type_text:
            continue
        if any(token in type_text for token in _SKIP_TS_TYPES):
            continue
        violations.append(f"{name}: {type_text}")

    assert not violations, (
        f"{interface} 里这些字段后端可能是 null，但前端声明不允许：{violations}。"
        "补上 `| null`，否则模板里直接读属性会抛 TypeError"
    )


# ---------------------------------------------------------------- 静态：类型宽度

# 比的是「JS 运行时拿到的是哪种值」，不是完整类型。TS 泛型、字面量联合、条件类型
# 这些真要比就得引 TypeScript 编译器，代价远大于收益
_JS_KINDS = {"string", "number", "boolean", "array", "object", "null"}
_WILDCARD = "any"


def _literal_kind(value: object) -> str:
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, str):
        return "string"
    return _WILDCARD


def _annotation_kinds(annotation: object) -> set[str]:
    """pydantic 注解 → 序列化后 JS 那边的类型集合。看不懂的返回 wildcard，不误报。"""
    if annotation is Any or annotation is None:
        return {_WILDCARD}
    if annotation is type(None):
        return {"null"}

    origin = get_origin(annotation)
    args = get_args(annotation)

    if origin is Annotated:
        return _annotation_kinds(args[0])
    if origin in (Union, UnionType):
        kinds: set[str] = set()
        for item in args:
            kinds |= _annotation_kinds(item)
        return kinds
    if origin is Literal:
        return {_literal_kind(item) for item in args}
    if origin in (list, set, frozenset, tuple):
        return {"array"}
    if origin is dict:
        return {"object"}

    if isinstance(annotation, type):
        # bool 是 int 的子类，顺序不能反
        if issubclass(annotation, bool):
            return {"boolean"}
        if issubclass(annotation, (int, float, Decimal)):
            return {"number"}
        # datetime / UUID / date 序列化后都是字符串
        if issubclass(annotation, (str, UUID, datetime, date, time)):
            return {"string"}
        if issubclass(annotation, Enum):
            return {"number"} if issubclass(annotation, int) else {"string"}
        if issubclass(annotation, BaseModel):
            return {"object"}

    return {_WILDCARD}


def _ts_kinds(type_text: str) -> set[str]:
    """前端类型文本 → 它能装下的 JS 类型集合。"""
    text = type_text.strip()
    if text.startswith("Record<") or text.startswith("{"):
        # 结构化声明里的 | 属于内层，先认整体
        return {"object"}

    kinds: set[str] = set()
    for raw in text.split("|"):
        member = raw.strip().strip("()").strip()
        lowered = member.lower()
        if lowered in ("null", "undefined"):
            kinds.add("null")
        elif lowered in (_WILDCARD, "unknown"):
            kinds.add(_WILDCARD)
        elif lowered in ("string", "number", "boolean"):
            kinds.add(lowered)
        elif member.endswith("[]") or member.startswith("Array<"):
            kinds.add("array")
        elif member.startswith("'") or member.startswith('"'):
            kinds.add("string")
        elif re.fullmatch(r"[A-Za-z_][\w.]*", member):
            # 命名的接口：types.ts 里这些名字都是 interface，序列化出来是对象
            kinds.add("object")
        else:
            kinds.add(_WILDCARD)
    return kinds


def _single(kinds: set[str]) -> str | None:
    """只有一个明确类型时返回它。联合类型与通配符都不猜，返回 None 表示「不比这一层」。"""
    if len(kinds) != 1:
        return None
    kind = next(iter(kinds))
    return None if kind == _WILDCARD else kind


def _annotation_element(annotation: object) -> str | None:
    """列表元素 / dict 值的类型。`list[str | None]` 这种联合不猜。"""
    origin = get_origin(annotation)
    args = get_args(annotation)
    if origin is Annotated:
        return _annotation_element(args[0])
    if origin is dict:
        return _single(_annotation_kinds(args[1])) if len(args) == 2 else None
    if origin in (list, set, frozenset, tuple):
        return _single(_annotation_kinds(args[0])) if args else None
    return None


_ARRAY_SUFFIX = re.compile(r"^(?P<inner>.+)\[\]$")
_ARRAY_GENERIC = re.compile(r"^Array<(?P<inner>.+)>$")
_RECORD_GENERIC = re.compile(r"^Record<[^,]+,\s*(?P<inner>.+)>$")


def _ts_element(type_text: str) -> str | None:
    """前端声明里的元素类型：`Foo[]`、`Array<Foo>`、`Record<string, Foo>`。"""
    text = type_text.strip()
    for pattern in (_ARRAY_SUFFIX, _ARRAY_GENERIC, _RECORD_GENERIC):
        match = pattern.match(text)
        if match:
            return _single(_ts_kinds(match.group("inner")))
    return None


@pytest.mark.parametrize("interface", sorted(MAPPED))
def test_frontend_type_width_matches_model(interface: str):
    """前端声明的类型必须装得下后端真正给的值。

    只查「后端给的 JS 类型 ⊆ 前端声明」，前端写得比后端宽不算错——`string | null`
    装在永远有值的字段上是保守，不是缺陷。反过来的错才是运行时崩：后端给字符串、
    前端声明 number，模板里 `.toFixed()` 直接炸，而 tsc 与 pytest 都不会响。

    `ProfilePatchBody` 这种请求体方向相反：值是前端发出去的，要验的是「前端可能发
    的类型，后端接得住」。后端宽松（`dict | None`）而前端只发对象，那是正常的。
    """
    model = MAPPED[interface]
    declared = INTERFACES.get(interface) or {}
    violations: list[str] = []

    for name, (type_text, _optional) in declared.items():
        field = model.model_fields.get(name)
        if field is None:
            continue
        backend = _annotation_kinds(field.annotation)
        frontend = _ts_kinds(type_text)
        if _WILDCARD in backend or _WILDCARD in frontend:
            continue

        if interface in REQUEST_INTERFACES:
            problem = sorted(frontend - backend)
            if problem:
                violations.append(f"{name}: 前端可能发 {sorted(frontend)}，后端只接 {sorted(backend)}")
        else:
            problem = sorted(backend - frontend)
            if problem:
                violations.append(f"{name}: 后端 {sorted(backend)}，前端写的是 {type_text!r}")

        # 容器对了，里面的东西也可能不对：`list[int]` 写成 `string[]`，模板里对元素
        # 调 `.toFixed()` 一样炸。两边都能定成一个类型时才比，联合与通配符跳过
        backend_element = _annotation_element(field.annotation)
        frontend_element = _ts_element(type_text)
        if backend_element and frontend_element and backend_element != frontend_element:
            violations.append(
                f"{name}: 元素类型后端是 {backend_element}，前端声明 {type_text!r} 里是 {frontend_element}"
            )

    assert not violations, (
        f"{interface} 里这些字段前后端的类型对不上：{violations}。"
        "tsc 只信声明，运行时不会替你转换"
    )


def test_annotation_kinds_mapping_is_what_the_frontend_sees():
    """把「注解 → JS 类型」这张表钉住。改了映射就等于改了守卫的判断标准。"""
    assert _annotation_kinds(int) == {"number"}
    assert _annotation_kinds(bool) == {"boolean"}
    assert _annotation_kinds(UUID) == {"string"}
    assert _annotation_kinds(datetime) == {"string"}
    assert _annotation_kinds(date) == {"string"}
    assert _annotation_kinds(Decimal) == {"number"}
    assert _annotation_kinds(list[int]) == {"array"}
    assert _annotation_kinds(dict[str, Any]) == {"object"}
    assert _annotation_kinds(Literal["male", "female"]) == {"string"}
    assert _annotation_kinds(Literal[1, 2]) == {"number"}
    assert _annotation_kinds(str | None) == {"string", "null"}
    assert _annotation_kinds(Annotated[int, "约束"]) == {"number"}


def test_element_types_are_mapped_consistently():
    """元素层的一小张表。容器对了、里面错了，是这一类里最容易漏的。"""
    assert _annotation_element(list[str]) == "string"
    assert _annotation_element(list[ProfileOut]) == "object"
    assert _annotation_element(dict[str, int]) == "number"
    assert _annotation_element(list[str | None]) is None
    assert _annotation_element(dict[str, Any]) is None
    assert _annotation_element(str) is None

    assert _ts_element("string[]") == "string"
    assert _ts_element("MetricPoint[]") == "object"
    assert _ts_element("Array<number>") == "number"
    assert _ts_element("Record<string, number>") == "number"
    assert _ts_element("number | null") is None
    assert _ts_element("string") is None


def test_ts_kinds_parsing_handles_the_shapes_types_file_uses():
    assert _ts_kinds("string") == {"string"}
    assert _ts_kinds("string | null") == {"string", "null"}
    assert _ts_kinds("MetricPoint[]") == {"array"}
    assert _ts_kinds("Record<string, number | string>") == {"object"}
    assert _ts_kinds("MedicalHistory") == {"object"}
    assert _ts_kinds("unknown") == {_WILDCARD}


# ---------------------------------------------------------------- 运行时：dict 响应

def _missing(actual: dict, interface: str) -> list[str]:
    return sorted(set(INTERFACES[interface]) - set(actual))


@pytest.mark.asyncio
async def test_profile_response_keys(client, auth):
    """AG-04 的防线：这条断言在漏 `age_years` 时会直接挂。"""
    response = await client.get("/api/v1/profiles/me", headers=auth)
    assert response.status_code == 200
    data = response.json()["data"]

    assert _missing(data, "Profile") == []
    assert "age_years" in data


@pytest.mark.asyncio
async def test_feedback_list_keys(client, auth):
    created = await client.post("/api/v1/tracking/feedback", headers=auth, json={"mood_status": "good"})
    assert created.status_code == 200

    response = await client.get("/api/v1/tracking/feedback", headers=auth)
    assert response.status_code == 200
    items = response.json()["data"]

    assert items, "刚记了一条感受，列表不该是空的"
    assert _missing(items[0], "FeedbackRecord") == []


@pytest.mark.asyncio
async def test_consent_list_keys(client, auth):
    created = await client.post(
        "/api/v1/consents",
        headers=auth,
        json={"consent_type": "health_data", "granted": True},
    )
    assert created.status_code == 200

    response = await client.get("/api/v1/consents", headers=auth)
    assert response.status_code == 200
    items = response.json()["data"]

    assert items
    assert _missing(items[0], "ConsentRecord") == []


@pytest.mark.asyncio
async def test_knowledge_source_keys(client, auth):
    response = await client.get("/api/v1/knowledge/sources", headers=auth)
    assert response.status_code == 200
    items = response.json()["data"]

    assert items, "知识库语料没导入，这条断言就成了空转"
    assert _missing(items[0], "KnowledgeSource") == []


@pytest.mark.asyncio
async def test_plan_summary_keys(client, auth):
    """首页拿 `GET /plans` 找生效中的计划，`status` 与 `current_version_id` 一改名就白屏。"""
    await activate_plan(client, auth)

    response = await client.get("/api/v1/plans", headers=auth)
    assert response.status_code == 200
    items = response.json()["data"]

    assert items
    assert _missing(items[0], "PlanSummary") == []


@pytest.mark.asyncio
async def test_assessment_summary_keys(client, auth):
    await activate_plan(client, auth)

    response = await client.get("/api/v1/assessments", headers=auth)
    assert response.status_code == 200
    page = response.json()["data"]

    assert page["items"], "刚走完一次评估，历史列表不该是空的"
    assert _missing(page["items"][0], "AssessmentSummary") == []


async def _make_admin(session, username: str) -> None:
    from sqlalchemy import select, update

    from app.db.models import User

    user_id = await session.scalar(select(User.id).where(User.username == username))
    await session.execute(update(User).where(User.id == user_id).values(role="admin"))
    await session.commit()


@pytest.mark.asyncio
async def test_admin_service_status_keys(client, auth, session):
    """管理页第一张卡片的字段，端点拼 dict 少了键前端就会显示 undefined。"""
    await _make_admin(session, auth["username"])

    # /health/* 挂在 app 根路径，不在 /api/v1 下（compose healthcheck 也用 /health/live）
    response = await client.get("/health/services", headers=auth)
    assert response.status_code == 200
    assert _missing(response.json()["data"], "ServiceStatus") == []


@pytest.mark.asyncio
async def test_security_incident_keys(client, auth, session):
    """管理页事件列表的字段，security_repo.as_dict 改名会让模板读不到值。"""
    for _ in range(5):
        await client.post("/api/v1/auth/login", json={"username": auth["username"], "password": "wrong-password"})
    await _make_admin(session, auth["username"])

    response = await client.get("/api/v1/security/incidents", headers=auth)
    assert response.status_code == 200
    items = response.json()["data"]
    assert items, "刚触发了 5 次失败，事件列表不该是空的"
    assert _missing(items[0], "SecurityIncident") == []
