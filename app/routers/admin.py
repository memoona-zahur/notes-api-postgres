"""
Admin-only route. get_current_admin 403s a valid-but-non-admin token, unlike
the plain 404 that /notes/* uses for ownership — see auth.py's docstring for
why these two failure modes are deliberately different.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth import get_current_admin
from app import models, schemas

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


@router.get("/notes", response_model=list[schemas.NoteRead])
def list_all_notes(
    db: Session = Depends(get_db),
    _admin: models.User = Depends(get_current_admin),
):
    return db.query(models.Note).order_by(models.Note.created_at.desc()).all()
