# Competitor Learnings

Catalog of ideas worth absorbing from adjacent open-source dub/translate projects. Each entry rates impact and fit for OmniVoice Studio's architecture (local-first, FastAPI + React + Tauri, single in-house TTS diffusion model).

Legend: 🔥 high impact · ⚙️ medium impact · 🚫 skip

---

## Source: [VideoLingo](https://github.com/Huanshere/VideoLingo)

Streamlit app that targets "Netflix-quality" subtitle and dub output. LLM-heavy, pluggable TTS backends.

### 🔥 Translate → Reflect → Adapt (3-step LLM)

One-shot translation loses nuance. VideoLingo runs:
1. **Translate** — literal pass.
2. **Reflect** — LLM critiques its own output (tone, pacing, idiom, subtitle length).
3. **Adapt** — rewrite for cinematic delivery using the critique.

**Where it lands in OmniVoice:** `backend/api/routers/dub_translate.py`. Replace the single call with a 3-step chain; expose a "Quality: Fast / Cinematic" toggle in the UI.

**Why it matters:** Biggest single-axis lift for dub quality. Directly competes with the thing these tools market on.

### 🔥 NLP-aware, Netflix-standard subtitle segmentation

Raw WhisperX segments don't respect subtitle readability limits. VideoLingo re-chunks at clause/sentence boundaries, enforcing single-line rule, max chars/line (~42), and max CPS.

**Where it lands in OmniVoice:** new service `backend/services/subtitle_segmenter.py`, called after `segmentation.py` transcription, before the dub table is populated.

**Why it matters:** Better segments → tighter lip-sync windows → better dub + much cleaner SRT/VTT export.

### 🔥 Term glossary (proper nouns + tech terms)

Pre-pass extracts recurring proper nouns / domain terms, LLM proposes translations, user edits once, then every segment translation is pinned to the glossary.

**Where it lands in OmniVoice:** new `terms` table in `backend/core/db.py` (project-scoped); UI surface in `DubTab.jsx` (collapsible glossary panel); inject glossary into translate prompts.

**Why it matters:** Eliminates the "same character's name translated three different ways" problem on long videos.

### 🔥 Speech-rate engineering

Before TTS, predict target-language duration vs. source slot; if over budget, LLM trims filler / reflows, if under, it expands. Runs in a loop until duration fits.

**Where it lands in OmniVoice:** tie into existing lip-sync scoring (`services/audio_dsp.py` region). Currently a passive badge — make it a *feedback signal* that drives a retry step in `dub_generate.py`.

**Why it matters:** Dubbed audio that actually fits the scene, without post-hoc time-stretching artifacts.

### ⚙️ Step-level resumability

VideoLingo checkpoints every pipeline step to disk. A crash at step 7/10 resumes from 6 on restart.

**Where it lands in OmniVoice:** extend `core/tasks.py` with per-step state in the task queue; persist partial artifacts keyed by (project_id, step).

**Why it matters:** Dubbing a 2-hour video can take 30+ min. Re-running from scratch after a crash is painful.

### ⚙️ Dual subtitle export (original + translation)

Common Netflix-style option.

**Where it lands in OmniVoice:** `backend/api/routers/dub_export.py` — add `--dual-subs` flag and a UI checkbox.

### ⚙️ Model searchbox with provider API fetch

Instead of static dropdown, query the configured LLM provider for available models and let users search/filter.

**Where it lands in OmniVoice:** only relevant if/when LLM providers become configurable (see "skip" below). Low priority unless that path is taken.

### 🚫 Streamlit UI

OmniVoice's React/Tauri UI is already ahead. Ignore.

### 🚫 Cloud provider zoo (302.ai, Azure, OpenAI)

Conflicts with the "no API keys, no cloud" positioning. If added, keep strictly optional and opt-in.

---

## Source: [pyVideoTrans](https://github.com/jianchang512/pyvideotrans)

PySide6 desktop app, GPL v3. Broader on integrations, narrower on per-step AI quality. Strong at workflow/tooling.

### 🔥 Staged human-in-the-loop checkpoints

