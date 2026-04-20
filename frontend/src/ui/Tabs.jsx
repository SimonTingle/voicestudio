import React from 'react';
import './Tabs.css';

/**
 * Tabs — pill-style segmented tab group.
 *
 * @param items     array of { id, label, icon?, accent? }
 * @param value     currently selected id
 * @param onChange  (id) => void
 * @param size      'sm' | 'md'
 * @param variant   'pill' (default) | 'underline'
 */
export default function Tabs({
  items = [],
  value,
  onChange,
  size = 'md',
  variant = 'pill',
  className = '',
  ...rest
}) {
  return (
    <div
      role="tablist"
      className={`ui-tabs ui-tabs--${variant} ui-tabs--size-${size} ${className}`}
      {...rest}
    >
      {items.map((item) => {
        const active = value === item.id;
        const Icon = item.icon;
        return (
          <button
            key={item.id}
            role="tab"
            aria-selected={active}
            tabIndex={active ? 0 : -1}
            className={`ui-tabs__tab ${active ? 'is-active' : ''}`}
            onClick={() => onChange?.(item.id)}
            style={active && item.accent ? { '--ui-tab-accent': item.accent } : undefined}
          >
            {Icon && <Icon size={12} className="ui-tabs__icon" />}
            <span>{item.label}</span>
          </button>
        );
      })}
    </div>
  );
}
