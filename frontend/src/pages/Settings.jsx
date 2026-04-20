import React, { useEffect, useState, useCallback } from 'react';
import {
  Cpu, FileText, Info, ShieldCheck, RefreshCw, Trash2, ExternalLink,
  CheckCircle, AlertCircle,
} from 'lucide-react';
import { toast } from 'react-hot-toast';
import { systemInfo, systemLogs, systemLogsTauri, clearSystemLogs, clearTauriLogs, modelStatus as fetchModelStatus } from '../api/system';
import { getFrontendLogs, clearFrontendLogs } from '../utils/consoleBuffer';
import { Tabs, Segmented, Button, Badge } from '../ui';
import './Settings.css';

const TABS = [
  { id: 'models',  label: 'Models',  icon: Cpu,          accent: '#f3a5b6' },
  { id: 'logs',    label: 'Logs',    icon: FileText,     accent: '#fabd2f' },
  { id: 'about',   label: 'About',   icon: Info,         accent: '#8ec07c' },
  { id: 'privacy', label: 'Privacy', icon: ShieldCheck,  accent: '#b8bb26' },
];

const LOG_SOURCES = [
  { value: 'backend',  label: 'Backend' },
  { value: 'frontend', label: 'Frontend' },
  { value: 'tauri',    label: 'Tauri' },
];

function Row({ label, value, mono }) {
  return (
    <div className="settings-row">
      <span className="label">{label}</span>
      <span className={`value ${mono ? 'settings-row__mono' : ''}`}>
        {value}
      </span>
    </div>
  );
}

