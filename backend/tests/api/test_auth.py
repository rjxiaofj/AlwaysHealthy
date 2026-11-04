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


async def test_profile_patch_and_bmi(client, auth):
    response = await client.patch(
        "/api/v1/profiles/me",
        headers=auth,
        json={"birth_date": "1990-01-01", "sex": "female", "height_cm": 165, "weight_kg": 60},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["bmi"] == 22.0
    assert data["age"] >= 18
    assert data["profile_version"] >= 2


async def test_request_id_present(client):
    response = await client.get("/health/live")
    assert response.status_code == 200
    assert response.headers["X-Request-ID"].startswith("req_")
