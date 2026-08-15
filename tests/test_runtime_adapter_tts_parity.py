"""The hosted runtime adapter must use the OSS OmniVoice render path."""
from __future__ import annotations

from contextlib import nullcontext


def test_runtime_adapter_preserves_seeded_gallery_render_contract(monkeypatch):
    from services import tts_backend
    from runtime_adapter.executor import _EngineWorker
    import api.routers.generation as generation

    model = object()
    backend = tts_backend.OmniVoiceBackend(model=model)
    captured = {}
    params = {
        "ref_audio": "/runtime-inputs/gallery.wav", "ref_text": "sample",
        "instruct": "female, whispering", "language": "English",
        "num_step": 32, "guidance_scale": 2.0, "speed": 1.0,
        "denoise": True, "postprocess_output": True, "seed": 42,
    }
    monkeypatch.setattr(tts_backend, "engine_in_use", lambda _backend: nullcontext())
    monkeypatch.setattr(generation, "_run_inference", lambda *args: captured.update(args=args) or "audio")

    assert _EngineWorker._synthesize(backend, "Test line.", params) == "audio"
    assert captured["args"][0] is model
    assert captured["args"][3] == "/runtime-inputs/gallery.wav"
    assert captured["args"][5] == "female, whispering"
    assert captured["args"][13:17] == (None, None, None, 42)
