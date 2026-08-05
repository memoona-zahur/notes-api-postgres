"""
Tests run against an isolated in-memory SQLite DB, NOT the Postgres server
from docker-compose — this is a deliberate, common pattern (fast, no
external service needed to run `pytest`), not an oversight. Production
schema is still 100% Alembic-managed against Postgres; this fixture just
uses Base.metadata.create_all() directly against a throwaway SQLite engine,
which is fine for tests since we're not testing Alembic itself here.

Want to run the suite against real Postgres instead? Point TEST_DATABASE_URL
at a Postgres test database (e.g. one more docker-compose service) and this
fixture will use it unchanged — no test code needs to change.
"""
import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.database import Base, get_db
from app.main import app
from app import models
from app.auth import create_access_token, hash_password

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", "sqlite:///:memory:")

_is_sqlite_memory = TEST_DATABASE_URL.startswith("sqlite") and ":memory:" in TEST_DATABASE_URL
engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False} if TEST_DATABASE_URL.startswith("sqlite") else {},
    poolclass=StaticPool if _is_sqlite_memory else None,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture()
def db_session():
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture()
def two_users(db_session):
    """Alice (regular) and Bob (admin) — mirrors seed.py, used to test ownership as two real users."""
    alice = models.User(email="alice@example.com", hashed_password=hash_password("alice-password"), role="user")
    bob = models.User(email="bob_admin@example.com", hashed_password=hash_password("bob-password"), role="admin")
    db_session.add_all([alice, bob])
    db_session.commit()
    db_session.refresh(alice)
    db_session.refresh(bob)
    return {
        "alice": alice,
        "bob": bob,
        "alice_token": create_access_token(user_id=alice.id, role="user"),
        "bob_token": create_access_token(user_id=bob.id, role="admin"),
    }
