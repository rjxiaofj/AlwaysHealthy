"""确认阶段的聊天记录不能出现重复文案。

`_stream()` 收尾时会 `reply = state["reply"] or reply`。恢复运行后若这一段没有节点产出新
reply（计划确认这一段 assess → intervene → plan → plan_validator 都不写 reply），拿到的就是
上一步的旧文案，于是计划确认阶段又存了一条与画像确认阶段完全相同的「已记录：年龄 39…」。
"""

from tests.helpers import confirm_profile, patch_profile, start_assessment


async def _confirms(client, headers):
    conversations = await client.get("/api/v1/conversations", headers=headers)
    conversation_id = conversations.json()["data"][0]["id"]
    response = await client.get(f"/api/v1/conversations/{conversation_id}/messages", headers=headers)
    assert response.status_code == 200, response.text
    return [item for item in response.json()["data"] if item["message_type"] == "confirm"]


async def test_profile_stage_confirm_message_is_kept(client, auth) -> None:
    await patch_profile(client, auth)
    await start_assessment(client, auth)

    confirms = await _confirms(client, auth)

    assert len(confirms) == 1
    # 画像确认阶段是有新 reply 的，这条要留住，用户需要看到系统识别到了哪些值
    assert confirms[0]["content"].startswith("已记录")


async def test_plan_stage_does_not_repeat_profile_text(client, auth) -> None:
    await patch_profile(client, auth)
    profile_confirm = await start_assessment(client, auth)
    await confirm_profile(client, auth, profile_confirm["run_id"])

    confirms = await _confirms(client, auth)
    texts = [item["content"] for item in confirms]

    assert len(texts) == 2, texts
    assert len(set(texts)) == 2, f"两条确认消息内容相同：{texts}"
    assert confirms[0]["content"].startswith("已记录")
    # 计划阶段要给出本阶段的提示，而不是把上一条抄一遍
    assert "计划" in confirms[1]["content"]
