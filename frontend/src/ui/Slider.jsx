import React, { forwardRef, useId } from 'react';
import './Slider.css';

/**
 * Slider — styled horizontal range input.
 *
 * @param value       controlled number
 * @param onChange    receives the new number (not the event)
 * @param min, max, step standard HTMLInputRange props
 * @param format      optional (v) => string for the value bubble
 * @param showValue   show the trailing value bubble (default true)
 * @param label       optional small label above the track
 * @param size        'sm' | 'md'
 */
const Slider = forwardRef(function Slider(
  {
    value,
    onChange,
    min = 0,
    max = 100,
    step = 1,
    format = (v) => v,
    showValue = true,
    label = null,
    size = 'md',
    className = '',
    ...rest
  },
  ref,
) {
  const id = useId();
  const pct = ((Number(value) - min) / (max - min)) * 100;

  return (
    <div className={`ui-slider ui-slider--size-${size} ${className}`}>
      {label && <label htmlFor={id} className="ui-slider__label">{label}</label>}
      <div className="ui-slider__row">
        <input
          ref={ref}
          id={id}
          type="range"
          className="ui-slider__input"
          value={value}
          min={min}
          max={max}
          step={step}
          onChange={(e) => onChange?.(Number(e.target.value))}
          style={{ '--ui-slider-pct': `${pct}%` }}
          {...rest}
        />
        {showValue && (
          <span className="ui-slider__value" aria-live="polite">
            {format(value)}
          </span>
        )}
      </div>
    </div>
  );
});

export default Slider;
