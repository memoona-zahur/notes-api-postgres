"""
Password hashing, JWT creation/decoding, and the get_current_user
dependency. One shared _decode() collapses missing/garbage/expired tokens
into the same 401. get_current_admin is added in a later step when the
admin route lands.
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
    """Shared by all auth dependencies so missing/garbage/expired are handled identically."""
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
