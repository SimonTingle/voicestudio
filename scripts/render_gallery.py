#!/usr/bin/env python3
"""Render the voice gallery: every archetype preview, once, as a signed bundle.

The app renders archetype previews on the GPU on first request, which means a
fresh install hears nothing until the 2.4 GB TTS checkpoint has downloaded, and
every user pays a cold model load per voice. This script does that work once, on
a machine that already has the weights, and produces the artifacts
``backend/services/gallery.py`` downloads:

    <out>/manifest.json          schema + per-key filename/sha256/bytes/duration
    <out>/previews/<key>.mp3     64 kbps mono, one per distinct preview key
    <out>/featured.tar.gz        the 51 featured previews, as one request

**Publishing is a manual owner step.** This script only builds the directory and
prints the two commands that follow: signing ``manifest.json`` with the existing
Tauri release key (the client verifies against the pubkey already baked into the
binary — no second trust root) and uploading the result. Nothing here talks to
GitHub.

MP3 at 64 kbps mono is a bytes decision, not a quality one: 1126 previews of a
sample script are ~110 MB as WAV and ~9 MB as MP3, and the featured tarball a
first run pulls is ~450 kB. The app already plays user-dropped MP3s.

Provenance: every clip is passed through ``mark_synthetic(force=True)`` at the
tensor stage before encoding — ``force`` because publication must not depend on
the *publisher's* watermark preference — and detection is then re-run **on the
decoded MP3**, so a bitrate that destroys the watermark fails the build instead
of shipping unmarked audio. That check is why the encode settings live here and
not in a shell one-liner.

Usage (from the repo root, with the model cached):

    python3 scripts/render_gallery.py --out dist/gallery
    python3 scripts/render_gallery.py --out dist/gallery --featured-only

Only the render step is on the GPU; marking, encoding, decoding and detection
are all CPU, so clips are built ``--jobs`` at a time (4 by default) and the card
does not sit idle through four stages per clip. ``--resume`` picks up whatever
is already in the output directory, including MP3s from a run that was
interrupted before it could write a manifest.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import gzip
import json
import sys
import tarfile
import tempfile
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = REPO_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

#: Must match ``services.gallery.SCHEMA_VERSION`` — the client refuses anything
#: else rather than guessing at an unknown layout.
SCHEMA_VERSION = 1

MP3_BITRATE = "64k"
MP3_CHANNELS = 1


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


async def _encode_mp3(wav_path: Path, mp3_path: Path) -> None:
    from services.ffmpeg_utils import find_ffmpeg, run_ffmpeg

    cmd = [
        find_ffmpeg(), "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(wav_path),
        "-ac", str(MP3_CHANNELS), "-b:a", MP3_BITRATE,
        # No metadata: the previews are identical for every user, and an
        # encoder/date tag would make otherwise-identical bytes differ per run.
        "-map_metadata", "-1",
        str(mp3_path),
    ]
    rc, _, err = await run_ffmpeg(cmd, timeout=120.0)
    if rc != 0 or not mp3_path.is_file():
        raise RuntimeError(f"mp3 encode failed: {err.decode('utf-8', 'replace')[:400]}")


async def _decode_wav(mp3_path: Path, wav_path: Path) -> None:
    """Decode back through ffmpeg so detection sees exactly the published bytes."""
    from services.ffmpeg_utils import find_ffmpeg, run_ffmpeg

    cmd = [
        find_ffmpeg(), "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(mp3_path), "-c:a", "pcm_s16le", str(wav_path),
    ]
    rc, _, err = await run_ffmpeg(cmd, timeout=120.0)
    if rc != 0 or not wav_path.is_file():
        raise RuntimeError(f"mp3 decode failed: {err.decode('utf-8', 'replace')[:400]}")


def _load(path: Path):
    import torchaudio

    wav, sr = torchaudio.load(str(path))
    return wav, int(sr)


def _mark_for_gallery(wav, sample_rate: int, context: str):
    """Embed a mandatory provenance mark without blocking the event loop."""
    from services.watermark import mark_synthetic

    return mark_synthetic(wav, sample_rate, force=True, context=context)


async def _build_one(archetype: dict, key: str, work: Path, out_previews: Path) -> dict:
    """Render, mark, encode, verify — returns the manifest entry for *key*."""
    from api.routers.archetypes import _render_archetype_wav
    from services.watermark import detect_watermark

    raw_wav = work / f"{key}.raw.wav"
    marked_wav = work / f"{key}.marked.wav"
    mp3_path = out_previews / f"{key}.mp3"

    await _render_archetype_wav(archetype, raw_wav)

    # Everything below that is CPU-bound goes through asyncio.to_thread. The
    # AudioSeal embed and detection are each a real neural forward pass, and run
    # inline they hold the event loop for the whole clip — so --jobs above 1
    # would queue work behind a busy loop and buy nothing. torch releases the
    # GIL inside those passes, which is what makes threads (rather than
    # processes) the right tool: no second model copy, no IPC for the tensors.
    wav, sr = await asyncio.to_thread(_load, raw_wav)

    # force=True: the published clip carries the mark regardless of whether the
    # machine doing the publishing has invisible watermarking switched on. Same
    # contract as persona_bundle's preview embed.
    marked = await asyncio.to_thread(_mark_for_gallery, wav, sr, "gallery.publish")
    from api.routers.generation import _safe_torchaudio_save

    await asyncio.to_thread(_safe_torchaudio_save, str(marked_wav), marked, sr)
    await _encode_mp3(marked_wav, mp3_path)

    check_wav = work / f"{key}.check.wav"
    await _decode_wav(mp3_path, check_wav)
    decoded, decoded_sr = await asyncio.to_thread(_load, check_wav)
    verdict = await asyncio.to_thread(detect_watermark, decoded, decoded_sr)
    if not verdict.get("is_watermarked"):
        mp3_path.unlink(missing_ok=True)
        raise AssertionError(
            f"watermark did not survive {MP3_BITRATE} mono encoding for {key} "
            f"(confidence {verdict.get('confidence')}, {verdict.get('error', '')}) — "
            "raise the bitrate or fix the embed before publishing"
        )

    data = mp3_path.read_bytes()
    duration = round(decoded.shape[-1] / max(decoded_sr, 1), 3)
    for scratch in (raw_wav, marked_wav, check_wav):
        scratch.unlink(missing_ok=True)
    return {
        "filename": mp3_path.name,
        "sha256": _sha256(data),
        "bytes": len(data),
        "duration": duration,
        "featured": bool(archetype.get("is_featured")),
    }


async def _preflight_watermark() -> None:
    """Prove the watermark works before rendering a thousand clips.

    Every clip is verified individually, so a broken embed was always caught —
    but only after the first full render, and the failure named the bitrate
    ("raise the bitrate or fix the embed") when the real cause can be nothing to
    do with audio at all. On a machine missing ``python3-dev``, AudioSeal's
    forward pass dies inside Inductor (``Python.h: No such file``),
    ``embed_watermark`` catches it, and the clip is returned *unmarked*. Five
    seconds here beats discovering that at clip 1 of 1126.

    Doubles as a single-threaded warm-up: the generator and detector are lazy
    module globals, so touching them once before --jobs fans out avoids several
    threads racing to load the same model.
    """
    import torch
    from services.watermark import detect_watermark

    sample_rate = 24000
    tone = torch.sin(
        2 * 3.14159 * 220 * torch.arange(sample_rate * 2) / sample_rate
    ).unsqueeze(0) * 0.3
    marked = await asyncio.to_thread(_mark_for_gallery, tone, sample_rate, "gallery.preflight")
    verdict = await asyncio.to_thread(detect_watermark, marked, sample_rate)
    if not verdict.get("is_watermarked"):
        raise SystemExit(
            "watermark preflight failed: mark_synthetic returned audio the "
            f"detector does not recognise (confidence {verdict.get('confidence')}). "
            "Publishing would ship unmarked audio, so this build stops here.\n"
            "Most common cause: torch.compile/Inductor cannot build its helper "
            "(missing Python headers — install python3-dev), which makes the "
            "embed raise and silently pass the audio through unchanged. "
            "TORCHDYNAMO_DISABLE=1 is the quick workaround."
        )


def _resume_from_disk(out_previews: Path, by_key: dict) -> dict:
    """Rebuild manifest entries for previews already rendered.

    The manifest is written once, at the end, so a run interrupted at clip 900
    leaves 900 perfectly good MP3s that ``--resume`` cannot see — it keys off
    the manifest, so it would render every one of them again. Everything an
    entry needs is recoverable from the file itself, so recover it.
    """
    recovered: dict = {}
    for mp3_path in sorted(out_previews.glob("*.mp3")):
        key = mp3_path.stem
        archetype = by_key.get(key)
        if archetype is None:
            continue  # a key from some older catalog — leave it out of the index
        data = mp3_path.read_bytes()
        if not data:
            mp3_path.unlink(missing_ok=True)
            continue
        recovered[key] = {
            "filename": mp3_path.name,
            "sha256": _sha256(data),
            "bytes": len(data),
            "duration": _probe_duration(mp3_path),
            "featured": bool(archetype.get("is_featured")),
        }
    return recovered


def _probe_duration(path: Path) -> float:
    """Duration in seconds, straight from the encoded file."""
    import subprocess

    from services.ffmpeg_utils import find_ffmpeg

    ffprobe = str(Path(find_ffmpeg()).with_name("ffprobe"))
    try:
        out = subprocess.run(
            [ffprobe, "-v", "error", "-show_entries", "format=duration",
             "-of", "default=nw=1:nk=1", str(path)],
            capture_output=True, text=True, timeout=30,
        ).stdout.strip()
        return round(float(out), 3)
    except (OSError, ValueError, subprocess.SubprocessError):
        return 0.0


def _write_featured_tarball(out: Path, previews: dict) -> dict:
    """Bundle the featured previews so a first run costs one request, not 51."""
    featured = sorted(k for k, e in previews.items() if e["featured"])
    archive = out / "featured.tar.gz"
    # mtime/uid/gid pinned so re-running with unchanged audio produces the same
    # archive bytes — the client diffs on sha256, and a timestamp would make
    # every rebuild look like a change worth re-downloading.
    with archive.open("wb") as raw, gzip.GzipFile(
        filename="", mode="wb", fileobj=raw, mtime=0
    ) as compressed, tarfile.open(fileobj=compressed, mode="w") as tar:
        for key in featured:
            path = out / "previews" / f"{key}.mp3"
            info = tar.gettarinfo(str(path), arcname=f"previews/{key}.mp3")
            info.mtime = 0
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            with path.open("rb") as fh:
                tar.addfile(info, fh)
    data = archive.read_bytes()
    return {
        "filename": archive.name,
        "sha256": _sha256(data),
        "bytes": len(data),
        "count": len(featured),
    }


async def _main(args: argparse.Namespace) -> int:
    from core import archetypes as catalog
    from core.version import APP_VERSION
    from api.routers.archetypes import _preview_key
    from services.tts_backend import active_backend_id

    out = Path(args.out).resolve()
    out_previews = out / "previews"
    out_previews.mkdir(parents=True, exist_ok=True)

    items = catalog.list_archetypes()
    if args.featured_only:
        items = [a for a in items if a["is_featured"]]
    # One clip per distinct key: archetypes that resolve to the same
    # (instruct, language) share a preview, exactly as the app's cache does.
    by_key: dict[str, dict] = {}
    for a in items:
        by_key.setdefault(_preview_key(a), a)
    keys = sorted(by_key)
    if args.limit:
        keys = keys[: args.limit]

    previews: dict[str, dict] = {}
    manifest_path = out / "manifest.json"
    if args.resume:
        if manifest_path.is_file():
            previous = json.loads(manifest_path.read_text(encoding="utf-8"))
            previews = {
                k: e for k, e in (previous.get("previews") or {}).items()
                if (out_previews / f"{k}.mp3").is_file()
            }
        # Also adopt clips on disk the manifest never got to describe — an
        # interrupted run has no manifest at all, and re-rendering audio that
        # is already correct is the most expensive way to do nothing.
        for key, entry in _resume_from_disk(out_previews, by_key).items():
            previews.setdefault(key, entry)
        if previews:
            print(f"resuming: {len(previews)} preview(s) already rendered", flush=True)

    await _preflight_watermark()

    pending = [k for k in keys if k not in previews]
    failures: list[str] = []
    with tempfile.TemporaryDirectory(prefix="gallery-render-") as tmp:
        work = Path(tmp)
        # Bounded fan-out. Each clip is render → embed → encode → decode →
        # detect, and only the first of those is on the GPU: with one clip in
        # flight the card idles through four CPU stages. The cap keeps that
        # overlap from turning into unbounded memory (every concurrent clip
        # holds decoded audio) and matches how the app itself bounds GPU work.
        limit = asyncio.Semaphore(max(1, args.jobs))
        completed = 0
        state = asyncio.Lock()

        async def build(key: str) -> None:
            nonlocal completed
            archetype = by_key[key]
            async with limit:
                entry = await _build_one(archetype, key, work, out_previews)
            async with state:
                previews[key] = entry
                completed += 1
                print(f"[{completed}/{len(pending)}] {key} {archetype['name']}", flush=True)

        tasks = [asyncio.create_task(build(key), name=key) for key in pending]
        try:
            for task in asyncio.as_completed(tasks):
                try:
                    await task
                except AssertionError:
                    # A lost watermark is a build failure, not a bad voice —
                    # stop the whole run rather than let the remaining jobs
                    # keep writing clips nobody has verified.
                    for other in tasks:
                        other.cancel()
                    raise
                except asyncio.CancelledError:
                    pass
                except Exception as exc:
                    failures.append(f"{type(exc).__name__}: {exc}")
                    print(f"    FAILED: {exc}", file=sys.stderr, flush=True)
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

    if not previews:
        print("nothing rendered", file=sys.stderr)
        return 1

    manifest = {
        "schema": SCHEMA_VERSION,
        "generated_at": int(time.time()),
        "engine": active_backend_id(),
        "engine_version": APP_VERSION,
        "format": {"codec": "mp3", "bitrate": MP3_BITRATE, "channels": MP3_CHANNELS},
        "featured": _write_featured_tarball(out, previews),
        "previews": dict(sorted(previews.items())),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n",
                             encoding="utf-8")

    print(f"\n{len(previews)} previews → {out}")
    if failures:
        print(f"{len(failures)} archetype(s) did not render:", file=sys.stderr)
        for line in failures:
            print(f"  {line}", file=sys.stderr)
    print(
        "\nNext (manual, owner):\n"
        f"  minisign -Sm {manifest_path} -s <tauri-release.key> "
        f"-x {manifest_path}.minisig\n"
        "  gh release create gallery-v1 --repo debpalash/omnivoice-gallery "
        f"{manifest_path} {manifest_path}.minisig {out / 'featured.tar.gz'} "
        f"{out_previews}/*.mp3"
    )
    return 1 if failures else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", default="dist/gallery", help="output directory")
    parser.add_argument("--featured-only", action="store_true",
                        help="render only the 51 featured archetypes")
    parser.add_argument("--limit", type=int, default=0, help="stop after N keys")
    parser.add_argument(
        "--jobs", type=int, default=4,
        help="clips built concurrently (default 4); 1 restores serial rendering",
    )
    parser.add_argument("--resume", action="store_true",
                        help="keep previews already in <out> (manifest entries "
                             "and any MP3s an interrupted run left behind)")
    return asyncio.run(_main(parser.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
