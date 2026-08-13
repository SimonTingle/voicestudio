"""Entry point: ``python -m backend.runtime_adapter``.

Serves the runtime adapter on a private Unix-domain socket (default
``/run/voicestudio/runtime.sock``, override ``VOICE_STUDIO_RUNTIME_SOCKET``
or ``--socket``). ``--selfcheck`` instead starts the server on a temp socket
and validates the GPU Gateway preflight expectations against it.
"""
from __future__ import annotations

import argparse
import sys

from ._paths import ensure_backend_on_path


def main(argv: list[str] | None = None) -> int:
    ensure_backend_on_path()
    parser = argparse.ArgumentParser(
        prog="backend.runtime_adapter",
        description="VoiceStudio runtime adapter (vssaas GPU-node gRPC server)",
    )
    parser.add_argument(
        "--socket",
        default=None,
        help="absolute Unix socket path (default: $VOICE_STUDIO_RUNTIME_SOCKET "
        "or /run/voicestudio/runtime.sock)",
    )
    parser.add_argument(
        "--selfcheck",
        action="store_true",
        help="start on a temp socket and validate the preflight expectations",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=10.0,
        help="selfcheck RPC timeout in seconds (default: 10)",
    )
    args = parser.parse_args(argv)

    if args.selfcheck:
        from .selfcheck import selfcheck  # noqa: PLC0415

        return selfcheck(timeout_s=args.timeout)

    from .production import build_runtime_context  # noqa: PLC0415
    from .server import resolve_socket_path, serve  # noqa: PLC0415

    return serve(build_runtime_context(), resolve_socket_path(args.socket))


if __name__ == "__main__":
    sys.exit(main())
