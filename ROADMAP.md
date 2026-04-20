# OmniVoice Studio — Road to World-Class

Honest plan for moving from "polished solo-dev project" to software that holds up under scrutiny at scale. This revision incorporates the critique of the v1 roadmap (fantasy timelines, wrong phase order, Phase-5 dumping ground, no risks, no resourcing) and threads in the design / features / performance / innovation moves needed to compete at the top of the category.

---

## 🎯 North Star

> The best **local-first** cinematic dubbing studio in the world. Indistinguishable from a cloud product in quality and UX, but never leaves the user's machine.

Three non-negotiables that define "world-class" here:
1. **Two defensible innovations** that no competitor can copy in a sprint, backed by obsessive polish everywhere else.
2. **Dub output quality** good enough that a human editor would only tweak wording, not rebuild timing.
3. **UX** where a non-technical user produces a polished dubbed video in under 10 minutes, end to end, and never waits on a spinner longer than they expect.

## 🎲 Our two bets

World-class products stand for one or two things. We stand for these:

### Bet A — Directorial AI
Natural-language direction as a first-class pipeline input. User writes *"make segment 14 feel more urgent and surprised"* and the pipeline rewrites the translate-reflection tone, the TTS `instruct` prompt, and the speech-rate target. Not a prompt field — a structured directorial layer, applied per-segment or per-scene. Competitors chasing this are a year behind once we have the taxonomy + evals.

### Bet B — Incremental re-dub
Change a single word in segment 14 of a two-hour video, re-generate only that segment + adjacent crossfades, reassemble in seconds. Requires a segment dependency graph, stable seeds, audio-level diffing. Turns dubbing from a render-and-wait tool into a live instrument.

**Together**: a directorial edit triggers an incremental re-dub. This composition is the story we tell.

---

## 📍 Where we are today

✅ Feature-complete MVP: transcribe → translate → dub → mux pipeline, voice cloning, timeline editor, diarization, YouTube ingest, selective export, project persistence, desktop Tauri shell.
⚠️ Code health: 1.8k-line App.jsx, 889-line dub_core.py, no TypeScript, in-memory task queue, thin tests, module-global model state.
⚠️ Quality ceiling: one-shot translation, raw WhisperX segments, no speech-rate adaptation, no glossary.
⚠️ UX ceiling: functional glassmorphism, no motion language, error messages confess engine internals, no onboarding.

References: [`research/LEARNINGS.md`](research/LEARNINGS.md), [`design/`](design/), [`STRUCTURE.md`](STRUCTURE.md).

---

## 📐 Resourcing assumption

**1 FTE + ad-hoc contributors.** Every estimate below is based on that. Double the team → roughly halve the time. Solo → roughly 1.5×. All timelines are **ranges**, not promises.

---

## 🧭 Sequential phases

Phases are ordered by **visible user impact first, foundational work second** — deliberately inverted from the v1 roadmap. The argument: three months of invisible plumbing before anything users feel is a motivation and signal-loss risk.

### Phase 0 — Momentum (1 week)

> *Ship-this-week wins. Nothing invisible. Build a habit of landing improvements.*

- Dead-code sweep ✓ *(already shipped)*
- Alembic skeleton + first real migration file (retire the hand-rolled ALTER allowlist in `backend/core/db.py`).
- One smoke test per router so CI turns green on every file.
- Rewrite the 10 most-seen error messages to: *what happened · why · what to do*. Start with `dub_generate.py:98` `"Engine VRAM crash on segment: …"`.
- Add a 500ms launch animation + skeleton screens on every page's first load.
- Pick a preloaded 30-second sample clip that ships with the app; make it the default empty-state offer.

**Exit criteria:** every error the user sees is actionable; every page has a skeleton on first load; the sample clip renders in <10s on a cold start.

---

### Phase 1 — Visible quality leap (6–8 weeks)

> *The single biggest user-visible upgrade. Directly from VideoLingo's playbook. Ship before any refactor, so users feel the improvement regardless of foundation work underneath.*

#### 1.1 Translate → Reflect → Adapt
- Replace the one-shot translation with a 3-step chain in `backend/services/translator.py` (new): translate → critique → cinematic rewrite.
- Expose a **Quality: Fast / Cinematic** toggle.
- **Files:** `backend/api/routers/dub_translate.py`, new `backend/services/translator.py`.

#### 1.2 NLP-aware subtitle segmentation
- Re-chunk WhisperX output at clause/sentence boundaries with Netflix rules (≤42 chars/line, single line preferred, ≤17 CPS).
- **Files:** new `backend/services/subtitle_segmenter.py`, called after transcription.

