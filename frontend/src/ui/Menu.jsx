import React, {
  useState, useRef, useId, useEffect, useCallback, cloneElement, isValidElement,
} from 'react';
import { createPortal } from 'react-dom';
import { ChevronRight } from 'lucide-react';
import './Menu.css';

/**
 * Menu — floating action menu triggered by a child element.
 *
 *   <Menu
 *     placement="bottom-start"
 *     items={[
 *       { id: 'rename',   label: 'Rename',     icon: Pencil,  onSelect: () => …, shortcut: '⌘R' },
 *       { id: 'dup',      label: 'Duplicate',  onSelect: () => … },
 *       'separator',
 *       { id: 'delete',   label: 'Delete',     icon: Trash2,  destructive: true, onSelect: () => … },
 *     ]}
 *   >
 *     <Button variant="icon">…</Button>
 *   </Menu>
 *
 * - Wraps exactly one child — the trigger. Click opens, click-outside closes.
 * - Keyboard: Space/Enter opens on focused trigger; ↑↓ navigate; Enter/Space select;
 *   ESC closes (returns focus to trigger); Tab closes.
 * - `aria-haspopup`, `aria-expanded`, `role=menu`, `role=menuitem` all wired.
 * - Rendered into a Portal at document.body so panels don't clip it.
 *
 * Items: array of either
 *   - 'separator'  (or { type: 'separator' })
 *   - { id, label, icon?, shortcut?, disabled?, destructive?, onSelect }
 *
 * Placement: 'bottom-start' | 'bottom-end' | 'top-start' | 'top-end'.
 */