Explicit pause points after ASR, after translation, after TTS for user review/correction.

**Where it lands in OmniVoice:** extend `core/tasks.py` job state machine with `awaiting_review` states. UI: present a "continue" button after each stage in `DubTab.jsx`, with the intermediate artifact editable.

**Why it matters:** Current OmniVoice flow is either "run all" or "edit after everything is done." Human correction between stages dramatically reduces compounding errors and wasted TTS compute.

### ⚙️ Full dub CLI

OmniVoice ships `omnivoice-infer` (TTS only) but no headless entry point for the whole dub pipeline.

**Where it lands in OmniVoice:** new `omnivoice-dub` script in `omnivoice/cli/`, driving the same services as the HTTP routers. Good for batch jobs, pyinstaller bundles, and CI.

### ⚙️ Pluggable ASR/TTS adapters

Abstract ASR and TTS behind a thin interface so users can slot in faster-whisper variants, F5-TTS, edge-tts for preview, etc. OmniVoice's TTS stays default.

**Where it lands in OmniVoice:** interface layer in `backend/services/` (`asr_backend.py`, `tts_backend.py`); register backends by name in config.

**Why it matters:** Broadens the user base without compromising the defaults. Also useful for fast-preview TTS while user is still editing.

### ⚙️ Standalone utility surface

pyVideoTrans exposes vocal-separation, subtitle↔audio alignment, video+SRT merge as first-class tools, independent of the dub flow.

**Where it lands in OmniVoice:** add a "Tools" page alongside `DubTab` / `CloneDesignTab`. Reuses existing services (`demucs`, `ffmpeg_utils`).

### ⚙️ Transcript matching (existing SRT → alignment without re-transcribing)

When the user already has subtitles, skip ASR and force-align to audio.

**Where it lands in OmniVoice:** new endpoint in `dub_core.py`; pyannote + wav2vec forced-align on provided SRT.

### 🚫 Pre-packaged `.exe` release

Tauri packaging (already scaffolded in `frontend/src-tauri/`) is the better answer for cross-platform desktop distribution.

### 🚫 PySide6 GUI

N/A — React UI already in place.

---

## Recommended first PR

Ship items together so they reinforce each other on the main quality axis:

1. **Translate → Reflect → Adapt** (VideoLingo)
2. **NLP-aware subtitle segmentation** (VideoLingo)
3. **Term glossary** (VideoLingo)

All three touch the translation stage and together make dub output a visible step-change — which is exactly the axis competitors market on.

Follow-up PR: **Staged human-in-the-loop checkpoints** (pyVideoTrans) + **speech-rate engineering** (VideoLingo). These change the *control surface* of dubbing rather than the raw quality, but are the difference between a demo and a working studio.

---

## Alt TTS Backend: [VoxCPM2](https://huggingface.co/openbmb/VoxCPM2) (OpenBMB)

Candidate **drop-in alternative** to the OmniVoice TTS model. Pair with the "Pluggable TTS adapters" item (pyVideoTrans, ⚙️ above) — VoxCPM2 becomes the second concrete backend behind the adapter interface.

### Why consider it

| Axis | OmniVoice (current) | VoxCPM2 |
|---|---|---|
| Architecture | Diffusion LM, zero-shot | Tokenizer-free diffusion autoregressive (LocEnc → TSLM → RALM → LocDiT), 2B params, MiniCPM-4 backbone |
| Training data | — | 2M+ hours multilingual speech |
| Languages | 600 (zero-shot, tag-based) | 30 languages + 9 Chinese dialects, **no language tags required** |
| Sample rate | — | 48 kHz studio (AudioVAE V2, asymmetric 16k→48k) |
| Voice design | Tag-driven | Natural-language prompts inline (`"(young woman, gentle voice)Hello..."`) |
| Voice cloning | 3s reference clip | Reference clip **+ optional transcript** for "ultimate cloning" fidelity |
| Streaming | Chunked WAV | First-class `generate_streaming()` iterator |
| License | — | **Apache-2.0**, commercial OK |
| VRAM | — | ~8 GB |
| RTF (RTX 4090) | — | 0.30 standard / 0.13 with Nano-vLLM |
| Fine-tuning | — | LoRA or full, 5–10 min audio sufficient |

