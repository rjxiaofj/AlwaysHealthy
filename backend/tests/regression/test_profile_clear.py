import pytest

PATCH = "/api/v1/profiles/me"


async def patch(client, headers, **body) -> dict:
    response = await client.patch(PATCH, json=body, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()["data"]


async def get(client, headers) -> dict:
    return (await client.get(PATCH, headers=headers)).json()["data"]


async def test_clear_scalar_fields(client, auth) -> None:
    await patch(client, auth, birth_date="1990-05-01", occupation="教师", weight_kg=62)
    assert (await get(client, auth))["occupation"] == "教师"

    data = await patch(client, auth, birth_date=None, occupation=None, weight_kg=None)

    assert data["birth_date"] is None
    assert data["occupation"] is None
    assert data["weight_kg"] is None


async def test_clear_lifestyle_key(client, auth) -> None:
    await patch(client, auth, lifestyle={"sleep_hours": 7.5, "exercise_days": 3})

    data = await patch(client, auth, lifestyle={"sleep_hours": None})

    # 传 null 的子键应该被删掉，没提到的子键保留
    assert "sleep_hours" not in data["lifestyle"]
    assert data["lifestyle"]["exercise_days"] == 3


async def test_omitted_fields_are_untouched(client, auth) -> None:
    await patch(client, auth, occupation="教师", lifestyle={"sleep_hours": 7.5})

    data = await patch(client, auth, sex="male")

    assert data["occupation"] == "教师"
    assert data["lifestyle"]["sleep_hours"] == 7.5
    assert data["sex"] == "male"


async def test_repeated_clear_does_not_bump_version(client, auth) -> None:
    await patch(client, auth, occupation="教师")
    first = await patch(client, auth, occupation=None)
    second = await patch(client, auth, occupation=None)

    # 已经是空值再清一次不算改动，空保存不该让档案版本一直涨
    assert first["profile_version"] == second["profile_version"]


async def test_real_change_bumps_version(client, auth) -> None:
    before = (await get(client, auth))["profile_version"]
    after = await patch(client, auth, occupation="教师")

    assert after["profile_version"] == before + 1


async def test_empty_lifestyle_dict_does_not_bump_version(client, auth) -> None:
    await patch(client, auth, lifestyle={"sleep_hours": 7.5})
    before = (await get(client, auth))["profile_version"]

    after = await patch(client, auth, lifestyle={})

    assert after["profile_version"] == before
    assert after["lifestyle"]["sleep_hours"] == 7.5


@pytest.mark.parametrize("field", ["height_cm", "weight_kg", "waist_cm"])
async def test_clear_metric_like_fields(client, auth, field: str) -> None:
    await patch(client, auth, **{field: 100 if field != "weight_kg" else 60})

    data = await patch(client, auth, **{field: None})

    assert data[field] is None


async def test_medical_history_persists(client, auth) -> None:
    created = await client.post(
        "/api/v1/profiles/me/histories",
        json={"history_type": "personal", "condition_code": "hypertension", "description": "两年前确诊"},
        headers=auth,
    )
    assert created.status_code == 200, created.text

    # 换一个请求读，确认写进去的东西没被事务回滚
    data = (await get(client, auth))["medical_histories"]
    assert [item["condition_code"] for item in data] == ["hypertension"]
    assert data[0]["description"] == "两年前确诊"
