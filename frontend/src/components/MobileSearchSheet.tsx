import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { useNavigate } from "react-router-dom";
import { motion, useReducedMotion } from "framer-motion";
import {
  CloseIcon,
  KitesurfIcon,
  MapIcon,
  PinIcon,
  SearchIcon,
  SurfIcon,
  WindsurfIcon,
  WingIcon,
} from "../lib/icons";
import MobileSearchWhen, { WhenToggle, type WhenTab } from "./MobileSearchWhen";
import { sportLabel } from "../lib/labels";
import { useRegions, useSpots } from "../lib/hooks";
import { addRecent } from "../lib/recentSearches";
import {
  buildSearchParams,
  EMPTY_SEARCH,
  whenLabel,
  type SearchValue,
  type WhereSelection,
} from "../lib/searchSubmit";

type Section = "where" | "when" | "which" | null;

// Figma order; backend values. /search consumes a single sport, so the mobile
// picker is single-select (stored as a 1-element `which`).
const SPORT_OPTIONS: { value: string; Icon: typeof SurfIcon }[] = [
  { value: "surf", Icon: SurfIcon },
  { value: "kitesurf", Icon: KitesurfIcon },
  { value: "windsurf", Icon: WindsurfIcon },
  { value: "wing", Icon: WingIcon },
];

// The whole sheet rides up (and snaps back on a swipe-down) on one native CSS
// transform transition — NOT a framer animation. A framer `drag` element is
// pinned to the JS engine and animates transform on the main thread, which on
// iOS Safari drops to well under 60fps whenever the thread is busy (the "too
// few frames" feel). A CSS `transition: transform` runs on the compositor
// instead, so the slide stays smooth regardless of main-thread load. The drag
// itself is a few pointer handlers below.
const SHEET_SLIDE_MS = 460;
const SHEET_EASE_CSS = "cubic-bezier(0.22, 1, 0.36, 1)";

/** A place suggestion, flattened for the mobile single-column list. */
interface WhereRowItem {
  key: string;
  kind: "spot" | "region";
  label: string;
  subtitle: string;
  pick: WhereSelection & { country?: string | null };
}

/**
 * Full mobile search flow (Figma Frames 16–20), Airbnb-style. The collapsed
 * trigger (MobileSearchTrigger) opens this overlay: white cards floating over
 * the hero, stacking the search axes as accordion sections — one open at a
 * time — above two actions. Drives the same `SearchValue` model as the desktop
 * SearchBar and submits through `buildSearchParams`.
 *
 * Built per frame:
 *   - Frame 16: overlay chrome + collapsed rows + actions
 *   - Frame 17: "Wohin?" picker (this pass)
 *   - Frame 18/19: "Wann?" picker (range + flex) — pending
 *   - Frame 20: "Welche Sportart?" picker — pending
 */
