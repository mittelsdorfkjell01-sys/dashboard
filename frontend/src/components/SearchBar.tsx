import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { useNavigate } from "react-router-dom";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import {
  KitesurfIcon,
  SearchIcon,
  SurfIcon,
  WindsurfIcon,
  WingIcon,
} from "../lib/icons";
import SearchWhere, { type WhereItem, type WherePick } from "./search/SearchWhere";
import SearchWhen from "./search/SearchWhen";
import { WhenToggle, type WhenTab } from "./MobileSearchWhen";
import { sportLabel } from "../lib/labels";
import { addRecent } from "../lib/recentSearches";
import { useRegions, useSpots } from "../lib/hooks";
import {
  buildSearchParams,
  loadSearchDraft,
  saveSearchDraft,
  whenLabel,
  type SearchValue,
  type WhereSelection,
} from "../lib/searchSubmit";

type Segment = "where" | "when" | "which";

const SPORT_OPTIONS: { value: string; Icon: typeof SurfIcon }[] = [
  { value: "surf", Icon: SurfIcon },
  { value: "kitesurf", Icon: KitesurfIcon },
  { value: "windsurf", Icon: WindsurfIcon },
  { value: "wing", Icon: WingIcon },
];

// One shared, non-bouncy spring gives the shell and active segment the same
// cadence. Panels keep their existing widths and alignment.
const SPRING = { type: "spring" as const, stiffness: 360, damping: 34, mass: 0.75 };
const PANEL_TRANSITION = { duration: 0.07, ease: [0.16, 1, 0.3, 1] as const };
const PANEL_HEIGHT = 350;
const PANEL_GAP = 12;
const SHELL_HEIGHT = 56;
const VIEWPORT_GUTTER = 24;

/**
 * Desktop search (Airbnb-style). Collapsed it is a single, simple bar. Tapping
 * it lifts a dimmed overlay: the bar rises to the top and grows into three
 * segments — Wohin · Wann · Welche Sportart — with a panel below whose width
 * follows the active segment (Wohin/Welche ≈ half, Wann full, incl. the
 * Datum/flexibel toggle). Desktop-only; mobile uses MobileSearchSheet.
 *
 *  - variant "hero": the large collapsed bar in the landing hero.
 *  - variant "pill": the compact pill docked in the header once scrolled.
 */
