from uuid import uuid4

from tests.helpers import activate_plan, register_another


async def adjust_plan(client, headers, plan_id, reason="任务太多，想减掉一些"):
    response = await client.post(f"/api/v1/plans/{plan_id}/adjust", json={"reason": reason}, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()["data"]["version_id"]


async def detail(client, headers, plan_id):
    return (await client.get(f"/api/v1/plans/{plan_id}", headers=headers)).json()["data"]


async def remove_task(client, headers, plan_id, version_id, task_id):
    return await client.delete(
        f"/api/v1/plans/{plan_id}/versions/{version_id}/tasks/{task_id}", headers=headers
    )


async def test_removing_draft_task_shrinks_pending_version(client, auth) -> None:
    plan = await activate_plan(client, auth)
    version_id = await adjust_plan(client, auth, plan["id"])

    pending = (await detail(client, auth, plan["id"]))["pending_version"]
    assert len(pending["tasks"]) == len(plan["tasks"])
    victim = pending["tasks"][0]["id"]

    response = await remove_task(client, auth, plan["id"], version_id, victim)
    assert response.status_code == 200, response.text

    pending = response.json()["data"]["pending_version"]
    assert len(pending["tasks"]) == len(plan["tasks"]) - 1
    assert victim not in [item["id"] for item in pending["tasks"]]


async def test_removed_task_disappears_after_approve(client, auth) -> None:
    plan = await activate_plan(client, auth)
    version_id = await adjust_plan(client, auth, plan["id"])
    pending = (await detail(client, auth, plan["id"]))["pending_version"]
    victim = pending["tasks"][0]["id"]
    remaining = len(pending["tasks"]) - 1

    await remove_task(client, auth, plan["id"], version_id, victim)
    response = await client.post(
        f"/api/v1/plans/{plan['id']}/approve", json={"version_id": version_id}, headers=auth
    )
    assert response.status_code == 200, response.text

    data = response.json()["data"]
    assert len(data["tasks"]) == remaining
    assert victim not in [item["id"] for item in data["tasks"]]
    assert data["pending_version"] is None


async def test_cannot_remove_last_task(client, auth) -> None:
    plan = await activate_plan(client, auth)
    version_id = await adjust_plan(client, auth, plan["id"])
    tasks = (await detail(client, auth, plan["id"]))["pending_version"]["tasks"]

    for item in tasks[:-1]:
        response = await remove_task(client, auth, plan["id"], version_id, item["id"])
        assert response.status_code == 200, response.text

    response = await remove_task(client, auth, plan["id"], version_id, tasks[-1]["id"])
    assert response.status_code == 409
    assert response.json()["code"] == "RESOURCE_CONFLICT"


async def test_cannot_remove_task_from_active_version(client, auth) -> None:
    plan = await activate_plan(client, auth)
    task_id = plan["tasks"][0]["id"]
    response = await remove_task(client, auth, plan["id"], plan["current_version_id"], task_id)
    assert response.status_code == 409


async def test_remove_unknown_task_returns_404(client, auth) -> None:
    plan = await activate_plan(client, auth)
    version_id = await adjust_plan(client, auth, plan["id"])
    response = await remove_task(client, auth, plan["id"], version_id, str(uuid4()))
    assert response.status_code == 404


async def test_remove_task_of_other_user_plan_returns_404(client, auth) -> None:
    plan = await activate_plan(client, auth)
    version_id = await adjust_plan(client, auth, plan["id"])
    task_id = (await detail(client, auth, plan["id"]))["pending_version"]["tasks"][0]["id"]

    other = await register_another(client)
    response = await remove_task(client, other, plan["id"], version_id, task_id)
    assert response.status_code == 404
