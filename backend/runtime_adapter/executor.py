"""Execute/Cancel: attempt registry, validation, and the event stream.

One ``Execute`` call is one *attempt*. The generator emits::

    started → progress* → exactly one of completed | failed | canceled

The engine call itself (``ensure_ready`` + ``generate``) runs on a daemon
worker thread; the streaming generator polls it, emitting bounded heartbeat
progress and enforcing the request deadline and cancellation. A blocking
engine cannot be interrupted mid-kernel, so on cancel/deadline the thread is
abandoned and its result discarded — the terminal event is what the Gateway
acts on, and slot accounting is released only when the thread actually exits.

The adapter never turns a customer string into a filesystem path: it touches
exactly the local handles the request carries, after validation.
"""
from __future__ import annotations

import os
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass, field

from . import codes
from ._paths import ensure_backend_on_path
from .digest import file_sha256
from .gen import runtime_adapter_pb2 as pb2
from .inventory import STATE_READY

_MAX_TEXT_BYTES = 512_000
_MAX_REF_AUDIO_BYTES = 100 * 1024 * 1024
_MAX_DEADLINE_S = 24 * 3600.0
_MAX_PROGRESS_EVENTS = 512

#: Typed, bounded Execute parameters → the engine ``generate()`` kwarg of the
#: same name. Kinds: ("string", max_len) / ("integer", lo, hi) /
#: ("number", lo, hi) / ("boolean",).
PARAMETER_SPECS: dict[str, tuple] = {
    "language": ("string", 32),
    "ref_text": ("string", 4096),
    "instruct": ("string", 2048),
    "description": ("string", 2048),
    "speed": ("number", 0.25, 4.0),
    "guidance_scale": ("number", 0.0, 16.0),
    "num_step": ("integer", 1, 128),
    # Gallery reference voices persist their OSS design seed.  Accept it at
    # the hosted runtime boundary so a selected voice produces the same take.
    "seed": ("integer", 0, 4_294_967_295),
}


# ── attempt registry ──────────────────────────────────────────────────────


@dataclass
class AttemptRecord:
    job_id: str
    attempt_id: str
    cancel: threading.Event = field(default_factory=threading.Event)
    terminal: str | None = None  # "completed" | "failed" | "canceled"


class AttemptRegistry:
    """Attempt bookkeeping: admission, idempotent cancel, bounded history."""

    def __init__(self, max_terminal: int = 4096):
        self._lock = threading.Lock()
        self._active: dict[str, AttemptRecord] = {}
        self._terminal: OrderedDict[str, AttemptRecord] = OrderedDict()
        self._max_terminal = max_terminal

    def begin(self, job_id: str, attempt_id: str, slot_limit: int) -> AttemptRecord:
        with self._lock:
            if attempt_id in self._active or attempt_id in self._terminal:
                raise codes.ExecutionFailure(
                    codes.INPUT_ATTEMPT_DUPLICATE, "attempt id already used"
                )
            if len(self._active) >= max(1, slot_limit):
                raise codes.ExecutionFailure(
                    codes.GPU_SLOTS_EXHAUSTED, "no free execution slot"
                )
            record = AttemptRecord(job_id=job_id, attempt_id=attempt_id)
            self._active[attempt_id] = record
            return record

    def finish(self, attempt_id: str, terminal: str) -> None:
        with self._lock:
            record = self._active.pop(attempt_id, None)
            if record is None:
                return
            record.terminal = terminal
            self._terminal[attempt_id] = record
            while len(self._terminal) > self._max_terminal:
                self._terminal.popitem(last=False)

    def active_count(self) -> int:
        with self._lock:
            return len(self._active)

    def cancel(self, job_id: str, attempt_id: str) -> int:
        """Idempotent by attempt id; returns a proto CancelDisposition."""
        with self._lock:
            record = self._active.get(attempt_id)
            if record is not None:
                if job_id and record.job_id and job_id != record.job_id:
                    return pb2.CANCEL_DISPOSITION_NOT_FOUND
                record.cancel.set()
                return pb2.CANCEL_DISPOSITION_ACCEPTED
            record = self._terminal.get(attempt_id)
            if record is not None:
                if job_id and record.job_id and job_id != record.job_id:
                    return pb2.CANCEL_DISPOSITION_NOT_FOUND
                return pb2.CANCEL_DISPOSITION_ALREADY_TERMINAL
        return pb2.CANCEL_DISPOSITION_NOT_FOUND


# ── request validation ────────────────────────────────────────────────────


