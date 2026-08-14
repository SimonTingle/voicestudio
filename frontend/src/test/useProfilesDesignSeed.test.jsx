import { describe, it, expect, vi, beforeEach } from 'vitest';
import { act, renderHook } from '@testing-library/react';
import useProfiles from '../hooks/useProfiles';
import { useAppStore } from '../store';

describe('useProfiles designed-voice selection', () => {
  beforeEach(() => {
    useAppStore.setState({
      defineMethod: 'audio',
      designSeed: null,
      keepSeed: false,
      refText: '',
      instruct: '',
    });
  });

  it('pins a gallery design profile to its stored identity seed', () => {
    const { result } = renderHook(() =>
      useProfiles({ loadHistory: vi.fn(), loadProfiles: vi.fn() }),
    );

    act(() => {
      result.current.handleSelectProfile({
        id: 'whisper-gallery',
        kind: 'design',
        seed: 42,
        ref_text: 'A gallery sample',
        instruct: 'female, whisper',
        language: 'English',
      });
    });

    expect(useAppStore.getState()).toMatchObject({
      defineMethod: 'design',
      designSeed: 42,
      keepSeed: true,
    });
  });
});