export default function MobileSearchSheet({
  open,
  onClose,
  returnFocusRef,
}: {
  open: boolean;
  onClose: () => void;
  /** Explicit opener, because tapping a control does not focus it in every
   * mobile browser and `document.activeElement` can therefore be the body. */
  returnFocusRef?: { current: HTMLElement | null };
  /** Viewport-y of the collapsed pill, so the sheet grows out of it (Airbnb). */
  originY?: number | null;
}) {
  const navigate = useNavigate();
  const reduce = useReducedMotion();
  const [val, setVal] = useState<SearchValue>(EMPTY_SEARCH);
  // Which accordion section is expanded (null = all collapsed to equal tiles).
  const [section, setSection] = useState<Section>(null);
  const [whenTab, setWhenTab] = useState<WhenTab>("date");
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const previousFocusRef = useRef<HTMLElement | null>(null);

  // Native-CSS slide state (see SHEET_SLIDE_MS). `mounted` keeps the node in the
  // DOM through the close animation; `slidIn` toggles the transform a frame
  // after mount so the transition actually runs; `dragging` cuts the transition
  // while a finger is driving the sheet directly.
  const sheetRef = useRef<HTMLDivElement>(null);
  const [mounted, setMounted] = useState(open);
  const [slidIn, setSlidIn] = useState(false);

  // Lock body scroll while open; move focus into the modal, contain keyboard
  // navigation, support Esc, and return focus to the control that opened it.
  useEffect(() => {
    if (!open) return;
    previousFocusRef.current = returnFocusRef?.current
      ?? (document.activeElement instanceof HTMLElement ? document.activeElement : null);
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
        return;
      }
      if (e.key !== "Tab") return;
      const dialog = document.getElementById("mobile-search-dialog");
      // Collapsed accordion bodies stay in the DOM but are `inert`; exclude them
      // (querySelectorAll ignores inert, but their controls can't take focus).
      const focusable = dialog
        ? Array.from(
            dialog.querySelectorAll<HTMLElement>(
              'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
            ),
          ).filter((el) => !el.closest("[inert]"))
        : [];
      if (!focusable.length) {
        e.preventDefault();
        dialog?.focus();
        return;
      }
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    };
    window.addEventListener("keydown", onKey);
    const frame = window.requestAnimationFrame(() => closeButtonRef.current?.focus({ preventScroll: true }));
    return () => {
      window.cancelAnimationFrame(frame);
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", onKey);
    };
  }, [open, onClose, returnFocusRef]);

  // Opening always starts a fresh search, fully collapsed (equal-size tiles).
  useEffect(() => {
    if (open) {
      setVal(EMPTY_SEARCH);
      setSection(null);
      setWhenTab("date");
      // Warm the code-split results route while the sheet is open. On slower
      // mobile networks this removes the first-navigation race; stale deploy
      // chunks are recovered centrally by the vite:preloadError handler.
      void import("../pages/SearchResults").catch(() => undefined);
    }
  }, [open]);

  // Mount on open; on close, slide out first and only then unmount and hand
  // focus back to the control that opened the sheet (replaces framer's
  // AnimatePresence exit + onExitComplete).
  useEffect(() => {
    if (open) {
      setMounted(true);
      return;
    }
    setSlidIn(false);
    const previous = previousFocusRef.current;
    const timer = window.setTimeout(() => {
      setMounted(false);
      if (previous?.isConnected) previous.focus({ preventScroll: true });
    }, reduce ? 160 : SHEET_SLIDE_MS);
    return () => window.clearTimeout(timer);
  }, [open, reduce]);

  // Once the node is mounted for an open sheet, flip to the slid-in transform on
  // a later frame (double rAF) so the browser paints the off-screen start state
  // first and the transition animates instead of jumping.
  useEffect(() => {
    if (!mounted || !open) return;
    let inner = 0;
    const outer = requestAnimationFrame(() => {
      inner = requestAnimationFrame(() => setSlidIn(true));
    });
    return () => {
      cancelAnimationFrame(outer);
      if (inner) cancelAnimationFrame(inner);
    };
  }, [mounted, open]);

  // Place data — fetched only while the sheet is engaged.
  const enabled = open && (section === "where" || val.whereText.trim().length > 0);
  const { data: spots } = useSpots({}, enabled);
  const { data: regions } = useRegions(enabled);
  const q = val.whereText.trim().toLowerCase();
  const regionById = useMemo(
    () => new Map((regions ?? []).map((r) => [r.id, r])),
    [regions]
  );
  const items = useMemo<WhereRowItem[]>(() => {
    const spotRows: WhereRowItem[] = (spots ?? [])
      .filter((s) => !q || s.name.toLowerCase().includes(q))
      .slice(0, 6)
      .map((s) => {
        const region = regionById.get(s.regionId ?? "");
        const country = region?.country ?? null;
        return {
          key: `spot-${s.id}`,
          kind: "spot",
          label: s.name,
          subtitle: [country, region?.name].filter(Boolean).join(", "),
          pick: { label: s.name, kind: "spot", id: s.uuid ?? s.id, country },
        };
      });
    const regionRows: WhereRowItem[] = (regions ?? [])
      .filter((r) => !q || r.name.toLowerCase().includes(q))
      .slice(0, 6)
      .map((r) => ({
        key: `region-${r.id}`,
        kind: "region",
        label: r.name,
        subtitle: r.country ?? "",
        pick: { label: r.name, kind: "region", id: r.id, country: r.country },
      }));
    return [...spotRows, ...regionRows];
  }, [spots, regions, regionById, q]);

  const submit = () => {
    navigate(`/search?${buildSearchParams(val).toString()}`);
    onClose();
  };

  // "Alles löschen": clear the search but stay in the sheet (Airbnb-style).
  const reset = () => {
    setVal(EMPTY_SEARCH);
    setSection(null);
    setWhenTab("date");
  };

  const toggleSection = (s: Exclude<Section, null>) =>
    setSection((cur) => (cur === s ? null : s));

  // Switching Datum ↔ flexibel starts that mode fresh (the two are exclusive).
  const changeWhenTab = (t: WhenTab) => {
    if (t === whenTab) return;
    setWhenTab(t);
    setVal((v) => ({ ...v, when: null }));
  };

  const pickWhere = (item: WhereRowItem) => {
    addRecent({
      label: item.pick.label,
      kind: item.pick.kind,
      id: item.pick.id,
      country: item.pick.country,
    });
    setVal((v) => ({
      ...v,
      whereSel: { label: item.pick.label, kind: item.pick.kind, id: item.pick.id },
      whereText: item.pick.label,
      whereOpen: false,
    }));
    // Airbnb flow: after the place, advance to the date step.
    setSection("when");
  };

  const whereValue =
    val.whereSel?.label || val.whereText || (val.whereOpen ? "Überall" : "");

  // Swipe-to-close, hand-rolled and fully imperative — NO React state changes
  // during a wipe, so the whole subtree never re-renders mid-gesture (that
  // re-render was the residual jank). Dragging the grab handle or header drives
  // the sheet 1:1; the scrolling body hands the gesture off once it is scrolled
  // to the very top and the thumb travels clearly downward, so a pull-down
  // closes from anywhere while an upward swipe still scrolls the tiles.
  //
  // The transform is written on the element directly and coalesced to one write
  // per frame via rAF. On release we settle imperatively (transition + target
  // transform) rather than relying on React: React keeps the same style object
  // between renders (transform stays "translateY(0)"), so it would NOT rewrite
  // our inline transform — which is exactly why a soft wipe used to stick in the
  // middle instead of snapping back.
  const dragRef = useRef({ startY: 0, lastY: 0, lastT: 0, vy: 0, active: false });
  const bodyStart = useRef<{ y: number; id: number } | null>(null);
  const moveRaf = useRef(0);
  const pendingY = useRef(0);

  const transformTransition = () =>
    reduce ? "opacity 150ms ease-out" : `transform ${SHEET_SLIDE_MS}ms ${SHEET_EASE_CSS}`;

  const beginDrag = (clientY: number, el: HTMLElement, pointerId: number) => {
    dragRef.current = { startY: clientY, lastY: clientY, lastT: performance.now(), vy: 0, active: true };
    if (sheetRef.current) sheetRef.current.style.transition = "none"; // follow 1:1
    try {
      el.setPointerCapture(pointerId);
    } catch {
      /* Safari < 16 without capture still works via the element's own events. */
    }
  };
  const moveDrag = (clientY: number) => {
    const d = dragRef.current;
    if (!d.active) return;
    const now = performance.now();
    const dt = now - d.lastT;
    if (dt > 0) d.vy = (clientY - d.lastY) / dt; // px/ms, for a flick check
    d.lastY = clientY;
    d.lastT = now;
    pendingY.current = clientY;
    if (!moveRaf.current) {
      moveRaf.current = requestAnimationFrame(() => {
        moveRaf.current = 0;
        const el = sheetRef.current;
        if (el && dragRef.current.active) {
          el.style.transform = `translateY(${Math.max(0, pendingY.current - dragRef.current.startY)}px)`;
        }
      });
    }
  };
  const endDrag = () => {
    const d = dragRef.current;
    if (!d.active) return;
    d.active = false;
    if (moveRaf.current) {
      cancelAnimationFrame(moveRaf.current);
      moveRaf.current = 0;
    }
    const dy = d.lastY - d.startY;
    const closing = dy > 120 || (dy > 40 && d.vy > 0.5);
    const el = sheetRef.current;
    if (el) {
      // Re-enable the transition and give it an explicit target so it animates
      // from the finger position — snap back to the open position, or continue
      // down and out. (For reduced motion, transform is instant.)
      el.style.transition = transformTransition();
      el.style.transform = reduce ? "" : closing ? "translateY(100%)" : "translateY(0)";
    }
    if (closing) onClose();
  };

  const onBodyPointerDown = (e: React.PointerEvent<HTMLDivElement>) => {
    bodyStart.current = { y: e.clientY, id: e.pointerId };
  };
  const onBodyPointerMove = (e: React.PointerEvent<HTMLDivElement>) => {
    if (dragRef.current.active) {
      moveDrag(e.clientY);
      return;
    }
    const bs = bodyStart.current;
    if (!bs) return;
    if (e.currentTarget.scrollTop <= 0 && e.clientY - bs.y > 14) {
      beginDrag(bs.y, e.currentTarget, bs.id);
      moveDrag(e.clientY);
    }
  };
  const onBodyPointerEnd = () => {
    bodyStart.current = null;
    endDrag();
  };
  // Delayed autofocus + auto-scroll refs.
  const whereInputRef = useRef<HTMLInputElement>(null);

  // Focus the "Wohin?" field only after its tile has finished expanding, so the
  // keyboard does not fight the open animation.
  useEffect(() => {
    if (!open || section !== "where") return;
    const t = window.setTimeout(() => whereInputRef.current?.focus(), 320);
    return () => window.clearTimeout(t);
  }, [open, section]);

  // Deliberately NO auto-scroll on section change: expanding a tile used to
  // scrollIntoView the opened tile, which shoved the already-picked (now small)
  // tiles above it off-screen. Tiles now expand in place; the earlier ones stay
  // put and the visitor scrolls only if they want to.

  if (!mounted) return null;

  // Compositor-driven slide: transform (or opacity, reduced motion) is toggled
  // by `slidIn`; the transition is cut while a finger is dragging.
  const sheetStyle: React.CSSProperties = reduce
    ? {
        willChange: "opacity",
        transition: dragRef.current.active ? "none" : "opacity 150ms ease-out",
        opacity: slidIn ? 1 : 0,
      }
    : {
        willChange: "transform",
        transition: dragRef.current.active ? "none" : `transform ${SHEET_SLIDE_MS}ms ${SHEET_EASE_CSS}`,
        transform: slidIn ? "translateY(0)" : "translateY(100%)",
      };

  return createPortal(
    <div
      ref={sheetRef}
      id="mobile-search-dialog"
      className="fixed inset-0 z-[1300] flex flex-col bg-page"
      role="dialog"
      aria-modal="true"
      aria-label="Suche"
      tabIndex={-1}
      style={sheetStyle}
    >
          {/* Grab handle — swipe down to close. */}
          <div
            className="flex cursor-grab justify-center pt-2 active:cursor-grabbing"
            style={{ touchAction: "none" }}
            onPointerDown={(e) => beginDrag(e.clientY, e.currentTarget, e.pointerId)}
            onPointerMove={(e) => moveDrag(e.clientY)}
            onPointerUp={endDrag}
            onPointerCancel={endDrag}
          >
            <span className="h-1.5 w-10 rounded-full bg-line" />
          </div>

          {/* Header — a clear close + title anchor the screen. The whole row is
              a drag zone (together with the grab handle), so a pull-down here
              closes the sheet; the close button opts out so its tap still fires. */}
          <div
            className="flex items-center gap-3 px-4 py-3"
            style={{ touchAction: "none" }}
            onPointerDown={(e) => beginDrag(e.clientY, e.currentTarget, e.pointerId)}
            onPointerMove={(e) => moveDrag(e.clientY)}
            onPointerUp={endDrag}
            onPointerCancel={endDrag}
          >
            <button
              ref={closeButtonRef}
              type="button"
              onClick={onClose}
              onPointerDown={(e) => e.stopPropagation()}
              aria-label="Schließen"
              // focus-visible only: the sheet moves focus here programmatically
              // on open, and on touch that must NOT paint an outline (the stray
              // "stroke" around the ✕). Keyboard users still get a clear ring.
              className="grid h-11 w-11 place-items-center rounded-full border border-line text-ink transition-colors hover:bg-band focus:outline-none focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink"
            >
              <CloseIcon className="text-body" />
            </button>
            <span className="text-body font-semibold text-ink">Suchen</span>
          </div>

          {/* Tiles — top-aligned; content sizes to itself and the whole area
              scrolls, so nothing lives in a cramped inner scroll box. */}
          <div
            data-lenis-prevent
            className="min-h-0 flex-1 overflow-y-auto px-4 pb-4"
            // Give the scrolling region its own compositor layer (translateZ)
            // so the sheet's slide-up stays a pure GPU transform on iOS instead
            // of repainting this scroll subtree each frame; `contain` also keeps
            // its overscroll from chaining into the page behind.
            style={{ overscrollBehaviorY: "contain", transform: "translateZ(0)" }}
            onPointerDown={onBodyPointerDown}
            onPointerMove={onBodyPointerMove}
            onPointerUp={onBodyPointerEnd}
            onPointerCancel={onBodyPointerEnd}
          >
            <div className="mx-auto flex w-full max-w-[520px] flex-col gap-3">
              {/* Wohin? */}
              <div id="msheet-where">
              <Section
                label="Wohin?"
                value={whereValue}
                placeholder="Region oder Spot suchen"
                open={section === "where"}
                onToggle={() => toggleSection("where")}
              >
                <input
                  ref={whereInputRef}
                  value={val.whereText}
                  onChange={(e) =>
                    setVal((v) => ({
                      ...v,
                      whereText: e.target.value,
                      whereSel: null,
                      whereOpen: false,
                    }))
                  }
                  placeholder="Region oder Spot suchen"
                  aria-label="Region oder Spot suchen"
                  className="search-plain w-full border-0 bg-transparent text-sz-16 text-ink outline-none ring-0 placeholder:text-muted focus:outline-none focus:ring-0"
                />
                <div className="mt-3">
                  {items.length ? (
                    <div className="flex flex-col">
                      {items.map((it) => (
                        <motion.button
                          key={it.key}
                          type="button"
                          whileTap={{ scale: 0.98 }}
                          onClick={() => pickWhere(it)}
                          className="flex items-center gap-3 rounded-[14px] px-1.5 py-2.5 text-left transition-colors hover:bg-band active:bg-band"
                        >
                          <span className="flex w-7 shrink-0 justify-center text-ink">
                            {it.kind === "spot" ? (
                              <PinIcon className="text-sz-22" />
                            ) : (
                              <MapIcon className="text-sz-22" />
                            )}
                          </span>
                          <span className="min-w-0">
                            <span className="block truncate text-sz-16 font-medium text-ink">
                              {it.label}
                            </span>
                            {it.subtitle && (
                              <span className="block truncate text-label text-muted">
                                {it.subtitle}
                              </span>
                            )}
                          </span>
                        </motion.button>
                      ))}
                    </div>
                  ) : (
                    <p className="px-1.5 py-2 text-ui text-muted">Keine Treffer.</p>
                  )}
                </div>
              </Section>
              </div>

              {/* Wann? — the Datum/flexibel toggle sits in the tile header. */}
              <div id="msheet-when">
              <Section
                label="Wann?"
                value={whenLabel(val.when)}
                placeholder="Zeitraum auswählen"
                open={section === "when"}
                onToggle={() => toggleSection("when")}
                headerAccessory={<WhenToggle tab={whenTab} onChange={changeWhenTab} />}
              >
                <MobileSearchWhen
                  tab={whenTab}
                  value={val.when}
                  onChange={(when) => {
                    setVal((v) => ({ ...v, when }));
                    // Guided flow: a concrete date advances to the sport step.
                    if (when?.mode === "range" && when.from) setSection("which");
                  }}
                />
              </Section>
              </div>

              {/* Welche Sportart? */}
              <div id="msheet-which">
              <Section
                label="Welche Sportart?"
                value={val.which.map(sportLabel).join(", ")}
                placeholder="Wähle deine Sportart aus"
                open={section === "which"}
                onToggle={() => toggleSection("which")}
              >
                <div className="flex flex-col gap-2">
                  {SPORT_OPTIONS.map(({ value: sport, Icon }) => {
                    const selected = val.which.includes(sport);
                    return (
                      <motion.button
                        key={sport}
                        type="button"
                        whileTap={{ scale: 0.98 }}
                        onClick={() =>
                          setVal((v) => ({
                            ...v,
                            which: selected
                              ? v.which.filter((s) => s !== sport)
                              : [...v.which, sport],
                          }))
                        }
                        aria-pressed={selected}
                        className="flex items-center gap-4 rounded-[14px] px-1.5 py-3 text-left transition-colors hover:bg-band"
                      >
                        <Icon className="shrink-0 text-sz-26 text-ink" />
                        <span className="flex-1 text-sz-16 font-medium text-ink">
                          {sportLabel(sport)}
                        </span>
                        <span
                          className={`grid h-6 w-6 shrink-0 place-items-center rounded-full border transition-colors ${
                            selected ? "border-teal" : "border-line"
                          }`}
                        >
                          {selected && (
                            <motion.span
                              initial={{ scale: 0 }}
                              animate={{ scale: 1 }}
                              transition={{ type: "spring", stiffness: 600, damping: 28 }}
                              className="h-3 w-3 rounded-full bg-teal"
                            />
                          )}
                        </span>
                      </motion.button>
                    );
                  })}
                </div>
              </Section>
              </div>
            </div>
          </div>

          {/* Actions — a text-link clear + a filled primary search button. */}
          <div className="border-t border-line bg-page px-4 pb-6 pt-3">
            <div className="mx-auto flex w-full max-w-[520px] items-center justify-between gap-3">
              <button
                type="button"
                onClick={reset}
                className="min-h-11 px-2 text-body font-semibold text-ink underline underline-offset-4 transition-opacity hover:opacity-70"
              >
                Alles löschen
              </button>
              <motion.button
                type="button"
                whileTap={{ scale: 0.97 }}
                onClick={submit}
                className="inline-flex min-h-12 items-center gap-2 rounded-full bg-teal px-6 text-body font-medium text-white transition-colors hover:bg-teal-hover"
              >
                <SearchIcon className="text-sz-18" />
                Suchen
              </motion.button>
            </div>
          </div>
    </div>,
    document.body
  );
}

