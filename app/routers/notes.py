"""
Every route here depends on get_current_user, so a missing/garbage/expired
token 401s before any handler body runs. Every query is filtered by
owner_id == current_user.id, so "not yours" and "doesn't exist" look
identical from the outside — both come back as a plain 404.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth import get_current_user
from app import models, schemas

router = APIRouter(prefix="/api/v1/notes", tags=["notes"])


def _get_owned_note_or_404(db: Session, note_id: int, owner_id: int) -> models.Note:
    """
    Single owner_id filter in the query itself (not a fetch-then-check)
    means a stranger's note is indistinguishable from a nonexistent one —
    that's what makes the 404-not-403 rule actually hold.
    """
    note = (
        db.query(models.Note)
        .filter(models.Note.id == note_id, models.Note.owner_id == owner_id)
        .first()
    )
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
    return db.query(models.Note).filter(models.Note.owner_id == current_user.id).order_by(models.Note.created_at.desc()).all()


@router.get("/{note_id}", response_model=schemas.NoteRead)
def get_note(
    note_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return _get_owned_note_or_404(db, note_id, current_user.id)


@router.put("/{note_id}", response_model=schemas.NoteRead)
def update_note(
    note_id: int,
    payload: schemas.NoteUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    note = _get_owned_note_or_404(db, note_id, current_user.id)
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
    note = _get_owned_note_or_404(db, note_id, current_user.id)
    db.delete(note)
    db.commit()
    return None
