"""Device and model inventory reported through Health/GetCapabilities.

The server is written against the small protocol at the top of this module so
tests can substitute fakes; :class:`ProductionInventory` is the real thing,
wired to ``services.tts_backend``'s engine registry, ``services.hf_revisions``
pinned revisions, and :mod:`runtime_adapter.digest`.

State rules (mirrors the Go preflight's expectations):

- READY is **explicit**: engine registered, availability probe passed, the
  pinned snapshot fully present on disk, and a digest computed. Anything
  less is INSTALLED / LOADING / FAILED — never READY.
- A loading or failed model is still listed (with its true state) so the
  Gateway can observe it; only READY models are schedulable.
"""
from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass, field

from . import SLOTS_ENV
from ._paths import ensure_backend_on_path
from .digest import snapshot_digest

STATE_INSTALLED = "installed"
STATE_LOADING = "loading"
STATE_READY = "ready"
STATE_FAILED = "failed"


@dataclass(frozen=True)
class DeviceInfo:
    device_id: str
    hardware_class: str
    total_vram_bytes: int
    total_slots: int
    free_slots: int


@dataclass(frozen=True)
class ModelInfo:
    catalog_model_id: str
    model_version: str
    model_digest: str
    precisions: tuple[str, ...] = ()
    features: tuple[str, ...] = ()
    state: str = STATE_INSTALLED


#: Engines this adapter can attest as digest-pinned models: TTS engine id →
#: curated Hugging Face repo (must be pinned in ``services.hf_revisions``).
#: Engines without a single pinned weights repo (external API servers,
#: multi-model muxes) are deliberately absent — they cannot be digest-pinned.
ENGINE_MODEL_REPOS: dict[str, str] = {
    "omnivoice": "k2-fsa/OmniVoice",
    "voxcpm2": "openbmb/VoxCPM2",
    "moss-tts-nano": "OpenMOSS-Team/MOSS-TTS-Nano-100M",
    "kittentts": "KittenML/kitten-tts-mini-0.8",
    "cosyvoice": "FunAudioLLM/Fun-CosyVoice3-0.5B-2512",
    "moss-tts-v15": "OpenMOSS-Team/MOSS-TTS-v1.5",
}


def slots_per_device(default: int = 1) -> int:
    raw = os.environ.get(SLOTS_ENV, "").strip()
    try:
        value = int(raw) if raw else default
    except ValueError:
        return default
    return max(1, min(value, 64))