@dataclass
class ValidatedRequest:
    text: str
    output_handle: str
    output_media_type: str
    output_size_bound: int
    engine_kwargs: dict
    deadline_monotonic: float
    catalog_model_id: str


def _validate_handle(handle: str, code: str = codes.INPUT_HANDLE_INVALID) -> str:
    cleaned = (handle or "").strip()
    if (
        not cleaned
        or "\x00" in cleaned
        or "://" in cleaned
        or not os.path.isabs(cleaned)
        or os.path.normpath(cleaned) != cleaned
    ):
        raise codes.ExecutionFailure(code, "local handle must be an absolute path")
    return cleaned


def _read_input_file(artifact, max_bytes: int) -> bytes:
    path = _validate_handle(artifact.local_handle)
    try:
        stat = os.lstat(path)
    except OSError as exc:
        raise codes.ExecutionFailure(
            codes.STORAGE_READ_FAILED, f"input handle unreadable: {type(exc).__name__}"
        )
    import stat as stat_module  # noqa: PLC0415

    if not stat_module.S_ISREG(stat.st_mode):
        raise codes.ExecutionFailure(
            codes.INPUT_HANDLE_INVALID, "input handle must be a regular file"
        )
    bound = max_bytes
    if 0 < artifact.expected_size_bytes <= max_bytes:
        bound = artifact.expected_size_bytes
    if stat.st_size > bound:
        raise codes.ExecutionFailure(
            codes.INPUT_TEXT_TOO_LARGE, "input exceeds its size bound"
        )
    try:
        with open(path, "rb") as fh:
            data = fh.read(bound + 1)
    except OSError as exc:
        raise codes.ExecutionFailure(
            codes.STORAGE_READ_FAILED, f"input read failed: {type(exc).__name__}"
        )
    if len(data) > bound:
        raise codes.ExecutionFailure(
            codes.INPUT_TEXT_TOO_LARGE, "input exceeds its size bound"
        )
    expected = (artifact.expected_sha256 or "").strip().lower().removeprefix("sha256:")
    if expected:
        import hashlib  # noqa: PLC0415

        if hashlib.sha256(data).hexdigest() != expected:
            raise codes.ExecutionFailure(
                codes.INPUT_CHECKSUM_MISMATCH, "input checksum mismatch"
            )
    return data


def _typed_parameter(name: str, value) -> object:
    spec = PARAMETER_SPECS.get(name)
    if spec is None:
        raise codes.ExecutionFailure(
            codes.INPUT_PARAMETER_UNKNOWN, f"unknown parameter {name!r}"
        )
    kind = spec[0]
    which = value.WhichOneof("value")
    if kind == "string":
        if which != "string_value":
            raise codes.ExecutionFailure(
                codes.INPUT_PARAMETER_TYPE, f"parameter {name!r} must be a string"
            )
        text = value.string_value
        if len(text) > spec[1]:
            raise codes.ExecutionFailure(
                codes.INPUT_PARAMETER_RANGE, f"parameter {name!r} too long"
            )
        return text
    if kind == "integer":
        if which != "integer_value":
            raise codes.ExecutionFailure(
                codes.INPUT_PARAMETER_TYPE, f"parameter {name!r} must be an integer"
            )
        number = value.integer_value
        if not spec[1] <= number <= spec[2]:
            raise codes.ExecutionFailure(
                codes.INPUT_PARAMETER_RANGE, f"parameter {name!r} out of range"
            )
        return int(number)
    if kind == "number":
        if which == "number_value":
            number = value.number_value
        elif which == "integer_value":
            number = float(value.integer_value)
        else:
            raise codes.ExecutionFailure(
                codes.INPUT_PARAMETER_TYPE, f"parameter {name!r} must be a number"
            )
        if not spec[1] <= number <= spec[2]:
            raise codes.ExecutionFailure(
                codes.INPUT_PARAMETER_RANGE, f"parameter {name!r} out of range"
            )
        return float(number)
    if which != "boolean_value":
        raise codes.ExecutionFailure(
            codes.INPUT_PARAMETER_TYPE, f"parameter {name!r} must be a boolean"
        )
    return bool(value.boolean_value)


# ── the executor ──────────────────────────────────────────────────────────


