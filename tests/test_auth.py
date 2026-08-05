"""
Covers the login/registration addition (see DESIGN.md) — not in the
assignment's checklist, but needed for the app to be usable end-to-end.
"""
def test_register_creates_user_as_role_user(client, db_session):
    resp = client.post("/api/v1/auth/register", json={"email": "new@example.com", "password": "a-good-password"})
    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == "new@example.com"
    assert body["role"] == "user"  # never admin, regardless of what's sent
    assert "password" not in body and "hashed_password" not in body  # never leaked


def test_register_ignores_client_supplied_role(client, db_session):
    # UserRegister schema doesn't even expose a role field, so a client
    # trying to smuggle one in just gets ignored by Pydantic, not honored.
    resp = client.post(
        "/api/v1/auth/register",
        json={"email": "sneaky@example.com", "password": "a-good-password", "role": "admin"},
    )
    assert resp.status_code == 201
    assert resp.json()["role"] == "user"


def test_register_duplicate_email_returns_409(client, db_session):
    client.post("/api/v1/auth/register", json={"email": "dup@example.com", "password": "a-good-password"})
    resp = client.post("/api/v1/auth/register", json={"email": "dup@example.com", "password": "another-password"})
    assert resp.status_code == 409


def test_login_with_correct_credentials_returns_token(client, db_session):
    client.post("/api/v1/auth/register", json={"email": "login@example.com", "password": "correct-password"})
    resp = client.post("/api/v1/auth/login", json={"email": "login@example.com", "password": "correct-password"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]

    # and the token actually works against a protected route
    notes_resp = client.get("/api/v1/notes", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert notes_resp.status_code == 200


def test_login_with_wrong_password_returns_401(client, db_session):
    client.post("/api/v1/auth/register", json={"email": "wrongpw@example.com", "password": "correct-password"})
    resp = client.post("/api/v1/auth/login", json={"email": "wrongpw@example.com", "password": "not-it"})
    assert resp.status_code == 401


def test_login_with_unknown_email_returns_401(client, db_session):
    resp = client.post("/api/v1/auth/login", json={"email": "nobody@example.com", "password": "whatever"})
    assert resp.status_code == 401


def test_promote_to_admin_requires_admin(client, two_users):
    # Alice (regular user) tries to promote herself — blocked.
    resp = client.patch(
        f"/api/v1/auth/users/{two_users['alice'].id}/role",
        json={"role": "admin"},
        headers={"Authorization": f"Bearer {two_users['alice_token']}"},
    )
    assert resp.status_code == 403


def test_admin_can_promote_a_user(client, two_users):
    resp = client.patch(
        f"/api/v1/auth/users/{two_users['alice'].id}/role",
        json={"role": "admin"},
        headers={"Authorization": f"Bearer {two_users['bob_token']}"},  # bob is the seeded admin
    )
    assert resp.status_code == 200
    assert resp.json()["role"] == "admin"