@dataclass
class ProductionInventory:
    """Real host inventory. All heavy imports happen inside methods.

    ``models()`` is memoized for ``model_ttl_s`` under a lock: the first call
    hashes every installed snapshot (minutes for multi-GB weights, then cached
    in the on-disk digest sidecar), and Health + GetCapabilities arrive
    back-to-back. Call :meth:`warm` before serving so the first RPC never
    pays the hashing cost inside its deadline.
    """

    slots: int = field(default_factory=slots_per_device)
    model_ttl_s: float = 15.0

    def __post_init__(self):
        self._model_lock = threading.Lock()
        self._model_cache: list[ModelInfo] | None = None
        self._model_cache_at = 0.0

    def warm(self) -> None:
        self.models()

    def devices(self, busy_slots: int = 0) -> list[DeviceInfo]:
        ensure_backend_on_path()
        devices = self._accelerators() or [self._cpu_device()]
        return [self._with_slots(device, busy_slots) for device in devices]

    def _with_slots(self, device: DeviceInfo, busy_slots: int) -> DeviceInfo:
        free = max(0, min(device.total_slots - busy_slots, device.total_slots))
        return DeviceInfo(
            device_id=device.device_id,
            hardware_class=device.hardware_class,
            total_vram_bytes=device.total_vram_bytes,
            total_slots=device.total_slots,
            free_slots=free,
        )

    def _accelerators(self) -> list[DeviceInfo]:
        try:
            import torch  # noqa: PLC0415
        except Exception:
            return []
        found: list[DeviceInfo] = []
        try:
            if torch.cuda.is_available():
                for index in range(torch.cuda.device_count()):
                    props = torch.cuda.get_device_properties(index)
                    found.append(
                        DeviceInfo(
                            device_id=f"cuda:{index}",
                            hardware_class=torch.cuda.get_device_name(index),
                            total_vram_bytes=int(props.total_memory),
                            total_slots=self.slots,
                            free_slots=self.slots,
                        )
                    )
                return found
        except Exception:
            pass
        try:
            if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
                vram = 0
                recommended = getattr(torch.mps, "recommended_max_memory", None)
                if callable(recommended):
                    try:
                        vram = int(recommended())
                    except Exception:
                        vram = 0
                if vram <= 0:
                    vram = _system_memory_bytes()
                return [
                    DeviceInfo(
                        device_id="mps:0",
                        hardware_class="apple-silicon-mps",
                        total_vram_bytes=vram,
                        total_slots=self.slots,
                        free_slots=self.slots,
                    )
                ]
        except Exception:
            pass
        return []

    def _cpu_device(self) -> DeviceInfo:
        # A CPU-only node is a valid (slow) execution device. total_vram_bytes
        # carries system memory so the Gateway's ">0" validity check reflects
        # real capacity rather than a made-up constant.
        import platform  # noqa: PLC0415

        return DeviceInfo(
            device_id="cpu:0",
            hardware_class=platform.processor() or platform.machine() or "cpu",
            total_vram_bytes=_system_memory_bytes(),
            total_slots=self.slots,
            free_slots=self.slots,
        )

    def models(self) -> list[ModelInfo]:
        with self._model_lock:
            now = time.monotonic()
            if (
                self._model_cache is not None
                and now - self._model_cache_at < self.model_ttl_s
            ):
                return list(self._model_cache)
            self._model_cache = self._scan_models()
            self._model_cache_at = time.monotonic()
            return list(self._model_cache)

    def _scan_models(self) -> list[ModelInfo]:
        ensure_backend_on_path()
        from services.hf_cache_repair import repo_cache_dir  # noqa: PLC0415
        from services.hf_revisions import installed_revision  # noqa: PLC0415
        from services.tts_backend import get_backend_class  # noqa: PLC0415

        models: list[ModelInfo] = []
        for engine_id, repo_id in sorted(ENGINE_MODEL_REPOS.items()):
            try:
                backend_cls = get_backend_class(engine_id)
            except Exception:
                continue  # engine not registered in this build
            repo_dir = repo_cache_dir(repo_id)
            try:
                revision = installed_revision(repo_id, os.path.dirname(repo_dir))
            except ValueError:
                continue  # repo not in the curated catalog — cannot attest
            snapshot = os.path.join(repo_dir, "snapshots", revision)
            if not os.path.isdir(snapshot):
                continue  # weights not installed at the pinned revision
            models.append(
                self._model_state(engine_id, backend_cls, repo_dir, revision, snapshot)
            )
        return models

    def _model_state(
        self, engine_id: str, backend_cls, repo_dir: str, revision: str, snapshot: str
    ) -> ModelInfo:
        base = ModelInfo(
            catalog_model_id=engine_id,
            model_version=revision,
            model_digest="",
            precisions=self._precisions(backend_cls),
            features=self._features(backend_cls),
        )
        try:
            ok, _message = backend_cls.is_available()
        except Exception:
            return _replace_state(base, STATE_FAILED)
        if not ok:
            return _replace_state(base, STATE_INSTALLED)
        if _snapshot_incomplete(repo_dir, snapshot):
            return _replace_state(base, STATE_LOADING)
        try:
            model_digest = snapshot_digest(
                snapshot,
                cache_path=os.path.join(repo_dir, f"voicestudio-digest-{revision}.json"),
            )
        except OSError:
            return _replace_state(base, STATE_LOADING)
        return ModelInfo(
            catalog_model_id=base.catalog_model_id,
            model_version=base.model_version,
            model_digest=model_digest,
            precisions=base.precisions,
            features=base.features,
            state=STATE_READY,
        )

    def _precisions(self, backend_cls) -> tuple[str, ...]:
        # Advisory execution precisions. fp32 always works; fp16 is offered
        # when the engine targets an accelerator this host actually has.
        compat = tuple(getattr(backend_cls, "gpu_compat", ("cpu",)))
        try:
            from core.device_caps import detect_host_caps  # noqa: PLC0415

            family = detect_host_caps().family
        except Exception:
            family = "cpu"
        if family != "cpu" and family in compat:
            return ("fp16", "fp32")
        return ("fp32",)

    def _features(self, backend_cls) -> tuple[str, ...]:
        features = ["tts"]
        if getattr(backend_cls, "supports_cloning", False) is True:
            features.append("voice_clone")
        if getattr(backend_cls, "supports_voice_design", False):
            features.append("voice_design")
        if getattr(backend_cls, "supports_emotion", False):
            features.append("emotion")
        return tuple(features)


def _replace_state(model: ModelInfo, state: str) -> ModelInfo:
    return ModelInfo(
        catalog_model_id=model.catalog_model_id,
        model_version=model.model_version,
        model_digest=model.model_digest,
        precisions=model.precisions,
        features=model.features,
        state=state,
    )


def _snapshot_incomplete(repo_dir: str, snapshot: str) -> bool:
    """A download in flight leaves ``*.incomplete`` blobs or dangling links."""
    blobs = os.path.join(repo_dir, "blobs")
    try:
        if any(name.endswith(".incomplete") for name in os.listdir(blobs)):
            return True
    except OSError:
        pass
    for current, _dirs, files in os.walk(snapshot):
        for name in files:
            path = os.path.join(current, name)
            if not os.path.exists(path):  # dangling symlink
                return True
    return False


def _system_memory_bytes() -> int:
    try:
        import psutil  # noqa: PLC0415

        return int(psutil.virtual_memory().total)
    except Exception:
        try:
            return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
        except (ValueError, OSError, AttributeError):
            return 1  # still nonzero: the preflight requires > 0
