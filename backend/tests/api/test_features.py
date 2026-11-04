"""新增功能用例，对应 docs/impact 的 NH-02 至 NH-07。

NH-01 注册登录与刷新轮换在 test_auth.py。
"""

from datetime import UTC, datetime, timedelta

from tests.helpers import (
    activate_plan,
    approve_plan,
    patch_profile,
    reach_plan_review,
    run_assessment_to_report,
    today_task_id,
)


async def test_nh_02_profile_save_and_bmi(client, auth):
    data = await patch_profile(
        client,
        auth,
        birth_date="1990-01-01",
        sex="female",
        height_cm=165,
        weight_kg=60,
    )
    assert data["bmi"] == 22.0
    assert data["age"] >= 18
    assert data["profile_version"] >= 2


async def test_nh_03_assessment_has_five_dimensions_with_sources(client, auth):
    await patch_profile(client, auth)

    # 只有身高体重时信息不足，这一档不能算低风险
    empty = await client.post("/api/v1/assessments", headers=auth)
    assert empty.status_code == 200
    assert empty.json()["data"]["overall_level"] == "信息不足"

    await patch_profile(
        client,
        auth,
        lifestyle={
            "sleep_hours": 6,
            "exercise_days": 1,
            "sedentary_hours": 9,
            "salt_intake_high": True,
            "smoking_status": "current",
        },
    )
    now = datetime.now(UTC).isoformat()
    await client.post(
        "/api/v1/tracking/metrics",
        headers=auth,
        json={"metric_code": "systolic_bp", "value": 150, "measured_at": now},
    )

    response = await client.post("/api/v1/assessments", headers=auth)
    assert response.status_code == 200
    data = response.json()["data"]

    assert len(data["dimensions"]) == 5
    assert data["overall_level"] in ("中", "高")
    # 结论要能追溯到依据，否则前端解释不了风险从哪来
    assert all("evidence_sources" in item for item in data["dimensions"])
    assert any(item["evidence_sources"] for item in data["dimensions"])

    evidence = await client.get(f"/api/v1/assessments/{data['id']}/evidence", headers=auth)
    assert evidence.status_code == 200
    assert len(evidence.json()["data"]) == 5


async def test_nh_04_plan_generate_approve_checkin_adjust(client, auth):
    plan_confirm = await reach_plan_review(client, auth)
    assert plan_confirm["approval_type"] == "plan"

    detail = await approve_plan(client, auth, plan_confirm)
    assert detail["status"] == "active"
    assert 7 <= detail["duration_days"] <= 30

    task_id = today_task_id(detail)
    checkin = await client.post(
        f"/api/v1/tasks/{task_id}/checkins",
        headers=auth,
        json={"status": "completed", "feedback": "今天完成"},
    )
    assert checkin.status_code == 200
    assert checkin.json()["data"]["status"] == "completed"

    # 同一天重复提交按更新处理，不新增打卡记录
    again = await client.post(
        f"/api/v1/tasks/{task_id}/checkins",
        headers=auth,
        json={"status": "partial"},
    )
    assert again.status_code == 200
    assert again.json()["data"]["id"] == checkin.json()["data"]["id"]
    assert again.json()["data"]["status"] == "partial"

    adjust = await client.post(
        f"/api/v1/plans/{detail['id']}/adjust",
        headers=auth,
        json={"reason": "出差期间任务量偏大"},
    )
    assert adjust.status_code == 200
    assert adjust.json()["data"]["version_no"] == 2

    after = await client.get(f"/api/v1/plans/{detail['id']}", headers=auth)
    versions = after.json()["data"]["versions"]
    assert [item["version_no"] for item in versions] == [1, 2]
    # 调整只生成草稿，已生效版本保持 active
    assert versions[0]["status"] == "active"
    assert versions[1]["status"] == "draft"


async def test_nh_05_metric_records_and_trends(client, auth):
    now = datetime.now(UTC)
    # 时间戳必须错开，同一时刻三条记录的趋势顺序不确定
    for offset, value in enumerate((148, 132, 128)):
        measured_at = (now - timedelta(days=2 - offset)).isoformat()
        response = await client.post(
            "/api/v1/tracking/metrics",
            headers=auth,
            json={"metric_code": "systolic_bp", "value": value, "measured_at": measured_at},
        )
        assert response.status_code == 200

    trends = await client.get("/api/v1/tracking/trends", params={"codes": "systolic_bp"}, headers=auth)
    assert trends.status_code == 200
    series = trends.json()["data"][0]
    assert len(series["points"]) == 3
    assert series["latest"] == 128
    assert series["change"] == -20

    # 超出可接受范围的数值在入口就拒绝，不写库也不进趋势
    rejected = await client.post(
        "/api/v1/tracking/metrics",
        headers=auth,
        json={"metric_code": "systolic_bp", "value": 400, "measured_at": now.isoformat()},
    )
    assert rejected.status_code == 422


async def test_nh_06_report_detail_and_export(client, auth):
    await run_assessment_to_report(client, auth)

    reports = await client.get("/api/v1/reports", headers=auth)
    report_id = reports.json()["data"][0]["id"]

    detail = await client.get(f"/api/v1/reports/{report_id}", headers=auth)
    content = detail.json()["data"]["content"]
    assert content["sections"]
    assert content["disclaimer"]

    export = await client.get(f"/api/v1/reports/{report_id}/export", headers=auth)
    assert export.status_code == 200
    assert "text/markdown" in export.headers["content-type"]
    assert content["disclaimer"] in export.text


async def test_nh_07_reminder_created_for_today_task(client, auth):
    await activate_plan(client, auth)

    reminders = await client.get("/api/v1/reminders", headers=auth)
    assert reminders.status_code == 200
    items = reminders.json()["data"]
    assert items
    assert any(item["notification_type"] == "task_due" for item in items)

    read = await client.post(f"/api/v1/reminders/{items[0]['id']}/read", headers=auth)
    assert read.status_code == 200
