import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Calendar, Check, ChevronDown, ChevronLeft, ChevronRight, X } from 'lucide-react';

export interface StudySelectOption<T extends string = string> {
  value: T;
  label: string;
  previewClassName?: string;
}

interface StudySelectProps<T extends string = string> {
  id?: string;
  ariaLabel: string;
  value: T;
  options: StudySelectOption<T>[];
  onChange: (value: T) => void;
  variant?: 'surface' | 'paper';
  preserveEditorFocus?: boolean;
  className?: string;
}

export function StudySelect<T extends string = string>({
  id,
  ariaLabel,
  value,
  options,
  onChange,
  variant = 'surface',
  preserveEditorFocus = false,
  className = '',
}: StudySelectProps<T>) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement | null>(null);

  const selectedOption = useMemo(
    () => options.find((opt) => opt.value === value) || options[0],
    [options, value]
  );

  useEffect(() => {
    if (!open) return;
    const handlePointerDown = (e: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handlePointerDown);
    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('mousedown', handlePointerDown);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [open]);

  return (
    <div
      ref={rootRef}
      className={`study-select-wrap ${variant === 'paper' ? 'is-paper' : 'is-surface'} ${className}`}
    >
      <button
        id={id}
        type="button"
        aria-label={ariaLabel}
        aria-haspopup="listbox"
        aria-expanded={open}
        className={`study-select-trigger ${open ? 'is-open' : ''}`}
        onMouseDown={(e) => {
          if (preserveEditorFocus) e.preventDefault();
        }}
        onClick={() => setOpen((prev) => !prev)}
      >
        <span className={`study-select-label ${selectedOption?.previewClassName || ''}`}>
          {selectedOption?.label || ''}
        </span>
        <ChevronDown className={`study-select-chevron ${open ? 'rotate-180' : ''}`} />
      </button>

      {open && (
        <div
          role="listbox"
          aria-label={ariaLabel}
          className="study-select-menu"
        >
          {options.map((opt) => {
            const isSelected = opt.value === value;
            return (
              <button
                key={opt.value}
                type="button"
                role="option"
                aria-selected={isSelected}
                className={`study-select-option ${isSelected ? 'is-selected' : ''}`}
                onMouseDown={(e) => {
                  if (preserveEditorFocus) e.preventDefault();
                }}
                onClick={() => {
                  onChange(opt.value);
                  setOpen(false);
                }}
              >
                <span className={`study-select-option-text ${opt.previewClassName || ''}`}>
                  {opt.label}
                </span>
                {isSelected && <Check className="w-4 h-4 shrink-0" />}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

interface StudyDatePickerProps {
  id?: string;
  ariaLabel: string;
  value: string;
  placeholder?: string;
  allowClear?: boolean;
  onChange: (isoDate: string) => void;
  className?: string;
}

const WEEKDAYS = ['Su', 'Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa'];

function parseIsoDate(iso: string): Date | null {
  if (!iso) return null;
  const parts = iso.slice(0, 10).split('-').map(Number);
  if (parts.length !== 3 || parts.some(Number.isNaN)) return null;
  return new Date(parts[0], parts[1] - 1, parts[2]);
}

function toIsoDate(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

function formatReadableDate(iso: string): string {
  const dt = parseIsoDate(iso);
  if (!dt) return '';
  return new Intl.DateTimeFormat('en-GB', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  }).format(dt);
}

export const StudyDatePicker: React.FC<StudyDatePickerProps> = ({
  id,
  ariaLabel,
  value,
  placeholder = 'Select date',
  allowClear = false,
  onChange,
  className = '',
}) => {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement | null>(null);

  const initialDate = parseIsoDate(value) || new Date();
  const [viewYear, setViewYear] = useState(initialDate.getFullYear());
  const [viewMonth, setViewMonth] = useState(initialDate.getMonth());

  useEffect(() => {
    const dt = parseIsoDate(value);
    if (dt) {
      setViewYear(dt.getFullYear());
      setViewMonth(dt.getMonth());
    }
  }, [value]);

  useEffect(() => {
    if (!open) return;
    const handlePointerDown = (e: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handlePointerDown);
    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('mousedown', handlePointerDown);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [open]);

  const monthLabel = useMemo(
    () =>
      new Intl.DateTimeFormat('en-US', { month: 'long', year: 'numeric' }).format(
        new Date(viewYear, viewMonth, 1)
      ),
    [viewMonth, viewYear]
  );

  const calendarCells = useMemo(() => {
    const firstDay = new Date(viewYear, viewMonth, 1).getDay();
    const daysInMonth = new Date(viewYear, viewMonth + 1, 0).getDate();
    const cells: Array<{ day: number | null; iso: string | null }> = [];
    for (let i = 0; i < firstDay; i += 1) {
      cells.push({ day: null, iso: null });
    }
    for (let d = 1; d <= daysInMonth; d += 1) {
      cells.push({ day: d, iso: toIsoDate(new Date(viewYear, viewMonth, d)) });
    }
    return cells;
  }, [viewMonth, viewYear]);

  const todayIso = toIsoDate(new Date());

  const stepMonth = (delta: number) => {
    const next = new Date(viewYear, viewMonth + delta, 1);
    setViewYear(next.getFullYear());
    setViewMonth(next.getMonth());
  };

  return (
    <div ref={rootRef} className={`study-date-wrap ${className}`}>
      <div className="study-date-trigger-row">
        <button
          id={id}
          type="button"
          aria-label={ariaLabel}
          aria-expanded={open}
          className={`study-date-trigger ${open ? 'is-open' : ''}`}
          onClick={() => setOpen((prev) => !prev)}
        >
          <Calendar className="w-4 h-4 shrink-0 opacity-75" />
          <span className="truncate">{value ? formatReadableDate(value) : placeholder}</span>
        </button>
        {allowClear && value && (
          <button
            type="button"
            aria-label="Clear date filter"
            title="Clear date"
            className="study-date-clear-btn"
            onClick={() => {
              onChange('');
              setOpen(false);
            }}
          >
            <X className="w-4 h-4" />
          </button>
        )}
      </div>

      {open && (
        <div className="study-date-popover" role="dialog" aria-label={`${ariaLabel} calendar`}>
          <div className="study-date-popover-header">
            <button
              type="button"
              className="study-date-nav-btn"
              aria-label="Previous month"
              onClick={() => stepMonth(-1)}
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            <span className="study-date-month-label">{monthLabel}</span>
            <button
              type="button"
              className="study-date-nav-btn"
              aria-label="Next month"
              onClick={() => stepMonth(1)}
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>

          <div className="study-date-weekdays">
            {WEEKDAYS.map((w) => (
              <span key={w}>{w}</span>
            ))}
          </div>

          <div className="study-date-grid">
            {calendarCells.map((cell, idx) =>
              cell.day === null || !cell.iso ? (
                <span key={`empty-${idx}`} className="study-date-empty" />
              ) : (
                <button
                  key={cell.iso}
                  type="button"
                  className={`study-date-day ${cell.iso === value ? 'is-selected' : ''} ${
                    cell.iso === todayIso ? 'is-today' : ''
                  }`}
                  onClick={() => {
                    onChange(cell.iso!);
                    setOpen(false);
                  }}
                >
                  {cell.day}
                </button>
              )
            )}
          </div>

          <div className="study-date-popover-footer">
            <button
              type="button"
              className="study-date-footer-link"
              onClick={() => {
                onChange(todayIso);
                setOpen(false);
              }}
            >
              Today
            </button>
            {allowClear && (
              <button
                type="button"
                className="study-date-footer-link"
                onClick={() => {
                  onChange('');
                  setOpen(false);
                }}
              >
                Clear
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

