"""Mark materialized gallery archetypes as voice-design profiles.

Revision ID: 0012_mark_archetype_profiles_design
Revises: 0010_remote_worker_schema
Create Date: 2026-08-15 00:00:00.000000

``POST /archetypes/{id}/use`` stores the archetype id in ``personality`` and
also stores a locally rendered identity WAV.  That WAV must not make the
profile a clone: the archetype's instruct recipe is authoritative.  Older
rows relied on the ``kind='clone'`` default and therefore selected the clone
generation path.  This data-only migration fixes every row whose personality
is a current archetype id, leaving unrelated persona and marketplace imports
untouched.
"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import inspect


revision: str = "0012_mark_archetype_profiles_design"
down_revision: Union[str, None] = "0010_remote_worker_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if "voice_profiles" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("voice_profiles")}
    if not {"kind", "personality"}.issubset(columns):
        return

    # The catalog is intentionally a value object, so checking an id against
    # its current generated list is the precise provenance test.  The
    # parameterized update avoids treating any other personality string as an
    # archetype.
    from core import archetypes

    archetype_ids = [item["id"] for item in archetypes.list_archetypes()]
    for archetype_id in archetype_ids:
        bind.exec_driver_sql(
            "UPDATE voice_profiles SET kind = 'design' "
            "WHERE personality = ? AND (kind IS NULL OR kind = '' OR kind = 'clone')",
            (archetype_id,),
        )


def downgrade() -> None:
    # Do not silently convert voice-design profiles back to clones: that would
    # reintroduce the generation mismatch for existing user data.
    pass
