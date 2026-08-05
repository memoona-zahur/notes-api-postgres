"""
Pydantic v2 schemas. Separate Create/Update/Out models per resource so
clients can never set fields they shouldn't (owner_id, created_at, role at
registration time) — those are always derived server-side.
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field


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


# ---- Auth (register/login — beyond the written spec, see DESIGN.md) ----

class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: str
    role: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class RoleUpdate(BaseModel):
    role: str = Field(pattern="^(user|admin)$")
