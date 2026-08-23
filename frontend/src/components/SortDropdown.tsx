import { useEffect, useId, useRef, useState } from "react";
import { SortIcon } from "../lib/icons";
import {
  LEVELS,
  WATER_CHARACTERS,
  STYLES,
  BOTTOM_TYPES,
  bottomTypeLabel,
  levelLabel,
  waterCharacterLabel,
  styleLabel,
} from "../lib/labels";
import {
  SORT_OPTIONS,
  activeFilterCount,
  emptyFilters,
  type FilterState,
  type SortKey,
} from "../lib/filters";
import { Chip } from "./ui";

/**
 * "Sortieren" button that opens a filter + sort panel. Filters by the three
 * category axes (level / water character / style) and sorts the list. Fully
 * keyboard-accessible: ESC closes and restores focus, click-outside closes,
 * and focus moves into the panel on open.
 */
export default function SortDropdown({
  value,
  onChange,
}: {
  value: FilterState;
  onChange: (next: FilterState) => void;
}) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const panelId = useId();

  const count = activeFilterCount(value);

  // Close on outside click / ESC; restore focus to the trigger on ESC.
  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node))
        setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setOpen(false);
        triggerRef.current?.focus();
      }
    };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  // Move focus into the panel when it opens.
  useEffect(() => {
    if (open) panelRef.current?.querySelector<HTMLElement>("button, [tabindex]")?.focus();
  }, [open]);

  const setLevel = (l: string) =>
    onChange({ ...value, level: value.level === l ? undefined : l });
  const setWater = (w: string) =>
    onChange({
      ...value,
      waterCharacter: value.waterCharacter === w ? undefined : w,
    });
  const toggleStyle = (s: string) =>
    onChange({
      ...value,
      styles: value.styles.includes(s)
        ? value.styles.filter((x) => x !== s)
        : [...value.styles, s],
    });
  const toggleBottom = (bottom: string) =>
    onChange({
      ...value,
      bottomTypes: (value.bottomTypes ?? []).includes(bottom)
        ? (value.bottomTypes ?? []).filter((x) => x !== bottom)
        : [...(value.bottomTypes ?? []), bottom],
    });
  const setSort = (sort: SortKey) => onChange({ ...value, sort });

  return (
    <div ref={rootRef} className="relative">
      <button
        ref={triggerRef}
        type="button"
        aria-haspopup="dialog"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-2 text-[15px] text-ink transition-colors hover:text-teal"
      >
        <SortIcon className="text-[18px]" />
        Sortieren & Filtern
        {count > 0 && (
          <span className="grid h-5 min-w-5 place-items-center rounded-2xl bg-ink px-1.5 text-[11px] font-semibold text-white">
            {count}
          </span>
        )}
      </button>

      {open && (
        <div
          ref={panelRef}
          id={panelId}
          role="dialog"
          aria-label="Sortieren und filtern"
          className="absolute right-0 z-30 mt-3 w-[300px] rounded-2xl bg-white p-5 ring-1 ring-line"
        >
          {/* Sortierung */}
          <fieldset>
            <legend className="text-[12px] font-semibold uppercase tracking-wide text-muted">
              Sortierung
            </legend>
            <div className="mt-2 space-y-1">
              {SORT_OPTIONS.map((o) => (
                <label
                  key={o.key}
                  className="flex min-h-11 cursor-pointer items-center gap-2 rounded-lg px-2 py-1.5 text-[13.5px] text-ink hover:bg-teal/[0.06]"
                >
                  <input
                    type="radio"
                    name="sort"
                    checked={value.sort === o.key}
                    onChange={() => setSort(o.key)}
                    className="accent-teal"
                  />
                  {o.label}
                </label>
              ))}
            </div>
          </fieldset>

          {/* Level */}
          <fieldset className="mt-4">
            <legend className="text-[12px] font-semibold uppercase tracking-wide text-muted">
              Level
            </legend>
            <div className="mt-2 flex flex-wrap gap-1.5">
              {LEVELS.map((l) => (
                <Chip key={l} active={value.level === l} onClick={() => setLevel(l)}>
                  {levelLabel(l)}
                </Chip>
              ))}
            </div>
          </fieldset>

          {/* Wasserart */}
          <fieldset className="mt-4">
            <legend className="text-[12px] font-semibold uppercase tracking-wide text-muted">
              Wasserart
            </legend>
            <div className="mt-2 flex flex-wrap gap-1.5">
              {WATER_CHARACTERS.map((w) => (
                <Chip
                  key={w}
                  active={value.waterCharacter === w}
                  onClick={() => setWater(w)}
                >
                  {waterCharacterLabel(w)}
                </Chip>
              ))}
            </div>
          </fieldset>

          {/* Fahrstil (Mehrfachauswahl) */}
          <fieldset className="mt-4">
            <legend className="text-[12px] font-semibold uppercase tracking-wide text-muted">
              Fahrstil
            </legend>
            <div className="mt-2 flex flex-wrap gap-1.5">
              {STYLES.map((s) => (
                <Chip
                  key={s}
                  active={value.styles.includes(s)}
                  onClick={() => toggleStyle(s)}
                >
                  {styleLabel(s)}
                </Chip>
              ))}
            </div>
          </fieldset>

          <fieldset className="mt-4">
            <legend className="text-[12px] font-semibold uppercase tracking-wide text-muted">
              Untergrund
            </legend>
            <div className="mt-2 flex flex-wrap gap-1.5">
              {BOTTOM_TYPES.map((bottom) => (
                <Chip
                  key={bottom}
                  active={(value.bottomTypes ?? []).includes(bottom)}
                  onClick={() => toggleBottom(bottom)}
                >
                  {bottomTypeLabel(bottom)}
                </Chip>
              ))}
            </div>
          </fieldset>

          <div className="mt-5 flex items-center justify-between">
            <button
              type="button"
              onClick={() => onChange(emptyFilters())}
              disabled={count === 0}
              className="text-[13px] font-medium text-ink underline-offset-2 hover:underline disabled:cursor-not-allowed disabled:text-muted disabled:no-underline"
            >
              Zurücksetzen
            </button>
            <button
              type="button"
              onClick={() => {
                setOpen(false);
                triggerRef.current?.focus();
              }}
              className="min-h-11 px-3 py-1.5 text-[13px] font-semibold text-ink transition-opacity hover:underline hover:underline-offset-4 hover:opacity-70"
            >
              Fertig
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
