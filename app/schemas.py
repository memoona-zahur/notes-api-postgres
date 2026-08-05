"""
Pydantic v2 schemas. Note schemas first — the auth schemas (UserRegister,
UserLogin, Token, RoleUpdate) are added in a later step alongside the
login/registration flow.
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


# ---- Notes ----

class CategoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str


class NoteCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    body: str = Field(min_length=1)
    category_id: Optional[int] = None


class NoteUpdate(BaseModel):
    # All fields optional: PUT here means "update the fields you send."
    title: Optional[str] = Field(default=None, min_length=1, max_length=255)
    body: Optional[str] = Field(default=None, min_length=1)
    category_id: Optional[int] = None


class NoteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    body: str
    owner_id: int
    category_id: Optional[int]
    created_at: datetime
