import React from 'react';
import './Segmented.css';

/**
 * Segmented — compact segmented control for small option sets.
 * Good for density pickers (S/M/L), view toggles, mode switches.
 *
 * @param items array of { value, label } — label is short text
 * @param value currently selected `value`
 * @param onChange (value) => void
 * @param size  'xs' | 'sm'
 */
export default function Segmented({
  items = [],
  value,
  onChange,
  size = 'sm',
  className = '',
  ...rest
}) {
  return (
    <div
      role="radiogroup"
      className={`ui-seg ui-seg--size-${size} ${className}`}
      {...rest}
    >
      {items.map((item) => {
        const active = value === item.value;
        return (
          <button
            key={item.value}
            role="radio"
            aria-checked={active}
            className={`ui-seg__opt ${active ? 'is-active' : ''}`}
            onClick={() => onChange?.(item.value)}
            title={item.title || undefined}
          >
            {item.label}
          </button>
        );
      })}
    </div>
  );
}
