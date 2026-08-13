"""VoiceStudio runtime adapter — the vssaas GPU-node runtime boundary.

Implements ``voicestudio.runtime.v1.RuntimeAdapterService`` over a private
Unix-domain socket so a vssaas GPU Gateway can drive VoiceStudio's TTS
engines as its inference runtime. No HTTP listener, no database access, no
outbound network: the adapter reads and writes only the local file handles
each ``Execute`` request carries. See ``README.md`` in this directory.
"""
from __future__ import annotations

#: Version of this adapter layer (the gRPC boundary), independent of the app
#: version, which is reported as ``runtime_version``. Bump on any behavioral
#: change to the adapter itself.
ADAPTER_VERSION = "0.1.0"

DEFAULT_SOCKET_PATH = "/run/voicestudio/runtime.sock"
SOCKET_ENV = "VOICE_STUDIO_RUNTIME_SOCKET"
SLOTS_ENV = "VOICE_STUDIO_RUNTIME_SLOTS"
