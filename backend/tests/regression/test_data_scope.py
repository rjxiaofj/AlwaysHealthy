"""数据范围用例，对应 docs/impact 的 RT-05，覆盖权限检查项 1 至 3。

越权一律返回 404 而不是 403，避免用状态码反推资源是否存在。
"""

from tests.helpers import (
    activate_plan,
    new_conversation,
    register_another,
    run_assessment_to_report,
    today_task_id,
)


async def test_rt_05a_other_user_cannot_read_plan_and_task(client, auth):
    plan = await activate_plan(client, auth)
    task_id = today_task_id(plan)
    other = await register_another(client)

    detail = await client.get(f"/api/v1/plans/{plan['id']}", headers=other)
    assert detail.status_code == 404
    assert detail.json()["code"] == "RESOURCE_NOT_FOUND"

    checkin = await client.post(
        f"/api/v1/tasks/{task_id}/checkins",
        headers=other,
        json={"status": "completed"},
    )
    assert checkin.status_code == 404


async def test_rt_05b_other_user_cannot_read_report(client, auth):
    await run_assessment_to_report(client, auth)
    report_id = (await client.get("/api/v1/reports", headers=auth)).json()["data"][0]["id"]
    other = await register_another(client)

    response = await client.get(f"/api/v1/reports/{report_id}", headers=other)
    assert response.status_code == 404

    export = await client.get(f"/api/v1/reports/{report_id}/export", headers=other)
    assert export.status_code == 404


async def test_rt_05c_other_user_cannot_read_conversation(client, auth):
    conversation_id = await new_conversation(client, auth)
    other = await register_another(client)

    response = await client.get(f"/api/v1/conversations/{conversation_id}", headers=other)
    assert response.status_code == 404

    messages = await client.get(f"/api/v1/conversations/{conversation_id}/messages", headers=other)
    assert messages.status_code == 404


async def test_rt_05d_unauthenticated_cannot_touch_business_api(client):
    for url in ("/api/v1/plans", "/api/v1/assessments", "/api/v1/reports", "/api/v1/reminders"):
        response = await client.get(url)
        assert response.status_code == 401
        assert response.json()["code"] == "AUTH_UNAUTHORIZED"
