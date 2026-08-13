"""``--selfcheck``: validate the Go preflight's expectations against ourselves.

Starts the server on a private temp socket, then runs a Python port of
``internal/gateway/preflight.go``'s checks over the wire: socket-path safety,
READY health with version evidence, identical versions across Health and
GetCapabilities, valid unique devices, and at least one explicitly READY,
digest-pinned model with a version and precisions. Prints only a bounded
readiness summary (never handles, paths, or credentials) and exits nonzero on
any failed expectation — the same fail-closed behavior a node deployment gets
from ``cmd/runtime-adapter-preflight``.
"""
from __future__ import annotations

import os
import stat as stat_module
import tempfile
from dataclasses import dataclass

import grpc

from .gen import runtime_adapter_pb2 as pb2
from .gen import runtime_adapter_pb2_grpc as pb2_grpc

_MAX_UINT32 = 2**32 - 1


class PreflightError(Exception):
    """One failed preflight expectation, with a bounded message."""


@dataclass(frozen=True)
class PreflightSummary:
    socket_path: str
    runtime_version: str
    adapter_version: str
    device_count: int
    ready_model_count: int
    total_slots: int
    free_slots: int

    def render(self) -> str:
        return (
            f"runtime={self.runtime_version} adapter={self.adapter_version} "
            f"devices={self.device_count} ready_models={self.ready_model_count} "
            f"slots={self.free_slots}/{self.total_slots}"
        )


def validate_socket_file(socket_path: str) -> None:
    if not socket_path or not os.path.isabs(socket_path):
        raise PreflightError("socket path must be absolute")
    info = os.lstat(socket_path)
    if stat_module.S_ISLNK(info.st_mode) or not stat_module.S_ISSOCK(info.st_mode):
        raise PreflightError("endpoint must be a local Unix socket")
    parent = os.stat(os.path.dirname(socket_path))
    if not stat_module.S_ISDIR(parent.st_mode) or parent.st_mode & 0o002:
        raise PreflightError("socket directory is unsafe")


def run_preflight(socket_path: str, timeout_s: float = 10.0) -> PreflightSummary:
    """Port of ``PreflightRuntime`` + ``validateRuntimeCapabilities``."""
    validate_socket_file(socket_path)
    with grpc.insecure_channel(f"unix:{socket_path}") as channel:
        stub = pb2_grpc.RuntimeAdapterServiceStub(channel)
        try:
            health = stub.Health(pb2.HealthRequest(), timeout=timeout_s)
        except grpc.RpcError as exc:
            raise PreflightError(f"health call failed: {exc.code().name}")
        if (
            health.state != pb2.SERVING_STATE_READY
            or not health.runtime_version.strip()
            or not health.adapter_version.strip()
        ):
            raise PreflightError("runtime is not ready with versioned adapter evidence")
        try:
            caps = stub.GetCapabilities(pb2.GetCapabilitiesRequest(), timeout=timeout_s)
        except grpc.RpcError as exc:
            raise PreflightError(f"capabilities call failed: {exc.code().name}")
    return _validate_capabilities(socket_path, health, caps)


def _validate_capabilities(socket_path, health, caps) -> PreflightSummary:
    if not caps.runtime_version.strip() or not caps.adapter_version.strip():
        raise PreflightError("capabilities lack version evidence")
    if (
        caps.runtime_version != health.runtime_version
        or caps.adapter_version != health.adapter_version
    ):
        raise PreflightError("health and capabilities versions disagree")
    if not caps.devices:
        raise PreflightError("no execution devices reported")
    total_slots = free_slots = 0
    seen_devices: set[str] = set()
    for device in caps.devices:
        if (
            not device.device_id.strip()
            or not device.hardware_class.strip()
            or device.total_vram_bytes == 0
            or device.total_slots == 0
            or device.free_slots > device.total_slots
        ):
            raise PreflightError("invalid execution device reported")
        if device.device_id in seen_devices:
            raise PreflightError("duplicate execution device reported")
        seen_devices.add(device.device_id)
        if (
            total_slots + device.total_slots > _MAX_UINT32
            or free_slots + device.free_slots > _MAX_UINT32
        ):
            raise PreflightError("slot total overflows protocol limit")
        total_slots += device.total_slots
        free_slots += device.free_slots
    ready = 0
    seen_models: set[tuple[str, str, str]] = set()
    for model in caps.models:
        if model.state != pb2.RUNTIME_MODEL_STATE_READY:
            continue
        if (
            not model.catalog_model_id.strip()
            or not model.model_version.strip()
            or not model.model_digest.strip()
            or not model.precisions
        ):
            raise PreflightError("invalid ready model reported")
        identity = (model.catalog_model_id, model.model_version, model.model_digest)
        if identity in seen_models:
            raise PreflightError("duplicate ready model reported")
        seen_models.add(identity)
        ready += 1
    if ready == 0:
        raise PreflightError("no ready model reported")
    return PreflightSummary(
        socket_path=socket_path,
        runtime_version=health.runtime_version,
        adapter_version=health.adapter_version,
        device_count=len(caps.devices),
        ready_model_count=ready,
        total_slots=total_slots,
        free_slots=free_slots,
    )


def selfcheck(timeout_s: float = 10.0) -> int:
    """Start the production server on a temp socket and preflight it."""
    from .production import build_runtime_context  # noqa: PLC0415
    from .server import create_server  # noqa: PLC0415

    context = build_runtime_context()
    warm = getattr(context.inventory, "warm", None)
    if callable(warm):
        print("selfcheck: warming model inventory (first run hashes weights)…")
        warm()
    # Short prefix: macOS caps Unix-socket paths at 103 characters and the
    # default macOS tempdir is already ~60 characters deep.
    with tempfile.TemporaryDirectory(prefix="vs-rta-") as tmp:
        os.chmod(tmp, 0o700)
        socket_path = os.path.join(tmp, "runtime.sock")
        server = create_server(context, socket_path)
        server.start()
        try:
            summary = run_preflight(socket_path, timeout_s=timeout_s)
        except PreflightError as failure:
            print(f"selfcheck: FAIL: {failure}")
            return 1
        finally:
            server.stop(grace=2).wait()
    print(f"selfcheck: OK: {summary.render()}")
    return 0
