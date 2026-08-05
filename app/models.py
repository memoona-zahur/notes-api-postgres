"""
ORM models. Note is the "many" side of two relationships (owner, category),
matching Wednesday's Task/Category shape on a new domain — see DESIGN.md.
"""
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship

from app.database import Base


class User(Base):
    """
    email/hashed_password/role exist because login is a real requirement
    for a working app, even though the written spec never mentions
    registration — see DESIGN.md's "beyond the written spec" section.
    """
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False, default="user", server_default="user")

    # cascade="all, delete-orphan": deleting a user cleans up their notes too.
    notes = relationship("Note", back_populates="owner", cascade="all, delete-orphan")

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"


class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)

    notes = relationship("Note", back_populates="category")


class Note(Base):
    __tablename__ = "notes"

    id = Column(Integer, primary_key=True)
    title = Column(String(255), nullable=False)
    body = Column(Text, nullable=False)

    # index=True reflects the *current* schema state. It was added by
    # migration 0002, not 0001 — see that migration's docstring for why.
    owner_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    owner = relationship("User", back_populates="notes")
    category = relationship("Category", back_populates="notes")
