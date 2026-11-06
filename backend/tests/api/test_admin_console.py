"""后台管理系统的权限、字段范围、角色护栏与事件状态收敛。

规则见 docs/rules/admin-console.md。这里最要紧的是：管理接口不能只是「前端藏起来」，
普通账号直接打接口必须被拒；账号列表不能把 User 整行吐出去；改角色与处置事件都要留痕。
"""

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID

import pytest
from sqlalchemy import select, update

from app.core.exceptions import Conflict
from app.db.models import SecurityAuditLog, User
from app.repositories import security as security_repo
from app.services import admin_service

ADMIN_CODE = "test-admin-code"
PASSWORD = "demo12345"


def _name() -> str:
    return f"u{uuid.uuid4().hex[:10]}"


def _enable_admin(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.auth_service.get_settings",
        lambda: SimpleNamespace(admin_registration_code=ADMIN_CODE),
    )


async def _register(client, *, role: str = "user", monkeypatch=None):
    username = _name()
    payload = {"username": username, "password": PASSWORD}
    if role == "admin":
        _enable_admin(monkeypatch)
        payload.update(role="admin", admin_code=ADMIN_CODE)
    response = await client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 200, response.text
    return response.json()["data"], username


def _headers(tokens: dict) -> dict[str, str]:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


async def _admin(client, monkeypatch):
    return await _register(client, role="admin", monkeypatch=monkeypatch)


async def _user_id(session, username: str) -> UUID:
    return await session.scalar(select(User.id).where(User.username == username))


async def _role_of(session, user_id: UUID) -> str:
    return await session.scalar(select(User.role).where(User.id == user_id))


async def _audits(session, action: str, result: str, resource_id: str) -> list[SecurityAuditLog]:
    """测试库是全量用例共用的，不按 resource_id 过滤会被别的用例留下的行喂成假绿。"""
    rows = await session.scalars(
        select(SecurityAuditLog).where(
            SecurityAuditLog.action == action,
            SecurityAuditLog.result == result,
            SecurityAuditLog.resource_id == resource_id,
        )
    )
    return list(rows)


async def _seed_incident(session) -> str:
    row = await security_repo.add_incident(
        session,
        incident_type=security_repo.BRUTEFORCE,
        severity="medium",
        description="account=demo failures=5 window=15min",
        occurred_at=datetime.now(UTC),
    )
    await session.flush()
    incident_id = str(row.id)
    await session.commit()
    return incident_id


# ---------- 权限 ----------


async def test_management_endpoints_require_login(client) -> None:
    target = uuid.uuid4()
    assert (await client.get("/api/v1/admin/users")).status_code == 401
    assert (
        await client.patch(f"/api/v1/admin/users/{target}/role", json={"role": "admin"})
    ).status_code == 401
    assert (
        await client.post(f"/api/v1/admin/incidents/{target}/resolve", json={})
    ).status_code == 401


async def test_regular_user_cannot_use_management_endpoints(client, auth) -> None:
    target = uuid.uuid4()
    assert (await client.get("/api/v1/admin/users", headers=auth)).status_code == 403
    assert (
        await client.patch(f"/api/v1/admin/users/{target}/role", headers=auth, json={"role": "admin"})
    ).status_code == 403
    assert (
        await client.post(f"/api/v1/admin/incidents/{target}/resolve", headers=auth, json={})
    ).status_code == 403


# ---------- 账号列表 ----------


async def test_admin_user_list_returns_metadata_only(client, monkeypatch) -> None:
    tokens, _ = await _admin(client, monkeypatch)
    await _register(client)

    response = await client.get("/api/v1/admin/users", headers=_headers(tokens))
    assert response.status_code == 200
    page = response.json()["data"]
    assert page["total"] >= 2
    assert page["page"] == 1
    assert page["page_size"] == 20
    assert set(page["items"][0]) == {
        "id", "username", "email", "role", "status", "created_at", "last_login_at"
    }
    assert "password_hash" not in page["items"][0]


async def test_admin_user_list_paginates(client, monkeypatch) -> None:
    tokens, _ = await _admin(client, monkeypatch)
    for _ in range(3):
        await _register(client)

    response = await client.get(
        "/api/v1/admin/users", headers=_headers(tokens), params={"page": 2, "page_size": 2}
    )
    assert response.status_code == 200
    page = response.json()["data"]
    assert page["page"] == 2
    assert page["page_size"] == 2
    assert len(page["items"]) == 2
    assert page["total"] >= 4

    bad = await client.get("/api/v1/admin/users", headers=_headers(tokens), params={"page_size": 0})
    assert bad.status_code == 422


# ---------- 角色变更 ----------


