"""Execute/Cancel: happy path, deadline, cancel race, failure taxonomy."""
from __future__ import annotations

import hashlib
import os
import sys
import threading
import time

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _runtime_adapter_helpers import (  # noqa: E402
    READY_MODEL,
    FailingEngine,
    FakeInventory,
    SlowEngine,
    make_context,
    make_execute_request,
    serve_over_socket,
    terminal_of,
)
from runtime_adapter import codes
from runtime_adapter.gen import runtime_adapter_pb2 as pb2
from runtime_adapter.inventory import STATE_INSTALLED, ModelInfo


def _run_direct(context, request):
    """Drive the executor without a live gRPC server (fast path for taxonomy)."""
    return list(context.executor().execute(request, None))


def _failure(events):
    kind, last = terminal_of(events)
    assert kind == "failed", f"expected failed terminal, got {kind}"
    return last.failed


# ── happy path ────────────────────────────────────────────────────────────


def test_execute_happy_path_streams_and_writes_the_manifest(tmp_path):
    context = make_context()
    request = make_execute_request(tmp_path, text="hello runtime")
    with serve_over_socket(context, tmp_path) as (stub, _):
        events = list(stub.Execute(request, timeout=30))

    payloads = [event.event.WhichOneof("payload") for event in events]
    assert payloads[0] == "started"
    assert payloads[-1] == "completed"
    assert all(kind == "progress" for kind in payloads[1:-1])
    sequences = [event.event.sequence for event in events]
    assert sequences == sorted(sequences)
    assert all(event.event.attempt_id == "attempt-1" for event in events)

    completed = events[-1].event.completed
    [manifest] = completed.outputs
    output_path = tmp_path / "output.wav"
    assert manifest.local_handle == str(output_path)
    assert output_path.stat().st_size == manifest.size_bytes > 0
    assert manifest.sha256 == hashlib.sha256(output_path.read_bytes()).hexdigest()
    assert manifest.media_type == "audio/wav"
    assert manifest.duration_ms == 500  # 12000 samples at 24 kHz

    measurements = completed.measurements
    assert measurements.normalized_input_characters == len("hello runtime")
    assert measurements.output_audio_ms == 500


def test_execute_passes_typed_parameters_to_the_engine(tmp_path):
    from _runtime_adapter_helpers import FakeEngine

    engine = FakeEngine()
    context = make_context(engine=engine)
    request = make_execute_request(
        tmp_path,
        parameters={
            "speed": pb2.ParameterValue(number_value=1.5),
            "language": pb2.ParameterValue(string_value="en"),
            "num_step": pb2.ParameterValue(integer_value=8),
        },
    )
    events = _run_direct(context, request)
    assert terminal_of(events)[0] == "completed"
    [(text, kwargs)] = engine.generate_calls
    assert text == "hello runtime"
    assert kwargs == {"speed": 1.5, "language": "en", "num_step": 8}


# ── deadline ──────────────────────────────────────────────────────────────


def test_deadline_is_enforced_with_a_stable_code(tmp_path):
    context = make_context(engine=SlowEngine(seconds=30))
    request = make_execute_request(tmp_path, deadline_in_s=0.4)
    start = time.monotonic()
    events = _run_direct(context, request)
    elapsed = time.monotonic() - start

    failed = _failure(events)
    assert failed.stable_code in (codes.INFERENCE_DEADLINE, codes.MODEL_LOAD_DEADLINE)
    assert failed.failure_class in (
        pb2.RUNTIME_FAILURE_CLASS_INFERENCE,
        pb2.RUNTIME_FAILURE_CLASS_MODEL_LOAD,
    )
    assert elapsed < 5, "terminal event must arrive promptly after the deadline"


def test_deadline_in_the_past_is_invalid_input(tmp_path):
    context = make_context()
    request = make_execute_request(tmp_path)
    request.deadline_unix_ms = int(time.time() * 1000) - 1000
    failed = _failure(_run_direct(context, request))
    assert failed.stable_code == codes.INPUT_DEADLINE_INVALID
    assert failed.failure_class == pb2.RUNTIME_FAILURE_CLASS_INPUT


# ── cancel ────────────────────────────────────────────────────────────────


