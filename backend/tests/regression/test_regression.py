"""关联回测用例，对应 docs/impact 的 RT-01 至 RT-04。

关注的是改动一处之后，相邻功能是否被带坏：分页、版本、快照、去重。
"""

from tests.helpers import activate_plan, patch_profile, run_assessment_to_report


async def test_rt_01_assessment_list_pagination(client, auth):
    await patch_profile(client, auth)
    first = await client.post("/api/v1/assessments", headers=auth)
    second = await client.post("/api/v1/assessments", headers=auth)
    assert first.status_code == 200
    assert second.status_code == 200

    page_1 = await client.get("/api/v1/assessments", params={"page": 1, "page_size": 1}, headers=auth)
    page_2 = await client.get("/api/v1/assessments", params={"page": 2, "page_size": 1}, headers=auth)

    data_1 = page_1.json()["data"]
    data_2 = page_2.json()["data"]
    assert data_1["total"] == 2
    assert len(data_1["items"]) == 1
    assert len(data_2["items"]) == 1
    # 翻页要真的换一条，不能两页返回同一条
    assert data_1["items"][0]["id"] != data_2["items"][0]["id"]


async def test_rt_02_plan_versions_match_current(client, auth):
    plan = await activate_plan(client, auth)

    await client.post(
        f"/api/v1/plans/{plan['id']}/adjust",
        headers=auth,
        json={"reason": "先把强度降一点"},
    )

    versions = await client.get(f"/api/v1/plans/{plan['id']}/versions", headers=auth)
    detail = await client.get(f"/api/v1/plans/{plan['id']}", headers=auth)
    listed = versions.json()["data"]
    detail_versions = detail.json()["data"]["versions"]

    assert [item["id"] for item in listed] == [item["id"] for item in detail_versions]

    current_version_id = detail.json()["data"]["current_version_id"]
    active = [item for item in listed if item["status"] == "active"]
    assert len(active) == 1
    assert active[0]["id"] == current_version_id


async def test_rt_02_new_active_plan_supersedes_old_version(client, auth):
    first = await activate_plan(client, auth)
    second = await activate_plan(client, auth)

    old = await client.get(f"/api/v1/plans/{first['id']}", headers=auth)
    old_detail = old.json()["data"]
    assert old_detail["status"] == "superseded"
    # 旧计划被顶替后不能还留着一个 active 版本
    assert all(item["status"] != "active" for item in old_detail["versions"])

    fresh = await client.get(f"/api/v1/plans/{second['id']}", headers=auth)
    assert fresh.json()["data"]["status"] == "active"


async def test_rt_03_report_content_frozen_after_profile_change(client, auth):
    await run_assessment_to_report(client, auth)

    reports = await client.get("/api/v1/reports", headers=auth)
    report_id = reports.json()["data"][0]["id"]
    before = (await client.get(f"/api/v1/reports/{report_id}", headers=auth)).json()["data"]["content"]

    # 档案改了，历史报告读的是落库快照，不应该跟着变
    await patch_profile(client, auth, weight_kg=80, waist_cm=92)

    after = (await client.get(f"/api/v1/reports/{report_id}", headers=auth)).json()["data"]["content"]
    assert after == before


async def test_rt_04_reminder_not_duplicated_on_revisit(client, auth):
    await activate_plan(client, auth)

    first = (await client.get("/api/v1/reminders", headers=auth)).json()["data"]
    second = (await client.get("/api/v1/reminders", headers=auth)).json()["data"]
    assert len(first) == len(second)
    assert [item["id"] for item in first] == [item["id"] for item in second]

    target = first[0]
    await client.post(f"/api/v1/reminders/{target['id']}/read", headers=auth)

    third = (await client.get("/api/v1/reminders", headers=auth)).json()["data"]
    assert len(third) == len(second)
    read_item = next(item for item in third if item["id"] == target["id"])
    assert read_item["read_at"] is not None
