#!/usr/bin/env bash
#
# run_all_tests.sh — one command to verify the whole Notes API stack:
#   Postgres connectivity -> Alembic migrations -> seed -> pytest ->
#   live curl checks against uvicorn (every assignment status code).
#
# Idempotent: safe to re-run. Uses the already-running server on :PORT if
# one exists, otherwise starts its own and shuts it down at the end.
#
# Usage:  bash run_all_tests.sh      (or  ./run_all_tests.sh)
#         PORT=8001 bash run_all_tests.sh

set -u
cd "$(dirname "$0")"

PORT="${PORT:-8000}"
BASE="http://127.0.0.1:${PORT}"
TMPLOG="$(mktemp /tmp/notes-api-e2e.XXXXXX.log)"

if [ -x venv/bin/python ]; then PY="venv/bin/python"
elif [ -x .venv/bin/python ]; then PY=".venv/bin/python"
else PY="python3"; fi
echo "Using python: $PY"
echo "Test base URL: $BASE"
echo

PASS=0
FAIL=0
FAILURES=()

ok()   { PASS=$((PASS + 1)); echo "  PASS: $1"; }
fail() { FAIL=$((FAIL + 1)); echo "  FAIL: $1"; FAILURES+=("$1"); }

# check_code <description> <expected_code> <curl args...>
check_code() {
    local desc="$1" expected="$2"
    shift 2
    local code
    code="$(curl -s -o /dev/null -w "%{http_code}" "$@")"
    if [ "$code" = "$expected" ]; then ok "$desc (HTTP $code)"; else fail "$desc (expected $expected, got $code)"; fi
}

# ---------------------------------------------------------------- 1. Postgres
echo "== 1. Postgres connectivity =="
if command -v pg_isready >/dev/null 2>&1 && pg_isready -h localhost -p 5432 -U notes_user -d notes_db >/dev/null 2>&1; then
    ok "Postgres reachable at localhost:5432/notes_db"
else
    fail "Postgres NOT reachable at localhost:5432/notes_db (start it: sudo systemctl enable --now postgresql)"
fi
echo

# ---------------------------------------------------------------- 2. Migrations
echo "== 2. Alembic migrations (real Postgres) =="
if "$PY" -m alembic upgrade head >"$TMPLOG" 2>&1; then
    ok "alembic upgrade head"
else
    fail "alembic upgrade head — see $TMPLOG"
    tail -20 "$TMPLOG"
fi
echo

# ---------------------------------------------------------------- 3. Seed
echo "== 3. Seed data =="
if "$PY" seed.py >"$TMPLOG" 2>&1; then
    ok "python seed.py (admin + alice + bob + tokens)"
else
    fail "python seed.py — see $TMPLOG"
    tail -20 "$TMPLOG"
fi
echo

# ---------------------------------------------------------------- 4. pytest
echo "== 4. Automated test suite (pytest) =="
if "$PY" -m pytest -q >"$TMPLOG" 2>&1; then
    ok "pytest — all tests passed"
else
    fail "pytest — some tests failed; see $TMPLOG"
    tail -20 "$TMPLOG"
fi
echo

# ---------------------------------------------------------------- 5. uvicorn
echo "== 5. Start API server =="
UV_PID=""
STARTED=0
if curl -s -m 2 "$BASE/health" >/dev/null 2>&1; then
    echo "  Using already-running server on port $PORT"
else
    "$PY" -m uvicorn app.main:app --host 127.0.0.1 --port "$PORT" >"$TMPLOG" 2>&1 &
    UV_PID=$!
    STARTED=1
    for _ in $(seq 1 30); do
        if curl -s -m 1 "$BASE/health" >/dev/null 2>&1; then break; fi
        sleep 1
    done
    if curl -s -m 1 "$BASE/health" >/dev/null 2>&1; then
        ok "uvicorn started (pid $UV_PID)"
    else
        fail "uvicorn failed to start — see $TMPLOG"
        tail -20 "$TMPLOG"
        exit 1
    fi
fi
echo

cleanup() {
    if [ "$STARTED" = "1" ] && [ -n "$UV_PID" ]; then
        kill "$UV_PID" 2>/dev/null
        wait "$UV_PID" 2>/dev/null
        echo "  (stopped uvicorn pid $UV_PID)"
    fi
    rm -f "$TMPLOG"
}
trap cleanup EXIT

# ---------------------------------------------------------------- 6. E2E curl
echo "== 6. Live E2E checks =="

# --- basics
check_code "GET / (root route)"          200 "$BASE/"
check_code "GET /health"                 200 "$BASE/health"

# --- auth: register / login
EMAIL="e2e$(date +%s)@example.com"
REG=$(curl -s -X POST "$BASE/api/v1/auth/register" -H "Content-Type: application/json" -d "{\"email\":\"$EMAIL\",\"password\":\"secret123\"}")
if echo "$REG" | "$PY" -c "import sys,json; d=json.load(sys.stdin); assert d['role']=='user'" 2>/dev/null; then
    ok "POST /auth/register (201, role=user)"
else
    fail "POST /auth/register — unexpected response: $REG"
fi
check_code "POST /auth/register duplicate (409)" 409 -X POST "$BASE/api/v1/auth/register" -H "Content-Type: application/json" -d "{\"email\":\"$EMAIL\",\"password\":\"secret123\"}"
check_code "POST /auth/login wrong password (401)" 401 -X POST "$BASE/api/v1/auth/login" -H "Content-Type: application/json" -d '{"email":"alice@example.com","password":"wrong"}'

