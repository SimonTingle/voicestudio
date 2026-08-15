"""Existing gallery voices keep voice-design conditioning after upgrade."""
import os
import sqlite3


_BASE_PROFILES = """
    CREATE TABLE voice_profiles (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        ref_audio_path TEXT,
        ref_text TEXT DEFAULT '',
        instruct TEXT DEFAULT '',
        language TEXT DEFAULT 'Auto',
        locked_audio_path TEXT DEFAULT '',
        seed INTEGER DEFAULT NULL,
        is_locked INTEGER DEFAULT 0,
        personality TEXT DEFAULT '',
        description TEXT DEFAULT '',
        is_demo INTEGER DEFAULT 0,
        created_at REAL
    );
"""


def _repo_root() -> str:
    root = os.path.abspath(os.path.dirname(__file__))
    while root and root != "/" and not os.path.isfile(os.path.join(root, "alembic.ini")):
        root = os.path.dirname(root)
    assert os.path.isfile(os.path.join(root, "alembic.ini")), "alembic.ini not found"
    return root


def _upgrade(db_path: str, target: str = "head") -> None:
    from alembic import command
    from alembic.config import Config

    config = Config(os.path.join(_repo_root(), "alembic.ini"))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    command.upgrade(config, target)


def test_migration_marks_only_materialized_archetypes_as_design(tmp_path):
    database = tmp_path / "gallery-voices.db"
    with sqlite3.connect(str(database)) as conn:
        conn.executescript(_BASE_PROFILES)

    _upgrade(str(database), target="0010_remote_worker_schema")
    with sqlite3.connect(str(database)) as conn:
        conn.executemany(
            "INSERT INTO voice_profiles (id, name, personality, kind) VALUES (?, ?, ?, 'clone')",
            [
                ("gallery", "The Librarian", "feat_00_the_librarian"),
                ("import", "User import", "custom-import"),
            ],
        )

    _upgrade(str(database))
    with sqlite3.connect(str(database)) as conn:
        kinds = dict(conn.execute("SELECT id, kind FROM voice_profiles").fetchall())

    assert kinds["gallery"] == "design"
    assert kinds["import"] == "clone"
