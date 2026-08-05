"""
Password hashing, JWT creation/decoding, and the two auth dependencies.

Two dependencies for the assignment's two different failure modes:
  - get_current_user  -> 401 on missing/garbage/expired token (any /notes/* route)
  - get_current_admin -> 403 on a *valid* token that lacks the admin role claim
                          (the caller is authenticated, just not authorized)

get_current_admin checks the JWT's own "role" claim directly, matching the
spec's literal wording ("requires the admin role claim") — it does not do a
second DB lookup of the user's current role. That's a deliberate trade-off:
a token keeps whatever role it was issued with until it expires, even if an
admin's role is later revoked in the DB. Documented here so it's a known
choice, not a surprise — short token lifetimes (see ACCESS_TOKEN_EXPIRE_MINUTES)
are what bound the blast radius of that trade-off.
"""
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from dotenv import load_dotenv
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.database import get_db
from app import models

load_dotenv()

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "change-me-to-a-long-random-value")
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# auto_error=False: if the header is missing entirely, HTTPBearer would
# otherwise raise its own generic 403. We want a uniform 401 for every
# "not properly authenticated" case (missing/garbage/expired alike).
bearer_scheme = HTTPBearer(auto_error=False)

_UNAUTHENTICATED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Not authenticated",
    headers={"WWW-Authenticate": "Bearer"},
)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(user_id: int, role: str, expires_minutes: Optional[int] = None) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=expires_minutes if expires_minutes is not None else ACCESS_TOKEN_EXPIRE_MINUTES
    )
    payload = {"sub": str(user_id), "role": role, "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def _decode(credentials: Optional[HTTPAuthorizationCredentials]) -> dict:
    """Shared by both dependencies so missing/garbage/expired are handled identically."""
    if credentials is None:
        raise _UNAUTHENTICATED  # missing token
    try:
        return jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise _UNAUTHENTICATED  # expired token
    except jwt.InvalidTokenError:
        raise _UNAUTHENTICATED  # garbage / malformed / wrong signature


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> models.User:
    payload = _decode(credentials)
    user = db.get(models.User, int(payload["sub"]))
    if user is None:
        # Token is well-formed but the user behind it is gone (or was
        # deleted) — still an auth failure, not a 404.
        raise _UNAUTHENTICATED
    return user


def get_current_admin(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> models.User:
    payload = _decode(credentials)
    user = db.get(models.User, int(payload["sub"]))
    if user is None:
        raise _UNAUTHENTICATED
    if payload.get("role") != "admin":
        # Authenticated, just not authorized — 403, not 401.
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin privileges required")
    return user