#### 1.3 Project-scoped term glossary
- Extract recurring proper nouns via LLM pre-pass; editable glossary panel; inject into every translate prompt.
- **Files:** new `terms` table, new `backend/api/routers/glossary.py`, new `frontend/src/components/GlossaryPanel.tsx`.

#### 1.4 Dual subtitle export
- SRT/VTT export with original + translated together.
- **Files:** `backend/api/routers/dub_export.py`.

**Exit criteria:** blind A/B on 3 clips (EN→DE, EN→JA, EN→ES) shows ≥70% preference for the new pipeline. Dub output materially feels more professional to an untrained listener.

---

### Phase 2 — Foundation refactor (10–14 weeks)

> *The invisible work that unblocks everything after Phase 4. Runs after Phase 1 so users feel progress first.*

#### 2.1 Persist the task queue
- Move `core/tasks.py` state to SQLite-backed `jobs` + `job_steps` tables; tasks survive restart; SSE reconnect replays from last checkpoint.

#### 2.2 Split the App.jsx monolith
- Extract global state to a Zustand store. Target: App.jsx ≤300 lines, pure shell + router.
- **Files:** new `frontend/src/store/{project,dub,ui,voice,engines}.ts`.

#### 2.3 TypeScript migration (incremental)
- Store + API layer + entrypoint first. Pages convert one at a time.
- Wire `tsc --noEmit` into CI.

#### 2.4 Split dub_core.py
- Business logic moves to `backend/services/dub_pipeline.py`. Router stays HTTP-only, ≤300 lines.

#### 2.5 Design-system primitives
- `<Button>`, `<Panel>`, `<Slider>`, `<Table>`, `<Dialog>` with variants. Kill inline style duplication across pages.
- **Files:** new `frontend/src/ui/`.

#### 2.6 Logging + telemetry baseline
- All `print()` → `logger`. Structured JSON logs behind a flag. Per-stage timing counters at `/metrics`.

#### 2.7 Test floor
- One integration test per pipeline stage, snapshot tests on segment math. **Every bug ships a regression test** (replaces the arbitrary "70% coverage" goal).

**Exit criteria:** server can restart mid-dub without losing work. Frontend type-checks. No router file >300 lines. App.jsx ≤300 lines. CI blocks regressions.

---

### Phase 3 — Pluggable engines (4–6 weeks)

> *Stop being locked to one model family. Unlock VoxCPM2 as a serious alternative and widen the ASR/LLM surface.*

#### 3.1 TTS adapter interface
- `services/tts_backend.py` protocol (`generate`, `generate_streaming`, `sample_rate`, `supported_languages`).
- Wrap current model as `OmniVoiceBackend` — zero behaviour change.

#### 3.2 VoxCPM2 backend
- `voxcpm` optional-dep group, `VoxCPM2Backend` implementation, engine selector in Settings, device-capability gating.

#### 3.3 ASR adapter interface
- Swappable WhisperX / mlx-whisper / faster-whisper.

#### 3.4 Optional LLM adapter
- One interface, Ollama default (local), cloud providers strictly opt-in per-feature. **Never** required.

**Exit criteria:** engine swap works without restart on Mac + Linux. VoxCPM2 available when CUDA 12+ detected.

---

### Phase 4 — The two bets land (10–14 weeks)

> *The defining phase. This is why someone chooses OmniVoice over everything else.*

Phase 4 is built on Phase 2's persistent job store and Phase 3's adapters. Attempting it earlier regrets.

#### 4.1 Incremental re-dub (Bet B)
- Segment dependency graph in `backend/services/dub_pipeline.py` — which artifacts change when text X, voice Y, rate Z change.
- Stable seeds per (segment_id, voice_id, text_hash).
- Audio-level diff + crossfade reassembly without full re-render.
- Regenerate triggered only for affected segments + their immediate neighbours.
- **Files:** new `backend/services/incremental.py`, `dub_pipeline.py`, `DubTab.tsx`.

#### 4.2 Directorial AI (Bet A)
- Taxonomy of directorial intents (energy, pace, emotion, intimacy, formality, etc.) with prompt templates per TTS backend.
- Natural-language direction field on segments; LLM parses to taxonomy tokens; tokens drive translate reflection + TTS `instruct` + speech-rate target.
- Eval set: 50 scripted directions × 3 voices × 3 languages, scored by a rubric.
- **Files:** new `backend/services/director.py`, new `frontend/src/components/DirectionField.tsx`, translation/generation routers.

