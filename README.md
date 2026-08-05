# Notes API (PostgreSQL edition)

A JWT-authenticated CRUD API for personal notes, with role-based admin
access and ownership enforcement — Week 3, Day 4's independent integration
assignment, now backed by PostgreSQL with a real login/registration flow.

## Stack

FastAPI · SQLAlchemy 2.0 · Alembic · **PostgreSQL** (via psycopg2) · PyJWT ·
Passlib (bcrypt) · Pydantic v2

## Setup — from absolute zero

Postgres can come from Docker **or** a native install — pick one, then do
the shared Python steps below. Both produce the same database, user, and
password the app expects by default (`DATABASE_URL` in `.env.example`).

**Option A — Postgres via Docker** (no local install needed):

```bash
docker compose up -d
docker compose ps                # wait until "healthy"
```

**Option B — native Postgres** (e.g. Ubuntu):

```bash
sudo apt install -y postgresql postgresql-contrib
sudo systemctl enable --now postgresql
sudo -u postgres psql -c "CREATE USER notes_user WITH PASSWORD 'notes_password';"
sudo -u postgres psql -c "CREATE DATABASE notes_db OWNER notes_user;"
```

Then the shared steps:

```bash
# 1. Python env
python -m venv venv
source venv/bin/activate         # Windows: venv\Scripts\activate
pip install -r requirements.txt  # pins bcrypt==4.0.1 — required by passlib 1.7.4

# 2. Config
cp .env.example .env             # defaults already match the database above
python -c "import secrets; print(secrets.token_hex(32))"   # paste into .env as JWT_SECRET_KEY

# 3. Schema — entirely via Alembic, nothing else creates tables
alembic upgrade head

# 4. Sample data (also bootstraps the first admin — see "Auth" below)
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

`pytest -v` needs **no** database at all — it runs against an isolated
in-memory SQLite DB by default, so Docker/Postgres don't need to be up to
run the automated suite. This is a deliberate, common pattern; it does
**not** mean production is SQLite (it's Postgres-only — see
`app/database.py`), and it doesn't test Alembic itself.

```bash
pytest -v
# => 23 passed
```

For a single command that checks *everything* — Postgres connectivity,
Alembic migrations on real Postgres, seed, pytest, then ~30 live curl
checks against uvicorn (every assignment status code):

```bash
bash run_all_tests.sh
# => RESULTS: 30 passed, 0 failed
```

To run the same suite against a real Postgres test database instead, first
create the test database (SQLAlchemy creates the tables, but not the
database itself), then point pytest at it:

```bash
sudo -u postgres psql -c "CREATE DATABASE notes_test_db OWNER notes_user;"   # once
export TEST_DATABASE_URL="postgresql+psycopg2://notes_user:notes_password@localhost:5432/notes_test_db"
pytest -v
# => 23 passed
```

One test per line of the assignment's checklist, plus a full set for the
added register/login/promote flow — see `tests/test_notes.py` and
`tests/test_auth.py`.

## Live smoke test (server + real Postgres)

To confirm the whole stack end-to-end — real Postgres, Alembic schema,
uvicorn, JWT auth, ownership filtering:

1. Start the server: `uvicorn app.main:app --reload`
2. Grab a token for the seeded admin and a normal user (`python seed.py`
   prints ready-made tokens), then run the curl examples in "Try the
   required routes with curl" below.
3. Expected codes: register **201**, login **200**, notes CRUD
   **201/200/204**, someone else's note **404** (not 403), no/garbage/
   expired token **401**, invalid payload **422**, admin route **403** for
   users and **200** for admins.

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
as the assignment requires. If you skip step 3 in setup, the app will fail
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
