"""First-run setup endpoints — model presence + live download progress.

`GET /setup/status` reports whether the primary model weights are cached on
disk + how much disk space remains. The frontend uses this on boot to decide
whether to show a setup wizard or the main UI.

`GET /setup/download-stream` is SSE that forwards every tqdm update emitted
by `huggingface_hub` through the monkey-patch in `utils/hf_progress`. The
frontend subscribes once and renders per-file progress bars until the wizard
completes.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import platform as _platform
import shutil
import sys
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from utils import hf_progress

logger = logging.getLogger("omnivoice.setup")
router = APIRouter()

# Minimum free disk space before we'd even attempt a full model download.
# Rough budget: ~6 GB for OmniVoice + Whisper-large-v3 + scratch; leave 4 GB
# of headroom so the machine isn't pinned on disk after install.
MIN_FREE_GB = 10

# Where HuggingFace caches downloads by default. If the user has overridden
# via HF_HOME or HUGGINGFACE_HUB_CACHE, we honour it — nothing to move.
def _hf_cache_dir() -> str:
    return (
        os.environ.get("HF_HUB_CACHE")
        or os.environ.get("HUGGINGFACE_HUB_CACHE")
        or os.environ.get("HF_HOME")
        or os.path.expanduser("~/.cache/huggingface")
    )


def _disk_free_gb(path: str) -> float:
    try:
        return shutil.disk_usage(path).free / (1024 ** 3)
    except Exception:
        return 0.0


# Every model the app knows about. `required=True` means the app doesn't
# function end-to-end without it (wizard blocks on these). `required=False`
# models are optional — ship with them uninstalled, user opts in from
# Settings > Models.
KNOWN_MODELS = [
    {
        "repo_id": "k2-fsa/OmniVoice",
        "label": "OmniVoice TTS (600+ languages, zero-shot)",
        "role": "TTS",
        "size_gb": 2.4,
        "required": True,
    },
    {
        # Cross-platform default ASR. CTranslate2-converted whisper-large-v3,
        # loads via faster-whisper (asr_backend.py:FasterWhisperBackend).
        # Works on Linux/Windows/mac-Intel/mac-ARM with no mlx dependency.
        "repo_id": "Systran/faster-whisper-large-v3",
        "label": "Whisper large-v3 (faster-whisper — default, cross-platform)",
        "role": "ASR",
        "size_gb": 2.9,
        "required": True,
    },
    {
        "repo_id": "mlx-community/whisper-large-v3-mlx",
        "label": "Whisper large-v3 (MLX — optional mac-ARM speedup)",
        "role": "ASR",
        "size_gb": 3.0,
        # Optional everywhere — only loadable on mac-ARM dev installs. The
        # frozen .app can't load mlx reliably (nanobind duplicate-registration
        # aborts on first mlx.core touch), and mlx doesn't exist on
        # Linux/Windows/mac-Intel at all. Users on a mac-ARM dev install can
        # opt in from Settings → Models for ~10-20% lower latency vs faster-
        # whisper int8 on large-v3.
        "required": False,
    },
    {
        "repo_id": "openai/whisper-large-v3",
        "label": "Whisper large-v3 (PyTorch — last-resort fallback)",
        "role": "ASR",
        "size_gb": 3.1,
        # Optional fallback. The faster-whisper repo above is the primary
        # ASR; openai/whisper-large-v3 is only needed if the user explicitly
        # picks pytorch-whisper in Settings (CUDA-heavy workflows or when
        # faster-whisper breaks on a specific host).
        "required": False,
    },
    {
        "repo_id": "mlx-community/whisper-tiny-mlx",
        "label": "Whisper tiny (MLX ASR — fast fallback)",
        "role": "ASR",
        "size_gb": 0.08,
        "required": False,
    },
    {
        "repo_id": "pyannote/speaker-diarization-3.1",
        "label": "pyannote speaker diarisation (multi-speaker videos)",
        "role": "Diarisation",
        "size_gb": 0.8,
        "required": False,
        "note": "Needs an HF_TOKEN with license accepted.",
    },
    {
        "repo_id": "OpenMOSS-Team/MOSS-TTS-Nano",
        "label": "MOSS-TTS-Nano (20 langs, CPU-realtime)",
        "role": "TTS",
        "size_gb": 0.4,
        "required": False,
    },
    {
        # Lightweight English "Turbo" TTS. Optional — the wizard doesn't
        # auto-download this; users opt in from Settings → Models when they
        # want fast English narration without voice cloning.
        "repo_id": "KittenML/kitten-tts-mini-0.8",
        "label": "KittenTTS (English, 8 preset voices, CPU realtime)",
        "role": "TTS",
        "size_gb": 0.08,
        "required": False,
    },
    # ── mlx-audio engines (mac-ARM only; opt-in from Settings → Models) ──
    # These come through backend.services.tts_backend:MLXAudioBackend. The
    # backend is only available on Apple Silicon; non-mac users never see
    # these download buttons as active because the backend is unavailable.
    {
        "repo_id": "mlx-community/Kokoro-82M-bf16",
        "label": "Kokoro 82M (8 langs, small, mlx-audio default)",
        "role": "TTS",
        "size_gb": 0.15,
        "required": False,
        "note": "Apple Silicon only — via mlx-audio backend.",
    },
    {
        "repo_id": "mlx-community/csm-1b-8bit",
        "label": "CSM 1B (voice cloning, mlx-audio)",
        "role": "TTS",
        "size_gb": 1.1,
        "required": False,
        "note": "Apple Silicon only — via mlx-audio backend.",
    },
    {
        "repo_id": "mlx-community/Qwen3-TTS-1.7B-4bit",
        "label": "Qwen3-TTS 1.7B 4bit (voice design, mlx-audio)",
        "role": "TTS",
        "size_gb": 1.4,
        "required": False,
        "note": "Apple Silicon only — via mlx-audio backend.",
    },
    {
        "repo_id": "mlx-community/Dia-1.6B",
        "label": "Dia 1.6B (expressive, mlx-audio)",
        "role": "TTS",
        "size_gb": 3.2,
        "required": False,
        "note": "Apple Silicon only — via mlx-audio backend.",
    },
    {
        "repo_id": "mlx-community/OuteTTS-0.3-500M",
        "label": "OuteTTS 0.3 500M (voice clone, mlx-audio)",
        "role": "TTS",
        "size_gb": 1.0,
        "required": False,
        "note": "Apple Silicon only — via mlx-audio backend.",
    },
]
# Back-compat tuple view for code that expects (repo_id, label) pairs.
REQUIRED_MODELS = [(m["repo_id"], m["label"]) for m in KNOWN_MODELS if m["required"]]


def _is_cached(repo_id: str) -> bool:
    """Best-effort check: does HF have this repo in its cache on disk?
    We don't validate the specific file set — presence of the repo dir is
    close enough for a first-run gate."""
    try:
        from huggingface_hub import scan_cache_dir
        info = scan_cache_dir()
        for entry in info.repos:
            if entry.repo_id == repo_id and entry.size_on_disk > 0:
                return True
        return False
    except Exception as e:
        logger.debug("scan_cache_dir failed: %s", e)
        # Pessimistic: if we can't tell, report missing so the wizard appears
        # and the user sees progress instead of a silent hang.
        return False


@router.get("/setup/status")
def setup_status():
    """Snapshot the setup state so the client can pick its boot screen.

    Returns everything the wizard needs to decide: missing model list, disk
    headroom, HF cache path (for the user's information + "clear cache" ops).
    """
    missing = [
        {"repo_id": rid, "label": label}
        for (rid, label) in REQUIRED_MODELS
        if not _is_cached(rid)
    ]
    cache = _hf_cache_dir()
    free_gb = _disk_free_gb(cache)
    return {
        "models_ready": len(missing) == 0,
        "missing": missing,
        "hf_cache_dir": cache,
        "disk_free_gb": round(free_gb, 2),
        "min_free_gb": MIN_FREE_GB,
        "enough_disk": free_gb >= MIN_FREE_GB,
    }


@router.get("/setup/download-stream")
async def setup_download_stream():
    """SSE: forward every HuggingFace download tqdm update as a JSON event.

    The client connects on mount, then kicks a separate `POST /setup/download`
    (or invokes a normal ASR/TTS call that triggers the download). This
    endpoint stays open until the client closes it.
    """
    # Buffered queue so fast-emitting tqdm updates don't drop events on slow
    # clients. Bounded so a stuck consumer can't grow memory indefinitely.
    queue: asyncio.Queue = asyncio.Queue(maxsize=512)
    loop = asyncio.get_event_loop()

    def listener(event):
        # tqdm lives on a background thread (hf's downloader). We need to
        # marshal events onto the FastAPI event loop before enqueueing.
        try:
            loop.call_soon_threadsafe(_safe_put, queue, event)
        except RuntimeError:
            # Loop closed between events — client has gone away, safe to drop.
            pass

    listener_id = hf_progress.register_listener(listener)

    async def gen():
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                except asyncio.TimeoutError:
                    # Heartbeat every 30 s so intermediaries don't time out.
                    yield ": keepalive\n\n"
                    continue
                yield f"data: {json.dumps(event)}\n\n"
        finally:
            hf_progress.unregister_listener(listener_id)

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
        },
    )


def _safe_put(queue: asyncio.Queue, event) -> None:
    """Non-blocking enqueue — drop oldest on overflow rather than block the
    tqdm thread."""
    try:
        queue.put_nowait(event)
    except asyncio.QueueFull:
        try:
            queue.get_nowait()
            queue.put_nowait(event)
        except Exception:
            pass


@router.get("/models")
def list_models():
    """Catalogue every known model + its on-disk install state.

    The frontend Models tab reads this to draw install/delete buttons. We
    don't walk disk for every model — instead `scan_cache_dir()` returns
    *everything* HF has cached, and we look up each known repo in that map.
    One os-walk regardless of model count.
    """
    cached_by_repo: dict[str, dict] = {}
    try:
        from huggingface_hub import scan_cache_dir
        info = scan_cache_dir()
        for entry in info.repos:
            cached_by_repo[entry.repo_id] = {
                "size_on_disk": entry.size_on_disk,
                "last_accessed": entry.last_accessed,
                "nb_files": entry.nb_files,
            }
    except Exception as e:
        logger.warning("scan_cache_dir failed: %s", e)

    out = []
    for m in KNOWN_MODELS:
        cached = cached_by_repo.get(m["repo_id"])
        out.append({
            **m,
            "installed": cached is not None and cached["size_on_disk"] > 0,
            "size_on_disk_bytes": cached["size_on_disk"] if cached else 0,
            "nb_files": cached["nb_files"] if cached else 0,
        })
    return {
        "models": out,
        "total_installed_bytes": sum(m["size_on_disk_bytes"] for m in out),
        "hf_cache_dir": _hf_cache_dir(),
    }


class InstallModelRequest(BaseModel):
    repo_id: str


@router.post("/models/install")
async def install_model(req: InstallModelRequest):
    """Download one HF repo snapshot; progress goes through the shared
    `/setup/download-stream` SSE feed. Returns immediately so the UI can
    start listening to the stream.

    Matching by repo_id only — no version pinning today. HF's default-branch
    "main" / "refs/heads/main" is what snapshot_download picks."""
    if req.repo_id not in [m["repo_id"] for m in KNOWN_MODELS]:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unknown model: {req.repo_id!r}. Known: "
                + ", ".join(m["repo_id"] for m in KNOWN_MODELS)
            ),
        )
    loop = asyncio.get_event_loop()

    def _do():
        try:
            from huggingface_hub import snapshot_download
            logger.info("model install starting: %s", req.repo_id)
            snapshot_download(repo_id=req.repo_id)
            logger.info("model install done: %s", req.repo_id)
        except Exception as e:
            logger.warning("model install failed for %s: %s", req.repo_id, e)

    # Non-blocking — client polls /models or listens on the SSE.
    loop.create_task(asyncio.to_thread(_do))
    return {"status": "install_started", "repo_id": req.repo_id}


@router.delete("/models/{repo_id:path}")
def delete_model(repo_id: str):
    """Remove every cached revision of a repo from the HF cache. Frees disk
    + lets the user re-install a fresh copy via POST /models/install."""
    try:
        from huggingface_hub import scan_cache_dir
        info = scan_cache_dir()
        commits = [
            rev.commit_hash
            for entry in info.repos if entry.repo_id == repo_id
            for rev in entry.revisions
        ]
        if not commits:
            raise HTTPException(
                status_code=404,
                detail=(
                    f"Model {repo_id!r} isn't installed. Nothing to delete — "
                    "run POST /models/install first if you want a fresh download."
                ),
            )
        strategy = info.delete_revisions(*commits)
        strategy.execute()
        return {
            "deleted": True,
            "repo_id": repo_id,
            "freed_bytes": strategy.expected_freed_size,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=(
                f"Could not delete {repo_id}: {e}. "
                "Close any process using the model (e.g. the app's main dub job) and retry."
            ),
        )


@router.get("/setup/recommendations")
def recommendations():
    """Return a curated model preset for the caller's device + architecture.

    The Settings / first-run Models tab uses this to render a prominent
    "Install recommended" card so users don't have to pick from 14 models.
    Logic mirrors the engine availability matrix:
      - mac-ARM gets the rich mlx-audio stack (Kokoro) + MLX-Whisper speedup
      - mac-Intel + Linux + Windows get the cross-platform subset
      - CUDA hosts optionally get the pytorch-whisper fallback baked in
    """
    is_mac_arm = sys.platform == "darwin" and _platform.machine() == "arm64"
    is_mac_intel = sys.platform == "darwin" and _platform.machine() == "x86_64"
    is_linux = sys.platform.startswith("linux")
    is_windows = sys.platform == "win32"

    has_cuda = False
    try:
        import torch
        has_cuda = bool(torch.cuda.is_available())
    except Exception:
        pass

    # Device label — used as the card title.
    if is_mac_arm:
        device_label = f"Apple Silicon ({_platform.machine()})"
    elif is_mac_intel:
        device_label = "macOS Intel (x86_64)"
    elif is_windows:
        device_label = "Windows x64" + (" + CUDA" if has_cuda else "")
    elif is_linux:
        device_label = "Linux x64" + (" + CUDA" if has_cuda else "")
    else:
        device_label = f"{sys.platform} / {_platform.machine()}"

    # Pick the preset for this device.
    if is_mac_arm:
        recommended_ids = [
            "k2-fsa/OmniVoice",                   # required — 600+ lang zero-shot
            "Systran/faster-whisper-large-v3",    # required — WhisperX ASR
            "mlx-community/whisper-large-v3-mlx", # optional mac speedup
            "mlx-community/Kokoro-82M-bf16",      # mlx-audio fast TTS
            "KittenML/kitten-tts-mini-0.8",       # English turbo tier
        ]
        rationale = (
            "Apple Silicon gets the full stack: OmniVoice for multilingual clone + "
            "WhisperX (faster-whisper weights) for cross-platform ASR + MLX-Whisper "
            "for the Apple-optimised speedup + Kokoro (mlx-audio) for fast local "
            "English + KittenTTS as a CPU-realtime backup."
        )
    else:
        recommended_ids = [
            "k2-fsa/OmniVoice",                   # required
            "Systran/faster-whisper-large-v3",    # required
            "KittenML/kitten-tts-mini-0.8",       # English turbo — cross-platform
        ]
        if has_cuda:
            # A CUDA box can actually run pytorch-whisper well; ship it as a
            # fallback so the user can pin it in Settings → Engines later.
            recommended_ids.append("openai/whisper-large-v3")
            rationale = (
                "Cross-platform stack + pytorch-whisper as a CUDA-accelerated "
                "ASR fallback. MLX / mlx-audio are Apple-Silicon-only and don't "
                "apply here."
            )
        else:
            rationale = (
                "Cross-platform stack: OmniVoice (multilingual clone) + WhisperX "
                "(faster-whisper ASR) + KittenTTS (English turbo, CPU-realtime). "
                "Clean install, every model runs on CPU."
            )

    # Cross-reference against KNOWN_MODELS so we can attach size + label to
    # each recommended entry, and flag which ones are already installed.
    known_by_id = {m["repo_id"]: m for m in KNOWN_MODELS}
    cached_ids: set[str] = set()
    try:
        from huggingface_hub import scan_cache_dir
        info = scan_cache_dir()
        cached_ids = {
            entry.repo_id for entry in info.repos if entry.size_on_disk > 0
        }
    except Exception:
        pass

    entries = []
    for rid in recommended_ids:
        meta = known_by_id.get(rid, {})
        entries.append({
            "repo_id": rid,
            "label": meta.get("label", rid),
            "role": meta.get("role", ""),
            "size_gb": meta.get("size_gb", 0),
            "required": bool(meta.get("required", False)),
            "note": meta.get("note"),
            "installed": rid in cached_ids,
        })

    # Headline number for the "Install recommended (~X GB)" CTA — only
    # count models not yet on disk so users with a warm cache see a low
    # remaining number instead of the full bundle size.
    to_download_gb = sum(e["size_gb"] for e in entries if not e["installed"])
    all_installed = all(e["installed"] for e in entries)

    return {
        "device": {
            "os": sys.platform,
            "arch": _platform.machine(),
            "is_mac_arm": is_mac_arm,
            "is_mac_intel": is_mac_intel,
            "is_linux": is_linux,
            "is_windows": is_windows,
            "has_cuda": has_cuda,
            "label": device_label,
        },
        "rationale": rationale,
        "models": entries,
        "download_gb_remaining": round(to_download_gb, 2),
        "total_gb": round(sum(e["size_gb"] for e in entries), 2),
        "all_installed": all_installed,
    }


@router.post("/setup/warmup")
async def setup_warmup():
    """Trigger a model load in the background so the first dub doesn't pay
    the cold-start tax. Progress flows through the SSE stream."""
    loop = asyncio.get_event_loop()

    async def _do_warmup():
        try:
            from services.model_manager import get_model
            await get_model()
        except Exception as e:
            logger.warning("setup/warmup: model load failed: %s", e)

    # Don't await — let it run in the background; client watches SSE.
    loop.create_task(_do_warmup())
    return {"status": "warmup_started"}
