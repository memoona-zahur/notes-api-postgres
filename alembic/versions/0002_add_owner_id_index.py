"""Add index on notes.owner_id

Ownership filtering now runs on every list/get/update/delete call for
/notes/* (see app/routers/notes.py) — every one of those queries filters on
owner_id, so this index is added now, once that query pattern actually
exists, rather than speculatively in the initial migration.

Revision ID: 0002_add_owner_id_index
Revises: 0001_initial
Create Date: 2026-08-05
"""
from alembic import op

revision = "0002_add_owner_id_index"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_notes_owner_id", "notes", ["owner_id"])


def downgrade() -> None:
    op.drop_index("ix_notes_owner_id", table_name="notes")
