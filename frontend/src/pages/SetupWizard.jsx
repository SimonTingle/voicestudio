import React, { useCallback, useEffect, useState } from 'react';
import { CheckCircle, Loader, Sparkles, ArrowRight } from 'lucide-react';
import { Button } from '../ui';
import { setupStatus } from '../api/setup';
import { ModelStoreTab, EnginesTab } from './Settings';
import './SetupWizard.css';

// macOS convention: double-click the title-bar drag region to toggle zoom.
// Same pattern as components/Header.jsx — we don't import `@tauri-apps/api`
// eagerly so the browser preview doesn't need it.
const doubleClickMaximize = async () => {
  try {
    if (!('__TAURI_INTERNALS__' in window)) return;
    const { getCurrentWindow } = await import('@tauri-apps/api/window');
    getCurrentWindow().toggleMaximize();
  } catch { /* non-tauri preview — ignore */ }
};

/**
 * First-run / "no models installed" gate.
 *
 * Re-uses the real Settings → Models and Settings → Engines panels inside a
 * 3-step guided flow so the wizard stays a single source of truth. If either
 * tab gets a feature later (new engine, new model column), onboarding
 * inherits it for free — no parallel UI to maintain.
 *
 * Flow:
 *   1. Welcome — hero + explainer + "continue"
 *   2. Models  — embed ModelStoreTab. User installs the required weights
 *                (OmniVoice + Systran/faster-whisper-large-v3). Polls
 *                /setup/status in the background — the "Finish" button
 *                unlocks as soon as `models_ready` flips true.
 *   3. Engines — embed EnginesTab. User picks TTS/ASR/LLM backends
 *                (or just clicks through on sensible defaults).
 *   Finish    — onReady() dismisses the wizard, main studio renders.
 */
export default function SetupWizard({ onReady }) {
  const [step, setStep] = useState(0);
  const [status, setStatus] = useState(null);

  const reload = useCallback(async () => {
    try { setStatus(await setupStatus()); }
    catch { /* backend warming up — retry on interval */ }
  }, []);

  useEffect(() => { reload(); }, [reload]);

  // Poll while on the Models step so the Finish button unlocks as soon as
  // downloads complete, without the user having to click "Recheck".
  useEffect(() => {
    if (step !== 1) return;
    const iv = setInterval(reload, 4000);
    return () => clearInterval(iv);
  }, [step, reload]);

  const modelsReady = !!status?.models_ready;

  return (
    <div className="setup-wizard">
      {/* Title-bar drag region. Covers the whole hero + step pill area so
          the user can drag the window by the top of the wizard and
          double-click to toggle zoom — matches macOS native behaviour. */}
      <div
        data-tauri-drag-region
        onDoubleClick={doubleClickMaximize}
        className="setup-wizard__hero"
      >
        <Sparkles size={36} color="#d3869b" />
        <h1 data-tauri-drag-region>Welcome to OmniVoice Studio</h1>
        <p className="setup-wizard__sub" data-tauri-drag-region>
          Dubbing, voice cloning, and voice design — all running locally on
          your machine. Three quick steps and you're in.
        </p>
      </div>

      {/* Step indicator */}
      <div className="setup-wizard__steps">
        {['Welcome', 'Install models', 'Pick engines'].map((label, i) => (
          <button
            key={label}
            className={[
              'setup-wizard__step',
              step === i ? 'setup-wizard__step--active' : '',
              step > i ? 'setup-wizard__step--done' : '',
            ].filter(Boolean).join(' ')}
            onClick={() => setStep(i)}
            type="button"
          >
            {step > i ? '✓ ' : `${i + 1}. `}{label}
          </button>
        ))}
      </div>

      {/* Step content */}
      {step === 0 && (
        <div className="setup-wizard__embed" style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <strong>What happens next</strong>
          <ol style={{ margin: 0, paddingLeft: 20, lineHeight: 1.7, color: 'var(--color-fg-muted)', fontSize: '0.9rem' }}>
            <li>
              <strong>Install models</strong> — we'll download ~5 GB of weights
              (OmniVoice TTS + Whisper). You'll see the full catalogue here —
              required ones first, plus optional engines you can enable now or
              later.
            </li>
            <li>
              <strong>Pick engines</strong> — choose which TTS / ASR / LLM
              backends to use. Defaults work; power users can pin specific
              engines per family.
            </li>
            <li>
              <strong>You're in.</strong> First launch takes ~5-10 minutes to
              download. After that, every launch is instant and fully offline.
            </li>
          </ol>
          <div>
            <Button
              variant="primary" size="lg"
              onClick={() => setStep(1)}
              trailing={<ArrowRight size={14} />}
            >
              Get started
            </Button>
          </div>
        </div>
      )}

      {step === 1 && (
        <>
          <div className="setup-wizard__embed">
            <ModelStoreTab info={null} modelBadge={null} />
          </div>
          <div className="setup-wizard__nav">
            <Button variant="ghost" onClick={() => setStep(0)}>Back</Button>
            <Button
              variant={modelsReady ? 'primary' : 'ghost'}
              onClick={() => setStep(2)}
              trailing={<ArrowRight size={14} />}
              disabled={!modelsReady}
              title={modelsReady ? '' : 'Install the required models above to continue.'}
            >
              {modelsReady
                ? 'Required models ready — continue'
                : 'Waiting for required models…'}
            </Button>
          </div>
          {!modelsReady && status?.missing?.length > 0 && (
            <p className="setup-wizard__muted" style={{ textAlign: 'center', fontSize: '0.78rem', margin: 0 }}>
              Still needed:{' '}
              {status.missing.map(m => m.label).join(', ')}
            </p>
          )}
        </>
      )}

      {step === 2 && (
        <>
          <div className="setup-wizard__embed">
            <EnginesTab />
          </div>
          <div className="setup-wizard__nav">
            <Button variant="ghost" onClick={() => setStep(1)}>Back</Button>
            <Button
              variant="primary"
              onClick={onReady}
              leading={<CheckCircle size={14} />}
            >
              Enter studio
            </Button>
          </div>
        </>
      )}

      {!status && step > 0 && (
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', justifyContent: 'center', color: 'var(--color-fg-muted)' }}>
          <Loader className="spinner" size={14} /> Checking setup…
        </div>
      )}

      <p className="setup-wizard__footnote">
        Downloads come from <code>huggingface.co</code>. Cache: {' '}
        <code>{status?.hf_cache_dir || '~/.cache/huggingface'}</code>
      </p>
    </div>
  );
}
