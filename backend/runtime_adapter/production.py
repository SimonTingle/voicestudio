"""Wires the adapter to the real VoiceStudio backend.

Kept separate from ``server.py`` so tests can build a
:class:`~runtime_adapter.server.RuntimeContext` from fakes without importing
torch or the engine registry.
"""
from __future__ import annotations

import sys

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

def prewarm_engines(context: RuntimeContext) -> None:
    """Load and compile every READY model before the socket accepts work.

    The GPU Gateway leases an attempt for a bounded window and renews it from
    execution evidence. A cold engine produces no evidence: weight loading and
    torch compilation can run for minutes emitting nothing, so the lease
    expires mid-load, the attempt is fenced, the Job requeues, and the next
    attempt pays the same cost — a loop that never yields audio.

    Paying that cost once at startup, before the adapter is reachable, means
    the first real Execute begins inference immediately. Preflight already
    refuses a runtime with no READY model, so a failure here is reported and
    the model is dropped from the advertised set rather than being offered as
    schedulable capacity the node cannot actually serve promptly.
    """
    ensure_backend_on_path()
    for model in context.inventory.models():
        if model.state != "ready":
            continue
        try:
            context.engine_provider(model.catalog_model_id)
        except Exception as error:  # noqa: BLE001 - reported, never fatal
            print(
                f"runtime adapter: prewarm of {model.catalog_model_id} failed: {error}",
                file=sys.stderr,
            )
