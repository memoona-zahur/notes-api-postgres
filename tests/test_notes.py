"""
One test per checklist line item in week3-day4.md, so a failing test names
exactly which requirement broke.
"""
import time

import jwt

from app.auth import SECRET_KEY, ALGORITHM


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ---- Five /notes endpoints, correct status codes (201/200/404/200/204/422) ----

def test_create_note_returns_201(client, two_users):
    resp = client.post(
        "/api/v1/notes",
        json={"title": "Groceries", "body": "milk, eggs"},
        headers=auth_headers(two_users["alice_token"]),
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["title"] == "Groceries"
    assert body["owner_id"] == two_users["alice"].id  # server sets it, client can't


def test_list_notes_returns_200(client, two_users):
    resp = client.get("/api/v1/notes", headers=auth_headers(two_users["alice_token"]))
    assert resp.status_code == 200
    assert resp.json() == []


def test_get_missing_note_returns_404(client, two_users):
    resp = client.get("/api/v1/notes/999", headers=auth_headers(two_users["alice_token"]))
    assert resp.status_code == 404


def test_update_note_returns_200(client, two_users):
    created = client.post(
        "/api/v1/notes", json={"title": "Draft", "body": "wip"}, headers=auth_headers(two_users["alice_token"])
    ).json()
    resp = client.put(
        f"/api/v1/notes/{created['id']}",
        json={"title": "Final"},
        headers=auth_headers(two_users["alice_token"]),
    )
    assert resp.status_code == 200
    assert resp.json()["title"] == "Final"
    assert resp.json()["body"] == "wip"  # untouched field preserved (exclude_unset)


def test_delete_note_returns_204_and_actually_deletes(client, two_users):
    """Previously missing: the success path for delete was only ever tested
    via the 404 (wrong-owner) case, never the happy path itself."""
    created = client.post(
        "/api/v1/notes", json={"title": "Temp", "body": "throwaway"}, headers=auth_headers(two_users["alice_token"])
    ).json()
    resp = client.delete(
        f"/api/v1/notes/{created['id']}", headers=auth_headers(two_users["alice_token"])
    )
    assert resp.status_code == 204
    assert resp.content == b""
    follow_up = client.get(
        f"/api/v1/notes/{created['id']}", headers=auth_headers(two_users["alice_token"])
    )
    assert follow_up.status_code == 404


def test_invalid_input_returns_422(client, two_users):
    resp = client.post(
        "/api/v1/notes", json={"body": "no title field at all"}, headers=auth_headers(two_users["alice_token"])
    )
    assert resp.status_code == 422


def test_invalid_category_id_returns_422(client, two_users):
    resp = client.post(
        "/api/v1/notes",
        json={"title": "Broken category", "body": "b", "category_id": 999},
        headers=auth_headers(two_users["alice_token"]),
    )
    assert resp.status_code == 422


# ---- JWT required on every /notes/* route: missing / garbage / expired / valid ----

def test_missing_token_returns_401(client, two_users):
    resp = client.get("/api/v1/notes")
    assert resp.status_code == 401


def test_garbage_token_returns_401(client, two_users):
    resp = client.get("/api/v1/notes", headers=auth_headers("this-is-not-a-jwt"))
    assert resp.status_code == 401


def test_expired_token_returns_401(client, two_users):
    expired_payload = {
        "sub": str(two_users["alice"].id),
        "role": "user",
        "exp": int(time.time()) - 60,  # expired one minute ago
    }
    expired_token = jwt.encode(expired_payload, SECRET_KEY, algorithm=ALGORITHM)
    resp = client.get("/api/v1/notes", headers=auth_headers(expired_token))
    assert resp.status_code == 401


def test_valid_token_returns_200(client, two_users):
    resp = client.get("/api/v1/notes", headers=auth_headers(two_users["alice_token"]))
    assert resp.status_code == 200


# ---- Ownership filtering: another user's note -> 404, confirmed as two different users ----

def test_ownership_filtering_returns_404_for_other_users_note(client, two_users):
    alice_note = client.post(
        "/api/v1/notes", json={"title": "Alice only", "body": "b"}, headers=auth_headers(two_users["alice_token"])
    ).json()

    resp = client.get(f"/api/v1/notes/{alice_note['id']}", headers=auth_headers(two_users["bob_token"]))
    assert resp.status_code == 404  # not 403 — existence itself isn't confirmed

    resp = client.put(
        f"/api/v1/notes/{alice_note['id']}", json={"title": "hijacked"}, headers=auth_headers(two_users["bob_token"])
    )
    assert resp.status_code == 404

    resp = client.delete(f"/api/v1/notes/{alice_note['id']}", headers=auth_headers(two_users["bob_token"]))
    assert resp.status_code == 404


def test_list_notes_only_shows_own_notes(client, two_users):
    client.post("/api/v1/notes", json={"title": "Alice's", "body": "b"}, headers=auth_headers(two_users["alice_token"]))
    client.post("/api/v1/notes", json={"title": "Bob's", "body": "b"}, headers=auth_headers(two_users["bob_token"]))

    alice_list = client.get("/api/v1/notes", headers=auth_headers(two_users["alice_token"])).json()
    assert len(alice_list) == 1
    assert alice_list[0]["title"] == "Alice's"


# ---- GET /admin/notes: role-gated, 403 for non-admin ----

def test_admin_notes_returns_403_for_non_admin(client, two_users):
    resp = client.get("/api/v1/admin/notes", headers=auth_headers(two_users["alice_token"]))
    assert resp.status_code == 403


def test_admin_notes_returns_200_and_all_notes_for_admin(client, two_users):
    client.post("/api/v1/notes", json={"title": "Alice's", "body": "b"}, headers=auth_headers(two_users["alice_token"]))
    client.post("/api/v1/notes", json={"title": "Bob's", "body": "b"}, headers=auth_headers(two_users["bob_token"]))

    resp = client.get("/api/v1/admin/notes", headers=auth_headers(two_users["bob_token"]))
    assert resp.status_code == 200
    titles = {n["title"] for n in resp.json()}
    assert titles == {"Alice's", "Bob's"}  # every user's notes, not just the admin's own
