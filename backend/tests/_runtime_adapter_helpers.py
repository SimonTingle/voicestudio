"""Shared fakes and harness for the runtime-adapter tests.

Not a test module (no ``test_`` prefix): imported by
``test_runtime_adapter_capabilities.py`` and
``test_runtime_adapter_execute.py``.
"""
from __future__ import annotations

import contextlib
import hashlib
import os
import shutil
import tempfile
import threading
import time

import grpc

from runtime_adapter.gen import runtime_adapter_pb2 as pb2
from runtime_adapter.gen import runtime_adapter_pb2_grpc as pb2_grpc
from runtime_adapter.inventory import (
    STATE_READY,
    DeviceInfo,
    ModelInfo,
)
from runtime_adapter.server import RuntimeContext, create_server

READY_MODEL = ModelInfo(
    catalog_model_id="fake-tts",
    model_version="a" * 40,
    model_digest="sha256:" + "b" * 64,
    precisions=("fp32",),
    features=("tts",),
    state=STATE_READY,
)

DEVICE = DeviceInfo(
    device_id="cpu:0",
    hardware_class="test-cpu",
    total_vram_bytes=8 * 1024**3,
    total_slots=1,
    free_slots=1,
)


class FakeInventory:
    def __init__(self, models=None, devices=None):
        self._models = list(models) if models is not None else [READY_MODEL]
        self._devices = list(devices) if devices is not None else [DEVICE]

    def devices(self, busy_slots: int = 0):
        return [
            DeviceInfo(
                device_id=d.device_id,
                hardware_class=d.hardware_class,
                total_vram_bytes=d.total_vram_bytes,
                total_slots=d.total_slots,
                free_slots=max(0, d.total_slots - busy_slots),
            )
            for d in self._devices
        ]

    def models(self):
        return list(self._models)


class FakeEngine:
    """Half a second of silence at 24 kHz, instantly."""

    sample_rate = 24000

    def __init__(self):
        self.generate_calls = []

    def ensure_ready(self):
        pass

    def generate(self, text, **kw):
        import torch

        self.generate_calls.append((text, kw))
        return torch.zeros(1, 12000)


class SlowEngine(FakeEngine):
    """Sleeps through generate in small slices so tests stay responsive."""

    def __init__(self, seconds: float = 10.0):
        super().__init__()
        self.seconds = seconds
        self.started = threading.Event()

    def generate(self, text, **kw):
        self.started.set()
        deadline = time.monotonic() + self.seconds
        while time.monotonic() < deadline:
            time.sleep(0.01)
        return super().generate(text, **kw)


class FailingEngine(FakeEngine):
    def __init__(self, exc: BaseException, phase: str = "synthesis"):
        super().__init__()
        self._exc = exc
        self._phase = phase

    def ensure_ready(self):
        if self._phase == "model_load":
            raise self._exc

    def generate(self, text, **kw):
        raise self._exc


def make_context(engine=None, inventory=None, **kw) -> RuntimeContext:
    engine = engine if engine is not None else FakeEngine()
    engines = {READY_MODEL.catalog_model_id: engine}
    kw.setdefault("progress_interval", 0.05)
    kw.setdefault("poll_interval", 0.005)
    return RuntimeContext(
        runtime_version="1.2.3-test",
        inventory=inventory if inventory is not None else FakeInventory(),
        engine_provider=lambda model_id: engines[model_id],
        **kw,
    )


@contextlib.contextmanager
def serve_over_socket(context: RuntimeContext, tmp_path=None):
    # A pytest tmp_path routinely exceeds the 103-character Unix-socket path
    # limit on macOS, so the socket gets its own short private tempdir.
    socket_dir = tempfile.mkdtemp(prefix="vs-rta-")
    socket_path = os.path.join(socket_dir, "runtime.sock")
    server = create_server(context, socket_path)
    server.start()
    channel = grpc.insecure_channel(f"unix:{socket_path}")
    try:
        yield pb2_grpc.RuntimeAdapterServiceStub(channel), socket_path
    finally:
        channel.close()
        server.stop(grace=0).wait()
        shutil.rmtree(socket_dir, ignore_errors=True)


def make_execute_request(
    tmp_path,
    text: str = "hello runtime",
    *,
    attempt_id: str = "attempt-1",
    job_id: str = "job-1",
    model: ModelInfo = READY_MODEL,
    device_id: str = "cpu:0",
    deadline_in_s: float = 30.0,
    parameters: dict | None = None,
    input_sha256: str | None = None,
    input_handle: str | None = None,
    output_handle: str | None = None,
) -> pb2.ExecuteRequest:
    if input_handle is None:
        input_path = tmp_path / "input.txt"
        input_path.write_text(text, encoding="utf-8")
        input_handle = str(input_path)
    if input_sha256 is None and text is not None:
        input_sha256 = hashlib.sha256(text.encode("utf-8")).hexdigest()
    if output_handle is None:
        output_handle = str(tmp_path / "output.wav")
    return pb2.ExecuteRequest(
        job_id=job_id,
        attempt_id=attempt_id,
        device_id=device_id,
        slot_id="slot-0",
        model=pb2.ModelSpec(
            catalog_model_id=model.catalog_model_id,
            model_version=model.model_version,
            model_digest=model.model_digest,
            precision="fp32",
        ),
        parameters=parameters or {},
        inputs=[
            pb2.LocalArtifact(
                artifact_id="in-1",
                local_handle=input_handle,
                operation=pb2.LOCAL_ARTIFACT_OPERATION_READ,
                expected_sha256=input_sha256 or "",
                media_type="text/plain",
            )
        ],
        outputs=[
            pb2.LocalArtifact(
                artifact_id="out-1",
                local_handle=output_handle,
                operation=pb2.LOCAL_ARTIFACT_OPERATION_WRITE,
                media_type="audio/wav",
            )
        ],
        deadline_unix_ms=int((time.time() + deadline_in_s) * 1000),
        maximum_preview_bytes=0,
    )


def terminal_of(events):
    last = events[-1].event
    kind = last.WhichOneof("payload")
    assert kind in ("completed", "failed", "canceled"), kind
    return kind, last
