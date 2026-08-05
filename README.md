# Notes API (PostgreSQL edition)

A JWT-authenticated CRUD API for personal notes, with role-based admin
access and ownership enforcement — Week 3, Day 4's independent integration
assignment, now backed by PostgreSQL with a real login/registration flow.

## Stack

FastAPI · SQLAlchemy 2.0 · Alembic · **PostgreSQL** (via psycopg2) · PyJWT ·
Passlib (bcrypt) · Pydantic v2

## Setup — from absolute zero

```bash
# 1. Start Postgres (needs Docker installed)
docker compose up -d
docker compose ps                # wait until "healthy"

# 2. Python env
python -m venv venv
source venv/bin/activate         # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 3. Config
cp .env.example .env             # defaults already match docker-compose.yml
python -c "import secrets; print(secrets.token_hex(32))"   # paste into .env as JWT_SECRET_KEY

# 4. Schema — entirely via Alembic, nothing else creates tables
alembic upgrade head

# 5. Sample data (also bootstraps the first admin — see "Auth" below)
python seed.py
```

## Run it

```bash
uvicorn app.main:app --reload
```

Docs at `http://127.0.0.1:8000/docs`. Health check at `/health`.

## Auth — register, login, and how admins get created

The assignment's endpoint list never says how to actually get a token, so
this was added (see `DESIGN.md`):

| Method | Path                          | Notes                                      |
|--------|-------------------------------|---------------------------------------------|
| POST   | `/api/v1/auth/register`       | Always creates `role="user"` — never admin |
| POST   | `/api/v1/auth/login`          | Returns a JWT for correct email+password    |
| PATCH  | `/api/v1/auth/users/{id}/role`| Admin-only — promotes another user          |

There is deliberately **no self-serve way to become admin**. Two paths only:
1. `python seed.py` bootstraps the very first admin (`admin@example.com` /
   `admin-password`).
2. Once one admin exists, they can `PATCH` anyone else to `role: "admin"`.

```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "you@example.com", "password": "a-real-password"}'

curl -s -X POST http://127.0.0.1:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "you@example.com", "password": "a-real-password"}'
# -> {"access_token": "...", "token_type": "bearer"}
```

## Required endpoints (the assignment's actual spec)

All mounted under `/api/v1`, all requiring `Authorization: Bearer <token>`:

| Method | Path                | Behavior                                            |
|--------|---------------------|-------------------------------------------------------|
| POST   | `/notes`             | Create a note for the current user (201)             |
| GET    | `/notes`              | List the current user's own notes (200)              |
| GET    | `/notes/{id}`         | Get one of the current user's own notes (200/404)    |
| PUT    | `/notes/{id}`         | Update one of the current user's own notes (200/404) |
| DELETE | `/notes/{id}`         | Delete one of the current user's own notes (204/404) |
| GET    | `/admin/notes`        | Admin-only: every note from every user (200/403)     |

**Requesting another user's note by ID returns 404, not 403** — existence
itself isn't information a non-owner is entitled to. The admin route is the
opposite case: a non-admin caller gets 403, because the endpoint's existence
isn't a secret, they just lack the role. See `DESIGN.md` for the reasoning.

## Try the required routes with curl

```bash
export ALICE_TOKEN="<from seed.py output>"
export BOB_TOKEN="<not used below>"
export ADMIN_TOKEN="<from seed.py output>"

curl -s -X POST http://127.0.0.1:8000/api/v1/notes \
  -H "Authorization: Bearer $ALICE_TOKEN" -H "Content-Type: application/json" \
  -d '{"title": "Groceries", "body": "milk, eggs"}'

# A non-owner (admin, in this example) requesting Alice's note by ID -> 404
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000/api/v1/notes/1 \
  -H "Authorization: Bearer $ADMIN_TOKEN"

# Alice hits the admin route -> 403 (she's not an admin)
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000/api/v1/admin/notes \
  -H "Authorization: Bearer $ALICE_TOKEN"

# Admin hits it -> 200, sees every user's notes
curl -s http://127.0.0.1:8000/api/v1/admin/notes -H "Authorization: Bearer $ADMIN_TOKEN"

# No token at all -> 401
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000/api/v1/notes
```

