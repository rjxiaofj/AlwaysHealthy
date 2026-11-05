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

from pathlib import Path
import re

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


def _top_level_fields(body: str) -> set[str]:
    """只取最外层的 `key:` / `key?:`。

    嵌套对象（`ReportDetail.content`）里的键属于后端自己拼的 dict，不在这里比，
    靠 `depth` 跳过——一行进入嵌套后 depth 就不为 0，直到对应的大括号关上。
    """
    fields: set[str] = set()
    depth = 0
    for raw in body.splitlines():
        line = raw.strip()
        if depth == 0:
            match = re.match(r"([A-Za-z_]\w*)\??\s*:", line)
            if match:
                fields.add(match.group(1))
        depth += line.count("{") - line.count("}")
    return fields


def _parse_types_file() -> tuple[dict[str, set[str]], set[str]]:
    """返回 (接口字段表, 泛型接口名集合)。"""
    text = _strip_comments(TYPES_FILE.read_text(encoding="utf-8"))
    interfaces: dict[str, set[str]] = {}
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

    missing = sorted(declared - set(model.model_fields))
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


# ---------------------------------------------------------------- 运行时：dict 响应


def _missing(actual: dict, interface: str) -> list[str]:
    return sorted(INTERFACES[interface] - set(actual))


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