class Executor:
    """Validates and runs attempts against an inventory + engine provider."""

    def __init__(
        self,
        inventory,
        engine_provider,
        registry: AttemptRegistry,
        *,
        slot_limit: int = 1,
        progress_interval: float = 0.5,
        poll_interval: float = 0.02,
        clock=time.monotonic,
    ):
        self._inventory = inventory
        self._engine_provider = engine_provider
        self._registry = registry
        self._slot_limit = max(1, slot_limit)
        self._progress_interval = progress_interval
        self._poll_interval = poll_interval
        self._clock = clock

    # -- validation ----------------------------------------------------

    def _validate(self, request) -> ValidatedRequest:
        now_ms = int(time.time() * 1000)
        if request.deadline_unix_ms <= now_ms:
            raise codes.ExecutionFailure(
                codes.INPUT_DEADLINE_INVALID, "deadline is not in the future"
            )
        budget_s = min((request.deadline_unix_ms - now_ms) / 1000.0, _MAX_DEADLINE_S)

        model = self._validate_model(request.model)
        self._validate_device(request.device_id)

        text_artifact, ref_artifact = self._split_inputs(request.inputs)
        output = self._single_output(request.outputs)
        output_handle = _validate_handle(output.local_handle)
        parent = os.path.dirname(output_handle)
        if not os.path.isdir(parent):
            raise codes.ExecutionFailure(
                codes.INPUT_HANDLE_INVALID, "output handle directory does not exist"
            )

        raw = _read_input_file(text_artifact, _MAX_TEXT_BYTES)
        try:
            text = raw.decode("utf-8").strip()
        except UnicodeDecodeError:
            raise codes.ExecutionFailure(
                codes.INPUT_TEXT_ENCODING, "input text is not valid UTF-8"
            )
        if not text:
            raise codes.ExecutionFailure(codes.INPUT_TEXT_EMPTY, "input text is empty")

        engine_kwargs: dict = {}
        for name in sorted(request.parameters):
            engine_kwargs[name] = _typed_parameter(name, request.parameters[name])
        if ref_artifact is not None:
            _read_input_file(ref_artifact, _MAX_REF_AUDIO_BYTES)  # existence/bounds/checksum
            engine_kwargs["ref_audio"] = _validate_handle(ref_artifact.local_handle)

        return ValidatedRequest(
            text=text,
            output_handle=output_handle,
            output_media_type=output.media_type or "audio/wav",
            output_size_bound=int(output.expected_size_bytes),
            engine_kwargs=engine_kwargs,
            deadline_monotonic=self._clock() + budget_s,
            catalog_model_id=request.model.catalog_model_id,
        )

    def _validate_model(self, spec):
        wanted = (spec.catalog_model_id or "").strip()
        if not wanted:
            raise codes.ExecutionFailure(
                codes.INPUT_MODEL_UNKNOWN, "catalog model id is required"
            )
        matches = [
            model
            for model in self._inventory.models()
            if model.catalog_model_id == wanted
        ]
        if not matches:
            raise codes.ExecutionFailure(codes.INPUT_MODEL_UNKNOWN, "model not present")
        model = matches[0]
        if model.state != STATE_READY:
            raise codes.ExecutionFailure(
                codes.INPUT_MODEL_NOT_READY, "model is not READY"
            )
        if spec.model_version and spec.model_version != model.model_version:
            raise codes.ExecutionFailure(
                codes.INPUT_MODEL_UNKNOWN, "model version mismatch"
            )
        if not spec.model_digest or spec.model_digest != model.model_digest:
            raise codes.ExecutionFailure(
                codes.INPUT_MODEL_DIGEST_MISMATCH, "approved model digest mismatch"
            )
        if spec.precision and spec.precision not in model.precisions:
            raise codes.ExecutionFailure(
                codes.INPUT_MODEL_PRECISION, "precision not offered by this model"
            )
        return model

    def _validate_device(self, device_id: str) -> None:
        wanted = (device_id or "").strip()
        if not wanted:
            raise codes.ExecutionFailure(
                codes.INPUT_DEVICE_UNKNOWN, "device id is required"
            )
        known = {device.device_id for device in self._inventory.devices()}
        if wanted not in known:
            raise codes.ExecutionFailure(
                codes.INPUT_DEVICE_UNKNOWN, "device id not in inventory"
            )

    @staticmethod
    def _split_inputs(inputs):
        text_artifacts, audio_artifacts = [], []
        for artifact in inputs:
            if artifact.operation != pb2.LOCAL_ARTIFACT_OPERATION_READ:
                raise codes.ExecutionFailure(
                    codes.INPUT_ARTIFACTS_INVALID, "inputs must be READ artifacts"
                )
            media = artifact.media_type or ""
            if media.startswith("audio/"):
                audio_artifacts.append(artifact)
            elif media == "" or media.startswith("text/"):
                text_artifacts.append(artifact)
            else:
                raise codes.ExecutionFailure(
                    codes.INPUT_ARTIFACTS_INVALID, f"unsupported input media {media!r}"
                )
        if len(text_artifacts) != 1 or len(audio_artifacts) > 1:
            raise codes.ExecutionFailure(
                codes.INPUT_ARTIFACTS_INVALID,
                "tts needs exactly one text input and at most one reference audio",
            )
        return text_artifacts[0], (audio_artifacts[0] if audio_artifacts else None)

    @staticmethod
    def _single_output(outputs):
        if len(outputs) != 1:
            raise codes.ExecutionFailure(
                codes.INPUT_ARTIFACTS_INVALID, "tts needs exactly one output artifact"
            )
        output = outputs[0]
        if output.operation != pb2.LOCAL_ARTIFACT_OPERATION_WRITE:
            raise codes.ExecutionFailure(
                codes.INPUT_ARTIFACTS_INVALID, "output must be a WRITE artifact"
            )
        media = output.media_type or ""
        if media and not media.startswith("audio/"):
            raise codes.ExecutionFailure(
                codes.INPUT_ARTIFACTS_INVALID, f"unsupported output media {media!r}"
            )
        return output

    # -- execution -----------------------------------------------------

    def execute(self, request, grpc_context=None):
        """Generator of ``pb2.ExecuteResponse``. Never raises for a
        classified failure — failures become terminal events."""
        session = _Session(self, request)
        return session.run(grpc_context)