## Tests

```bash
pytest -v
```

Runs against an isolated in-memory SQLite DB by default — fast, no external
service required. This is a deliberate, common pattern; it does **not**
mean production is SQLite (it's Postgres-only — see `app/database.py`), and
it doesn't test Alembic itself. To run the same suite against a real
Postgres test database instead:

```bash
export TEST_DATABASE_URL="postgresql+psycopg2://notes_user:notes_password@localhost:5432/notes_test_db"
pytest -v
```

One test per line of the assignment's checklist, plus a full set for the
added register/login/promote flow — see `tests/test_notes.py` and
`tests/test_auth.py`.

## Migrations

Two, on purpose:

1. `0001_initial` — users, categories, notes. No index on `owner_id` yet.
2. `0002_add_owner_id_index` — adds that index, once ownership filtering
   (which is what actually queries by `owner_id` on every request) exists
   in the code. See `DESIGN.md`.

```bash
alembic upgrade head      # apply
alembic downgrade -1      # roll back one step
alembic history            # see the schema's history
```

`app/main.py` deliberately does **not** call `Base.metadata.create_all()` —
the schema is built and evolved entirely through these migrations, exactly
as the assignment requires. If you skip step 4 in setup, the app will fail
to find its tables rather than silently building them a different way.

## Project layout

```
docker-compose.yml   # local Postgres — `docker compose up -d`
app/
  database.py         # engine, session, Base, get_db dependency (Postgres only)
  models.py            # User, Category, Note (SQLAlchemy ORM)
  schemas.py            # Pydantic request/response shapes
  auth.py                # password hashing, JWT create/decode, get_current_user, get_current_admin
  routers/
    auth.py               # /api/v1/auth/* — register, login, promote (beyond spec)
    notes.py               # /api/v1/notes/* — JWT + ownership filtering
    admin.py                # /api/v1/admin/notes — JWT + admin role claim
  main.py                    # FastAPI app, router wiring — no create_all()
alembic/
  versions/                   # 0001_initial, 0002_add_owner_id_index
seed.py                        # bootstraps first admin + sample users/notes/tokens
tests/
  test_notes.py                # one test per assignment checklist item
  test_auth.py                  # register/login/promote coverage
DESIGN.md                        # paper schema design, FK direction, auth rationale
SELF_REVIEW.md                    # completed self-review checklist
```

## Environment this was built and checked in

This code was written in a network-isolated sandbox, where `pytest`,
`uvicorn`, and a real Postgres server couldn't be run live at the time. What
*was* verified by direct execution there (not just reading): the JWT claim
logic (valid/garbage/expired) and the register/login control flow
(uniqueness conflict, wrong-password rejection, correct-password
acceptance) — via standalone scripts using only PyJWT and stdlib
(`sqlite3`/`hashlib`) as stand-ins for the real DB/hashing libraries. Every
`.py` file also passed `python -m py_compile`.

It has since been fully checked in live on Ubuntu 22.04 with PostgreSQL 14,
where the entire flow was re-verified end-to-end:

- `alembic upgrade head` applied both migrations (`0001_initial`,
  `0002_add_owner_id_index`) to a real Postgres database.
- `python seed.py` bootstrapped the admin and sample users.
- `uvicorn app.main:app` served the API, and every endpoint was exercised
  with `curl`: register (201), login (200), notes CRUD
  (201/200/204/404), ownership filtering (404, not 403), missing/garbage/
  expired tokens (401), validation errors (422), and the admin route
  (403 for users, 200 for admins).
- `pytest` = 23 passed against the isolated in-memory SQLite DB.

Reproduce live with `docker compose up -d && pytest -v`, or use the
Postgres you already have by following "Setup — from absolute zero".
