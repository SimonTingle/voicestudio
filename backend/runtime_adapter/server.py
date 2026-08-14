"""The gRPC server: Unix-domain socket only, no HTTP, no TCP.

``Health`` and ``GetCapabilities`` read the same version constants from one
:class:`RuntimeContext`, so the "identical versions" preflight expectation
holds by construction. Socket-path safety mirrors the Go preflight's checks
(absolute path, no symlink, parent directory not world-writable) at bind time
so an unsafe deployment fails closed on our side too.
"""
from __future__ import annotations

import os
import stat as stat_module
import threading
from concurrent import futures
from dataclasses import dataclass, field

import grpc

from . import ADAPTER_VERSION, DEFAULT_SOCKET_PATH, SOCKET_ENV
from .executor import AttemptRegistry, Executor
from .gen import runtime_adapter_pb2 as pb2
from .gen import runtime_adapter_pb2_grpc as pb2_grpc
from .inventory import (
    STATE_FAILED,
    STATE_INSTALLED,
    STATE_LOADING,
    STATE_READY,
)

_MODEL_STATE_TO_PB = {
    STATE_INSTALLED: pb2.RUNTIME_MODEL_STATE_INSTALLED,
    STATE_LOADING: pb2.RUNTIME_MODEL_STATE_LOADING,
    STATE_READY: pb2.RUNTIME_MODEL_STATE_READY,
    STATE_FAILED: pb2.RUNTIME_MODEL_STATE_FAILED,
}


@dataclass
class RuntimeContext:
    """Everything the servicer needs; tests build it from fakes."""

    runtime_version: str
    inventory: object
    engine_provider: object
    adapter_version: str = ADAPTER_VERSION
    slot_limit: int = 1
    progress_interval: float = 0.5
    poll_interval: float = 0.02
    registry: AttemptRegistry = field(default_factory=AttemptRegistry)

    def executor(self) -> Executor:
        return Executor(
            self.inventory,
            self.engine_provider,
            self.registry,
            slot_limit=self.slot_limit,
            progress_interval=self.progress_interval,
            poll_interval=self.poll_interval,
        )


class RuntimeAdapterServicer(pb2_grpc.RuntimeAdapterServiceServicer):
    def __init__(self, context: RuntimeContext):
        self._context = context
        self._executor = context.executor()

    def Health(self, request, grpc_context):
        flags: list[str] = []
        state = pb2.SERVING_STATE_READY
        try:
            devices = self._context.inventory.devices(
                busy_slots=self._context.registry.active_count()
            )
            models = self._context.inventory.models()
        except Exception:
            return pb2.HealthResponse(
                state=pb2.SERVING_STATE_UNHEALTHY,
                runtime_version=self._context.runtime_version,
                adapter_version=self._context.adapter_version,
                health_flags=["inventory-error"],
            )
        if not devices:
            state = pb2.SERVING_STATE_UNHEALTHY
            flags.append("no-device")
        if not any(model.state == STATE_READY for model in models):
            state = max(state, pb2.SERVING_STATE_DEGRADED)
            flags.append("no-ready-model")
        return pb2.HealthResponse(
            state=state,
            runtime_version=self._context.runtime_version,
            adapter_version=self._context.adapter_version,
            health_flags=flags,
        )

    def GetCapabilities(self, request, grpc_context):
        busy = self._context.registry.active_count()
        response = pb2.GetCapabilitiesResponse(
            runtime_version=self._context.runtime_version,
            adapter_version=self._context.adapter_version,
        )
        for device in self._context.inventory.devices(busy_slots=busy):
            response.devices.append(
                pb2.RuntimeDevice(
                    device_id=device.device_id,
                    hardware_class=device.hardware_class,
                    total_vram_bytes=device.total_vram_bytes,
                    total_slots=device.total_slots,
                    free_slots=device.free_slots,
                )
            )
        for model in self._context.inventory.models():
            response.models.append(
                pb2.RuntimeModel(
                    catalog_model_id=model.catalog_model_id,
                    model_version=model.model_version,
                    model_digest=model.model_digest,
                    precisions=list(model.precisions),
                    features=list(model.features),
                    state=_MODEL_STATE_TO_PB.get(
                        model.state, pb2.RUNTIME_MODEL_STATE_UNSPECIFIED
                    ),
                )
            )
        return response

    def Execute(self, request, grpc_context):
        yield from self._executor.execute(request, grpc_context)

    def Cancel(self, request, grpc_context):
        disposition = self._context.registry.cancel(request.job_id, request.attempt_id)
        return pb2.CancelResponse(disposition=disposition)


def resolve_socket_path(explicit: str | None = None) -> str:
    return (
        (explicit or "").strip()
        or os.environ.get(SOCKET_ENV, "").strip()
        or DEFAULT_SOCKET_PATH
    )


def prepare_socket(socket_path: str) -> str:
    """Fail closed on any unsafe socket placement; remove only a stale socket."""
    if not socket_path or not os.path.isabs(socket_path):
        raise ValueError("runtime socket path must be absolute")
    parent = os.path.dirname(socket_path)
    try:
        parent_stat = os.stat(parent)
    except OSError as exc:
        raise ValueError(f"runtime socket directory is missing: {exc}") from exc
    if not stat_module.S_ISDIR(parent_stat.st_mode) or parent_stat.st_mode & 0o002:
        raise ValueError("runtime socket directory is unsafe (world-writable?)")
    try:
        existing = os.lstat(socket_path)
    except FileNotFoundError:
        return socket_path
    if stat_module.S_ISSOCK(existing.st_mode):
        os.unlink(socket_path)  # stale socket from a previous run
        return socket_path
    raise ValueError("runtime socket path exists and is not a socket")


def create_server(
    context: RuntimeContext, socket_path: str, *, max_workers: int | None = None
) -> grpc.Server:
    prepare_socket(socket_path)
    workers = max_workers or max(8, context.slot_limit * 2 + 4)
    server = grpc.server(
        futures.ThreadPoolExecutor(
            max_workers=workers, thread_name_prefix="runtime-adapter"
        )
    )
    pb2_grpc.add_RuntimeAdapterServiceServicer_to_server(
        RuntimeAdapterServicer(context), server
    )
    bound = server.add_insecure_port(f"unix:{socket_path}")
    if bound == 0:
        raise RuntimeError("failed to bind the runtime adapter socket")
    return server


def serve(context: RuntimeContext, socket_path: str) -> int:
    """Run until SIGINT/SIGTERM. Returns a process exit code."""
    import signal  # noqa: PLC0415

    warm = getattr(context.inventory, "warm", None)
    if callable(warm):
        warm()  # hash installed snapshots before the socket exists
    server = create_server(context, socket_path)
    server.start()
    try:
        os.chmod(socket_path, 0o660)  # gateway runs under the same service identity
    except OSError:
        pass
    stop = threading.Event()

    def _stop(_signum, _frame):
        stop.set()

    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)
    stop.wait()
    server.stop(grace=10).wait()
    try:
        os.unlink(socket_path)
    except OSError:
        pass
    return 0
