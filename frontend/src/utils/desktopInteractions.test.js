import { describe, expect, it, vi } from 'vitest';

import { installDesktopInteractionGuards } from './desktopInteractions';

describe('installDesktopInteractionGuards', () => {
  it('leaves the native context menu available for copying and browser commands', () => {
    const dispose = installDesktopInteractionGuards({
      onDrop: vi.fn(),
    });
    const event = new MouseEvent('contextmenu', { bubbles: true, cancelable: true });

    window.dispatchEvent(event);

    expect(event.defaultPrevented).toBe(false);
    dispose();
  });

  it('still blocks browser reload, print, and zoom shortcuts', () => {
    const dispose = installDesktopInteractionGuards({
      onDrop: vi.fn(),
    });

    for (const key of ['r', 'p', '=', '-', '+']) {
      const event = new KeyboardEvent('keydown', { key, ctrlKey: true, cancelable: true });
      window.dispatchEvent(event);
      expect(event.defaultPrevented).toBe(true);
    }
    const inspect = new KeyboardEvent('keydown', { key: 'i', ctrlKey: true, cancelable: true });
    window.dispatchEvent(inspect);
    expect(inspect.defaultPrevented).toBe(false);
    dispose();
  });
});
