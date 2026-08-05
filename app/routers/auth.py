"""
Registration and login — not in the assignment's required endpoint list,
but without these there's no way to actually obtain a JWT to use the rest
of the API with. See DESIGN.md's "beyond the written spec" section for why
these exist and what they deliberately don't allow (self-granted admin).
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth import (
    create_access_token,
    get_current_admin,
    hash_password,
    verify_password,
)
from app.database import get_db
from app import models, schemas

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/register", response_model=schemas.UserRead, status_code=status.HTTP_201_CREATED)
def register(payload: schemas.UserRegister, db: Session = Depends(get_db)):
    existing = db.query(models.User).filter(models.User.email == payload.email).first()
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    # role is always "user" here — self-registration can never grant admin,
    # regardless of what a client tries to send (UserRegister doesn't even
    # expose a role field, so there's nothing to ignore-and-override).
    user = models.User(email=payload.email, hashed_password=hash_password(payload.password), role="user")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=schemas.Token)
def login(payload: schemas.UserLogin, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == payload.email).first()
    # Same error for "no such user" and "wrong password" — don't leak which
    # one it was, same reasoning as the notes ownership 404.
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")

    token = create_access_token(user_id=user.id, role=user.role)
    return schemas.Token(access_token=token)


@router.patch("/users/{user_id}/role", response_model=schemas.UserRead)
def update_user_role(
    user_id: int,
    payload: schemas.RoleUpdate,
    db: Session = Depends(get_db),
    _admin: models.User = Depends(get_current_admin),
):
    """
    Admin-only. The only way to create a second admin without touching the
    DB directly — bootstrap the *first* admin via seed.py, then use this.
    """
    user = db.get(models.User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    user.role = payload.role
    db.commit()
    db.refresh(user)
    return user