def test_cancel_race_yields_canceled_terminal_and_idempotent_dispositions(tmp_path):
    engine = SlowEngine(seconds=30)
    context = make_context(engine=engine)
    request = make_execute_request(tmp_path)
    with serve_over_socket(context, tmp_path) as (stub, _):
        stream = stub.Execute(request, timeout=30)
        first = next(stream)
        assert first.event.WhichOneof("payload") == "started"
        assert engine.started.wait(5), "engine must be mid-generate for the race"

        cancel = pb2.CancelRequest(job_id="job-1", attempt_id="attempt-1")
        assert stub.Cancel(cancel, timeout=5).disposition == (
            pb2.CANCEL_DISPOSITION_ACCEPTED
        )
        # Idempotent while still running.
        assert stub.Cancel(cancel, timeout=5).disposition == (
            pb2.CANCEL_DISPOSITION_ACCEPTED
        )

        events = [first, *stream]
        kind, last = terminal_of(events)
        assert kind == "canceled"
        assert last.canceled.HasField("measurements")

        # After the terminal event the same cancel is ALREADY_TERMINAL …
        assert stub.Cancel(cancel, timeout=5).disposition == (
            pb2.CANCEL_DISPOSITION_ALREADY_TERMINAL
        )
        # … and an unknown attempt is NOT_FOUND.
        unknown = pb2.CancelRequest(job_id="job-1", attempt_id="nope")
        assert stub.Cancel(unknown, timeout=5).disposition == (
            pb2.CANCEL_DISPOSITION_NOT_FOUND
        )


def test_cancel_before_any_execute_is_not_found(tmp_path):
    with serve_over_socket(make_context(), tmp_path) as (stub, _):
        response = stub.Cancel(
            pb2.CancelRequest(job_id="j", attempt_id="never-ran"), timeout=5
        )
    assert response.disposition == pb2.CANCEL_DISPOSITION_NOT_FOUND


# ── failure classification ────────────────────────────────────────────────


def test_model_load_failure_is_classified(tmp_path):
    engine = FailingEngine(RuntimeError("weights corrupted"), phase="model_load")
    failed = _failure(
        _run_direct(make_context(engine=engine), make_execute_request(tmp_path))
    )
    assert failed.stable_code == codes.MODEL_LOAD_FAILED
    assert failed.failure_class == pb2.RUNTIME_FAILURE_CLASS_MODEL_LOAD


def test_inference_failure_is_classified(tmp_path):
    engine = FailingEngine(ValueError("synthesis exploded"))
    failed = _failure(
        _run_direct(make_context(engine=engine), make_execute_request(tmp_path))
    )
    assert failed.stable_code == codes.INFERENCE_FAILED
    assert failed.failure_class == pb2.RUNTIME_FAILURE_CLASS_INFERENCE


def test_gpu_oom_is_classified_as_gpu_resource(tmp_path):
    engine = FailingEngine(RuntimeError("CUDA out of memory. Tried to allocate…"))
    failed = _failure(
        _run_direct(make_context(engine=engine), make_execute_request(tmp_path))
    )
    assert failed.stable_code == codes.GPU_OUT_OF_MEMORY
    assert failed.failure_class == pb2.RUNTIME_FAILURE_CLASS_GPU_RESOURCE


def test_engine_input_rejection_is_invalid_input(tmp_path):
    from services.tts_backend import TTSInputError

    engine = FailingEngine(TTSInputError("text too long for this engine"))
    failed = _failure(
        _run_direct(make_context(engine=engine), make_execute_request(tmp_path))
    )
    assert failed.stable_code == codes.INPUT_REJECTED
    assert failed.failure_class == pb2.RUNTIME_FAILURE_CLASS_INPUT


def test_url_handles_are_rejected_never_fetched(tmp_path):
    request = make_execute_request(
        tmp_path, input_handle="https://evil.example/input.txt", input_sha256=""
    )
    failed = _failure(_run_direct(make_context(), request))
    assert failed.stable_code == codes.INPUT_HANDLE_INVALID
    assert failed.failure_class == pb2.RUNTIME_FAILURE_CLASS_INPUT


def test_relative_output_handle_is_rejected(tmp_path):
    request = make_execute_request(tmp_path, output_handle="relative/out.wav")
    failed = _failure(_run_direct(make_context(), request))
    assert failed.stable_code == codes.INPUT_HANDLE_INVALID


def test_model_digest_mismatch_is_rejected(tmp_path):
    request = make_execute_request(tmp_path)
    request.model.model_digest = "sha256:" + "f" * 64
    failed = _failure(_run_direct(make_context(), request))
    assert failed.stable_code == codes.INPUT_MODEL_DIGEST_MISMATCH