export default function Menu({
  children,
  items = [],
  placement = 'bottom-start',
  open: controlledOpen,
  onOpenChange,
  width,                   // optional fixed width (px)
  disabled = false,
}) {
  const isControlled = controlledOpen != null;
  const [internalOpen, setInternalOpen] = useState(false);
  const open = isControlled ? controlledOpen : internalOpen;

  const setOpen = useCallback((next) => {
    if (!isControlled) setInternalOpen(next);
    onOpenChange?.(next);
  }, [isControlled, onOpenChange]);

  const triggerRef = useRef(null);
  const panelRef = useRef(null);
  const menuId = useId();
  const [focusIndex, setFocusIndex] = useState(-1);
  const [coords, setCoords] = useState(null);

  const enabledIndices = items
    .map((it, i) => (typeof it === 'string' || it?.type === 'separator' || it?.disabled ? -1 : i))
    .filter((i) => i !== -1);

  // Position the panel relative to the trigger.
  useEffect(() => {
    if (!open) return;
    const trigger = triggerRef.current;
    if (!trigger) return;
    const compute = () => {
      const r = trigger.getBoundingClientRect();
      const below = placement.startsWith('bottom');
      const end = placement.endsWith('end');
      setCoords({
        top:  below ? r.bottom + 4 : r.top - 4,
        left: end   ? r.right      : r.left,
        end,
        below,
      });
    };
    compute();
    window.addEventListener('scroll', compute, true);
    window.addEventListener('resize', compute);
    return () => {
      window.removeEventListener('scroll', compute, true);
      window.removeEventListener('resize', compute);
    };
  }, [open, placement]);

  // Focus first enabled item when opened by keyboard; reset when closed.
  useEffect(() => {
    if (!open) { setFocusIndex(-1); return; }
    // default focus index = first enabled
    setFocusIndex(enabledIndices[0] ?? -1);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  // Click-outside + ESC dismiss.
  useEffect(() => {
    if (!open) return;
    const onMouseDown = (e) => {
      if (
        triggerRef.current && !triggerRef.current.contains(e.target) &&
        panelRef.current && !panelRef.current.contains(e.target)
      ) {
        setOpen(false);
      }
    };
    const onKey = (e) => {
      if (e.key === 'Escape') {
        e.stopPropagation();
        setOpen(false);
        triggerRef.current?.focus?.();
      } else if (e.key === 'Tab') {
        setOpen(false);
      } else if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
        if (!enabledIndices.length) return;
        e.preventDefault();
        const dir = e.key === 'ArrowDown' ? 1 : -1;
        const pos = enabledIndices.indexOf(focusIndex);
        const next = (pos + dir + enabledIndices.length) % enabledIndices.length;
        setFocusIndex(enabledIndices[next]);
      } else if (e.key === 'Home') {
        e.preventDefault(); setFocusIndex(enabledIndices[0] ?? -1);
      } else if (e.key === 'End') {
        e.preventDefault(); setFocusIndex(enabledIndices[enabledIndices.length - 1] ?? -1);
      }
    };
    window.addEventListener('mousedown', onMouseDown);
    window.addEventListener('keydown', onKey);
    return () => {
      window.removeEventListener('mousedown', onMouseDown);
      window.removeEventListener('keydown', onKey);
    };
  }, [open, focusIndex, enabledIndices, setOpen]);

  // Focus the active menu item as focusIndex changes.
  useEffect(() => {
    if (!open || focusIndex < 0) return;
    const el = panelRef.current?.querySelector(`[data-ui-menu-idx="${focusIndex}"]`);
    el?.focus?.();
  }, [focusIndex, open]);

  if (!isValidElement(children)) {
    // Keep the API resilient to a bare string or nothing.
    return children ?? null;
  }

  const trigger = cloneElement(children, {
    ref: (node) => {
      triggerRef.current = node;
      const orig = children.ref;
      if (typeof orig === 'function') orig(node);
      else if (orig && 'current' in orig) orig.current = node;
    },
    'aria-haspopup': 'menu',
    'aria-expanded': open,
    'aria-controls': open ? menuId : undefined,
    onClick: (e) => {
      children.props.onClick?.(e);
      if (e.defaultPrevented || disabled) return;
      setOpen(!open);
    },
    onKeyDown: (e) => {
      children.props.onKeyDown?.(e);
      if (disabled) return;
      if (!open && (e.key === 'Enter' || e.key === ' ' || e.key === 'ArrowDown')) {
        e.preventDefault();
        setOpen(true);
      }
    },
  });

  const handleSelect = (item) => {
    if (item.disabled) return;
    setOpen(false);
    triggerRef.current?.focus?.();
    item.onSelect?.();
  };

  const panel = open && coords ? createPortal(
    <div
      ref={panelRef}
      id={menuId}
      role="menu"
      className={`ui-menu ui-menu--${coords.below ? 'below' : 'above'} ui-menu--${coords.end ? 'end' : 'start'}`}
      style={{
        top:  coords.below ? coords.top : undefined,
        bottom: coords.below ? undefined : window.innerHeight - coords.top,
        left: coords.end   ? undefined : coords.left,
        right: coords.end  ? window.innerWidth - coords.left : undefined,
        width,
      }}
    >
      {items.map((item, i) => {
        if (item === 'separator' || item?.type === 'separator') {
          return <div key={`sep-${i}`} role="separator" className="ui-menu__separator" />;
        }
        const Icon = item.icon;
        return (
          <button
            key={item.id ?? i}
            type="button"
            role="menuitem"
            data-ui-menu-idx={i}
            className={`ui-menu__item ${item.destructive ? 'is-destructive' : ''} ${item.disabled ? 'is-disabled' : ''}`}
            aria-disabled={item.disabled || undefined}
            tabIndex={focusIndex === i ? 0 : -1}
            onMouseEnter={() => setFocusIndex(i)}
            onClick={() => handleSelect(item)}
          >
            {Icon && <Icon size={12} className="ui-menu__icon" />}
            <span className="ui-menu__label">{item.label}</span>
            {item.shortcut && <span className="ui-menu__shortcut">{item.shortcut}</span>}
            {item.trailing}
          </button>
        );
      })}
    </div>,
    document.body,
  ) : null;

  return <>{trigger}{panel}</>;
}
