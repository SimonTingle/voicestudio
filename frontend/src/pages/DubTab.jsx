import React, { Suspense, lazy, useState } from 'react';
import {
  PanelLeftOpen, PanelLeftClose, Film, Save, UploadCloud, Sparkles, Loader, Square,
  FileText, Play, DownloadIcon, Volume2, Music, Package, Layers, Link2,
  Languages, ChevronDown, ChevronUp, Wand2, Trash2, Check, Globe, UserSquare2, User, AlertCircle,
} from 'lucide-react';
// lucide-react exports DownloadIcon as "Download"; alias here to match App.jsx naming.
import { Download as Download } from 'lucide-react';
import SearchableSelect from '../components/SearchableSelect';
import WaveformTimeline from '../components/WaveformTimeline';
import ALL_LANGUAGES from '../languages.json';
import { POPULAR_LANGS, POPULAR_ISO, PRESETS } from '../utils/constants';
import { LANG_CODES } from '../utils/languages';
import { formatTime } from '../utils/format';
import { API } from '../api/client';
import { Button, Segmented, Badge, Progress } from '../ui';
import './DubTab.css';

const DubSegmentTable = lazy(() => import('../components/DubSegmentTable'));

const LazyFallback = () => (
  <div style={{ padding: 12, color: '#6b6657', fontSize: '0.7rem' }}>Loading…</div>
);