#### 4.3 Staged checkpoints (supporting)
- Pipeline states `awaiting_review_asr → awaiting_review_translation → awaiting_review_tts → done`. "Continue" gates with editable intermediate artifact.

#### 4.4 Speech-rate engineering (supporting)
- Predict target-duration vs. source slot before TTS. LLM trims or expands text. Loop until fit (max 3). Lip-sync score becomes feedback signal, not decoration.

#### 4.5 Step-level resumability (supporting)
- Every step checkpoints partial artifacts keyed by `(project_id, step, segment_id)`. Crash at step 7/10 resumes from 6.

#### 4.6 Headless CLI + Tools page
- `omnivoice-dub video.mp4 --target de --voice marcus --engine voxcpm2` for batch/CI.
- Standalone utilities surface: vocal separation, subtitle alignment, video+SRT merge, transcript matching.

**Exit criteria:** changing one word regenerates in <5s on the fixture clip. Directorial evals beat baseline by ≥15% on the rubric. Kill -9 mid-dub resumes to completion.

---

### Phase 5 — Productisation (demand-driven)

> *When real users and real deployments force these to be addressed. Do not build proactively.*

Candidate tracks, picked **based on signal**, not built speculatively:

| Track | Trigger that starts it |
|---|---|
| Multi-worker + Redis/Postgres job queue | First team asks to share a GPU across users |
| OpenTelemetry tracing | First "why is this slow?" incident we can't diagnose |
| Optional auth (magic-link / passkey) | First team-deployment request |
| Signed installers + auto-update (Tauri) | Paid release or pre-order list forms |
| Plugin SDK (third-party TTS/ASR/LLM) | First external contributor ships an adapter |

None of these are on the critical path to world-class. All of them are answers to real demand.

---

## 🛤️ Parallel tracks (always running)

Tracks don't have start/end dates. They run continuously, each owned by whoever's touching that surface.

### 🎨 Design track

Running during and after every phase. Dedicated audit hour every Friday.

- **Motion language.** Every state transition has a purpose: springs on drag, spring-back on rejection, stagger on reveal. 60fps budget.
- **Density dial rebuild.** Small/Normal/Max rebuilds layout, not just font-size scaling. Pros see 80 segments; newcomers see 8.
- **Error messages** rewritten in every code path (not just the top 10 from Phase 0).
- **Onboarding** as "first action on a pre-loaded real-looking project," not a tutorial modal.
- **Launch animation** + recognisable sound.
- **Weekly inconsistency audit.** One hour. Anything off the system gets logged and fixed the next week.

### ⚡ Performance track

One developer-week per quarter is protected for nothing but: instrument → profile → fix top 3 regressions. Non-negotiable.

- **Batched TTS.** Today `dub_generate.py:81` is one `_model.generate` per segment. Batch 8–16 per forward pass. 3–5× throughput.
- **Kill per-segment disk round-trip.** Tensors stay in memory until final assembly (`dub_generate.py:132-133` today re-reads every segment from disk).
- **Cold start ≤1.5s to first audible sample.** Today 4s+. Pre-warm on app launch; stream first segment before second is queued; verify `torch.compile` didn't silently skip (`model_manager.py:42`).
- **Speculative regeneration.** On hover over "regenerate," start generation. If clicked, it's done. If not, discarded.
- **Crash-sandbox engines.** Each TTS/ASR/LLM in its own subprocess. Engine crash auto-restarts; jobs resume. Today one CUDA OOM kills the server.
- **Interaction budgets.** <50ms UI feedback · <200ms preview audio · <4s first generated segment · <1× realtime full dub. Measured. Dashboarded. Regress-gated.

### ✨ Feature-magic track

The "five features that would matter" from the strategy review. Shipped opportunistically after their prerequisite phase lands.

1. **Project-level casting view.** One screen, entire show cast in 30 seconds. Drag voices to speakers. Auto-match from reference clips. — *after Phase 3.*
2. **Voice memory across projects.** Marcus in ep. 12 sounds like Marcus in ep. 1 with zero casting work. New `voice_performances` table accumulates pitch/pacing/rhythm signatures. — *after Phase 4.*
3. **Context-aware pipeline.** Video frames into the pipeline: scene cuts reset emotional context; face tracking anchors diarisation; close-ups tighten lip-sync tolerance. — *after Phase 4.*
4. **On-device learning from corrections.** User edits toward a better version → capture as LoRA training signal. Gated: never ships until quality evals prove the model improves, not drifts. — *research project; possibly Phase 5+.*
5. **Real-time dub preview.** Streaming TTS during edit — user hears the new take within 200ms of a text change. — *requires Phase 4.1 + performance track maturity.*

