def test_login_with_correct_credentials_returns_token(client, director_user):
    res = client.post(
        "/auth/login",
        data={"username": "director@test.local", "password": "TestPass!1"},
    )
    assert res.status_code == 200
    assert "access_token" in res.json()


def test_login_with_wrong_password_is_rejected(client, director_user):
    res = client.post(
        "/auth/login",
        data={"username": "director@test.local", "password": "wrong"},
    )
    assert res.status_code == 401


def test_login_with_unknown_email_is_rejected(client):
    res = client.post(
        "/auth/login",
        data={"username": "nobody@test.local", "password": "whatever"},
    )
    assert res.status_code == 401


def test_me_without_token_is_rejected(client):
    res = client.get("/auth/me")
    assert res.status_code == 401


def test_me_with_valid_token_returns_the_right_user(client, director_user):
    login_res = client.post(
        "/auth/login",
        data={"username": "director@test.local", "password": "TestPass!1"},
    )
    token = login_res.json()["access_token"]

    res = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    body = res.json()
    assert body["email"] == "director@test.local"
    assert body["role"] == "director"


def test_me_with_garbage_token_is_rejected(client):
    res = client.get("/auth/me", headers={"Authorization": "Bearer not-a-real-token"})
    assert res.status_code == 401
