# Schema Design (paper kata — done before any code)

## Entities

**User** — required for JWT auth ("the currently authenticated user"), and
the assignment spec doesn't hand this to you, so it's a first design
decision, not a revision of Tuesday's work.
- id (PK)
- email (unique, indexed — used as the login identifier)
- hashed_password (never stored or returned in plaintext)
- role (string, default "user" — backs the admin role claim)

**Category**
- id (PK)
- name (unique, not null)

**Note**
- id (PK)
- title (not null)
- body (not null)
- owner_id (FK -> users.id, not null) — every note has exactly one owner
- category_id (FK -> categories.id, nullable) — "optionally one Category"
- created_at (not null, server-side default now())

## Foreign key direction

`Note` is the "many" side of both relationships:
- many Notes -> one User (`Note.owner_id -> users.id`)
- many Notes -> one Category (`Note.category_id -> categories.id`)

Mirrors Wednesday's Task/Category shape exactly, per the assignment. The FK
lives on Note in both cases; User and Category never point at Note via a
column (only via SQLAlchemy `relationship()`, which is Python-level, not a
second foreign key).

## Index decision (deliberately deferred)

`owner_id` is queried on every /notes/* request (ownership filtering scopes
every list/get/update/delete). The build sequence adds ownership filtering
*after* basic CRUD exists, so the index is its own incremental migration
(0002), once the query pattern that justifies it actually exists in the
code — migration 0001 ships without it.

## 404-vs-403 rule (the one deliberate wrinkle)

- Unowned note, valid auth, valid endpoint -> 404 (don't confirm the note
  exists to someone who isn't allowed to see it).
- Non-admin hitting /admin/notes -> 403 (the endpoint's existence isn't a
  secret; the caller just lacks the role).

Enforced once in the dependency layer (`app/auth.py`), not scattered across
route handlers.

## Login/registration — beyond the written spec, added deliberately

The spec's endpoint list has no way to actually get a token in the first
place — that's a real gap for a "100% working" app, not a missing nice-to-have.
Added:
- `POST /api/v1/auth/register` — creates a user. Always `role="user"`,
  regardless of what the client sends — self-registration can never grant
  admin.
- `POST /api/v1/auth/login` — verifies email + password, returns a JWT.
- `PATCH /api/v1/auth/users/{id}` — admin-only, promotes another user to
  admin. The only two ways to get an admin account are this endpoint (once
  at least one admin already exists) or `seed.py` (bootstraps the first one).

These three routes are additions on top of the assignment's required
six — kept in their own `auth.py` router so the required `/notes/*` and
`/admin/notes` routes are unambiguously the ones the spec asked for.

## Why Postgres changes almost nothing here

Every column type used (`Integer`, `String`, `Text`, `Boolean`-as-role-string,
`DateTime(timezone=True)`) is dialect-portable, and both migrations use
Alembic's `op.*` calls rather than raw SQL — so the schema is defined once
and Alembic emits the right SQL for whichever `DATABASE_URL` it's pointed
at. The only Postgres-specific addition is the driver (`psycopg2-binary`)
and the connection string; nothing in `models.py` or the migrations
special-cases SQLite anymore, because there's no SQLite in production.
