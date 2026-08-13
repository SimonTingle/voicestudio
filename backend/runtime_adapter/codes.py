"""Stable failure codes and exception classification for Execute.

The vssaas API Gateway keys retry and customer-charge policy off these codes,
so they are a wire contract: never rename an existing code, only add. Every
code maps to exactly one proto ``RuntimeFailureClass``.
"""
from __future__ import annotations

import re

from .gen import runtime_adapter_pb2 as pb2

# ── invalid approved input ────────────────────────────────────────────────
INPUT_ATTEMPT_IDENTITY = "RTA_INPUT_ATTEMPT_IDENTITY"
INPUT_ATTEMPT_DUPLICATE = "RTA_INPUT_ATTEMPT_DUPLICATE"
INPUT_MODEL_UNKNOWN = "RTA_INPUT_MODEL_UNKNOWN"
INPUT_MODEL_NOT_READY = "RTA_INPUT_MODEL_NOT_READY"
INPUT_MODEL_DIGEST_MISMATCH = "RTA_INPUT_MODEL_DIGEST_MISMATCH"
INPUT_MODEL_PRECISION = "RTA_INPUT_MODEL_PRECISION_UNSUPPORTED"
INPUT_DEVICE_UNKNOWN = "RTA_INPUT_DEVICE_UNKNOWN"
INPUT_HANDLE_INVALID = "RTA_INPUT_HANDLE_INVALID"
INPUT_ARTIFACTS_INVALID = "RTA_INPUT_ARTIFACTS_INVALID"
INPUT_CHECKSUM_MISMATCH = "RTA_INPUT_CHECKSUM_MISMATCH"
INPUT_TEXT_EMPTY = "RTA_INPUT_TEXT_EMPTY"
INPUT_TEXT_TOO_LARGE = "RTA_INPUT_TEXT_TOO_LARGE"
INPUT_TEXT_ENCODING = "RTA_INPUT_TEXT_ENCODING"
INPUT_PARAMETER_UNKNOWN = "RTA_INPUT_PARAMETER_UNKNOWN"
INPUT_PARAMETER_TYPE = "RTA_INPUT_PARAMETER_TYPE"
INPUT_PARAMETER_RANGE = "RTA_INPUT_PARAMETER_RANGE"
INPUT_DEADLINE_INVALID = "RTA_INPUT_DEADLINE_INVALID"
INPUT_REJECTED = "RTA_INPUT_REJECTED"  # engine-level TTSInputError

# ── model load / inference ────────────────────────────────────────────────
MODEL_LOAD_FAILED = "RTA_MODEL_LOAD_FAILED"
MODEL_LOAD_DEADLINE = "RTA_MODEL_LOAD_DEADLINE_EXCEEDED"
INFERENCE_FAILED = "RTA_INFERENCE_FAILED"
INFERENCE_BAD_OUTPUT = "RTA_INFERENCE_BAD_OUTPUT"
INFERENCE_DEADLINE = "RTA_INFERENCE_DEADLINE_EXCEEDED"

# ── GPU resource ──────────────────────────────────────────────────────────
GPU_OUT_OF_MEMORY = "RTA_GPU_OUT_OF_MEMORY"
GPU_SLOTS_EXHAUSTED = "RTA_GPU_SLOTS_EXHAUSTED"

# ── local storage ─────────────────────────────────────────────────────────
STORAGE_READ_FAILED = "RTA_STORAGE_READ_FAILED"
STORAGE_WRITE_FAILED = "RTA_STORAGE_WRITE_FAILED"

# ── adapter crash ─────────────────────────────────────────────────────────
RUNTIME_CRASH = "RTA_RUNTIME_CRASH"

_INPUT = pb2.RUNTIME_FAILURE_CLASS_INPUT
_MODEL_LOAD = pb2.RUNTIME_FAILURE_CLASS_MODEL_LOAD
_INFERENCE = pb2.RUNTIME_FAILURE_CLASS_INFERENCE
_GPU = pb2.RUNTIME_FAILURE_CLASS_GPU_RESOURCE
_STORAGE = pb2.RUNTIME_FAILURE_CLASS_LOCAL_STORAGE
_RUNTIME = pb2.RUNTIME_FAILURE_CLASS_RUNTIME