class _Session:
    def __init__(self, executor: Executor, request):
        self._x = executor
        self.request = request
        self.job_id = request.job_id
        self.attempt_id = request.attempt_id
        self.sequence = 0
        self.phase = "model_load"
        self.terminal_sent = False
        self.chars = 0
        self.gpu_ms = 0
        self.cpu_ms = 0
        self.output_audio_ms = 0

    # event builders ---------------------------------------------------

    def _event(self, **payload):
        self.sequence += 1
        return pb2.ExecuteResponse(
            event=pb2.ExecutionEvent(
                job_id=self.job_id,
                attempt_id=self.attempt_id,
                sequence=self.sequence,
                observed_at_unix_ms=int(time.time() * 1000),
                **payload,
            )
        )

    def _measurements(self):
        return pb2.RuntimeMeasurements(
            normalized_input_characters=self.chars,
            output_audio_ms=self.output_audio_ms,
            gpu_execution_ms=self.gpu_ms,
            cpu_execution_ms=self.cpu_ms,
        )

    def _failed(self, failure: codes.ExecutionFailure):
        self.terminal_sent = True
        return self._event(
            failed=pb2.ExecutionFailed(
                failure_class=failure.failure_class,
                stable_code=failure.stable_code,
                safe_detail=failure.safe_detail,
                measurements=self._measurements(),
            )
        )

    def _canceled(self):
        self.terminal_sent = True
        return self._event(
            canceled=pb2.ExecutionCanceled(measurements=self._measurements())
        )

    # main flow --------------------------------------------------------

    def run(self, grpc_context):
        if not self.attempt_id.strip() or not self.job_id.strip():
            yield self._failed(
                codes.ExecutionFailure(
                    codes.INPUT_ATTEMPT_IDENTITY, "job and attempt ids are required"
                )
            )
            return
        registry = self._x._registry
        try:
            record = registry.begin(self.job_id, self.attempt_id, self._x._slot_limit)
        except codes.ExecutionFailure as failure:
            yield self._failed(failure)
            return
        try:
            yield from self._run_admitted(record, grpc_context)
        finally:
            terminal = "canceled"
            if self.terminal_sent:
                terminal = self._terminal_kind or "failed"
            registry.finish(self.attempt_id, terminal)

    _terminal_kind: str | None = None

    def _run_admitted(self, record, grpc_context):
        try:
            validated = self._x._validate(self.request)
        except codes.ExecutionFailure as failure:
            self._terminal_kind = "failed"
            yield self._failed(failure)
            return
        except Exception as exc:  # adapter bug — still a classified event
            self._terminal_kind = "failed"
            yield self._failed(
                codes.ExecutionFailure(codes.RUNTIME_CRASH, f"{type(exc).__name__}")
            )
            return

        self.chars = len(validated.text)
        yield self._event(started=pb2.ExecutionStarted())

        worker = _EngineWorker(self._x._engine_provider, validated, self)
        worker.start()

        clock = self._x._clock
        next_progress = clock() + self._x._progress_interval
        progress_events = 0
        while not worker.done.wait(self._x._poll_interval):
            if record.cancel.is_set() or (
                grpc_context is not None and not grpc_context.is_active()
            ):
                self._terminal_kind = "canceled"
                yield self._canceled()
                return
            now = clock()
            if now >= validated.deadline_monotonic:
                self._terminal_kind = "failed"
                yield self._failed(codes.deadline_failure(self.phase))
                return
            if now >= next_progress and progress_events < _MAX_PROGRESS_EVENTS:
                progress_events += 1
                next_progress = now + self._x._progress_interval
                permille = 100 if self.phase == "model_load" else 550
                yield self._event(
                    progress=pb2.ExecutionProgress(
                        progress_permille=permille, stage_code=self.phase
                    )
                )

        if record.cancel.is_set():
            self._terminal_kind = "canceled"
            yield self._canceled()
            return
        if worker.error is not None:
            self._terminal_kind = "failed"
            yield self._failed(codes.classify_engine_error(worker.error, worker.phase))
            return

        try:
            manifest = self._write_output(worker, validated)
        except codes.ExecutionFailure as failure:
            self._terminal_kind = "failed"
            yield self._failed(failure)
            return
        self._terminal_kind = "completed"
        self.terminal_sent = True
        yield self._event(
            completed=pb2.ExecutionCompleted(
                outputs=[manifest], measurements=self._measurements()
            )
        )

    def _write_output(self, worker, validated: ValidatedRequest):
        ensure_backend_on_path()
        tensor = worker.result
        sample_rate = worker.sample_rate
        if tensor is None or not hasattr(tensor, "numel") or tensor.numel() == 0:
            raise codes.ExecutionFailure(
                codes.INFERENCE_BAD_OUTPUT, "engine returned no audio"
            )
        if not isinstance(sample_rate, int) or sample_rate <= 0:
            raise codes.ExecutionFailure(
                codes.INFERENCE_BAD_OUTPUT, "engine reported no sample rate"
            )
        try:
            from services.audio_io import atomic_save_wav  # noqa: PLC0415

            atomic_save_wav(validated.output_handle, tensor.detach().cpu(), sample_rate)
        except codes.ExecutionFailure:
            raise
        except Exception as exc:
            raise codes.ExecutionFailure(
                codes.STORAGE_WRITE_FAILED, f"{type(exc).__name__}: {exc}"
            )
        try:
            size = os.stat(validated.output_handle).st_size
            sha = file_sha256(validated.output_handle)
        except OSError as exc:
            raise codes.ExecutionFailure(
                codes.STORAGE_WRITE_FAILED, f"{type(exc).__name__}"
            )
        if 0 < validated.output_size_bound < size:
            raise codes.ExecutionFailure(
                codes.STORAGE_WRITE_FAILED, "output exceeds its size bound"
            )
        samples = tensor.numel() if tensor.dim() == 1 else tensor.shape[-1]
        self.output_audio_ms = int(samples * 1000 / sample_rate)
        return pb2.LocalArtifactManifest(
            artifact_id=self.request.outputs[0].artifact_id,
            local_handle=validated.output_handle,
            size_bytes=size,
            sha256=sha,
            media_type=validated.output_media_type,
            duration_ms=self.output_audio_ms,
        )


