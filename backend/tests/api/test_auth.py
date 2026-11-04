"""NH-01 注册登录与刷新轮换。

档案与 BMI 见 test_features.py 的 NH-02。
"""

import uuid


async def test_me_requires_token(client):
    response = await client.get("/api/v1/users/me")
    assert response.status_code == 401
    assert response.json()["code"] == "AUTH_UNAUTHORIZED"


async def test_login_refresh_and_logout(client):
    username = f"u{uuid.uuid4().hex[:10]}"
    register = await client.post("/api/v1/auth/register", json={"username": username, "password": "demo12345"})
    assert register.status_code == 200
    refresh_token = register.json()["data"]["refresh_token"]

    login = await client.post("/api/v1/auth/login", json={"username": username, "password": "demo12345"})
    assert login.status_code == 200

    refreshed = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert refreshed.status_code == 200
    new_refresh = refreshed.json()["data"]["refresh_token"]
    assert new_refresh != refresh_token

    reuse = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert reuse.status_code == 401

    logout = await client.post("/api/v1/auth/logout", json={"refresh_token": new_refresh})
    assert logout.status_code == 200
    after = await client.post("/api/v1/auth/refresh", json={"refresh_token": new_refresh})
    assert after.status_code == 401


async def test_wrong_password_rejected(client):
    username = f"u{uuid.uuid4().hex[:10]}"
    await client.post("/api/v1/auth/register", json={"username": username, "password": "demo12345"})
    response = await client.post("/api/v1/auth/login", json={"username": username, "password": "wrongpass1"})
    assert response.status_code == 401
    assert response.json()["code"] == "AUTH_INVALID_CREDENTIALS"


async def test_duplicate_username_rejected(client):
    username = f"u{uuid.uuid4().hex[:10]}"
    await client.post("/api/v1/auth/register", json={"username": username, "password": "demo12345"})
    response = await client.post("/api/v1/auth/register", json={"username": username, "password": "demo12345"})
    assert response.status_code == 409


async def test_request_id_present(client):
    response = await client.get("/health/live")
    assert response.status_code == 200
    assert response.headers["X-Request-ID"].startswith("req_")


async def test_nh_08_consent_keeps_history(client, auth):
    grant = await client.post("/api/v1/consents", headers=auth, json={"consent_type": "health_data", "granted": True})
    assert grant.status_code == 200
    revoke = await client.post("/api/v1/consents", headers=auth, json={"consent_type": "health_data", "granted": False})
    assert revoke.status_code == 200
    assert revoke.json()["data"]["consent_status"] == "revoked"

    records = await client.get("/api/v1/consents", headers=auth)
    items = records.json()["data"]
    # 撤回不覆盖授权记录，历史两条都在
    assert len(items) == 2
    assert items[0]["consent_status"] == "revoked"
    assert items[1]["consent_status"] == "granted"
    assert items[0]["label"] == "健康数据处理"


async def test_nh_08_consent_type_is_limited(client, auth):
    response = await client.post(
        "/api/v1/consents",
        headers=auth,
        json={"consent_type": "ad_targeting", "granted": True},
    )
    assert response.status_code == 422


async def test_nh_11_login_failure_written_to_audit(client, session, auth):
    from sqlalchemy import select

    from app.db.models import SecurityAuditLog

    username = auth["username"]
    await client.post("/api/v1/auth/login", json={"username": username, "password": "wrongpass1"})

    rows = await session.scalars(
        select(SecurityAuditLog).where(SecurityAuditLog.action == "login", SecurityAuditLog.result == "fail")
    )
    audit_rows = [row for row in rows if row.resource_id == username]
    assert audit_rows
    # 审计里不能出现密码
    assert all("wrongpass1" not in (row.resource_id or "") for row in audit_rows)
