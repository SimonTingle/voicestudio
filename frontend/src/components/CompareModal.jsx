import React from 'react';
import { Scale, Fingerprint, Play } from 'lucide-react';
import { toast } from 'react-hot-toast';
import { PRESETS } from '../utils/constants';
import { generateSpeech } from '../api/generate';
import { Dialog, Button, Panel, Field, Textarea, Select } from '../ui';
import './CompareModal.css';

export default function CompareModal({
  open, onClose,
  profiles,
  compareText, setCompareText,
  compareVoiceA, setCompareVoiceA,
  compareVoiceB, setCompareVoiceB,
  compareResultA, setCompareResultA,
  compareResultB, setCompareResultB,
  compareProgress, setCompareProgress,
  isComparing, setIsComparing,
  steps, cfg, speed, denoise, postprocess,
  fileToMediaUrl, loadHistory,
}) {
  const runCompare = async () => {
    setIsComparing(true);
    setCompareResultA(null);
    setCompareResultB(null);

    const generateVoice = async (voiceId) => {
      setCompareProgress('Preparing voice...');
      const formData = new FormData();
      formData.append('text', compareText);
      let fin_prof = voiceId;
      let fin_inst = '';
      if (fin_prof.startsWith('preset:')) {
        const pr = PRESETS.find(p => p.id === fin_prof.replace('preset:', ''));
        if (pr) {
          const parts = Object.values(pr.attrs).filter(v => v !== 'Auto');
          fin_inst = parts.join(', ');
        }
        fin_prof = '';
      } else if (profiles.find(p => p.id === fin_prof)?.instruct) {
        fin_inst = profiles.find(p => p.id === fin_prof).instruct;
      }
      if (fin_prof) formData.append('profile_id', fin_prof);
      if (fin_inst) formData.append('instruct', fin_inst);
      formData.append('num_step', steps);
      formData.append('guidance_scale', cfg);
      formData.append('speed', speed);
      formData.append('denoise', denoise);
      formData.append('postprocess_output', postprocess);
      const res = await generateSpeech(formData);
      const blob = await res.blob();
      const urls = await fileToMediaUrl(blob, null);
      return urls.audioUrl;
    };

    try {
      setCompareProgress('Generating Voice A...');
      const audioA = await generateVoice(compareVoiceA);
      setCompareResultA(audioA);
      setCompareProgress('Generating Voice B...');
      const audioB = await generateVoice(compareVoiceB);
      setCompareResultB(audioB);
      setCompareProgress('');
      toast.success('Comparison complete!');
      loadHistory();
    } catch (err) {
      toast.error('Play failed: ' + err.message);
      setCompareProgress('');
    } finally {
      setIsComparing(false);
    }
  };

  const canCompare = !isComparing && compareVoiceA && compareVoiceB && compareText.trim();

  return (
    <Dialog
      open={open}
      onClose={onClose}
      size="lg"
      title={<><Scale size={14} /> A/B Voice Comparison</>}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>Close</Button>
          <Button
            variant="primary"
            loading={isComparing}
            disabled={!canCompare}
            onClick={runCompare}
            leading={!isComparing && <Play size={12} />}
          >
            {isComparing ? (compareProgress || 'Comparing…') : 'Compare'}
          </Button>
        </>
      }
    >
      <p className="ui-compare__desc">
        Compare two voices side by side to make casting decisions.
      </p>

      <Field label="Test phrase">
        <Textarea
          value={compareText}
          onChange={e => setCompareText(e.target.value)}
          rows={2}
          style={{ resize: 'none' }}
        />
      </Field>

      <div className="ui-compare__grid">
        <CompareSide
          accent="var(--color-brand)"
          label="Voice A"
          profiles={profiles}
          value={compareVoiceA}
          onChange={setCompareVoiceA}
          audio={compareResultA}
        />
        <CompareSide
          accent="var(--color-success)"
          label="Voice B"
          profiles={profiles}
          value={compareVoiceB}
          onChange={setCompareVoiceB}
          audio={compareResultB}
        />
      </div>
    </Dialog>
  );
}

function CompareSide({ accent, label, profiles, value, onChange, audio }) {
  return (
    <Panel variant="flat" padding="sm">
      <h3 className="ui-compare__head" style={{ color: accent }}>
        <Fingerprint size={14} /> {label}
      </h3>
      <Field>
        <Select value={value} onChange={e => onChange(e.target.value)}>
          <option value="">— Select voice —</option>
          {profiles.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
          {PRESETS.map(p => <option key={p.id} value={`preset:${p.id}`}>{p.name} (Preset)</option>)}
        </Select>
      </Field>
      {audio ? (
        <audio src={audio} controls className="ui-compare__audio" />
      ) : (
        <div className="ui-compare__audio-empty">No audio yet</div>
      )}
    </Panel>
  );
}
