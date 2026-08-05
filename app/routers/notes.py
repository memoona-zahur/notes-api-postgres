"""
Every route here depends on get_current_user, so a missing/garbage/expired
token 401s before any handler body runs. Ownership filtering is the next
step — for now the user identifier comes from the token, but queries aren't
scoped to it yet.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth import get_current_user
from app import models, schemas

router = APIRouter(prefix="/api/v1/notes", tags=["notes"])


def _get_note_or_404(db: Session, note_id: int) -> models.Note:
    note = db.get(models.Note, note_id)
    if note is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")
    return note


def _validate_category(db: Session, category_id):
    if category_id is not None and db.get(models.Category, category_id) is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Category not found")


@router.post("", response_model=schemas.NoteRead, status_code=status.HTTP_201_CREATED)
def create_note(
    payload: schemas.NoteCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    _validate_category(db, payload.category_id)
    note = models.Note(**payload.model_dump(), owner_id=current_user.id)
    db.add(note)
    db.commit()
    db.refresh(note)
    return note


@router.get("", response_model=list[schemas.NoteRead])
def list_notes(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return db.query(models.Note).order_by(models.Note.created_at.desc()).all()


@router.get("/{note_id}", response_model=schemas.NoteRead)
def get_note(
    note_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return _get_note_or_404(db, note_id)


@router.put("/{note_id}", response_model=schemas.NoteRead)
def update_note(
    note_id: int,
    payload: schemas.NoteUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    note = _get_note_or_404(db, note_id)
    data = payload.model_dump(exclude_unset=True)
    if "category_id" in data:
        _validate_category(db, data["category_id"])
    for field, value in data.items():
        setattr(note, field, value)
    db.commit()
    db.refresh(note)
    return note


@router.delete("/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_note(
    note_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    note = _get_note_or_404(db, note_id)
    db.delete(note)
    db.commit()
    return None
