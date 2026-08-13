"""Wires the adapter to the real VoiceStudio backend.

Kept separate from ``server.py`` so tests can build a
:class:`~runtime_adapter.server.RuntimeContext` from fakes without importing
torch or the engine registry.
"""
from __future__ import annotations

from . import ADAPTER_VERSION
from ._paths import ensure_backend_on_path
from .inventory import ProductionInventory, slots_per_device
from .server import RuntimeContext


def production_engine_provider(catalog_model_id: str):
    """Resolve a READY catalog model id to its cached engine instance."""
    ensure_backend_on_path()
    from services.tts_backend import get_engine_instance_for  # noqa: PLC0415

    return get_engine_instance_for(catalog_model_id)


def build_runtime_context() -> RuntimeContext:
    ensure_backend_on_path()
    from core.version import APP_VERSION  # noqa: PLC0415

    slots = slots_per_device()
    return RuntimeContext(
        runtime_version=APP_VERSION,
        adapter_version=ADAPTER_VERSION,
        inventory=ProductionInventory(slots=slots),
        engine_provider=production_engine_provider,
        slot_limit=slots,
    )
