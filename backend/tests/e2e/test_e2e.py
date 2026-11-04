"""全链路用例，对应 docs/impact 的 E2E-01 至 E2E-04。

这些用例故意走完整的 SSE 流程，直接调接口会绕过 interrupt 与落库时机的耦合。
"""

from tests.helpers import (
    activate_plan,
    collect_events,
    confirm_profile,
    new_conversation,
    patch_profile,
    run_assessment_to_report,
    start_assessment,
    today_task_id,
)


async def test_e2e_01_login_to_report(client, auth):
    await run_assessment_to_report(client, auth)

    assessment = await client.get("/api/v1/assessments/latest", headers=auth)
    data = assessment.json()["data"]
    assert data["overall_level"] in ("中", "高")
    assert len(data["dimensions"]) == 5

    plans = await client.get("/api/v1/plans", headers=auth)
    assert plans.json()["data"][0]["status"] == "active"

    reports = await client.get("/api/v1/reports", headers=auth)
    assert reports.json()["data"][0]["report_type"] == "assessment"


async def test_e2e_02_plan_checkin_summary(client, auth):
    plan = await activate_plan(client, auth)

    task_id = today_task_id(plan)
    checkin = await client.post(
        f"/api/v1/tasks/{task_id}/checkins",
        headers=auth,
        json={"status": "completed"},
    )
    assert checkin.status_code == 200

    summary = await client.get("/api/v1/tracking/summary", headers=auth)
    assert summary.status_code == 200
    data = summary.json()["data"]
    assert data["task_completed"] >= 1
    assert data["completion_rate"] > 0
    assert data["period_start"] <= data["period_end"]


async def test_e2e_03_emergency_blocks_normal_flow(client, auth):
    conversation_id = await new_conversation(client, auth)
    events = await collect_events(
        client,
        "POST",
        f"/api/v1/conversations/{conversation_id}/messages/stream",
        auth,
        {"content": "现在突然胸痛，喘不上气"},
    )
    names = [name for name, _ in events]
    assert "confirmation_required" not in names

    reply = next(data["content"] for name, data in events if name == "token")
    assert "120" in reply
    assert "急诊" in reply

    # 高危分支直接结束，不产生评估与计划
    assessments = await client.get("/api/v1/assessments", headers=auth)
    assert assessments.json()["data"]["total"] == 0
    plans = await client.get("/api/v1/plans", headers=auth)
    assert plans.json()["data"] == []


async def test_e2e_04_resume_does_not_duplicate_writes(client, auth):
    await patch_profile(client, auth)
    profile_confirm = await start_assessment(client, auth)
    plan_confirm = await confirm_profile(client, auth, profile_confirm["run_id"])

    events = await collect_events(
        client,
        "POST",
        f"/api/v1/runs/{plan_confirm['run_id']}/resume/stream",
        auth,
        {
            "approval_type": "plan",
            "decision": "approve",
            "business_id": plan_confirm["plan_id"],
            "version_id": plan_confirm["plan_version_id"],
        },
    )
    assert "run_completed" in [name for name, _ in events]

    # 两次中断两次恢复，评估、计划、报告各只应有一条
    assessments = await client.get("/api/v1/assessments", headers=auth)
    assert assessments.json()["data"]["total"] == 1
    plans = await client.get("/api/v1/plans", headers=auth)
    assert len(plans.json()["data"]) == 1
    reports = await client.get("/api/v1/reports", headers=auth)
    assert len(reports.json()["data"]) == 1

    # 同一版本重复确认要被拒，不能靠前端按钮置灰兜住
    again = await client.post(
        f"/api/v1/plans/{plan_confirm['plan_id']}/approve",
        headers=auth,
        json={"version_id": plan_confirm["plan_version_id"]},
    )
    assert again.status_code == 409