ALICE_TOKEN=$(curl -s -X POST "$BASE/api/v1/auth/login" -H "Content-Type: application/json" -d '{"email":"alice@example.com","password":"alice-password"}' | "$PY" -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
BOB_TOKEN=$(curl -s -X POST "$BASE/api/v1/auth/login" -H "Content-Type: application/json" -d '{"email":"bob@example.com","password":"bob-password"}' | "$PY" -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
ADMIN_TOKEN=$(curl -s -X POST "$BASE/api/v1/auth/login" -H "Content-Type: application/json" -d '{"email":"admin@example.com","password":"admin-password"}' | "$PY" -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
if [ -n "$ALICE_TOKEN" ] && [ -n "$BOB_TOKEN" ] && [ -n "$ADMIN_TOKEN" ]; then
    ok "login for alice/bob/admin returned tokens"
else
    fail "login tokens missing (did seed.py run?)"
fi

EXPIRED_TOKEN=$("$PY" -c "import sys; sys.path.insert(0,'.'); from app.auth import create_access_token; print(create_access_token(1,'user',expires_minutes=-60))" 2>/dev/null)

# --- notes CRUD (alice)
NOTE_ID=$(curl -s -X POST "$BASE/api/v1/notes" -H "Authorization: Bearer $ALICE_TOKEN" -H "Content-Type: application/json" -d '{"title":"E2E note","body":"created by run_all_tests.sh","category_id":1}' | "$PY" -c "import sys,json; print(json.load(sys.stdin).get('id',''))" 2>/dev/null)
if [ -n "$NOTE_ID" ]; then ok "POST /notes (201, id=$NOTE_ID)"; else fail "POST /notes — could not read id from response"; fi

check_code "GET /notes list (200)"      200 "$BASE/api/v1/notes" -H "Authorization: Bearer $ALICE_TOKEN"
check_code "GET /notes/{id} (200)"      200 "$BASE/api/v1/notes/$NOTE_ID" -H "Authorization: Bearer $ALICE_TOKEN"
check_code "PUT /notes/{id} (200)"      200 -X PUT "$BASE/api/v1/notes/$NOTE_ID" -H "Authorization: Bearer $ALICE_TOKEN" -H "Content-Type: application/json" -d '{"title":"E2E note updated","category_id":1}'
check_code "DELETE /notes/{id} (204)"   204 -X DELETE "$BASE/api/v1/notes/$NOTE_ID" -H "Authorization: Bearer $ALICE_TOKEN"
check_code "GET deleted note (404)"     404 "$BASE/api/v1/notes/$NOTE_ID" -H "Authorization: Bearer $ALICE_TOKEN"

# --- ownership: bob on alice's note 1 -> 404 (NOT 403)
check_code "bob GET alice's note (404)"  404 "$BASE/api/v1/notes/1" -H "Authorization: Bearer $BOB_TOKEN"
check_code "bob PUT alice's note (404)"  404 -X PUT "$BASE/api/v1/notes/1" -H "Authorization: Bearer $BOB_TOKEN" -H "Content-Type: application/json" -d '{"title":"hacked"}'
check_code "bob DELETE alice's note (404)" 404 -X DELETE "$BASE/api/v1/notes/1" -H "Authorization: Bearer $BOB_TOKEN"
check_code "missing note id 999 (404)"   404 "$BASE/api/v1/notes/999" -H "Authorization: Bearer $ALICE_TOKEN"

# --- auth enforcement: 401s
check_code "no token (401)"      401 "$BASE/api/v1/notes"
check_code "garbage token (401)" 401 "$BASE/api/v1/notes" -H "Authorization: Bearer garbage.token.here"
if [ -n "$EXPIRED_TOKEN" ]; then
    check_code "expired token (401)" 401 "$BASE/api/v1/notes" -H "Authorization: Bearer $EXPIRED_TOKEN"
else
    fail "could not generate expired token"
fi

# --- validation: 422
check_code "empty create payload (422)" 422 -X POST "$BASE/api/v1/notes" -H "Authorization: Bearer $ALICE_TOKEN" -H "Content-Type: application/json" -d '{}'
check_code "bad category_id (422)"      422 -X POST "$BASE/api/v1/notes" -H "Authorization: Bearer $ALICE_TOKEN" -H "Content-Type: application/json" -d '{"title":"x","body":"y","category_id":999}'

# --- admin route: 403 vs 200
check_code "user on admin route (403)" 403 "$BASE/api/v1/admin/notes" -H "Authorization: Bearer $ALICE_TOKEN"
check_code "admin on admin route (200)" 200 "$BASE/api/v1/admin/notes" -H "Authorization: Bearer $ADMIN_TOKEN"

# --- promote (admin-only)
check_code "user promotes (403)"        403 -X PATCH "$BASE/api/v1/auth/users/4/role" -H "Authorization: Bearer $BOB_TOKEN" -H "Content-Type: application/json" -d '{"role":"admin"}'
check_code "admin promotes (200)"       200 -X PATCH "$BASE/api/v1/auth/users/4/role" -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" -d '{"role":"admin"}'
check_code "admin promote missing user (404)" 404 -X PATCH "$BASE/api/v1/auth/users/999/role" -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" -d '{"role":"admin"}'

# ---------------------------------------------------------------- summary
echo
echo "=========================================="
echo "  RESULTS:  $PASS passed, $FAIL failed"
echo "=========================================="
if [ "$FAIL" -gt 0 ]; then
    printf '  Failed checks:\n'
    for f in "${FAILURES[@]}"; do printf '    - %s\n' "$f"; done
    exit 1
fi
echo "  All checks passed."