class _EngineWorker:
    """Runs the engine on a daemon thread, recording phase and timings."""

    def __init__(self, engine_provider, validated: ValidatedRequest, session: _Session):
        self._engine_provider = engine_provider
        self._validated = validated
        self._session = session
        self.done = threading.Event()
        self.error: BaseException | None = None
        self.result = None
        self.sample_rate: int | None = None
        self.phase = "model_load"

    def start(self) -> None:
        thread = threading.Thread(
            target=self._run,
            name=f"runtime-adapter-attempt-{self._session.attempt_id}",
            daemon=True,
        )
        thread.start()

    def _run(self) -> None:
        wall_start = time.monotonic()
        cpu_start = time.process_time()
        try:
            engine = self._engine_provider(self._validated.catalog_model_id)
            ensure_ready = getattr(engine, "ensure_ready", None)
            if callable(ensure_ready):
                ensure_ready()
            self.phase = "synthesis"
            self._session.phase = "synthesis"
            synth_start = time.monotonic()
            self.result = engine.generate(self._validated.text, **self._validated.engine_kwargs)
            rate = getattr(engine, "sample_rate", None)
            self.sample_rate = int(rate) if isinstance(rate, (int, float)) and rate else None
            self._session.gpu_ms = int((time.monotonic() - synth_start) * 1000)
        except BaseException as exc:  # classified later, never lost
            self.error = exc
        finally:
            self._session.cpu_ms = int((time.process_time() - cpu_start) * 1000)
            if self._session.gpu_ms == 0 and self.error is None:
                self._session.gpu_ms = int((time.monotonic() - wall_start) * 1000)
            self.done.set()