### 🧪 Quality track

- **Every bug ships a regression test.** Replaces the v1's "70% coverage" vanity target.
- **Perf regression budget.** No PR may increase end-to-end dub wall-time by >5% on the fixture clip without written justification.
- **Accessibility.** Keyboard-first on every surface. WCAG AA contrast. ARIA live regions for long tasks.
- **Privacy.** No feature calls a third party without explicit per-feature opt-in. Zero telemetry by default.
- **Docs.** Every phase ships a `docs/` update. `design/` ASCII mockups get replaced with screenshots once implemented.

---

## ⚠️ Risks & unknowns

Honest list of what could derail this roadmap.

| Risk | Why it matters | Mitigation |
|---|---|---|
| **Local LLM ≠ frontier LLM for translation** | Phase 1's "Cinematic" quality realistically benefits from Claude/GPT-class models. Ollama local is not yet at parity for niche language pairs. | Accept "Cinematic w/ local" and "Cinematic w/ cloud (opt-in)" as two SKUs. Never make cloud required. |
| **Model landscape drift** | VoxCPM3 / F5-TTS-v3 / new frontier TTS land during the roadmap. Phase 3's adapter work may be outdated before it ships. | Adapter interface is the hedge. Land it once, swap models freely. |
| **Tauri code-signing / notarisation** | Desktop distribution requires Apple Developer + Windows EV cert. Costs and process overhead not yet scoped. | Budget Phase 5's installer track with 2 weeks of compliance headroom. |
| **pyannote HF-token friction** | Diarisation requires an HF token users must fetch manually. Bounces new users on install. | Ship a "skip diarisation for now" path; auto-diarise on first token-present run. |
| **On-device fine-tuning quality** | User-correction LoRAs can drift the model toward worse output if ungated. | Research project only. Ships with an automatic eval gate; discarded if evals regress. |
| **Voice cloning likeness/IP concerns** | Regulators and platforms will tighten voice-cloning rules over the next 18 months. | Log every clone with its source; surface consent prompts; build deletion tools early. |
| **Apple MPS parity with CUDA** | VoxCPM2 and some optimisations are CUDA-first. | Adapter interface + capability gates. Never ship a Mac build with a broken option visible. |
| **Solo-dev bandwidth** | Everything above assumes 1 FTE sustained. Real life interrupts. | Explicit 20% buffer baked into every estimate. Phases can slip without changing order. |

---

## 📏 Success metrics

Falsifiable. Measured continuously. Replaces the v1's vanity metrics (GitHub stars, arbitrary coverage number).

- [ ] **Dub quality:** ≥70% blind preference vs. VideoLingo + pyVideoTrans on a 10-clip benchmark.
- [ ] **Time to first dub:** ≤10 minutes from fresh install to finished MP4 on a 3-minute YouTube clip.
- [ ] **Cold start:** model load → first audible sample streamed in ≤1.5s.
- [ ] **Incremental re-dub:** single-word change → regenerated audio on timeline in ≤5s on fixture clip.
- [ ] **Recovery:** `kill -9` during a dub, restart, resume to completion with zero data loss.
- [ ] **Directorial eval:** natural-language direction beats baseline on taxonomy rubric by ≥15%.
- [ ] **Engine robustness:** engine subprocess crash during a dub → auto-recovery, job continues.
- [ ] **Interaction latency:** p95 UI feedback <50ms; p95 preview audio <200ms; measured in telemetry.
- [ ] **Regression safety:** zero shipped bugs in the last quarter re-surface in the next one.
- [ ] **Contributor onboarding:** an external contributor can ship a non-trivial PR within their first week (validated by 3 successive external PRs).

---

## 🧭 Design target

The intended shape of the mature product is captured in [`design/`](design/) — one ASCII mockup per view, plus a system architecture diagram. Every phase and track above brings the shipped product one step closer to what those views describe. When code and design diverge, one of them is wrong — decide which, then fix it.

---

## 🔁 Review cadence

- **Weekly:** design consistency audit (1h).
- **Bi-weekly:** roadmap status check, estimate drift review.
- **End of each phase:** retrospective + exit-criteria gate + roadmap revision (this document is updated, not appended).
- **Quarterly:** success-metric check + performance track dedicated week.

---

*Last revised: 2026-04-21. This roadmap is a living document. Every phase ends with a revision, not an append.*