CODE_CLASS: dict[str, int] = {
    INPUT_ATTEMPT_IDENTITY: _INPUT,
    INPUT_ATTEMPT_DUPLICATE: _INPUT,
    INPUT_MODEL_UNKNOWN: _INPUT,
    INPUT_MODEL_NOT_READY: _INPUT,
    INPUT_MODEL_DIGEST_MISMATCH: _INPUT,
    INPUT_MODEL_PRECISION: _INPUT,
    INPUT_DEVICE_UNKNOWN: _INPUT,
    INPUT_HANDLE_INVALID: _INPUT,
    INPUT_ARTIFACTS_INVALID: _INPUT,
    INPUT_CHECKSUM_MISMATCH: _INPUT,
    INPUT_TEXT_EMPTY: _INPUT,
    INPUT_TEXT_TOO_LARGE: _INPUT,
    INPUT_TEXT_ENCODING: _INPUT,
    INPUT_PARAMETER_UNKNOWN: _INPUT,
    INPUT_PARAMETER_TYPE: _INPUT,
    INPUT_PARAMETER_RANGE: _INPUT,
    INPUT_DEADLINE_INVALID: _INPUT,
    INPUT_REJECTED: _INPUT,
    MODEL_LOAD_FAILED: _MODEL_LOAD,
    MODEL_LOAD_DEADLINE: _MODEL_LOAD,
    INFERENCE_FAILED: _INFERENCE,
    INFERENCE_BAD_OUTPUT: _INFERENCE,
    INFERENCE_DEADLINE: _INFERENCE,
    GPU_OUT_OF_MEMORY: _GPU,
    GPU_SLOTS_EXHAUSTED: _GPU,
    STORAGE_READ_FAILED: _STORAGE,
    STORAGE_WRITE_FAILED: _STORAGE,
    RUNTIME_CRASH: _RUNTIME,
}


class ExecutionFailure(Exception):
    """A classified, wire-safe execution failure."""

    def __init__(self, stable_code: str, safe_detail: str = ""):
        if stable_code not in CODE_CLASS:  # programming error, not a wire case
            raise ValueError(f"unknown stable code {stable_code!r}")
        super().__init__(stable_code)
        self.stable_code = stable_code
        self.failure_class = CODE_CLASS[stable_code]
        self.safe_detail = scrub_detail(safe_detail)


_PATHISH = re.compile(r"(?:[A-Za-z]:)?[/\\][^\s'\"]+")
_MAX_DETAIL = 240


def scrub_detail(detail: str) -> str:
    """Bound and de-path a detail string before it crosses the wire.

    Local handles are server-generated, but engine exceptions routinely embed
    checkpoint paths, cache dirs, and home directories. None of that belongs
    in an event the Gateway relays upstream.
    """
    scrubbed = _PATHISH.sub("<path>", detail or "").strip()
    return scrubbed[:_MAX_DETAIL]


_OOM_MARKERS = (
    "out of memory",
    "cuda error: out of memory",
    "mps backend out of memory",
    "hip out of memory",
    "cublas_status_alloc_failed",
)


def _is_oom(exc: BaseException) -> bool:
    if type(exc).__name__ == "OutOfMemoryError":  # torch.cuda.OutOfMemoryError
        return True
    message = str(exc).lower()
    return any(marker in message for marker in _OOM_MARKERS)


def _is_engine_input_error(exc: BaseException) -> bool:
    try:
        from services.tts_backend import TTSInputError  # noqa: PLC0415
    except Exception:
        return False
    return isinstance(exc, TTSInputError)


def classify_engine_error(exc: BaseException, phase: str) -> ExecutionFailure:
    """Map an engine exception to a stable failure code.

    ``phase`` is ``"model_load"`` or ``"synthesis"`` — the phase the engine
    thread was in when it raised.
    """
    if isinstance(exc, ExecutionFailure):
        return exc
    detail = f"{type(exc).__name__}: {exc}"
    if _is_oom(exc):
        return ExecutionFailure(GPU_OUT_OF_MEMORY, detail)
    if _is_engine_input_error(exc):
        return ExecutionFailure(INPUT_REJECTED, detail)
    if isinstance(exc, OSError):
        return ExecutionFailure(STORAGE_READ_FAILED, detail)
    if phase == "model_load":
        return ExecutionFailure(MODEL_LOAD_FAILED, detail)
    return ExecutionFailure(INFERENCE_FAILED, detail)


def deadline_failure(phase: str) -> ExecutionFailure:
    code = MODEL_LOAD_DEADLINE if phase == "model_load" else INFERENCE_DEADLINE
    return ExecutionFailure(code, "attempt deadline exceeded")
