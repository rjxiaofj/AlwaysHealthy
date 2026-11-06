"""登录页身份选项卡对应的后端边界。

选项卡不能只是前端换文案：注册管理员要凭邀请码，管理员登录要按库里的 role 校验，
否则任何一个普通账号都能从「管理员登录」进来，后端 `admin_user` 那道权限就成了摆设。
"""

import uuid
from types import SimpleNamespace

from sqlalchemy import select

from app.db.models import SecurityAuditLog, User

DEMO_CODE = "test-admin-code"


def _name():
    return f"u{uuid.uuid4().hex[:10]}"


async def _register(client, username, **extra):
    payload = {"username": username, "password": "demo12345", **extra}
    return await client.post("/api/v1/auth/register", json=payload)


async def _login(client, username, **extra):
    payload = {"username": username, "password": "demo12345", **extra}
    return await client.post("/api/v1/auth/login", json=payload)


def _enable_admin(monkeypatch, code=DEMO_CODE):
    monkeypatch.setattr(
        "app.services.auth_service.get_settings",
        lambda: SimpleNamespace(admin_registration_code=code),
    )


# ---------- 注册 ----------


async def test_default_registration_stays_regular_user(client) -> None:
    response = await _register(client, _name())
    assert response.status_code == 200
    assert response.json()["data"]["role"] == "user"


async def test_admin_registration_closed_when_code_not_configured(client) -> None:
    username = _name()
    response = await _register(client, username, role="admin", admin_code="anything")
    assert response.status_code == 403
    assert "未开放" in response.json()["message"]


async def test_admin_registration_rejects_wrong_code(client, monkeypatch) -> None:
    _enable_admin(monkeypatch)
    response = await _register(client, _name(), role="admin", admin_code="guess-me")
    assert response.status_code == 403
    assert "邀请码" in response.json()["message"]


async def test_admin_registration_rejects_missing_code(client, monkeypatch) -> None:
    _enable_admin(monkeypatch)
    response = await _register(client, _name(), role="admin")
    assert response.status_code == 403


async def test_admin_registration_with_code_creates_real_admin(client, monkeypatch) -> None:
    _enable_admin(monkeypatch)
    response = await _register(client, _name(), role="admin", admin_code=DEMO_CODE)
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["role"] == "admin"

    headers = {"Authorization": f"Bearer {data['access_token']}"}
    me = await client.get("/api/v1/users/me", headers=headers)
    assert me.json()["data"]["role"] == "admin"
    # 真管理员才读得到安全事件，普通账号这一步是 403
    incidents = await client.get("/api/v1/security/incidents", headers=headers)
    assert incidents.status_code == 200


async def test_admin_registration_leaves_audit(client, monkeypatch, session) -> None:
    _enable_admin(monkeypatch)
    response = await _register(client, _name(), role="admin", admin_code=DEMO_CODE)
    assert response.status_code == 200

    rows = await session.scalars(
        select(SecurityAuditLog).where(SecurityAuditLog.action == "register_admin")
    )
    assert list(rows)


async def test_bad_role_value_rejected(client) -> None:
    response = await _register(client, _name(), role="superuser")
    assert response.status_code == 422


# ---------- 登录 ----------


async def test_regular_account_cannot_use_admin_tab(client) -> None:
    username = _name()
    await _register(client, username)

    response = await _login(client, username, expected_role="admin")

    assert response.status_code == 403
    assert "不是管理员" in response.json()["message"]


async def test_role_mismatch_is_audited(client, session) -> None:
    username = _name()
    await _register(client, username)
    await _login(client, username, expected_role="admin")

    user_id = await session.scalar(select(User.id).where(User.username == username))
    rows = await session.scalars(
        select(SecurityAuditLog).where(
            SecurityAuditLog.action == "login",
            SecurityAuditLog.result == "fail",
            SecurityAuditLog.resource_id == str(user_id),
        )
    )
    assert list(rows)


async def test_admin_account_can_use_admin_tab(client, monkeypatch) -> None:
    _enable_admin(monkeypatch)
    username = _name()
    await _register(client, username, role="admin", admin_code=DEMO_CODE)

    response = await _login(client, username, expected_role="admin")
    assert response.status_code == 200
    assert response.json()["data"]["role"] == "admin"


async def test_admin_account_can_still_browse_as_user(client, monkeypatch) -> None:
    """选项卡是「最低身份要求」不是精确匹配：管理员也能从用户登录进前台看自己的档案。"""
    _enable_admin(monkeypatch)
    username = _name()
    await _register(client, username, role="admin", admin_code=DEMO_CODE)

    response = await _login(client, username, expected_role="user")
    assert response.status_code == 200


async def test_login_without_expected_role_keeps_old_behaviour(client) -> None:
    """不带字段的老客户端（脚本、接口测试）仍然照常登录。"""
    username = _name()
    await _register(client, username)
    response = await _login(client, username)
    assert response.status_code == 200
