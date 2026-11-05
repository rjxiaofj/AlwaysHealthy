from sqlalchemy import select, update

from app.db.models import SecurityIncident, User


async def wrong_password(client, username: str, times: int = 1):
    response = None
    for _ in range(times):
        response = await client.post(
            "/api/v1/auth/login", json={"username": username, "password": "wrong-password"}
        )
    return response


async def incidents(session, account: str) -> list[SecurityIncident]:
    """测试库是多个用例共用的，按账号过滤，不然条数断言会被别的用例带偏。"""
    rows = await session.scalars(select(SecurityIncident).order_by(SecurityIncident.occurred_at))
    return [row for row in rows if row.description.startswith(f"account={account} ")]


async def test_five_failures_raise_one_incident(client, auth, session) -> None:
    await wrong_password(client, auth["username"], 4)
    assert await incidents(session, auth["username"]) == []

    await wrong_password(client, auth["username"], 1)
    rows = await incidents(session, auth["username"])
    assert len(rows) == 1
    assert rows[0].incident_type == "login_bruteforce"
    assert rows[0].severity == "medium"
    assert rows[0].status == "open"
    assert "wrong-password" not in rows[0].description


async def test_more_failures_do_not_add_rows(client, auth, session) -> None:
    await wrong_password(client, auth["username"], 5)
    await wrong_password(client, auth["username"], 3)

    rows = await incidents(session, auth["username"])
    assert len(rows) == 1


async def test_other_account_gets_own_incident(client, auth, session) -> None:
    await wrong_password(client, auth["username"], 5)
    await wrong_password(client, "someone_else", 5)

    assert len(await incidents(session, auth["username"])) == 1
    assert len(await incidents(session, "someone_else")) == 1


async def test_incidents_require_admin(client, auth) -> None:
    response = await client.get("/api/v1/security/incidents", headers=auth)
    assert response.status_code == 403
    assert response.json()["code"] == "RESOURCE_FORBIDDEN"


async def test_admin_can_read_incidents(client, auth, session) -> None:
    await wrong_password(client, auth["username"], 5)

    user_id = await session.scalar(select(User.id).where(User.username == auth["username"]))
    await session.execute(update(User).where(User.id == user_id).values(role="admin"))
    await session.commit()

    response = await client.get("/api/v1/security/incidents", headers=auth)
    assert response.status_code == 200, response.text
    rows = response.json()["data"]
    mine = [row for row in rows if row["description"].startswith(f"account={auth['username']} ")]
    assert len(mine) == 1
    assert mine[0]["incident_type"] == "login_bruteforce"


async def test_incidents_require_login(client) -> None:
    response = await client.get("/api/v1/security/incidents")
    assert response.status_code == 401


async def test_underscore_accounts_do_not_swallow_each_other(client, session) -> None:
    """账号里的下划线在 LIKE 里是通配符，a_b 与 axb 必须各自一条。"""
    await wrong_password(client, "u_a_b", 5)
    await wrong_password(client, "uXaXb", 5)

    assert len(await incidents(session, "u_a_b")) == 1
    assert len(await incidents(session, "uXaXb")) == 1
