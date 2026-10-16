import { useEffect, useId, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { CloseIcon, FilterIcon } from "../lib/icons";
import { LEVELS, SPORTS, levelLabel, sportLabel } from "../lib/labels";
import { useDesktopViewport } from "../lib/useAutoHideHeader";
import Chip from "./ui/Chip";
import Checkbox from "./ui/Checkbox";
import Radio from "./ui/Radio";

export type LandingSort = "recommended" | "az";

export interface CountryOption {
  code: string;
  name: string;
}

// The mobile sheet rides up on a single compositor-driven CSS transform so the
// slide stays smooth on iOS (same reasoning as MobileSearchSheet).
const SHEET_SLIDE_MS = 320;
const SHEET_EASE_CSS = "cubic-bezier(0.22, 1, 0.36, 1)";

interface LandingFiltersProps {
  sort: LandingSort;
  onSort: (next: LandingSort) => void;
  sport: string;
  onSport: (next: string) => void;
  country: string;
  onCountry: (next: string) => void;
  countries: CountryOption[];
  level: string;
  onLevel: (next: string) => void;
  showPersonalization: boolean;
  ignorePersonalization: boolean;
  onIgnorePersonalization: (next: boolean) => void;
  onReset: () => void;
}

/**
 * Icon-only "Filter" control (Figma Frame 78: the sliders glyph, no text label)
 * that opens the landing's sort + filter surface — sort (Empfohlen / A–Z),
 * sport, land and level, plus the signed-in personalisation toggle. The axes
 * speak the same chip/dialog language as SortDropdown (the region page).
 *
 * One responsive variant is rendered at a time (never both CSS-hidden): a
 * right-aligned dropdown popover on desktop, and a bottom-sheet "window" with a
 * close ✕ on mobile — matching the frame. Rendering only one variant also keeps
 * the desktop popover's outside-click handler from eating taps inside the mobile
 * portal (see the portal-outside-click note in project memory).
 */
export default function LandingFilters(props: LandingFiltersProps) {
  const { sort, onReset } = props;
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const panelId = useId();
  const desktop = useDesktopViewport();

  // Badge counts the active *filters* (sport / land / level) plus a non-default
  // sort — the personalisation toggle is a mode, not a filter, so it is left out.
  const count =
    (props.sport ? 1 : 0) +
    (props.country ? 1 : 0) +
    (props.level ? 1 : 0) +
    (sort !== "recommended" ? 1 : 0);

  const close = () => {
    setOpen(false);
    triggerRef.current?.focus();
  };

  // Desktop dropdown: close on outside click / ESC. Only wired on desktop so it
  // never runs while the mobile portal (rendered outside rootRef) is open.
  useEffect(() => {
    if (!open || !desktop) return;
    const onDown = (e: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") close();
    };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open, desktop]);

  // Move focus into the panel when the desktop dropdown opens.
  useEffect(() => {
    if (open && desktop) {
      panelRef.current?.querySelector<HTMLElement>("button, input, [tabindex]")?.focus();
    }
  }, [open, desktop]);

  // Close whichever surface is open when the viewport crosses the breakpoint, so
  // we never leave the wrong variant mounted.
  useEffect(() => {
    setOpen(false);
  }, [desktop]);

  const trigger = (
    <button
      ref={triggerRef}
      type="button"
      aria-haspopup="dialog"
      aria-expanded={open}
      aria-controls={open ? panelId : undefined}
      aria-label="Filter"
      onClick={() => setOpen((o) => !o)}
      className="relative flex h-11 w-11 items-center justify-center rounded-full text-ink transition-colors hover:text-accent focus:outline-none focus-visible:ring-2 focus-visible:ring-ink/60"
    >
      <FilterIcon className="text-title" />
      {count > 0 && (
        <span className="absolute -right-0.5 -top-0.5 grid h-5 min-w-5 place-items-center rounded-card bg-ink px-1.5 text-caption font-semibold text-white">
          {count}
        </span>
      )}
    </button>
  );

  return (
    <div ref={rootRef} className="relative">
      {trigger}

      {open &&
        (desktop ? (
          <div
            ref={panelRef}
            id={panelId}
            role="dialog"
            aria-label="Filter"
            className="absolute right-0 z-40 mt-3 max-h-[70vh] w-[300px] max-w-[calc(100vw-2rem)] overflow-y-auto rounded-card bg-surface p-5 shadow-float ring-1 ring-line"
          >
            <FilterFields {...props} />
            <FilterFooter count={count} onReset={onReset} onDone={close} />
          </div>
        ) : (
          <FilterSheet
            panelId={panelId}
            panelRef={panelRef}
            count={count}
            onReset={onReset}
            onClose={close}
            fields={<FilterFields {...props} />}
          />
        ))}
    </div>
  );
}

/** Shared sort + filter fieldsets, reused by the desktop dropdown and the
 * mobile sheet so the two never drift. */
function FilterFields({
  sort,
  onSort,
  sport,
  onSport,
  country,
  onCountry,
  countries,
  level,
  onLevel,
  showPersonalization,
  ignorePersonalization,
  onIgnorePersonalization,
}: Omit<LandingFiltersProps, "onReset">) {
  return (
    <>
      {/* Sortierung */}
      <fieldset>
        <legend className="text-caption font-semibold uppercase tracking-wide text-muted">
          Sortierung
        </legend>
        <div className="mt-2 space-y-1">
          {(
            [
              { key: "recommended", label: "Empfohlen" },
              { key: "az", label: "A – Z" },
            ] as { key: LandingSort; label: string }[]
          ).map((o) => (
            <Radio key={o.key} name="landing-sort" checked={sort === o.key} onChange={() => onSort(o.key)}>{o.label}</Radio>
          ))}
        </div>
      </fieldset>

      {/* Sportart */}
      <fieldset className="mt-4">
        <legend className="text-caption font-semibold uppercase tracking-wide text-muted">
          Sportart
        </legend>
        <div className="mt-2 flex flex-wrap gap-1.5">
          <Chip active={sport === ""} onClick={() => onSport("")}>
            Alle
          </Chip>
          {SPORTS.map((s) => (
            <Chip key={s} active={sport === s} onClick={() => onSport(s)}>
              {sportLabel(s)}
            </Chip>
          ))}
        </div>
      </fieldset>

      {/* Land */}
      {countries.length > 0 && (
        <fieldset className="mt-4">
          <legend className="text-caption font-semibold uppercase tracking-wide text-muted">
            Land
          </legend>
          <div className="mt-2 flex flex-wrap gap-1.5">
            <Chip active={country === ""} onClick={() => onCountry("")}>
              Alle
            </Chip>
            {countries.map((c) => (
              <Chip key={c.code} active={country === c.code} onClick={() => onCountry(c.code)}>
                {c.name}
              </Chip>
            ))}
          </div>
        </fieldset>
      )}

      {/* Level */}
      <fieldset className="mt-4">
        <legend className="text-caption font-semibold uppercase tracking-wide text-muted">
          Level
        </legend>
        <div className="mt-2 flex flex-wrap gap-1.5">
          <Chip active={level === ""} onClick={() => onLevel("")}>
            Alle
          </Chip>
          {LEVELS.map((l) => (
            <Chip key={l} active={level === l} onClick={() => onLevel(l)}>
              {levelLabel(l)}
            </Chip>
          ))}
        </div>
      </fieldset>

      {showPersonalization && (
        <Checkbox layout="row" className="mt-4 -mx-2" checked={ignorePersonalization} onChange={(e) => onIgnorePersonalization(e.target.checked)}>Personalisierung ignorieren</Checkbox>
      )}
    </>
  );
}

/** Zurücksetzen / Fertig footer, shared by both surfaces. */
function FilterFooter({
  count,
  onReset,
  onDone,
}: {
  count: number;
  onReset: () => void;
  onDone: () => void;
}) {
  return (
    <div className="mt-5 flex items-center justify-between">
      <button
        type="button"
        onClick={onReset}
        disabled={count === 0}
        className="text-ui font-medium text-ink underline-offset-2 hover:underline disabled:cursor-not-allowed disabled:text-muted disabled:no-underline"
      >
        Zurücksetzen
      </button>
      <button
        type="button"
        onClick={onDone}
        className="min-h-11 px-3 py-1.5 text-ui font-semibold text-ink transition-opacity hover:underline hover:underline-offset-4 hover:opacity-70"
      >
        Fertig
      </button>
    </div>
  );
}

/**
 * Mobile "window": a bottom-sheet that slides up over a scrim, with a grab
 * handle, a titled header carrying the close ✕ (Figma Frame 78), the shared
 * filter fields in a scroll area, and the Zurücksetzen / Fertig footer. Locks
 * body scroll and closes on scrim tap or ESC.
 */
function FilterSheet({
  panelId,
  panelRef,
  count,
  fields,
  onReset,
  onClose,
}: {
  panelId: string;
  panelRef: React.RefObject<HTMLDivElement>;
  count: number;
  fields: ReactNode;
  onReset: () => void;
  onClose: () => void;
}) {
  const [slidIn, setSlidIn] = useState(false);
  const closeButtonRef = useRef<HTMLButtonElement>(null);

  // Lock body scroll, support ESC, and slide the sheet up a frame after mount so
  // the transform transition actually runs (paint the off-screen start first).
  useEffect(() => {
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
      }
    };
    window.addEventListener("keydown", onKey);
    const outer = requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        setSlidIn(true);
        closeButtonRef.current?.focus({ preventScroll: true });
      });
    });
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", onKey);
      cancelAnimationFrame(outer);
    };
  }, [onClose]);

  return createPortal(
    <div className="fixed inset-0 z-sheet flex flex-col justify-end">
      {/* Scrim */}
      <button
        type="button"
        aria-label="Schließen"
        tabIndex={-1}
        onClick={onClose}
        className={`absolute inset-0 bg-ink/40 transition-opacity duration-slow ${
          slidIn ? "opacity-100" : "opacity-0"
        }`}
      />

      <div
        ref={panelRef}
        id={panelId}
        role="dialog"
        aria-modal="true"
        aria-label="Filter"
        className="relative flex max-h-[85vh] flex-col rounded-t-card bg-surface"
        style={{
          willChange: "transform",
          transition: `transform ${SHEET_SLIDE_MS}ms ${SHEET_EASE_CSS}`,
          transform: slidIn ? "translateY(0)" : "translateY(100%)",
        }}
      >
        {/* Grab handle */}
        <div className="flex justify-center pt-2">
          <span aria-hidden className="h-1.5 w-10 rounded-full bg-line" />
        </div>

        {/* Header — title + close ✕ */}
        <div className="flex items-center justify-between gap-3 px-5 py-3">
          <span className="text-body font-semibold text-ink">Filter</span>
          <button
            ref={closeButtonRef}
            type="button"
            onClick={onClose}
            aria-label="Schließen"
            className="grid h-11 w-11 place-items-center rounded-full border border-line text-ink transition-colors hover:bg-band focus:outline-none focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink"
          >
            <CloseIcon className="text-body" />
          </button>
        </div>

        {/* Fields — scrolls if the list is long */}
        <div
          data-lenis-prevent
          className="min-h-0 flex-1 overflow-y-auto px-5 pb-2"
          style={{ overscrollBehaviorY: "contain" }}
        >
          {fields}
        </div>

        {/* Footer */}
        <div className="border-t border-line px-5 pb-6 pt-3">
          <FilterFooter count={count} onReset={onReset} onDone={onClose} />
        </div>
      </div>
    </div>,
    document.body,
  );
}
