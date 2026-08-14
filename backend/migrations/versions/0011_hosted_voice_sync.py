"""Opt-in hosted Voice ID on local profiles.

Revision ID: 0011_hosted_voice_sync
Revises: 0010_remote_worker_schema
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0011_hosted_voice_sync"
down_revision: Union[str, None] = "0010_remote_worker_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(table: str, column: str) -> bool:
    rows = op.get_bind().execute(sa.text(f"PRAGMA table_info({table})")).fetchall()
    return any(row[1] == column for row in rows)


def upgrade() -> None:
    if not _has_column("voice_profiles", "hosted_voice_id"):
        op.add_column("voice_profiles", sa.Column("hosted_voice_id", sa.Text(), nullable=True, server_default=""))


def downgrade() -> None:
    if _has_column("voice_profiles", "hosted_voice_id"):
        op.drop_column("voice_profiles", "hosted_voice_id")
