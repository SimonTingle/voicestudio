"""Stable digests for locally installed model snapshots.

``model_digest`` in the wire contract pins the exact bytes a READY model will
execute with. Hugging Face snapshots are symlink farms into ``blobs/``, so the
digest is computed over the *resolved* file contents: SHA-256 of the sorted
sequence ``<posix relpath>\\n<file sha256>\\n``. That is stable across hosts,
cache locations, and symlink layout, and changes whenever any weight byte or
the file set changes.

Hashing multi-GB weights on every ``GetCapabilities`` call would be absurd, so
the result is cached in a JSON sidecar keyed by a cheap fingerprint of the
file list (relpath, size, mtime_ns). Any file change invalidates the cache and
forces a full re-hash.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

DIGEST_PREFIX = "sha256:"
_CHUNK = 1024 * 1024


def file_sha256(path: str | os.PathLike[str]) -> str:
    hasher = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            chunk = fh.read(_CHUNK)
            if not chunk:
                break
            hasher.update(chunk)
    return hasher.hexdigest()


def _manifest(root: Path) -> list[tuple[str, int, int]]:
    """Sorted (relpath, size, mtime_ns) for every regular file under root.

    Follows symlinks (HF snapshot layout); a dangling symlink raises
    ``FileNotFoundError`` — callers treat that as an incomplete install.
    """
    entries: list[tuple[str, int, int]] = []
    for current, dirs, files in os.walk(root, followlinks=True):
        dirs.sort()
        for name in sorted(files):
            path = Path(current) / name
            stat = path.stat()  # resolves symlinks; raises if dangling
            rel = path.relative_to(root).as_posix()
            entries.append((rel, stat.st_size, stat.st_mtime_ns))
    entries.sort()
    return entries


def _fingerprint(entries: list[tuple[str, int, int]]) -> str:
    return hashlib.sha256(
        json.dumps(entries, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def snapshot_digest(root: str | os.PathLike[str], cache_path: str | os.PathLike[str] | None = None) -> str:
    """``sha256:<hex>`` digest of the snapshot at ``root``.

    Raises ``FileNotFoundError`` for a missing/empty snapshot or dangling
    symlink and ``OSError`` for unreadable files — callers classify those as
    not-READY rather than fabricating a digest.
    """
    root = Path(root)
    entries = _manifest(root)
    if not entries:
        raise FileNotFoundError(f"empty model snapshot: {root}")
    fingerprint = _fingerprint(entries)

    if cache_path is not None:
        cached = _read_cache(cache_path)
        if cached is not None and cached.get("fingerprint") == fingerprint:
            digest = cached.get("digest", "")
            if isinstance(digest, str) and digest.startswith(DIGEST_PREFIX):
                return digest

    hasher = hashlib.sha256()
    for rel, _size, _mtime in entries:
        hasher.update(rel.encode("utf-8"))
        hasher.update(b"\n")
        hasher.update(file_sha256(root / rel).encode("ascii"))
        hasher.update(b"\n")
    digest = DIGEST_PREFIX + hasher.hexdigest()

    if cache_path is not None:
        _write_cache(cache_path, fingerprint, digest)
    return digest


def _read_cache(cache_path: str | os.PathLike[str]) -> dict | None:
    try:
        with open(cache_path, encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


def _write_cache(cache_path: str | os.PathLike[str], fingerprint: str, digest: str) -> None:
    cache_path = Path(cache_path)
    payload = json.dumps({"fingerprint": fingerprint, "digest": digest})
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = cache_path.with_suffix(f".tmp-{os.getpid()}")
        temporary.write_text(payload, encoding="utf-8")
        os.replace(temporary, cache_path)
    except OSError:
        pass  # cache is an optimization; the digest itself is already computed
