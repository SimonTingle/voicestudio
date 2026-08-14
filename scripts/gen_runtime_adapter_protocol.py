#!/usr/bin/env python3
"""Regenerate the runtime-adapter stubs from ``runtime_adapter.proto``.

    uv run python scripts/gen_runtime_adapter_protocol.py

The ``.proto`` is a byte-identical vendored copy of the vssaas contract
``api/proto/voicestudio/runtime/v1/runtime_adapter.proto`` (the wire contract
between the vssaas GPU Gateway and this runtime). The generated files are
committed so that neither the installer, the frozen build, nor Docker needs
``protoc`` — only developers changing the ``.proto`` do.
``tests/test_runtime_adapter_gen.py`` regenerates into a temporary directory
and fails if the committed output has drifted, so a forgotten regeneration is
a red test rather than a runtime import error.

The one post-processing step is the import fixup: ``protoc`` emits
``import runtime_adapter_pb2`` in the gRPC stub, which only resolves if the
output directory happens to be on ``sys.path``. Rewriting it to a relative
import lets the package be imported normally.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_PROTO_DIR = _REPO / "backend" / "runtime_adapter"
_OUT_DIR = _PROTO_DIR / "gen"
_PROTO = _PROTO_DIR / "runtime_adapter.proto"

_INIT = '''"""Generated protocol stubs — DO NOT EDIT.

Regenerate with ``uv run python scripts/gen_runtime_adapter_protocol.py``
after any change to ``../runtime_adapter.proto``.
"""
'''


def generate(out_dir: Path) -> int:
    """Run protoc into ``out_dir``. Returns protoc's exit code."""
    from grpc_tools import protoc  # noqa: PLC0415 — dev-only dependency

    out_dir.mkdir(parents=True, exist_ok=True)
    code = protoc.main(
        [
            "protoc",
            f"-I{_PROTO_DIR}",
            f"--python_out={out_dir}",
            f"--pyi_out={out_dir}",
            f"--grpc_python_out={out_dir}",
            str(_PROTO),
        ]
    )
    if code != 0:
        return code
    _fix_imports(out_dir)
    (out_dir / "__init__.py").write_text(_INIT, encoding="utf-8")
    return 0


def _fix_imports(out_dir: Path) -> None:
    """Make protoc's flat sibling import work inside a package."""
    stub = out_dir / "runtime_adapter_pb2_grpc.py"
    if not stub.exists():
        return
    text = stub.read_text(encoding="utf-8")
    text = re.sub(
        r"^import (\w+_pb2) as (\w+)$",
        r"from . import \1 as \2",
        text,
        flags=re.M,
    )
    stub.write_text(text, encoding="utf-8")


def main() -> int:
    code = generate(_OUT_DIR)
    if code == 0:
        print(f"Generated {_OUT_DIR.relative_to(_REPO)}")
    return code


if __name__ == "__main__":
    sys.exit(main())
