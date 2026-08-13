"""The committed runtime-adapter stubs must match the .proto they came from.

Same contract as ``test_worker_protocol_gen.py``: the stubs are committed so
that neither the installer, the frozen build, nor Docker needs ``protoc``.
Regenerating into a temporary directory and diffing turns forgotten
regeneration into a red test with an obvious fix.

The vendored ``backend/runtime_adapter/runtime_adapter.proto`` must also stay
byte-identical to the upstream vssaas contract
(``api/proto/voicestudio/runtime/v1/runtime_adapter.proto``); provenance is
documented in ``backend/runtime_adapter/README.md``.
"""
from __future__ import annotations

import os
import sys

import pytest

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_GEN_DIR = os.path.join(_REPO, "backend", "runtime_adapter", "gen")
_GENERATED_FILES = (
    "runtime_adapter_pb2.py",
    "runtime_adapter_pb2_grpc.py",
    "runtime_adapter_pb2.pyi",
)

pytest.importorskip(
    "grpc_tools",
    reason="grpcio-tools is a dev dependency; the committed stubs are what ship.",
)

sys.path.insert(0, os.path.join(_REPO, "scripts"))


def _normalise(text: str) -> list[str]:
    """Ignore trailing whitespace and blank-line churn between protoc builds."""
    return [line.rstrip() for line in text.splitlines() if line.strip()]


@pytest.mark.parametrize("filename", _GENERATED_FILES)
def test_committed_stubs_match_the_proto(tmp_path, filename):
    import gen_runtime_adapter_protocol

    assert gen_runtime_adapter_protocol.generate(tmp_path) == 0, "protoc failed"

    fresh = (tmp_path / filename).read_text(encoding="utf-8")
    with open(os.path.join(_GEN_DIR, filename), encoding="utf-8") as fh:
        committed = fh.read()

    assert _normalise(committed) == _normalise(fresh), (
        f"{filename} is out of date with runtime_adapter.proto. "
        "Run: uv run python scripts/gen_runtime_adapter_protocol.py"
    )


def test_generated_package_is_importable():
    """protoc emits a flat sibling import that only resolves if the output
    directory happens to be on sys.path; the generator rewrites it."""
    from runtime_adapter.gen import runtime_adapter_pb2 as pb
    from runtime_adapter.gen import runtime_adapter_pb2_grpc as pb_grpc

    assert hasattr(pb_grpc, "RuntimeAdapterServiceStub")
    assert pb.ExecuteRequest(attempt_id="a").attempt_id == "a"


def test_stub_import_is_relative():
    with open(
        os.path.join(_GEN_DIR, "runtime_adapter_pb2_grpc.py"), encoding="utf-8"
    ) as fh:
        source = fh.read()
    assert "from . import runtime_adapter_pb2" in source
    assert "\nimport runtime_adapter_pb2" not in source