export default function Settings() {
  const [activeTab, setActiveTab] = useState('models');
  const [info, setInfo] = useState(null);
  const [status, setStatus] = useState(null);
  const [logSource, setLogSource] = useState('backend');
  const [logs, setLogs] = useState([]);
  const [logMeta, setLogMeta] = useState({ path: '', exists: false });
  const [loadingLogs, setLoadingLogs] = useState(false);

  const refreshInfo = useCallback(async () => {
    try {
      const [i, s] = await Promise.all([systemInfo(), fetchModelStatus()]);
      setInfo(i); setStatus(s);
    } catch (e) { /* ignore */ }
  }, []);

  const refreshLogs = useCallback(async () => {
    setLoadingLogs(true);
    try {
      if (logSource === 'backend') {
        const r = await systemLogs(400);
        setLogs(r.lines || []);
        setLogMeta({ path: r.path || '', exists: !!r.exists });
      } else if (logSource === 'tauri') {
        const r = await systemLogsTauri(400);
        setLogs(r.lines || []);
        setLogMeta({ path: r.path || '—', exists: !!r.exists, candidates: r.candidates });
      } else {
        const entries = getFrontendLogs();
        const lines = entries.map((e) => {
          const ts = new Date(e.t).toISOString().slice(11, 23);
          return `[${ts}] [${e.level}] ${e.msg}\n`;
        });
        setLogs(lines);
        setLogMeta({ path: 'in-memory (last 500)', exists: true });
      }
    } catch (e) {
      toast.error('Failed to load logs: ' + e.message);
    } finally {
      setLoadingLogs(false);
    }
  }, [logSource]);

  useEffect(() => {
    refreshInfo();
    const iv = setInterval(refreshInfo, 4000);
    return () => clearInterval(iv);
  }, [refreshInfo]);

  useEffect(() => {
    if (activeTab === 'logs') refreshLogs();
  }, [activeTab, logSource, refreshLogs]);

  const onClearLogs = async () => {
    if (logSource === 'frontend') {
      if (!confirm('Clear the in-memory frontend log buffer?')) return;
      clearFrontendLogs();
      toast.success('Frontend logs cleared');
      setLogs([]);
      return;
    }
    if (logSource === 'tauri') {
      if (!confirm('Truncate the Tauri-side log files? The OS will continue to write new entries.')) return;
      try {
        const r = await clearTauriLogs();
        if (!r?.cleared?.length) {
          toast('Nothing to clear — no Tauri log file on disk yet.', { icon: 'ℹ️' });
        } else {
          toast.success(`Cleared ${r.cleared.length} Tauri log file(s)`);
          setLogs([]);
        }
      } catch (e) {
        toast.error('Failed to clear Tauri logs: ' + e.message);
      }
      return;
    }
    if (!confirm('Clear the backend runtime + crash logs? This cannot be undone.')) return;
    try {
      await clearSystemLogs();
      toast.success('Backend logs cleared');
      setLogs([]);
    } catch (e) {
      toast.error('Failed to clear logs');
    }
  };

  const modelBadge =
    status?.status === 'ready'   ? <Badge tone="success"><CheckCircle size={11} /> Ready</Badge>
  : status?.status === 'loading' ? <Badge tone="warn"><RefreshCw size={11} className="spinner" /> Loading…</Badge>
                                 : <Badge tone="warn">Idle</Badge>;

  return (
    <div className="settings-page">
      <h1>Settings</h1>
      <div className="settings-subtitle">
        Where your files live, what the model's doing, and what's gone wrong lately.
      </div>

      <Tabs
        items={TABS}
        value={activeTab}
        onChange={setActiveTab}
        className="settings-tabs-ui"
      />

      {activeTab === 'models' && (
        <section className="settings-section">
          <h2><Cpu size={16} color="#f3a5b6" /> Models</h2>
          {info ? (
            <>
              <Row label="TTS checkpoint"       value={info.model_checkpoint} mono />
              <Row label="ASR model (Whisper)"  value={info.asr_model} mono />
              <Row label="Translate provider"   value={info.translate_provider} />
              <Row label="Device"               value={info.device?.toUpperCase()} />
              <Row label="Status"               value={modelBadge} />
              <Row label="Idle timeout"         value={`${info.idle_timeout_seconds}s`} />
              <Row
                label="Hugging Face token"
                value={info.has_hf_token
                  ? <Badge tone="success"><CheckCircle size={11} /> Set</Badge>
                  : <Badge tone="warn"><AlertCircle size={11} /> Missing — diarization disabled</Badge>}
              />
            </>
          ) : (
            <div className="settings-muted">Loading…</div>
          )}
        </section>
      )}

      {activeTab === 'logs' && (
        <section className="settings-section">
          <h2 className="settings-section__head-row">
            <span className="settings-section__head-left">
              <FileText size={16} color="#fabd2f" /> Logs
            </span>
            <span className="settings-section__head-actions">
              <Button
                variant="subtle"
                size="sm"
                onClick={refreshLogs}
                loading={loadingLogs}
                leading={!loadingLogs && <RefreshCw size={11} />}
              >
                Refresh
              </Button>
              <Button
                variant="danger"
                size="sm"
                onClick={onClearLogs}
                leading={<Trash2 size={11} />}
              >
                Clear
              </Button>
            </span>
          </h2>

          <Segmented
            items={LOG_SOURCES}
            value={logSource}
            onChange={setLogSource}
          />

          <div className="settings-log-meta">
            <span>{logMeta.path || '—'}</span>
            {logSource === 'tauri' && !logMeta.exists && (
              <Badge tone="warn">
                <AlertCircle size={11} /> No Tauri log on disk yet — launch via the desktop build to produce one
              </Badge>
            )}
          </div>
          <div className="settings-log">
            {logs.length === 0
              ? <span className="settings-log__empty">
                  {logSource === 'frontend'
                    ? 'No frontend console entries captured yet. Interact with the app — every console.* will appear here.'
                    : logSource === 'tauri'
                      ? 'No Tauri log available. Runs in the desktop shell only.'
                      : "Runtime log is empty. Activity will appear here as the backend logs it."}
                </span>
              : logs.join('')}
          </div>
        </section>
      )}

      {activeTab === 'about' && (
        <section className="settings-section">
          <h2><Info size={16} color="#8ec07c" /> About</h2>
          <Row label="App"             value="OmniVoice Studio" />
          <Row label="Python"          value={info?.python || '—'} mono />
          <Row label="Platform"        value={info?.platform || '—'} />
          <Row label="Data directory"  value={info?.data_dir || '—'} mono />
          <div className="settings-link-row">
            <Button
              variant="subtle"
              size="md"
              leading={<ExternalLink size={12} />}
              onClick={() => window.open('https://github.com/k2-fsa/OmniVoice', '_blank', 'noopener,noreferrer')}
            >
              OmniVoice on GitHub
            </Button>
            <Button
              variant="subtle"
              size="md"
              leading={<ExternalLink size={12} />}
              onClick={() => window.open('https://huggingface.co/k2-fsa/OmniVoice', '_blank', 'noopener,noreferrer')}
            >
              Model card
            </Button>
          </div>
        </section>
      )}

      {activeTab === 'privacy' && (
        <section className="settings-section">
          <h2><ShieldCheck size={16} color="#b8bb26" /> Privacy</h2>
          <p className="settings-prose">
            Everything runs on <strong>this machine</strong>. Your audio, video, and transcripts
            never leave your computer unless you explicitly use an online translator (Google, DeepL, etc.) or
            push to HuggingFace.
          </p>
          <Row label="Uploads stored at"   value={info?.data_dir ? `${info.data_dir}/` : '—'} mono />
          <Row label="Outputs stored at"   value={info?.outputs_dir || '—'} mono />
          <Row label="Generation history"  value={<Badge tone="neutral">Local SQLite</Badge>} />
          <Row
            label="Network calls"
            value={
              info?.translate_provider && ['google', 'deepl', 'mymemory', 'microsoft', 'openai'].includes(info.translate_provider)
                ? <Badge tone="warn"><AlertCircle size={11} /> Translator is online: {info.translate_provider}</Badge>
                : <Badge tone="success"><CheckCircle size={11} /> Offline translator</Badge>
            }
          />
          <Row
            label="Model telemetry"
            value={<Badge tone="success"><CheckCircle size={11} /> None — no tracking</Badge>}
          />
        </section>
      )}
    </div>
  );
}