export default function DubTab(props) {
  const {
    // State
    dubJobId, dubStep, dubPrepStage, dubVideoFile, dubFilename, dubDuration, dubSegments, dubTranscript,
    dubLang, dubLangCode, dubInstruct, dubTracks, dubError, dubProgress, dubLocalBlobUrl,
    activeProjectName,
    isSidebarCollapsed, setIsSidebarCollapsed,
    transcribeElapsed, translateProvider, setTranslateProvider,
    isTranslating,
    preserveBg, setPreserveBg, defaultTrack, setDefaultTrack,
    exportTracks, setExportTracks,
    showTranscript, setShowTranscript,
    profiles,
    segmentPreviewLoading,
    selectedSegIds,
    // Setters
    setDubVideoFile, setDubStep, setDubLocalBlobUrl, setDubSegments,
    setDubLang, setDubLangCode, setDubInstruct,
    // Handlers
    handleDubAbort, handleDubUpload, handleDubIngestUrl, handleDubStop, handleDubGenerate,
    handleDubDownload, handleDubAudioDownload,
    handleSegmentPreview, handleTranslateAll, handleCleanupSegments,
    triggerDownload, fileToMediaUrl,
    editSegments, saveProject, resetDub,
    segmentEditField, segmentDelete, segmentRestoreOriginal, segmentSplit, segmentMerge,
    toggleSegSelect, selectAllSegs, clearSegSelection,
    bulkApplyToSelected, bulkDeleteSelected,
  } = props;

  const showIdleSkeleton = !(dubJobId && (dubStep === 'editing' || dubStep === 'generating' || dubStep === 'done'));
  const [ingestUrl, setIngestUrl] = useState('');
  const [previewMode, setPreviewMode] = useState('original'); // 'original' | 'dubbed'
  const onIngestUrl = () => {
    if (!ingestUrl.trim() || !handleDubIngestUrl) return;
    handleDubIngestUrl(ingestUrl.trim());
    setIngestUrl('');
  };
  const hasDubbedTrack = dubStep === 'done' && dubLangCode && dubLangCode !== 'und' && (dubTracks?.length > 0 || !!dubTracks);
  const videoSrc = (previewMode === 'dubbed' && hasDubbedTrack)
    ? `${API}/dub/preview-video/${dubJobId}?lang=${encodeURIComponent(dubLangCode)}&preserve_bg=${preserveBg ? 1 : 0}`
    : `${API}/dub/media/${dubJobId}`;

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
      {/* ── Idle: show full editor skeleton with drop zone ── */}
      {showIdleSkeleton && (
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
          {/* Header bar */}
          <div className="studio-panel dub-head">
            <div className="label-row dub-head__title">
              <Button
                variant="icon"
                iconSize="sm"
                active={isSidebarCollapsed}
                onClick={() => setIsSidebarCollapsed(!isSidebarCollapsed)}
                title="Toggle Sidebar"
              >
                {isSidebarCollapsed ? <PanelLeftOpen size={12} /> : <PanelLeftClose size={12} />}
              </Button>
              <Film className="label-icon" size={11} />
              <span className="dub-head__filename">{dubVideoFile ? dubVideoFile.name : 'Video Dubbing Studio'}</span>
              {dubVideoFile && <span className="dub-head__meta">· {(dubVideoFile.size / 1024 / 1024).toFixed(1)} MB</span>}
              {activeProjectName && <span className="dub-head__project">— {activeProjectName}</span>}
            </div>
            <div className="dub-head__actions">
              <Button variant="subtle" size="sm" disabled leading={<Save size={9} />}>Save</Button>
              <Button variant="ghost"  size="sm" disabled>Reset</Button>
            </div>
          </div>

          {/* SPLIT LAYOUT skeleton */}
          <div className="dub-split-grid" style={{ display: 'grid', gridTemplateColumns: dubVideoFile ? '1fr 1fr' : '1fr', gap: 6, flex: 1, minHeight: 0 }}>
            {/* LEFT */}
            <div className="studio-panel" style={{ marginBottom: 0, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
              {dubVideoFile ? (
                <>
                  <WaveformTimeline
                    audioSrc={dubLocalBlobUrl?.audioUrl}
                    videoSrc={dubLocalBlobUrl?.videoUrl}
                    segments={[]}
                    onSegmentsChange={() => { }}
                    disabled={true}
                    overlayContent={
                      dubStep === 'uploading' ? (
                        <PrepOverlay stage={dubPrepStage} onAbort={handleDubAbort} />
                      ) : dubStep === 'transcribing' ? (
                        <TranscribeOverlay
                          elapsed={transcribeElapsed}
                          duration={dubDuration}
                          onAbort={handleDubAbort}
                        />
                      ) : null
                    }
                  />
                  <div style={{ display: 'flex', gap: 8, marginTop: 8, alignItems: 'center' }}>
                    <label htmlFor="video-upload" style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '6px 12px', background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 6, cursor: 'pointer', fontSize: '0.8rem', color: '#a89984' }}>
                      <Film size={13} /> Change file
                    </label>
                    <button className="btn-primary" style={{ flex: 1, marginTop: 0 }}
                      onClick={handleDubUpload}
                      disabled={dubStep === 'uploading' || dubStep === 'transcribing'}>
                      {dubStep === 'uploading' || dubStep === 'transcribing'
                        ? <><Loader className="spinner" size={14} /> Processing…</>
                        : <><Sparkles size={14} /> Upload &amp; Transcribe</>}
                    </button>
                  </div>
                </>
              ) : dubStep === 'uploading' ? (
                <PrepOverlay stage={dubPrepStage} onAbort={handleDubAbort} large />
              ) : (
                <label htmlFor="video-upload" style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 14, cursor: 'pointer', border: '2px dashed rgba(255,255,255,0.06)', borderRadius: 8, transition: 'all 0.3s', margin: 4 }}
                  onDragOver={e => { e.preventDefault(); e.currentTarget.style.borderColor = '#d3869b'; e.currentTarget.style.background = 'rgba(211,134,155,0.05)'; }}
                  onDragLeave={e => { e.currentTarget.style.borderColor = 'rgba(255,255,255,0.06)'; e.currentTarget.style.background = 'transparent'; }}
                  onDrop={e => {
                    e.preventDefault();
                    e.currentTarget.style.borderColor = 'rgba(255,255,255,0.06)';
                    e.currentTarget.style.background = 'transparent';
                    const file = e.dataTransfer.files[0];
                    if (file && file.type.startsWith('video/')) {
                      setDubVideoFile(file);
                      setDubStep('idle');
                      fileToMediaUrl(file, null).then(urls => setDubLocalBlobUrl(urls));
                    }
                  }}>
                  <div style={{ width: 60, height: 60, borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'rgba(211,134,155,0.06)', border: '1px solid rgba(211,134,155,0.1)' }}>
                    <UploadCloud color="#d3869b" size={28} />
                  </div>
                  <div style={{ textAlign: 'center' }}>
                    <div style={{ fontSize: '0.9rem', color: '#ebdbb2', fontWeight: 500, marginBottom: 4 }}>Drop video here</div>
                    <div style={{ fontSize: '0.7rem', color: '#665c54' }}>MP4 · MOV · MKV · WEBM</div>
                  </div>
                  <div
                    style={{ display: 'flex', gap: 6, alignItems: 'center', padding: '6px 10px', marginTop: 10, background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.06)', borderRadius: 6, width: 'min(420px, 80%)' }}
                    onClick={e => e.preventDefault()}
                  >
                    <Link2 size={13} color="#a89984" />
                    <input
                      type="text"
                      placeholder="…or paste YouTube / video URL"
                      value={ingestUrl}
                      onChange={e => setIngestUrl(e.target.value)}
                      onClick={e => { e.preventDefault(); e.stopPropagation(); }}
                      onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); e.stopPropagation(); onIngestUrl(); } }}
                      style={{ flex: 1, background: 'transparent', border: 'none', outline: 'none', color: '#ebdbb2', fontSize: '0.75rem' }}
                    />
                    <button
                      type="button"
                      onClick={e => { e.preventDefault(); e.stopPropagation(); onIngestUrl(); }}
                      disabled={!ingestUrl.trim()}
                      style={{ padding: '3px 10px', background: ingestUrl.trim() ? 'rgba(211,134,155,0.15)' : 'rgba(255,255,255,0.03)', border: `1px solid ${ingestUrl.trim() ? 'rgba(211,134,155,0.3)' : 'rgba(255,255,255,0.06)'}`, color: ingestUrl.trim() ? '#d3869b' : '#665c54', borderRadius: 4, fontSize: '0.7rem', cursor: ingestUrl.trim() ? 'pointer' : 'default' }}
                    >
                      Ingest
                    </button>
                  </div>
                </label>
              )}

              <input type="file" accept="video/*" id="video-upload" style={{ display: 'none' }}
                onChange={e => {
                  const file = e.target.files[0];
                  if (!file) return;
                  setDubVideoFile(file);
                  setDubStep('idle');
                  setDubLocalBlobUrl(prev => { fileToMediaUrl(file, prev).then(urls => setDubLocalBlobUrl(urls)); return prev; });
                }} />

              <div style={{ marginTop: 4, padding: '3px 6px', background: 'rgba(255,255,255,0.015)', borderRadius: 4, border: '1px solid rgba(255,255,255,0.03)' }}>
                <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                  <span style={{ fontSize: '0.62rem', color: '#504945', fontWeight: 600 }}>CAST</span>
                  <span style={{ fontSize: '0.62rem', color: '#504945' }}>Speaker 1:</span>
                  <span style={{ fontSize: '0.62rem', color: '#504945', padding: '1px 4px', background: 'rgba(255,255,255,0.02)', borderRadius: 2 }}>Default</span>
                </div>
              </div>
            </div>

            {/* RIGHT: Ghost settings + segment table (only when video loaded) */}
            {dubVideoFile ? (
            <div className="studio-panel" style={{ marginBottom: 0, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
              <div style={{ display: 'flex', gap: 4, marginBottom: 4, flexWrap: 'wrap', alignItems: 'flex-end', opacity: 0.4 }}>
                <div style={{ flex: 1, minWidth: 90 }}>
                  <div className="label-row"><Globe className="label-icon" size={9} /> Language</div>
                  <select className="input-base" disabled style={{ fontSize: '0.65rem' }}>
                    <option>Auto</option>
                  </select>
                </div>
                <div style={{ flex: 1, minWidth: 80 }}>
                  <div className="label-row">ISO Code</div>
                  <select className="input-base" disabled style={{ fontSize: '0.65rem' }}>
                    <option>en — English</option>
                  </select>
                </div>
                <div style={{ flex: 1, minWidth: 90 }}>
                  <div className="label-row"><UserSquare2 className="label-icon" size={9} /> Style</div>
                  <input className="input-base" disabled placeholder="e.g. female" style={{ fontSize: '0.65rem' }} />
                </div>
                <button disabled style={{ padding: '3px 8px', background: 'rgba(131,165,152,0.08)', border: '1px solid rgba(131,165,152,0.12)', color: '#504945', borderRadius: 4, fontSize: '0.62rem', display: 'flex', alignItems: 'center', gap: 3, whiteSpace: 'nowrap' }}>
                  <Languages size={10} /> Translate All
                </button>
              </div>
              <div style={{ marginBottom: 4 }}>
                <div className="override-toggle" style={{ marginTop: 0, padding: '2px 6px', fontSize: '0.65rem', opacity: 0.3, cursor: 'default' }}>
                  <span><FileText size={10} style={{ verticalAlign: 'middle', marginRight: 3 }} /> Transcript</span>
                  <ChevronDown size={10} />
                </div>
              </div>
              <div className="segment-table" style={{ flex: 1, maxHeight: 'none', overflowY: 'auto', minHeight: 0 }}>
                <div className="segment-header">
                  <span style={{ width: 55 }}>Time</span>
                  <span style={{ width: 50 }}>Spkr</span>
                  <span style={{ flex: 1 }}>Text</span>
                  <span style={{ width: 90 }}>Voice</span>
                  <span style={{ width: 40 }}></span>
                </div>
                {[1, 2, 3, 4, 5, 6, 7, 8].map(i => (
                  <div key={i} className="segment-row" style={{ opacity: 0.15 + (0.04 * (8 - i)) }}>
                    <span className="segment-time" style={{ width: 55 }}>0:00.0–0:00.0</span>
                    <span style={{ width: 50, fontSize: '0.58rem', color: '#504945' }}>Speaker 1</span>
                    <div style={{ flex: 1, height: 18, background: 'rgba(255,255,255,0.03)', borderRadius: 3 }} />
                    <span style={{ width: 90, fontSize: '0.6rem', color: '#504945' }}>Default</span>
                    <div style={{ display: 'flex', gap: 1, width: 40 }}>
                      <span className="segment-del" style={{ opacity: 0.3 }}><Trash2 size={9} /></span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
            ) : null}
          </div>

          {/* Ghost footer */}
          <div className="studio-panel" style={{ padding: '4px 8px', flexShrink: 0 }}>
            <div style={{ display: 'flex', gap: 4 }}>
              <button className="btn-primary" disabled style={{ marginTop: 0, flex: 1, padding: '4px 8px', fontSize: '0.7rem', opacity: 0.4 }}>
                <Play size={11} /> Generate Dub
              </button>
              <button className="btn-primary" disabled style={{ marginTop: 0, flex: 1, padding: '4px 8px', fontSize: '0.7rem', opacity: 0.4 }}>
                <Download size={11} /> MP4
              </button>
              <button className="btn-primary" disabled style={{ marginTop: 0, flex: 1, padding: '4px 8px', fontSize: '0.7rem', opacity: 0.4 }}>
                <Volume2 size={11} /> WAV
              </button>
              <button className="btn-primary" disabled style={{ marginTop: 0, flex: 1, padding: '4px 8px', fontSize: '0.7rem', opacity: 0.4 }}>
                <FileText size={11} /> SRT
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── After transcription: side-by-side editor ── */}
      {dubJobId && (dubStep === 'editing' || dubStep === 'generating' || dubStep === 'done') && (
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
          <div className="studio-panel dub-head">
            <div className="label-row dub-head__title">
              <Button
                variant="icon"
                iconSize="sm"
                active={isSidebarCollapsed}
                onClick={() => setIsSidebarCollapsed(!isSidebarCollapsed)}
                title="Toggle Sidebar"
              >
                {isSidebarCollapsed ? <PanelLeftOpen size={12} /> : <PanelLeftClose size={12} />}
              </Button>
              <FileText className="label-icon" size={11} />
              <span className="dub-head__filename">{dubFilename}</span>
              <span className="dub-head__meta">· {formatTime(dubDuration)} · {dubSegments.length} segs</span>
              {activeProjectName && <span className="dub-head__project">— {activeProjectName}</span>}
            </div>
            <div className="dub-head__actions">
              <Button variant="subtle" size="sm" onClick={saveProject} leading={<Save size={9} />}>Save</Button>
              <Button variant="danger" size="sm" onClick={resetDub}>Reset</Button>
            </div>
          </div>

          <div className="dub-split-grid" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6, flex: 1, minHeight: 0 }}>
            {/* LEFT: Waveform + Video */}
            <div className="studio-panel" style={{ marginBottom: 0, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
              {hasDubbedTrack && (
                <div className="dub-preview-toggle">
                  <span className="dub-preview-toggle__kicker">Preview</span>
                  <Segmented
                    size="sm"
                    value={previewMode}
                    onChange={setPreviewMode}
                    items={[
                      { value: 'original', label: 'Original' },
                      { value: 'dubbed',   label: `Dubbed (${dubLangCode})` },
                    ]}
                  />
                  {previewMode === 'dubbed' && (
                    <span className="dub-preview-toggle__hint">first play may take a moment to mux</span>
                  )}
                </div>
              )}
              <WaveformTimeline
                key={videoSrc}
                audioSrc={`${API}/dub/audio/${dubJobId}`}
                videoSrc={videoSrc}
                segments={dubSegments}
                onSegmentsChange={setDubSegments}
                disabled={dubStep === 'generating' || dubStep === 'stopping'}
                overlayContent={(dubStep === 'generating' || dubStep === 'stopping') ? (
                  <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6, width: '100%' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                      {dubStep === 'stopping' ? <Loader className="spinner" size={14} color="#a89984" /> : <Sparkles className="spinner" size={14} color="#d3869b" />}
                      <span style={{ color: dubStep === 'stopping' ? '#a89984' : '#ebdbb2', fontWeight: 500, fontSize: '0.72rem' }}>
                        {dubStep === 'stopping' ? 'Stopping…' : `Dubbing ${dubProgress.current}/${dubProgress.total}…`}
                      </span>
                    </div>
                    {dubStep === 'generating' && (
                      <>
                        <div style={{ width: '80%', maxWidth: 240 }}>
                          <Progress
                            value={dubProgress.total ? (dubProgress.current / dubProgress.total) * 100 : 0}
                            tone="brand"
                            size="sm"
                          />
                        </div>
                        {dubProgress.text && <span style={{ fontSize: '0.65rem', color: '#a89984' }}>{dubProgress.text}</span>}
                      </>
                    )}
                  </div>
                ) : null}
              />

              {/* Cast Diarization */}
              {dubSegments.some(s => s.speaker_id) && (
                <div style={{ marginTop: 4, padding: '3px 6px', background: 'rgba(255,255,255,0.02)', borderRadius: 4, border: '1px solid rgba(255,255,255,0.04)' }}>
                  <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                    <span style={{ fontSize: '0.62rem', color: '#a89984', fontWeight: 600 }} title="Assign a voice profile to each speaker detected in the video">SPEAKER VOICES</span>
                    {[...new Set(dubSegments.map(s => s.speaker_id).filter(Boolean))].map(spk => (
                      <div key={spk} style={{ display: 'flex', alignItems: 'center', gap: 3 }}>
                        <span style={{ fontSize: '0.62rem', color: '#ebdbb2' }}>{spk}:</span>
                        <select className="input-base" style={{ width: 100, padding: '1px 4px', fontSize: '0.62rem' }}
                          value={dubSegments.find(s => s.speaker_id === spk)?.profile_id || ''}
                          onChange={e => {
                            const val = e.target.value;
                            setDubSegments(dubSegments.map(s => s.speaker_id === spk ? { ...s, profile_id: val } : s));
                          }}>
                          <option value="">Default</option>
                          {profiles.length > 0 && (
                            <optgroup label="Clone Profiles">
                              {profiles.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
                            </optgroup>
                          )}
                          {PRESETS.length > 0 && (
                            <optgroup label="Design Presets">
                              {PRESETS.map(p => <option key={p.id} value={`preset:${p.id}`}>{p.name}</option>)}
                            </optgroup>
                          )}
                        </select>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* RIGHT: Settings + Segment Table */}
            <div className="studio-panel" style={{ marginBottom: 0, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
              <div className="dub-settings-bar" style={{ display: 'flex', gap: 4, marginBottom: 4, flexWrap: 'wrap', alignItems: 'flex-end' }}>
                <div style={{ flex: 1, minWidth: 90 }}>
                  <div className="label-row"><Globe className="label-icon" size={9} /> Language</div>
                  <SearchableSelect
                    size="sm"
                    value={dubLang}
                    options={ALL_LANGUAGES}
                    popular={POPULAR_LANGS}
                    recentsKey="omnivoice.recents.dubLang"
                    onChange={(lang) => {
                      setDubLang(lang);
                      const match = LANG_CODES.find(lc => lc.label.toLowerCase() === lang.toLowerCase());
                      if (match) setDubLangCode(match.code);
                    }}
                  />
                </div>
                <div style={{ flex: 1, minWidth: 80 }}>
                  <div className="label-row">ISO Code</div>
                  <SearchableSelect
                    size="sm"
                    value={dubLangCode}
                    options={LANG_CODES.map(lc => ({ value: lc.code, label: `${lc.code} — ${lc.label}` }))}
                    popular={POPULAR_ISO}
                    recentsKey="omnivoice.recents.dubIso"
                    onChange={setDubLangCode}
                  />
                </div>
                <div style={{ flex: 1, minWidth: 90 }}>
                  <div className="label-row"><UserSquare2 className="label-icon" size={9} /> Style</div>
                  <input className="input-base" placeholder="e.g. female" value={dubInstruct} onChange={e => setDubInstruct(e.target.value)} style={{ fontSize: '0.65rem' }} />
                </div>
                <div style={{ flex: 1, minWidth: 90 }}>
                  <div className="label-row">Engine</div>
                  <select className="input-base" value={translateProvider} onChange={e => setTranslateProvider(e.target.value)} style={{ fontSize: '0.65rem', padding: '5px 8px' }}>
                    {[{ id: 'argos', name: 'Argos (Fast Local)' }, { id: 'nllb', name: 'NLLB (Heavy Local)' }, { id: 'google', name: 'Google (Online)' }, { id: 'openai', name: 'OpenAI (LLM)' }].map(p => (
                      <option key={p.id} value={p.id}>{p.name}</option>
                    ))}
                  </select>
                </div>
                <Button
                  variant="subtle" size="sm"
                  onClick={handleTranslateAll}
                  disabled={isTranslating || !dubSegments.length}
                  loading={isTranslating}
                  leading={!isTranslating && <Languages size={10} />}
                >
                  {isTranslating ? 'Translating…' : 'Translate All'}
                </Button>
                <Button
                  variant="subtle" size="sm"
                  onClick={() => editSegments(dubSegments.map(s => ({ ...s, text: s.text_original || s.text, translate_error: undefined })))}
                  disabled={!dubSegments.some(s => s.text_original && s.text_original !== s.text)}
                  title="Restore all segments to the original transcribed text"
                >
                  ↺ Restore
                </Button>
                <Button
                  variant="subtle" size="sm"
                  onClick={handleCleanupSegments}
                  disabled={!dubSegments.length || !dubJobId}
                  title="Merge tiny fragments and adjacent short segments"
                  leading={<Wand2 size={10} />}
                >
                  Clean Up
                </Button>
              </div>

              {dubTranscript && (
                <div style={{ marginBottom: 4 }}>
                  <div className="override-toggle" onClick={() => setShowTranscript(!showTranscript)} style={{ marginTop: 0, padding: '2px 6px', fontSize: '0.65rem' }}>
                    <span><FileText size={10} style={{ verticalAlign: 'middle', marginRight: 3 }} /> Transcript</span>
                    {showTranscript ? <ChevronUp size={10} /> : <ChevronDown size={10} />}
                  </div>
                  {showTranscript && (
                    <div style={{ background: 'rgba(0,0,0,0.15)', border: '1px solid rgba(255,255,255,0.04)', borderTop: 'none', borderRadius: '0 0 4px 4px', padding: 6, fontSize: '0.65rem', color: 'var(--text-secondary)', lineHeight: 1.5, maxHeight: 80, overflowY: 'auto' }}>
                      {dubTranscript}
                    </div>
                  )}
                </div>
              )}

              {dubSegments.length > 0 && profiles.length > 0 && (
                <div className="dub-bulk-row dub-bulk-row--apply">
                  <User size={10} color="#8ec07c" />
                  <span className="dub-bulk-row__label-success">Apply Voice to All:</span>
                  <select className="input-base" style={{ flex: 1, fontSize: '0.62rem', padding: '2px 4px' }}
                    value=""
                    onChange={e => {
                      const val = e.target.value;
                      if (val === '__reset__') {
                        setDubSegments(dubSegments.map(s => ({ ...s, profile_id: '' })));
                      } else if (val) {
                        setDubSegments(dubSegments.map(s => ({ ...s, profile_id: val })));
                      }
                    }}>
                    <option value="">— Select profile —</option>
                    <option value="__reset__">⊘ Default (reset all)</option>
                    {profiles.filter(p => !p.instruct).length > 0 && (
                      <optgroup label="Clone Profiles">
                        {profiles.filter(p => !p.instruct).map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
                      </optgroup>
                    )}
                    {profiles.filter(p => !!p.instruct).length > 0 && (
                      <optgroup label="Designed Voices">
                        {profiles.filter(p => !!p.instruct).map(p => <option key={p.id} value={p.id}>{p.name}{p.is_locked ? ' 🔒' : ''}</option>)}
                      </optgroup>
                    )}
                  </select>
                </div>
              )}

              {selectedSegIds.size > 0 && (
                <div className="dub-bulk-row dub-bulk-row--select">
                  <span className="dub-bulk-row__label-brand">{selectedSegIds.size} selected</span>
                  <select className="input-base" style={{ fontSize: '0.62rem', padding: '2px 4px', minWidth: 100 }}
                    value="" onChange={(e) => { const v = e.target.value; if (v === '__clear__') bulkApplyToSelected({ profile_id: '' }); else if (v) bulkApplyToSelected({ profile_id: v }); }}>
                    <option value="">Set voice…</option>
                    <option value="__clear__">⊘ Default</option>
                    {profiles.filter(p => !p.instruct).length > 0 && (
                      <optgroup label="Clone">
                        {profiles.filter(p => !p.instruct).map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
                      </optgroup>
                    )}
                    {profiles.filter(p => !!p.instruct).length > 0 && (
                      <optgroup label="Designed">
                        {profiles.filter(p => !!p.instruct).map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
                      </optgroup>
                    )}
                  </select>
                  <select className="input-base" style={{ fontSize: '0.62rem', padding: '2px 4px', width: 90 }}
                    value="" onChange={(e) => { if (e.target.value === '__def__') bulkApplyToSelected({ target_lang: null }); else if (e.target.value) bulkApplyToSelected({ target_lang: e.target.value }); }}>
                    <option value="">Set lang…</option>
                    <option value="__def__">(Default)</option>
                    {LANG_CODES.map(lc => <option key={lc.code} value={lc.code}>{lc.code.toUpperCase()}</option>)}
                  </select>
                  <Button variant="danger" size="sm" onClick={bulkDeleteSelected}>Delete</Button>
                  <Button variant="ghost"  size="sm" onClick={clearSegSelection} style={{ marginLeft: 'auto' }}>Clear</Button>
                </div>
              )}

              <Suspense fallback={<LazyFallback />}>
                <DubSegmentTable
                  segments={dubSegments}
                  profiles={profiles}
                  dubStep={dubStep}
                  dubProgress={dubProgress}
                  previewLoadingId={segmentPreviewLoading}
                  selectedIds={selectedSegIds}
                  onSelect={toggleSegSelect}
                  onSelectAll={selectAllSegs}
                  onClearSelection={clearSegSelection}
                  onEditField={segmentEditField}
                  onDelete={segmentDelete}
                  onRestore={segmentRestoreOriginal}
                  onPreview={handleSegmentPreview}
                  onSplit={segmentSplit}
                  onMerge={segmentMerge}
                />
              </Suspense>
            </div>
          </div>

          {/* Actions footer */}
          <div className="studio-panel" style={{ padding: '4px 8px', flexShrink: 0 }}>
            {dubStep === 'done' && (
              <div className="dub-footer-banner">
                <Badge tone="success">
                  <Check size={11} /> Done! Tracks: {dubTracks.join(', ')}
                </Badge>
              </div>
            )}
            {dubError && (
              <div className="dub-footer-banner">
                <Badge tone="danger">
                  <AlertCircle size={11} /> {dubError}
                </Badge>
              </div>
            )}
            <div className="dub-outputs-row">
              <span style={{ fontWeight: 600, color: 'var(--color-fg)' }}>Output Options:</span>
              <label>
                <input type="checkbox" checked={preserveBg} onChange={e => setPreserveBg(e.target.checked)} /> Mix BG Audio
              </label>
              <label>
                Default Track:
                <select className="input-base" value={defaultTrack} onChange={e => setDefaultTrack(e.target.value)} style={{ fontSize: '0.6rem', padding: '2px 4px', width: '120px' }}>
                  <option value="original">Original</option>
                  {dubLangCode && <option value={dubLangCode}>{dubLangCode} (Selected Dub)</option>}
                  {dubTracks.filter(t => t !== dubLangCode).map(t => (
                    <option key={t} value={t}>{t} (Dub)</option>
                  ))}
                </select>
              </label>
            </div>
            {dubTracks.length > 0 && (
              <div className="dub-tracks-row">
                <span className="dub-tracks-row__title">Export Tracks:</span>
                <label className={exportTracks['original'] ? 'is-on' : 'is-off'}>
                  <input type="checkbox" checked={exportTracks['original'] !== false} onChange={e => setExportTracks(prev => ({ ...prev, original: e.target.checked }))} />
                  <span>Original</span>
                </label>
                {dubTracks.map(t => (
                  <label key={t} className={exportTracks[t] !== false ? 'is-on is-success' : 'is-off'}>
                    <input type="checkbox" checked={exportTracks[t] !== false} onChange={e => setExportTracks(prev => ({ ...prev, [t]: e.target.checked }))} />
                    <span className="code">{t}</span>
                  </label>
                ))}
              </div>
            )}
            <div className="dub-footer-btns" style={{ display: 'flex', gap: 4 }}>
              {dubStep === 'stopping' ? (
                <FooterBtn tone="stopping" disabled icon={<Loader className="spinner" size={9} />} label="Stopping…" />
              ) : dubStep === 'generating' ? (
                <FooterBtn tone="danger" onClick={handleDubStop} icon={<Square size={9} />}
                  label={`Stop (${dubProgress.current}/${dubProgress.total})`} />
              ) : (
                <FooterBtn tone={dubSegments.length ? 'idle' : 'idle'} onClick={handleDubGenerate}
                  disabled={!dubSegments.length} icon={<Play size={11} />} label="Generate Dub" />
              )}
              <FooterBtn tone={dubStep === 'done' ? 'green' : 'idle'} disabled={dubStep !== 'done'}
                onClick={handleDubDownload} icon={<Download size={11} />} label="MP4" />
              <FooterBtn tone={dubStep === 'done' ? 'blue' : 'idle'} disabled={dubStep !== 'done'}
                onClick={handleDubAudioDownload} icon={<Volume2 size={11} />} label="WAV" />
              <FooterBtn tone={dubSegments.length ? 'pink' : 'idle'} disabled={!dubSegments.length}
                onClick={() => triggerDownload(`${API}/dub/srt/${dubJobId}/subtitles.srt`, 'subtitles.srt')}
                icon={<FileText size={11} />} label="SRT" />
            </div>
            <div className="dub-footer-btns" style={{ display: 'flex', gap: 4, marginTop: 4 }}>
              <FooterBtn sm tone={dubSegments.length ? 'lime' : 'idle'} disabled={!dubSegments.length}
                onClick={() => triggerDownload(`${API}/dub/vtt/${dubJobId}/subtitles.vtt`, 'subtitles.vtt')}
                icon={<FileText size={10} />} label="VTT" />
              <FooterBtn sm tone={dubStep === 'done' ? 'amber' : 'idle'} disabled={dubStep !== 'done'}
                onClick={() => triggerDownload(`${API}/dub/download-mp3/${dubJobId}/audio.mp3?preserve_bg=${preserveBg}`, 'dubbed_audio.mp3')}
                icon={<Music size={10} />} label="MP3" />
              <FooterBtn sm tone={dubStep === 'done' ? 'orange' : 'idle'} disabled={dubStep !== 'done'}
                onClick={() => triggerDownload(`${API}/dub/export-segments/${dubJobId}`, 'segments.zip')}
                icon={<Package size={10} />} label="Clips" />
              <FooterBtn sm tone={dubStep === 'done' ? 'pink' : 'idle'} disabled={dubStep !== 'done'}
                onClick={() => triggerDownload(`${API}/dub/export-stems/${dubJobId}`, 'stems.zip')}
                icon={<Layers size={10} />} label="Stems" />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

const PREP_STAGE_LABEL = {
  download: 'Downloading video…',
  extract:  'Extracting audio…',
  demucs:   'Separating vocals / music (Demucs)…',
  scene:    'Detecting scene cuts…',
  cached:   '⚡ Using cached results…',
};
const PREP_FULL   = ['download', 'extract', 'demucs', 'scene'];
const PREP_CACHED = ['download', 'extract', 'cached'];

/**
 * PrepOverlay — the prepare-upload stage indicator.
 * `large` makes the surrounding frame bigger (used for the empty-state drop zone).
 */
function PrepOverlay({ stage, onAbort, large = false }) {
  const stages = stage === 'cached' ? PREP_CACHED : PREP_FULL;
  const body = (
    <>
      <Loader className="spinner" size={large ? 28 : 20} color="#d3869b" />
      <span className="dub-prep-overlay__title" style={{ fontSize: large ? '0.95rem' : '0.85rem' }}>
        {PREP_STAGE_LABEL[stage] || 'Preparing…'}
      </span>
      <div className={`dub-prep-chips ${large ? 'dub-prep-chips--lg' : ''}`}>
        {stages.map(s => (
          <span
            key={s}
            className={`dub-prep-chip ${stage === s ? 'is-active' : ''} ${s === 'cached' ? 'is-cached' : ''}`}
          >
            {s === 'cached' ? '⚡ cached' : s}
          </span>
        ))}
      </div>
      {stage === 'demucs' && (
        <span className="dub-prep-overlay__note">
          Demucs can take several minutes on long videos. Long audio = longer wait.
        </span>
      )}
      <Button variant="danger" size="sm" onClick={onAbort} leading={<Square size={11} />}>
        Stop
      </Button>
    </>
  );
  return large
    ? <div className="dub-prep-overlay dub-prep-overlay--large">{body}</div>
    : <div className="dub-prep-overlay">{body}</div>;
}

/**
 * TranscribeOverlay — Whisper progress + ETA while transcribing.
 */
function TranscribeOverlay({ elapsed, duration, onAbort }) {
  const est = duration > 0 ? Math.max(10, Math.ceil(duration / 60) * 3 + 8) : 0;
  const mm = Math.floor(elapsed / 60);
  const ss = String(elapsed % 60).padStart(2, '0');
  return (
    <div className="dub-trans-overlay">
      <div className="dub-trans-overlay__head">
        <Loader className="spinner" size={18} color="#d3869b" />
        <span className="dub-trans-overlay__title">Transcribing with Whisper…</span>
      </div>
      <div className="dub-trans-overlay__stats">
        <span>⏱ {mm}:{ss} elapsed</span>
        {est > 0 && <span>~{Math.max(0, est - elapsed)}s remaining</span>}
      </div>
      {duration > 0 && (
        <div className="dub-trans-overlay__bar">
          <Progress value={Math.min(95, (elapsed / est) * 100)} tone="brand" size="sm" />
        </div>
      )}
      <Button variant="danger" size="sm" onClick={onAbort} leading={<Square size={11} />}>
        Stop
      </Button>
    </div>
  );
}

/**
 * FooterBtn — the gradient-per-tone download button family in the action footer.
 * Uses the legacy .btn-primary as the shape/hover base, just picks a tone class.
 */
function FooterBtn({ tone = 'idle', sm = false, disabled, onClick, icon, label }) {
  const cls = [
    'btn-primary',
    'dub-footer-btn',
    sm && 'dub-footer-btn--sm',
    `dub-footer-btn--${tone}`,
  ].filter(Boolean).join(' ');
  return (
    <button className={cls} disabled={disabled} onClick={onClick}>
      {icon} {label}
    </button>
  );
}
