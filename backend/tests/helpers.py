"""接口用例共用的流程片段。

用例编号与 docs/impact 的回归清单一一对应，改流程时从这里改，避免同一段
SSE 解析和三步确认散落在多个文件里各写一份。
"""

import json
from datetime import date

# 覆盖血压、血糖、体重、运动、久坐、睡眠、饮食、吸烟多个维度，
# 改动这段文本会让多数用例的风险等级断言失效
ASSESS_TEXT = (
    "我今年39岁，男，身高175，体重88公斤，血压150/95，"
    "每周运动1天，久坐9小时，睡眠6小时，口味重，吸烟"
)


async def collect_events(client, method, url, headers=None, payload=None):
    events = []
    current = None
    async with client.stream(method, url, headers=headers, json=payload) as response:
        assert response.status_code == 200
        async for line in response.aiter_lines():
            if line.startswith("event: "):
                current = line[7:]
            elif line.startswith("data: ") and current:
                events.append((current, json.loads(line[6:])))
                current = None
    return events


async def new_conversation(client, headers):
    response = await client.post("/api/v1/conversations", headers=headers, json={})
    return response.json()["data"]["id"]


async def patch_profile(client, headers, **fields):
    payload = {
        "birth_date": "1986-05-01",
        "sex": "male",
        "height_cm": 175,
        "weight_kg": 88,
    }
    payload.update(fields)
    response = await client.patch("/api/v1/profiles/me", headers=headers, json=payload)
    assert response.status_code == 200
    return response.json()["data"]


async def register_another(client):
    """建一个与当前用户无关的账号，用于验证数据范围。"""
    import uuid

    response = await client.post(
        "/api/v1/auth/register",
        json={"username": f"u{uuid.uuid4().hex[:10]}", "password": "demo12345"},
    )
    return {"Authorization": f"Bearer {response.json()['data']['access_token']}"}


async def start_assessment(client, headers, text=ASSESS_TEXT):
    """走完一次消息流，停在画像确认。返回 confirmation_required 的数据。"""
    conversation_id = await new_conversation(client, headers)
    events = await collect_events(
        client,
        "POST",
        f"/api/v1/conversations/{conversation_id}/messages/stream",
        headers,
        {"content": text},
    )
    return next(data for name, data in events if name == "confirmation_required")


async def confirm_profile(client, headers, run_id):
    """确认画像后停在计划确认。返回 confirmation_required 的数据。"""
    events = await collect_events(
        client,
        "POST",
        f"/api/v1/runs/{run_id}/resume/stream",
        headers,
        {"approval_type": "profile", "decision": "approve"},
    )
    return next(data for name, data in events if name == "confirmation_required")


async def reach_plan_review(client, headers, text=ASSESS_TEXT):
    """从空账号走到计划待确认，返回计划确认数据。"""
    await patch_profile(client, headers)
    profile_confirm = await start_assessment(client, headers, text)
    return await confirm_profile(client, headers, profile_confirm["run_id"])


async def approve_plan(client, headers, plan_confirm):
    response = await client.post(
        f"/api/v1/plans/{plan_confirm['plan_id']}/approve",
        headers=headers,
        json={"version_id": plan_confirm["plan_version_id"]},
    )
    assert response.status_code == 200
    return response.json()["data"]


async def activate_plan(client, headers):
    """生成计划并确认，返回已生效的计划详情。"""
    plan_confirm = await reach_plan_review(client, headers)
    return await approve_plan(client, headers, plan_confirm)


def today_task_id(plan_detail):
    """取当天第一个任务。

    计划按 start_date 生成任务，start_date 默认当天，所以当天一定有任务。
    """
    today = date.today().isoformat()
    return next(item["id"] for item in plan_detail["tasks"] if item["scheduled_date"] == today)


async def run_assessment_to_report(client, headers):
    """完整链路：画像确认、计划确认、报告落库。返回各阶段关键数据。"""
    await patch_profile(client, headers)
    profile_confirm = await start_assessment(client, headers)
    plan_confirm = await confirm_profile(client, headers, profile_confirm["run_id"])

    events = await collect_events(
        client,
        "POST",
        f"/api/v1/runs/{plan_confirm['run_id']}/resume/stream",
        headers,
        {
            "approval_type": "plan",
            "decision": "approve",
            "business_id": plan_confirm["plan_id"],
            "version_id": plan_confirm["plan_version_id"],
        },
    )
    return {
        "profile_confirm": profile_confirm,
        "plan_confirm": plan_confirm,
        "plan_events": events,
    }
