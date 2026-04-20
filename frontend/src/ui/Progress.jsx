import React from 'react';
import './Progress.css';

/**
 * Progress — determinate or indeterminate progress bar.
 *
 * @param value       0–100 when determinate. Omit for indeterminate.
 * @param tone        'brand' (default) | 'success' | 'warn' | 'danger'
 * @param size        'xs' | 'sm' | 'md'
 * @param shimmer     add moving highlight overlay (default true when determinate)
 */
export default function Progress({
  value,
  tone = 'brand',
  size = 'sm',
  shimmer,
  className = '',
  ...rest
}) {
  const indeterminate = value == null;
  const showShimmer = shimmer ?? !indeterminate;
  const clamped = indeterminate ? 100 : Math.max(0, Math.min(100, value));

  return (
    <div
      role="progressbar"
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={indeterminate ? undefined : clamped}
      className={`ui-progress ui-progress--${tone} ui-progress--size-${size} ${indeterminate ? 'is-indeterminate' : ''} ${className}`}
      {...rest}
    >
      <div
        className={`ui-progress__fill ${showShimmer ? 'has-shimmer' : ''}`}
        style={indeterminate ? undefined : { width: `${clamped}%` }}
      />
    </div>
  );
}
