"""Import-path bootstrap for running outside the FastAPI app.

The backend is laid out to run with ``--app-dir backend`` (imports like
``services.tts_backend`` resolve against the ``backend/`` directory). When
the adapter is launched as ``python -m backend.runtime_adapter`` from the
repo root, ``backend/`` is a namespace package but not on ``sys.path`` — so
call :func:`ensure_backend_on_path` before any ``services.*`` / ``core.*``
import. Idempotent; mirrors ``backend/tests/conftest.py``.
"""
from __future__ import annotations

import os
import sys


def ensure_backend_on_path() -> str:
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if backend_dir not in sys.path:
        sys.path.insert(0, backend_dir)
    return backend_dir