**Strengths over current model:**
- Inline natural-language voice direction in the *same string* as the text — no separate tag field, no style profile gymnastics.
- "Ultimate cloning" (reference audio + transcript) is a meaningful quality tier above the current 3-sec clone.
- Native streaming iterator simplifies `services/model_manager.py` streaming plumbing.
- 48 kHz studio output vs. typical 24 kHz TTS.
- Apache-2.0 — clean for Tauri desktop distribution.

**Trade-offs:**
- **30 languages vs. 600.** Narrower, but covers ~all major dub-target languages. If the user base is dubbing to Hindi / Spanish / German / Japanese, this is not a regression in practice.
- **CUDA ≥12 required.** Current OmniVoice works on MPS (Apple Silicon) via `mlx-whisper`; VoxCPM2 docs show only CUDA. Verify MPS/CPU paths before shipping Mac builds with this backend.
- **2B params / 8 GB VRAM** is heavier than some setups.
- Single model weight (`openbmb/VoxCPM2`) — need to confirm HuggingFace mirror + `HF_TOKEN` path works inside Docker image.

### Where it lands in OmniVoice

**Step 1 — adapter layer (prerequisite).** Introduce `backend/services/tts_backend.py` with a minimal interface:

```python
class TTSBackend(Protocol):
    def generate(self, text: str, *, reference_wav: Path | None, **kw) -> np.ndarray: ...
    def generate_streaming(self, text: str, **kw) -> Iterator[np.ndarray]: ...
    @property
    def sample_rate(self) -> int: ...
    @property
    def supported_languages(self) -> list[str]: ...
```

Move the current OmniVoice integration into `OmniVoiceBackend`. Register backends by name; `model_manager.py` picks one from config (`OMNIVOICE_TTS_BACKEND=omnivoice|voxcpm2`).

**Step 2 — VoxCPM2 backend.**

- Add dep: `voxcpm` (pip). Check whether it pulls heavy/conflicting torch deps vs. current `torch==2.8.0` constraint in `pyproject.toml:106`. May need a separate optional-dep group: `[project.optional-dependencies] voxcpm = ["voxcpm>=...", ...]`.
- New file: `backend/services/voxcpm_backend.py`.
- Load once in `model_manager.py` (same idle-eviction pattern as current model).
- Map OmniVoice's voice-design tags → VoxCPM2's inline natural-language prefix (`"(female, british accent, excited)..."`).
- Route "ultimate cloning" (reference + transcript) through the existing clone flow when a transcript is available — the cloned voice profiles already capture sample audio, transcript just needs a new column.

**Step 3 — UI surface (`CloneDesignTab.jsx`, `Settings.jsx`).**

- Settings page: "TTS Engine" radio (`OmniVoice (600 lang, zero-shot)` / `VoxCPM2 (studio 48 kHz, 30 lang)`).
- Clone panel: optional "Reference transcript" textarea — unlocks Ultimate Cloning when VoxCPM2 is active.
- Language dropdown filters to the active backend's `supported_languages`.

**Step 4 — Docker / Tauri.**

- Docker: CUDA 12+ base already in use; just add `voxcpm` to the optional-dep install in `Dockerfile`.
- Tauri macOS build: if VoxCPM2 has no MPS/CPU path, gate the backend selector so Mac users only see backends that actually run. Don't ship a broken option.

### Shipping order

1. Land the **TTS adapter interface** (pyVideoTrans item) — unblocks everything.
2. Wrap **OmniVoiceBackend** behind it (no behavior change, just refactor). CI should prove zero regression.
3. Land **VoxCPM2Backend** as an opt-in second choice behind a config flag.
4. Promote to UI once it's been soak-tested on a real dub of ≥30 min of video.

Treat VoxCPM2 as **additive**, not replacement. OmniVoice's 600-lang reach is still the differentiator in the long tail; VoxCPM2 is the "studio-quality big-language" option.
