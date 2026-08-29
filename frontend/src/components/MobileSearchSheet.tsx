import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { useNavigate } from "react-router-dom";
import {
  AnimatePresence,
  motion,
  useDragControls,
  useReducedMotion,
} from "framer-motion";
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

// One shared spring so every motion in the sheet feels of a piece.
const SPRING = { type: "spring" as const, stiffness: 420, damping: 34, mass: 0.9 };
// Staggered tile entrance on open.
const TILES = { hidden: {}, show: { transition: { staggerChildren: 0.06, delayChildren: 0.05 } } };
const TILE = {
  hidden: { opacity: 0, y: 14 },
  show: { opacity: 1, y: 0, transition: SPRING },
};

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
}: {
  open: boolean;
  onClose: () => void;
  /** Viewport-y of the collapsed pill, so the sheet grows out of it (Airbnb). */
  originY?: number | null;
}) {
  const navigate = useNavigate();
  const reduce = useReducedMotion();
  const [val, setVal] = useState<SearchValue>(EMPTY_SEARCH);
  // Which accordion section is expanded (null = all collapsed to equal tiles).
  const [section, setSection] = useState<Section>(null);
  const [whenTab, setWhenTab] = useState<WhenTab>("date");

  // Lock body scroll while open; Esc closes.
  useEffect(() => {
    if (!open) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", onKey);
    };
  }, [open, onClose]);

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

  // Swipe-to-close: dragging the grab handle drives the sheet's y.
  const dragControls = useDragControls();
  // Delayed autofocus + auto-scroll refs.
  const whereInputRef = useRef<HTMLInputElement>(null);

  // Focus the "Wohin?" field only after its tile has finished expanding, so the
  // keyboard does not fight the open animation.
  useEffect(() => {
    if (!open || section !== "where") return;
    const t = window.setTimeout(() => whereInputRef.current?.focus(), 320);
    return () => window.clearTimeout(t);
  }, [open, section]);

  // Bring the freshly opened tile fully into view above the action bar.
  useEffect(() => {
    if (!open || !section) return;
    const t = window.setTimeout(() => {
      document
        .getElementById(`msheet-${section}`)
        ?.scrollIntoView({ block: "nearest", behavior: "smooth" });
    }, 300);
    return () => window.clearTimeout(t);
  }, [open, section]);

  return createPortal(
    <AnimatePresence>
      {open && (
        <motion.div
          key="sheet"
          className="fixed inset-0 z-[1300] flex flex-col bg-page"
          role="dialog"
          aria-modal="true"
          aria-label="Suche"
          initial={reduce ? { opacity: 0 } : { y: "100%" }}
          animate={reduce ? { opacity: 1 } : { y: 0 }}
          exit={reduce ? { opacity: 0 } : { y: "100%" }}
          transition={reduce ? { duration: 0.15 } : SPRING}
          drag="y"
          dragListener={false}
          dragControls={dragControls}
          dragConstraints={{ top: 0 }}
          dragElastic={{ top: 0, bottom: 0.2 }}
          dragSnapToOrigin
          onDragEnd={(_, info) => {
            if (info.offset.y > 120 || info.velocity.y > 600) onClose();
          }}
        >
          {/* Grab handle — swipe down to close. */}
          <div
            className="flex cursor-grab justify-center pt-2 active:cursor-grabbing"
            style={{ touchAction: "none" }}
            onPointerDown={(e) => dragControls.start(e)}
          >
            <span className="h-1.5 w-10 rounded-full bg-line" />
          </div>

          {/* Header — a clear close + title anchor the screen. The whole row is
              a drag zone (together with the grab handle), so a pull-down here
              closes the sheet; the close button opts out so its tap still fires. */}
          <div
            className="flex items-center gap-3 px-4 py-3"
            style={{ touchAction: "none" }}
            onPointerDown={(e) => dragControls.start(e)}
          >
            <button
              type="button"
              onClick={onClose}
              onPointerDown={(e) => e.stopPropagation()}
              aria-label="Schließen"
              className="grid h-11 w-11 place-items-center rounded-full border border-line text-ink transition-colors hover:bg-band"
            >
              <CloseIcon className="text-body" />
            </button>
            <span className="text-body font-semibold text-ink">Suchen</span>
          </div>

          {/* Tiles — top-aligned; content sizes to itself and the whole area
              scrolls, so nothing lives in a cramped inner scroll box. */}
          <div data-lenis-prevent className="min-h-0 flex-1 overflow-y-auto px-4 pb-4">
            <motion.div
              variants={TILES}
              initial={reduce ? false : "hidden"}
              animate="show"
              className="mx-auto flex w-full max-w-[520px] flex-col gap-3"
            >
              {/* Wohin? */}
              <motion.div variants={TILE} id="msheet-where">
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
                          className="flex items-center gap-3 rounded-xl px-1.5 py-2.5 text-left transition-colors hover:bg-band active:bg-band"
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
              </motion.div>

              {/* Wann? — the Datum/flexibel toggle sits in the tile header. */}
              <motion.div variants={TILE} id="msheet-when">
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
              </motion.div>

              {/* Welche Sportart? */}
              <motion.div variants={TILE} id="msheet-which">
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
                        className="flex items-center gap-4 rounded-xl px-1.5 py-3 text-left transition-colors hover:bg-band"
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
              </motion.div>
            </motion.div>
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
        </motion.div>
      )}
    </AnimatePresence>,
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
  return (
    <div className="overflow-hidden rounded-3xl bg-surface shadow-float">
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
      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            key="body"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.3, ease: [0.22, 1, 0.36, 1] }}
            className="overflow-hidden"
          >
            <div className="px-5 pb-5">{children}</div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