def test_non_ready_model_is_rejected(tmp_path):
    installed = ModelInfo(
        catalog_model_id=READY_MODEL.catalog_model_id,
        model_version=READY_MODEL.model_version,
        model_digest=READY_MODEL.model_digest,
        precisions=READY_MODEL.precisions,
        features=READY_MODEL.features,
        state=STATE_INSTALLED,
    )
    context = make_context(inventory=FakeInventory(models=[installed]))
    failed = _failure(_run_direct(context, make_execute_request(tmp_path)))
    assert failed.stable_code == codes.INPUT_MODEL_NOT_READY


def test_unknown_model_is_rejected(tmp_path):
    request = make_execute_request(tmp_path)
    request.model.catalog_model_id = "who-dis"
    failed = _failure(_run_direct(make_context(), request))
    assert failed.stable_code == codes.INPUT_MODEL_UNKNOWN


def test_unknown_and_out_of_range_parameters_are_rejected(tmp_path):
    unknown = make_execute_request(
        tmp_path,
        parameters={"exfiltrate": pb2.ParameterValue(string_value="x")},
    )
    assert _failure(_run_direct(make_context(), unknown)).stable_code == (
        codes.INPUT_PARAMETER_UNKNOWN
    )
    out_of_range = make_execute_request(
        tmp_path,
        attempt_id="attempt-2",
        parameters={"speed": pb2.ParameterValue(number_value=99.0)},
    )
    assert _failure(_run_direct(make_context(), out_of_range)).stable_code == (
        codes.INPUT_PARAMETER_RANGE
    )


def test_input_checksum_mismatch_is_rejected(tmp_path):
    request = make_execute_request(tmp_path, input_sha256="0" * 64)
    failed = _failure(_run_direct(make_context(), request))
    assert failed.stable_code == codes.INPUT_CHECKSUM_MISMATCH


def test_empty_text_is_rejected(tmp_path):
    request = make_execute_request(tmp_path, text="   ")
    failed = _failure(_run_direct(make_context(), request))
    assert failed.stable_code == codes.INPUT_TEXT_EMPTY


def test_unwritable_output_directory_is_local_storage(tmp_path):
    locked = tmp_path / "locked"
    locked.mkdir()
    request = make_execute_request(tmp_path, output_handle=str(locked / "out.wav"))
    locked.chmod(0o500)
    try:
        failed = _failure(_run_direct(make_context(), request))
    finally:
        locked.chmod(0o700)
    assert failed.stable_code == codes.STORAGE_WRITE_FAILED
    assert failed.failure_class == pb2.RUNTIME_FAILURE_CLASS_LOCAL_STORAGE


def test_duplicate_attempt_id_is_rejected(tmp_path):
    context = make_context()
    executor = context.executor()
    first = make_execute_request(tmp_path)
    assert terminal_of(list(executor.execute(first, None)))[0] == "completed"
    duplicate = make_execute_request(tmp_path)
    events = list(executor.execute(duplicate, None))
    failed = _failure(events)
    assert failed.stable_code == codes.INPUT_ATTEMPT_DUPLICATE


def test_slot_exhaustion_is_gpu_resource(tmp_path):
    engine = SlowEngine(seconds=30)
    context = make_context(engine=engine, slot_limit=1)
    executor = context.executor()
    hog = make_execute_request(tmp_path, attempt_id="hog")
    hog_events = []
    hog_thread = threading.Thread(
        target=lambda: hog_events.extend(executor.execute(hog, None)), daemon=True
    )
    hog_thread.start()
    assert engine.started.wait(5)
    try:
        crowded = make_execute_request(tmp_path, attempt_id="crowded")
        failed = _failure(list(executor.execute(crowded, None)))
        assert failed.stable_code == codes.GPU_SLOTS_EXHAUSTED
        assert failed.failure_class == pb2.RUNTIME_FAILURE_CLASS_GPU_RESOURCE
    finally:
        context.registry.cancel("job-1", "hog")
        hog_thread.join(timeout=10)
    assert terminal_of(hog_events)[0] == "canceled"


def test_safe_detail_never_carries_local_paths(tmp_path):
    engine = FailingEngine(RuntimeError(f"failed loading {tmp_path}/weights.bin"))
    failed = _failure(
        _run_direct(make_context(engine=engine), make_execute_request(tmp_path))
    )
    assert str(tmp_path) not in failed.safe_detail
    assert "<path>" in failed.safe_detail
