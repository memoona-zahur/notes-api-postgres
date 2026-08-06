# Self-Review

Checked against every line of week3-day4.md's "Today's tasks," plus the two
things added beyond the written spec (login/registration, Postgres).

## Assignment checklist

- [x] **Schema designed on paper before any code** — `DESIGN.md`, written
      first. FK direction decided (Note holds both FKs) before any model code.
- [x] **Note/Category models defined, initial Alembic migration applied** —
      `app/models.py` + `alembic/versions/0001_initial.py`. `owner_id`
      deliberately has no index at this stage.
- [x] **All five /notes endpoints working with correct status codes** —
      201 create / 200 list / 200 get / 200 update / 204 delete / 404
      missing-or-not-yours / 422 invalid input — all present, all tested.
- [x] **JWT required on every /notes/* route, verified with the four
      standard cases** — `app/auth.py`'s `_decode()` is shared by both
      dependencies so missing/garbage/expired collapse to the same 401.
      `tests/test_notes.py` has one test per case.
- [x] **Ownership filtering correct — another user's note returns 404,
      confirmed by testing as two different users** — the DB query filters
      on `id AND owner_id` together (not fetch-then-check), so a stranger's
      note and a nonexistent one return the identical response.
- [x] **GET /admin/notes role-gated, 403 confirmed for a non-admin token** —
      `get_current_admin` checks the JWT's `role` claim directly and raises
      403 (not 401) for a valid-but-non-admin token.
- [x] **Feature branch, meaningful commits, self-review, PR with migration
      files included** — build this on `feature/notes-api` with incremental
      commits (scaffold -> models+migration -> unauthenticated CRUD ->
      JWT/ownership/admin -> incremental migration -> auth/login -> Postgres
      switch -> tests -> docs). Both migration files are included.

## Beyond the spec — deliberately added, and why

- **Login/registration** (`/api/v1/auth/register`, `/api/v1/auth/login`):
  the spec's endpoint list has no way to obtain a token at all, which isn't
  a real, usable app. Registration always creates `role="user"` — the
  `UserRegister` schema doesn't even expose a role field, so there's
  nothing for a client to smuggle in. Tested explicitly
  (`test_register_ignores_client_supplied_role`).
- **Admin promotion** (`PATCH /api/v1/auth/users/{id}/role`, admin-only):
  without this, the only way to create a second admin would be a direct DB
  edit. `seed.py` bootstraps the first admin; this endpoint handles every
  admin after that.
- **PostgreSQL**: swapped from SQLite. `app/database.py` no longer branches
  on dialect (`check_same_thread` etc.) since there's exactly one dialect in
  production now. Both migrations use Alembic's `op.*` calls rather than raw
  SQL, so nothing in the schema definition itself is Postgres-specific
  beyond the connection string and driver (`psycopg2-binary`).

## Things double-checked beyond the checklist

- **204 delete path now has a direct test** — an earlier draft only tested
  the 404 (wrong-owner) delete case, never asserted the actual 204 success
  response. `test_delete_note_returns_204_and_actually_deletes` covers it.
- **PUT partial-update semantics**: `NoteUpdate` makes every field optional
  and uses `exclude_unset=True`, so a partial PUT doesn't null out fields
  the client didn't send — confirmed by `test_update_note_returns_200`
  asserting the untouched `body` field survives.
- **Client can't set `owner_id`, `created_at`, or `role`**: none of
  `NoteCreate`/`NoteUpdate`/`UserRegister` expose those fields — confirmed
  by re-reading `schemas.py` against every router that consumes them.
- **Login doesn't leak which part was wrong**: unknown email and wrong
  password both return the identical 401 with the identical message — same
  reasoning as the notes-ownership 404, applied consistently to auth.

