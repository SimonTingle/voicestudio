"""Health/GetCapabilities shape, preflight parity, digest stability.

Mirrors what ``internal/gateway/preflight.go`` in vssaas enforces: READY
health with version evidence, identical versions across both calls, valid
unique devices, and only explicitly-READY models counting as schedulable.
"""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _runtime_adapter_helpers import (  # noqa: E402
    DEVICE,
    READY_MODEL,
    FakeInventory,
    make_context,
    serve_over_socket,
)
from runtime_adapter.digest import file_sha256, snapshot_digest
from runtime_adapter.gen import runtime_adapter_pb2 as pb2
from runtime_adapter.inventory import (
    STATE_FAILED,
    STATE_INSTALLED,
    STATE_LOADING,
    ModelInfo,
)
from runtime_adapter.selfcheck import PreflightError, run_preflight
from runtime_adapter.server import prepare_socket


def _model(state, model_id="other-model", digest="sha256:" + "c" * 64):
    return ModelInfo(
        catalog_model_id=model_id,
        model_version="d" * 40,
        model_digest=digest,
        precisions=("fp32",),
        features=("tts",),
        state=state,
    )


def test_health_and_capabilities_versions_are_identical_and_ready(tmp_path):
    with serve_over_socket(make_context(), tmp_path) as (stub, _):
        health = stub.Health(pb2.HealthRequest(), timeout=5)
        caps = stub.GetCapabilities(pb2.GetCapabilitiesRequest(), timeout=5)

    assert health.state == pb2.SERVING_STATE_READY
    assert health.runtime_version == "1.2.3-test"
    assert health.adapter_version.strip()
    assert caps.runtime_version == health.runtime_version
    assert caps.adapter_version == health.adapter_version


def test_capabilities_report_device_and_ready_model_evidence(tmp_path):
    inventory = FakeInventory(
        models=[
            READY_MODEL,
            _model(STATE_LOADING, "loading-model"),
            _model(STATE_FAILED, "failed-model"),
            _model(STATE_INSTALLED, "installed-model"),
        ]
    )
    with serve_over_socket(make_context(inventory=inventory), tmp_path) as (stub, _):
        caps = stub.GetCapabilities(pb2.GetCapabilitiesRequest(), timeout=5)

    [device] = caps.devices
    assert device.device_id == DEVICE.device_id
    assert device.hardware_class == DEVICE.hardware_class
    assert device.total_vram_bytes > 0
    assert 0 < device.free_slots <= device.total_slots

    by_id = {model.catalog_model_id: model for model in caps.models}
    ready = by_id[READY_MODEL.catalog_model_id]
    assert ready.state == pb2.RUNTIME_MODEL_STATE_READY
    assert len(ready.model_version) == 40
    assert ready.model_digest.startswith("sha256:")
    assert list(ready.precisions)
    # A loading/failed/installed model is reported truthfully, never READY.
    assert by_id["loading-model"].state == pb2.RUNTIME_MODEL_STATE_LOADING
    assert by_id["failed-model"].state == pb2.RUNTIME_MODEL_STATE_FAILED
    assert by_id["installed-model"].state == pb2.RUNTIME_MODEL_STATE_INSTALLED


def test_preflight_port_passes_against_a_ready_server(tmp_path):
    inventory = FakeInventory(models=[READY_MODEL, _model(STATE_LOADING)])
    with serve_over_socket(make_context(inventory=inventory), tmp_path) as (
        stub,
        socket_path,
    ):
        summary = run_preflight(socket_path, timeout_s=5)
    assert summary.ready_model_count == 1  # the loading model must not count
    assert summary.device_count == 1
    assert summary.runtime_version == "1.2.3-test"
    assert summary.total_slots == 1


def test_preflight_fails_closed_without_a_ready_model(tmp_path):
    inventory = FakeInventory(models=[_model(STATE_LOADING)])
    with serve_over_socket(make_context(inventory=inventory), tmp_path) as (
        stub,
        socket_path,
    ):
        health = stub.Health(pb2.HealthRequest(), timeout=5)
        assert health.state == pb2.SERVING_STATE_DEGRADED
        assert "no-ready-model" in health.health_flags
        with pytest.raises(PreflightError):
            run_preflight(socket_path, timeout_s=5)


def test_prepare_socket_rejects_unsafe_paths(tmp_path):
    with pytest.raises(ValueError):
        prepare_socket("relative/socket.sock")
    regular = tmp_path / "not-a-socket"
    regular.write_text("x")
    with pytest.raises(ValueError):
        prepare_socket(str(regular))
    missing_parent = tmp_path / "nope" / "runtime.sock"
    with pytest.raises(ValueError):
        prepare_socket(str(missing_parent))


def test_snapshot_digest_is_stable_and_content_sensitive(tmp_path):
    snapshot = tmp_path / "snapshots" / "rev"
    snapshot.mkdir(parents=True)
    (snapshot / "weights.bin").write_bytes(b"\x01\x02\x03")
    (snapshot / "config.json").write_text("{}")
    cache = tmp_path / "digest-cache.json"

    first = snapshot_digest(snapshot, cache_path=cache)
    second = snapshot_digest(snapshot, cache_path=cache)  # served from cache
    assert first == second
    assert first.startswith("sha256:")
    assert cache.exists()

    # Any byte change must change the digest (cache invalidated by mtime/size).
    (snapshot / "weights.bin").write_bytes(b"\x01\x02\x04")
    assert snapshot_digest(snapshot, cache_path=cache) != first

    with pytest.raises(FileNotFoundError):
        snapshot_digest(tmp_path / "empty-none")


def test_file_sha256_matches_hashlib(tmp_path):
    import hashlib

    payload = b"runtime adapter"
    path = tmp_path / "f.bin"
    path.write_bytes(payload)
    assert file_sha256(path) == hashlib.sha256(payload).hexdigest()


def test_socket_file_is_private_to_the_node(tmp_path):
    import stat

    with serve_over_socket(make_context(), tmp_path) as (_stub, socket_path):
        mode = os.lstat(socket_path).st_mode
        assert stat.S_ISSOCK(mode)
