import React, { useState, useRef, useId, useEffect } from 'react';
import './Tooltip.css';

/**
 * Tooltip — keyboard-accessible replacement for `title=`.
 *
 * Shows on hover and on keyboard focus. Dismisses on Escape.
 * Wraps exactly one child; forwards aria-describedby to it.
 *
 * @param content  tooltip body (string or node)
 * @param placement 'top' | 'bottom' | 'left' | 'right'
 * @param delay    ms before showing (default 300)
 */
export default function Tooltip({
  content,
  placement = 'top',
  delay = 300,
  children,
}) {
  const [open, setOpen] = useState(false);
  const timer = useRef(null);
  const id = useId();

  const show = () => {
    clearTimeout(timer.current);
    timer.current = setTimeout(() => setOpen(true), delay);
  };
  const hide = () => {
    clearTimeout(timer.current);
    setOpen(false);
  };

  useEffect(() => {
    if (!open) return;
    const onKey = (e) => { if (e.key === 'Escape') hide(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open]);

  useEffect(() => () => clearTimeout(timer.current), []);

  if (!content) return children;
  if (!React.isValidElement(children)) return children;

  const trigger = React.cloneElement(children, {
    'aria-describedby': open ? id : children.props['aria-describedby'],
    onMouseEnter: (...args) => { show(); children.props.onMouseEnter?.(...args); },
    onMouseLeave: (...args) => { hide(); children.props.onMouseLeave?.(...args); },
    onFocus:      (...args) => { show(); children.props.onFocus?.(...args); },
    onBlur:       (...args) => { hide(); children.props.onBlur?.(...args); },
  });

  return (
    <span className="ui-tooltip-wrap">
      {trigger}
      {open && (
        <span
          id={id}
          role="tooltip"
          className={`ui-tooltip ui-tooltip--${placement}`}
        >
          {content}
        </span>
      )}
    </span>
  );
}