async def test_promote_user_grants_admin_access(client, monkeypatch, session) -> None:
    admin_tokens, _ = await _admin(client, monkeypatch)
    target_tokens, target_name = await _register(client)
    target_id = await _user_id(session, target_name)
    assert (await client.get("/health/services", headers=_headers(target_tokens))).status_code == 403

    response = await client.patch(
        f"/api/v1/admin/users/{target_id}/role",
        headers=_headers(admin_tokens),
        json={"role": "admin"},
    )
    assert response.status_code == 200
    assert response.json()["data"]["role"] == "admin"
    assert await _role_of(session, target_id) == "admin"
    # role 按库判断，旧令牌不用重签就生效
    assert (await client.get("/health/services", headers=_headers(target_tokens))).status_code == 200
    assert await _audits(session, "update_user_role", "success", str(target_id))


async def test_admin_cannot_change_own_role(client, monkeypatch, session) -> None:
    tokens, username = await _admin(client, monkeypatch)
    own_id = await _user_id(session, username)

    response = await client.patch(
        f"/api/v1/admin/users/{own_id}/role", headers=_headers(tokens), json={"role": "user"}
    )
    assert response.status_code == 409
    assert "自己" in response.json()["message"]
    assert await _role_of(session, own_id) == "admin"
    assert await _audits(session, "update_user_role", "fail", str(own_id))


async def test_last_admin_cannot_be_demoted(client, monkeypatch, session) -> None:
    """自改被禁后，这条护栏正常接口路径走不到，直接验服务层：库里只剩一个 admin 时拒绝降权。"""
    _, username = await _admin(client, monkeypatch)
    only_admin_id = await _user_id(session, username)
    actor = SimpleNamespace(id=uuid.uuid4())
    # 测试库是全量用例共用的，前面几个用例已经建了别的管理员；先把它们降权，
    # 让「库里只剩一个 admin」这个前提真的成立，断言才不是靠别的用例喂绿
    await session.execute(update(User).where(User.id != only_admin_id).values(role="user"))
    await session.commit()
    assert await admin_service.admin_repo.count_admins(session) == 1

    with pytest.raises(Conflict, match="至少"):
        await admin_service.set_role(
            session, actor=actor, target_id=only_admin_id, role="user", request_id="test"
        )
    assert await _role_of(session, only_admin_id) == "admin"
    assert await _audits(session, "update_user_role", "fail", str(only_admin_id))


async def test_second_admin_can_be_demoted(client, monkeypatch, session) -> None:
    actor_tokens, _ = await _admin(client, monkeypatch)
    target_tokens, target_name = await _admin(client, monkeypatch)
    target_id = await _user_id(session, target_name)

    response = await client.patch(
        f"/api/v1/admin/users/{target_id}/role",
        headers=_headers(actor_tokens),
        json={"role": "user"},
    )
    assert response.status_code == 200
    assert await _role_of(session, target_id) == "user"
    assert (await client.get("/health/services", headers=_headers(target_tokens))).status_code == 403


async def test_role_patch_rejects_unknown_role_and_missing_account(client, monkeypatch, session) -> None:
    tokens, _ = await _admin(client, monkeypatch)
    missing_id = str(uuid.uuid4())

    invalid = await client.patch(
        f"/api/v1/admin/users/{missing_id}/role", headers=_headers(tokens), json={"role": "root"}
    )
    assert invalid.status_code == 422

    missing = await client.patch(
        f"/api/v1/admin/users/{missing_id}/role", headers=_headers(tokens), json={"role": "admin"}
    )
    assert missing.status_code == 404
    assert await _audits(session, "update_user_role", "fail", missing_id)


# ---------- 事件处置 ----------


async def test_resolve_incident_converges_once_and_keeps_evidence(client, monkeypatch, session) -> None:
    tokens, _ = await _admin(client, monkeypatch)
    incident_id = await _seed_incident(session)
    headers = _headers(tokens)

    listed = await client.get("/api/v1/security/incidents", headers=headers)
    before = next(item for item in listed.json()["data"] if item["id"] == incident_id)

    response = await client.post(f"/api/v1/admin/incidents/{incident_id}/resolve", headers=headers, json={})
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["status"] == "resolved"
    assert data["resolved_at"]
    assert data["description"] == before["description"]
    assert data["severity"] == before["severity"]
    assert data["occurred_at"] == before["occurred_at"]

    again = await client.post(f"/api/v1/admin/incidents/{incident_id}/resolve", headers=headers, json={})
    assert again.status_code == 200
    assert again.json()["data"]["resolved_at"] == data["resolved_at"]
    assert len(await _audits(session, "resolve_incident", "success", incident_id)) == 1


async def test_resolve_missing_incident_returns_404_and_audits(client, monkeypatch, session) -> None:
    tokens, _ = await _admin(client, monkeypatch)
    missing_id = str(uuid.uuid4())

    response = await client.post(
        f"/api/v1/admin/incidents/{missing_id}/resolve", headers=_headers(tokens), json={}
    )
    assert response.status_code == 404
    assert await _audits(session, "resolve_incident", "fail", missing_id)