export default function SearchBar({
  variant = "hero",
  whereOnly = false,
  onResolve,
}: {
  variant?: "hero" | "pill";
  /** Place-only search (the wind map): no "Wann?"/"Welche Sportart?" segments. */
  whereOnly?: boolean;
  /** When set, submitting hands the picked place back instead of navigating. */
  onResolve?: (selection: WhereSelection | null, text: string) => void;
}) {
  const navigate = useNavigate();
  const reduce = useReducedMotion();
  const [expanded, setExpanded] = useState(false);
  const [exiting, setExiting] = useState(false);
  const [shellReady, setShellReady] = useState(false);
  const [heroAnchor, setHeroAnchor] = useState<{
    top: number;
    left: number;
    width: number;
  } | null>(null);
  const [open, setOpen] = useState<Segment>("where");
  const [val, setVal] = useState<SearchValue>(() => loadSearchDraft());
  const [whenTab, setWhenTab] = useState<WhenTab>("date");

  // "Wohin?" results (owned here so ↑/↓/Enter can navigate them). Spots first,
  // then Regionen — the flat order the arrow keys move through.
  const searchDataEnabled = expanded || val.whereText.trim().length > 0;
  const { data: spots, loading: spotsLoading, error: spotsError, reload: reloadSpots } = useSpots({}, searchDataEnabled);
  const { data: regions, loading: regionsLoading, error: regionsError, reload: reloadRegions } = useRegions(searchDataEnabled);
  const placeLoading = (spotsLoading || regionsLoading) && !spots && !regions;
  const placeError = spotsError ?? regionsError;
  const q = val.whereText.trim().toLowerCase();
  const regionById = useMemo(
    () => new Map((regions ?? []).map((r) => [r.id, r])),
    [regions]
  );
  const spotItems = useMemo<WhereItem[]>(
    () =>
      (spots ?? [])
        .filter((s) => !q || s.name.toLowerCase().includes(q))
        .slice(0, 6)
        .map((s) => ({
          key: s.id,
          label: s.name,
          pick: {
            label: s.name,
            kind: "spot",
            id: s.uuid ?? s.id,
            country: regionById.get(s.regionId ?? "")?.country ?? null,
          },
        })),
    [spots, q, regionById]
  );
  const regionItems = useMemo<WhereItem[]>(
    () =>
      (regions ?? [])
        .filter((r) => !q || r.name.toLowerCase().includes(q))
        .slice(0, 6)
        .map((r) => ({
          key: r.id,
          label: r.name,
          pick: { label: r.name, kind: "region", id: r.id, country: r.country },
        })),
    [regions, q]
  );
  // Keyboard highlight for "Wohin?": which column + row (-1 = none).
  const [activeCol, setActiveCol] = useState<"spot" | "region">("spot");
  const [activeRow, setActiveRow] = useState(-1);
  useEffect(() => {
    setActiveRow(-1);
    setActiveCol("spot");
  }, [val.whereText]);

  const whereInputRef = useRef<HTMLInputElement>(null);
  const heroTriggerRef = useRef<HTMLButtonElement>(null);

  const openExpanded = (seg: Segment = "where") => {
    if (variant === "hero") {
      const rect = heroTriggerRef.current?.getBoundingClientRect();
      if (rect) {
        // Keep the shell anchored to the clicked bar whenever the viewport has
        // room. The panel always opens below it; on short viewports the complete
        // stack shifts upward only as far as needed to remain reachable.
        const panelSpan = PANEL_HEIGHT + PANEL_GAP;
        const maxTop = window.innerHeight - (SHELL_HEIGHT + panelSpan) - VIEWPORT_GUTTER;
        let top = Math.min(rect.top, maxTop);
        top = Math.max(VIEWPORT_GUTTER, top);
        setHeroAnchor({ top, left: rect.left, width: rect.width });
      }
    }
    setOpen(seg);
    setExiting(false);
    setShellReady(Boolean(reduce));
    setExpanded(true);
  };
  const collapse = () => {
    setExiting(true);
    setExpanded(false);
    setShellReady(false);
  };

  // Lock body scroll while the overlay is up; Esc closes it.
  useEffect(() => {
    if (!expanded) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && collapse();
    window.addEventListener("keydown", onKey);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", onKey);
    };
  }, [expanded]);

  // Focus only once the opening motion has settled. A fixed timer could fire
  // midway through a spring on slower devices and make the browser jump.
  useEffect(() => {
    if (!expanded || !shellReady || open !== "where") return;
    const frame = window.requestAnimationFrame(() => whereInputRef.current?.focus());
    return () => window.cancelAnimationFrame(frame);
  }, [expanded, open, shellReady]);

  const submit = () => {
    // Place-only callers (the wind map) zoom to the pick themselves.
    if (onResolve) {
      onResolve(val.whereSel ?? null, val.whereText.trim());
      collapse();
      return;
    }
    saveSearchDraft(val);
    navigate(`/search?${buildSearchParams(val).toString()}`);
    collapse();
  };

  const pickWhere = (pick: WherePick) => {
    addRecent({ label: pick.label, kind: pick.kind, id: pick.id, country: pick.country });
    setVal((v) => ({
      ...v,
      whereSel: { label: pick.label, kind: pick.kind, id: pick.id },
      whereText: pick.label,
      whereOpen: false,
    }));
    // Airbnb flow: after the place, advance to the date step. A place-only
    // search has no later step, so it stays on the place segment.
    setOpen(whereOnly ? "where" : "when");
  };

  // Switching Datum ↔ flexibel starts that mode fresh (the two are exclusive).
  const changeWhenTab = (t: WhenTab) => {
    if (t === whenTab) return;
    setWhenTab(t);
    setVal((v) => ({ ...v, when: null }));
  };

  const toggleSport = (sport: string) =>
    setVal((v) => ({
      ...v,
      which: v.which.includes(sport)
        ? v.which.filter((s) => s !== sport)
        : [...v.which, sport],
    }));

  const onWhereKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    const curLen = activeCol === "spot" ? spotItems.length : regionItems.length;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      if (open !== "where") setOpen("where");
      setActiveRow((r) => Math.min(r + 1, curLen - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActiveRow((r) => Math.max(r - 1, -1));
    } else if (e.key === "ArrowRight" && activeRow >= 0 && regionItems.length) {
      e.preventDefault();
      setActiveCol("region");
      setActiveRow((r) => Math.min(Math.max(r, 0), regionItems.length - 1));
    } else if (e.key === "ArrowLeft" && activeRow >= 0 && spotItems.length) {
      e.preventDefault();
      setActiveCol("spot");
      setActiveRow((r) => Math.min(Math.max(r, 0), spotItems.length - 1));
    } else if (e.key === "Enter") {
      e.preventDefault();
      const items = activeCol === "spot" ? spotItems : regionItems;
      const item = activeRow >= 0 ? items[activeRow] : undefined;
      if (item) pickWhere(item.pick);
      else if (val.whereText.trim()) setOpen("when");
      else submit();
    }
  };

  const whereText = val.whereSel?.label || val.whereText;
  const sportText = val.which.map(sportLabel).join(", ");
  const summary = [whereText, whenLabel(val.when), sportText]
    .filter(Boolean)
    .join(" · ");

  return (
    <>
      {/* Collapsed trigger — a simple bar (hero) or compact pill (header). */}
      {variant === "pill" ? (
        <motion.button
          layoutId={reduce ? undefined : "search-shell"}
          type="button"
          onClick={() => openExpanded()}
          className={`flex max-w-full items-center gap-2.5 rounded-card border border-line bg-surface py-1 pl-4 pr-1 text-ui font-medium text-ink shadow-card transition-shadow hover:shadow-float ${
            expanded || exiting ? "invisible" : ""
          }`}
        >
          <span className="truncate">{summary || "Suchen"}</span>
          <span className="grid h-7 w-7 shrink-0 place-items-center text-ink">
            <SearchIcon className="text-ui" />
          </span>
        </motion.button>
      ) : (
        <button
          ref={heroTriggerRef}
          type="button"
          onClick={() => openExpanded()}
          className={`flex h-14 w-full items-center gap-3 rounded-card border border-line bg-surface p-1 pl-5 text-left shadow-float ${
            expanded || exiting ? "invisible" : ""
          }`}
        >
          <span
            className={`flex-1 truncate text-body ${
              summary ? "font-medium text-ink" : "text-muted"
            }`}
          >
            {summary || "Jetzt suchen"}
          </span>
          <span className="grid h-12 w-12 shrink-0 place-items-center text-ink">
            <SearchIcon className="text-lead" />
          </span>
        </button>
      )}

      {createPortal(
        <AnimatePresence onExitComplete={() => setExiting(false)}>
          {expanded && (
            <motion.div
              key="overlay"
              role="dialog"
              aria-modal="true"
              aria-label="Suche"
              // Header searches rise to the top. In the landing hero the open
              // stack ends exactly at the collapsed bar's former bottom edge:
              // search shell first, active panel directly underneath.
              className={`fixed inset-0 z-sheet bg-black/25 ${
                variant === "pill" ? "flex items-start justify-center px-4 pt-4 sm:pt-6" : ""
              }`}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: reduce ? 0.07 : expanded ? 0.14 : 0.09, ease: "easeOut" }}
              onClick={collapse}
            >
              <motion.div
                data-testid="desktop-search-stack"
                className="relative w-[760px] max-w-full"
                style={
                  variant === "hero" && heroAnchor
                    ? {
                        position: "absolute",
                        top: heroAnchor.top,
                        left: heroAnchor.left,
                        width: heroAnchor.width,
                        transformOrigin: "center top",
                      }
                    : { transformOrigin: "center top" }
                }
                onClick={(e) => e.stopPropagation()}
                initial={variant === "hero" && !reduce ? { opacity: 0, scale: 0.98 } : false}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={
                  variant === "hero" && !reduce
                    ? { opacity: 0, scale: 0.99, transition: { duration: 0.09, ease: "easeOut" } }
                    : { opacity: 0, transition: { duration: 0.09, ease: "easeOut" } }
                }
                transition={reduce ? { duration: 0.12 } : SPRING}
                onAnimationComplete={() => {
                  if (expanded) setShellReady(true);
                }}
              >
                <div className="relative">
                  {/* Segmented bar — same radius as the tiles (rounded-card). The
                      shared layoutId (pill trigger only) makes this grow out of
                      the header pill instead of fading in mid-page. */}
                  <motion.div
                    layoutId={variant === "pill" && !reduce ? "search-shell" : undefined}
                    className="flex h-14 items-stretch gap-1 rounded-card bg-surface p-1 shadow-float"
                  >
                    {/* Wohin? — the Tippleiste lives in the bar. */}
                    <label
                      onClick={() => setOpen("where")}
                      className="relative flex h-12 flex-1 cursor-text flex-col items-start justify-center rounded-card px-5 py-0 transition-colors hover:bg-band/60"
                    >
                      {open === "where" && (
                        <motion.span
                          layoutId={reduce ? undefined : "search-seg"}
                          className="absolute inset-0 rounded-card bg-band"
                          transition={reduce ? { duration: 0.05 } : PANEL_TRANSITION}
                        />
                      )}
                      <span className="relative z-10 text-caption font-semibold leading-tight text-accent">Wohin?</span>
                      <input
                        ref={whereInputRef}
                        value={val.whereText}
                        onFocus={() => setOpen("where")}
                        onChange={(e) => {
                          const text = e.target.value;
                          setVal((v) => ({ ...v, whereText: text, whereSel: null, whereOpen: false }));
                          if (open !== "where") setOpen("where");
                        }}
                        onKeyDown={onWhereKeyDown}
                        placeholder="Region oder Spot suchen"
                        aria-label="Region oder Spot suchen"
                        aria-expanded={open === "where"}
                        className="search-plain relative z-10 w-full truncate border-0 bg-transparent text-ui leading-tight text-ink outline-none ring-0 placeholder:text-muted focus:outline-none focus:ring-0"
                      />
                    </label>

                    {!whereOnly && (
                      <>
                        <SegmentButton
                          label="Wann?"
                          placeholder="Datum wählen"
                          value={whenLabel(val.when)}
                          active={open === "when"}
                          reduceMotion={Boolean(reduce)}
                          onClick={() => setOpen("when")}
                        />

                        <SegmentButton
                          label="Welche Sportart?"
                          placeholder="Sportart wählen"
                          value={sportText}
                          active={open === "which"}
                          reduceMotion={Boolean(reduce)}
                          onClick={() => setOpen("which")}
                        />
                      </>
                    )}

                    <button
                      type="button"
                      onClick={submit}
                      aria-label="Suchen"
                      className="my-auto flex h-12 w-12 shrink-0 items-center justify-center rounded-card bg-teal text-white transition-colors hover:bg-teal-hover focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
                    >
                      <SearchIcon className="text-lead" />
                    </button>
                  </motion.div>

                  {/* Incoming and outgoing panels cross-fade concurrently with
                      one shared timing, so every switch has the same cadence. */}
                  <AnimatePresence initial={false}>
                    <motion.div
                      key={open}
                      initial={reduce ? false : { opacity: 0, y: 3 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: reduce ? 0 : -2 }}
                      transition={reduce ? { duration: 0.05, ease: "easeOut" } : PANEL_TRANSITION}
                      className={`absolute top-full mt-3 ${
                        open === "when"
                          ? "inset-x-0"
                          : open === "where"
                          ? "left-0 w-1/2"
                          : "right-0 w-1/2"
                      }`}
                    >
                      {/* Every step uses the calendar's content height so the
                          shell no longer jumps vertically while switching. */}
                      <div
                        data-testid="desktop-search-panel"
                        className="h-[350px] overflow-y-auto rounded-card bg-surface p-5 shadow-float"
                      >
                        {open === "where" && (
                          placeLoading ? (
                            <p role="status" className="py-4 text-ui text-muted">Orte werden geladen …</p>
                          ) : placeError && spotItems.length === 0 && regionItems.length === 0 ? (
                            <div role="alert" className="rounded-card bg-band px-4 py-3 text-ui text-ink">
                              <p className="font-semibold">Orte konnten nicht geladen werden.</p>
                              <p className="mt-1 text-muted">{placeError}</p>
                              <button
                                type="button"
                                onClick={() => { reloadSpots(); reloadRegions(); }}
                                className="mt-2 min-h-11 font-semibold text-accent underline underline-offset-4"
                              >
                                Erneut versuchen
                              </button>
                            </div>
                          ) : (
                            <SearchWhere
                              spotItems={spotItems}
                              regionItems={regionItems}
                              activeCol={activeCol}
                              activeRow={activeRow}
                              onPick={pickWhere}
                            />
                          )
                        )}
                        {open === "when" && (
                          <div>
                            <div className="mb-3 flex justify-center">
                              <WhenToggle tab={whenTab} onChange={changeWhenTab} />
                            </div>
                            <SearchWhen
                              tab={whenTab}
                              value={val.when}
                              onChange={(when) => {
                                setVal((v) => ({ ...v, when }));
                                // Guided flow: a concrete date advances to sport.
                                if (when?.mode === "range" && when.from) setOpen("which");
                              }}
                            />
                          </div>
                        )}
                        {open === "which" && (
                          <SportPicker selected={val.which} onToggle={toggleSport} />
                        )}
                      </div>
                    </motion.div>
                  </AnimatePresence>
                </div>
              </motion.div>
            </motion.div>
          )}
        </AnimatePresence>,
        document.body
      )}
    </>
  );
}