/**
 * One accordion tile. Collapsed, every tile is the same size — just the header
 * row (label + current value). Tapping expands it: the header label turns teal
 * and the body reveals with a smooth height/opacity animation; collapsing
 * reverses it. Exactly one tile is open at a time (state lives in the parent).
 */
function Section({
  label,
  value,
  placeholder,
  open,
  onToggle,
  headerAccessory,
  children,
}: {
  label: string;
  value: string;
  placeholder: string;
  open: boolean;
  onToggle: () => void;
  /** Rendered on the header's right when open (e.g. the Datum/flexibel toggle). */
  headerAccessory?: ReactNode;
  children: ReactNode;
}) {
  // Native grid-rows 0fr→1fr accordion instead of framer's per-frame JS height:
  // the browser animates it in one pass (smoother on iOS). Two guards keep it
  // fast and correct:
  //  - `render` mounts the (heavy — e.g. the 12-month calendar) body only once
  //    the tile is first opened, and keeps it through the collapse so the close
  //    also animates; it never mounts on the sheet's own open.
  //  - `expanded` flips a couple of frames after mount so the mount cost is paid
  //    before the transition starts (no first-frame hitch), and drives the row.
  //  - `inert` drops collapsed content out of the tab order / AT (it stays in
  //    the DOM for the animation).
  const [render, setRender] = useState(open);
  const [expanded, setExpanded] = useState(open);
  const bodyRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (open) {
      setRender(true);
      const outer = requestAnimationFrame(() => {
        requestAnimationFrame(() => setExpanded(true));
      });
      return () => cancelAnimationFrame(outer);
    }
    setExpanded(false);
    const timer = window.setTimeout(() => setRender(false), 320);
    return () => window.clearTimeout(timer);
  }, [open]);

  useEffect(() => {
    const el = bodyRef.current;
    if (!el) return;
    if (open) el.removeAttribute("inert");
    else el.setAttribute("inert", "");
  }, [open, render]);

  return (
    <div className="overflow-hidden rounded-[14px] bg-surface shadow-float">
      <div className="flex items-center justify-between gap-3 px-5 py-4">
        <button
          type="button"
          onClick={onToggle}
          aria-expanded={open}
          className="flex min-w-0 flex-1 items-center justify-between gap-3 text-left"
        >
          <span
            className={`shrink-0 text-sz-16 font-semibold transition-colors ${
              open ? "text-teal" : "text-ink"
            }`}
          >
            {label}
          </span>
          {!open && (
            <span className="min-w-0 truncate text-body text-muted">
              {value || placeholder}
            </span>
          )}
        </button>
        {open && headerAccessory}
      </div>
      <div
        ref={bodyRef}
        style={{
          display: "grid",
          gridTemplateRows: expanded ? "1fr" : "0fr",
          opacity: expanded ? 1 : 0,
          transition:
            "grid-template-rows 300ms cubic-bezier(0.22, 1, 0.36, 1), opacity 300ms cubic-bezier(0.22, 1, 0.36, 1)",
        }}
      >
        <div className="overflow-hidden">
          <div className="px-5 pb-5">{render ? children : null}</div>
        </div>
      </div>
    </div>
  );
}
