import React, { useEffect, useRef } from 'react';
import { X } from 'lucide-react';
import Button from './Button';
import './Dialog.css';

/**
 * Dialog — accessible modal.
 *
 * - Click-outside closes (unless dismissable={false}).
 * - ESC closes.
 * - Focus is returned to the previously-focused element on close.
 * - `role="dialog" aria-modal="true"` wired up.
 *
 * @param open       controlled visibility
 * @param onClose    called on backdrop click / ESC / close button
 * @param title      string in the header; omit for header-less dialog
 * @param footer     node rendered in the footer region (actions)
 * @param size       'sm' | 'md' | 'lg' | 'xl'
 * @param dismissable whether backdrop click / ESC closes (default true)
 */
export default function Dialog({
  open,
  onClose,
  title = null,
  footer = null,
  size = 'md',
  dismissable = true,
  children,
}) {
  const dialogRef = useRef(null);
  const previouslyFocused = useRef(null);

  useEffect(() => {
    if (!open) return;
    previouslyFocused.current = document.activeElement;
    const firstFocusable = dialogRef.current?.querySelector(
      'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
    );
    firstFocusable?.focus?.();

    const onKey = (e) => {
      if (e.key === 'Escape' && dismissable) {
        e.stopPropagation();
        onClose?.();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => {
      window.removeEventListener('keydown', onKey);
      previouslyFocused.current?.focus?.();
    };
  }, [open, dismissable, onClose]);

  if (!open) return null;

  return (
    <div
      className="ui-dialog-backdrop"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget && dismissable) onClose?.();
      }}
    >
      <div
        ref={dialogRef}
        className={`ui-dialog ui-dialog--${size}`}
        role="dialog"
        aria-modal="true"
        aria-labelledby={title ? 'ui-dialog-title' : undefined}
      >
        {(title || dismissable) && (
          <header className="ui-dialog__header">
            {title && <h2 id="ui-dialog-title" className="ui-dialog__title">{title}</h2>}
            {dismissable && (
              <Button variant="icon" iconSize="sm" onClick={onClose} aria-label="Close">
                <X size={12} />
              </Button>
            )}
          </header>
        )}
        <div className="ui-dialog__body">{children}</div>
        {footer && <footer className="ui-dialog__footer">{footer}</footer>}
      </div>
    </div>
  );
}