function SegmentButton({
  label,
  placeholder,
  value,
  active,
  reduceMotion,
  onClick,
}: {
  label: string;
  placeholder: string;
  value: string;
  active: boolean;
  reduceMotion: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-expanded={active}
      className="relative flex h-12 flex-1 flex-col items-start justify-center rounded-card px-5 py-0 text-left transition-colors hover:bg-band/60"
    >
      {active && (
        <motion.span
          layoutId={reduceMotion ? undefined : "search-seg"}
          className="absolute inset-0 rounded-card bg-band"
          transition={reduceMotion ? { duration: 0.05 } : PANEL_TRANSITION}
        />
      )}
      <span className="relative z-10 text-caption font-semibold leading-tight text-accent">{label}</span>
      <span className={`relative z-10 truncate text-ui leading-tight ${value ? "text-ink" : "text-muted"}`}>
        {value || placeholder}
      </span>
    </button>
  );
}

/** "Welche Sportart?" — a compact multi-select list of the four sports. */
function SportPicker({
  selected,
  onToggle,
}: {
  selected: string[];
  onToggle: (sport: string) => void;
}): ReactNode {
  return (
    <div className="flex flex-col gap-2">
      {SPORT_OPTIONS.map(({ value: sport, Icon }) => {
        const isOn = selected.includes(sport);
        return (
          <button
            key={sport}
            type="button"
            onClick={() => onToggle(sport)}
            aria-pressed={isOn}
            className="flex items-center gap-4 rounded-card px-1.5 py-3 text-left transition-colors hover:bg-band"
          >
            <Icon className="shrink-0 text-heading text-ink" />
            <span className="flex-1 text-body font-medium text-ink">{sportLabel(sport)}</span>
            <span
              className={`grid h-6 w-6 shrink-0 place-items-center rounded-full border transition-colors ${
                isOn ? "border-accent" : "border-line"
              }`}
            >
              {isOn && <span className="h-3 w-3 rounded-full bg-teal" />}
            </span>
          </button>
        );
      })}
    </div>
  );
}
