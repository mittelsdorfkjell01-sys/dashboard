import { useEffect, useMemo, useState } from "react";
import { createPortal } from "react-dom";
import { useNavigate } from "react-router-dom";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import {
  KitesurfIcon,
  MapIcon,
  PinIcon,
  SearchIcon,
  SurfIcon,
  WindsurfIcon,
  WingIcon,
} from "../lib/icons";
import MobileSearchWhen from "./MobileSearchWhen";
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
  originY,
}: {
  open: boolean;
  onClose: () => void;
  /** Viewport-y of the collapsed pill, so the sheet grows out of it (Airbnb). */
  originY?: number | null;
}) {
  const navigate = useNavigate();
  const reduce = useReducedMotion();
  const [val, setVal] = useState<SearchValue>(EMPTY_SEARCH);
  // Which accordion section is expanded. "Wohin?" leads, like Airbnb.
  const [section, setSection] = useState<Section>("where");

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

  // Opening always starts a fresh search from the leading section.
  useEffect(() => {
    if (open) {
      setVal(EMPTY_SEARCH);
      setSection("where");
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

  // "Alles löschen": clear and collapse back to the small search pill.
  const reset = () => {
    setVal(EMPTY_SEARCH);
    setSection("where");
    onClose();
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

  return createPortal(
    <AnimatePresence>
      {open && (
        <motion.div
          key="sheet"
          className="fixed inset-0 z-[1300] flex flex-col"
          role="dialog"
          aria-modal="true"
          aria-label="Suche"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.2 }}
        >
          {/* Backdrop — keeps the hero visible, taps close. */}
          <button
            type="button"
            aria-label="Suche schließen"
            className="absolute inset-0 bg-black/15"
            onClick={onClose}
          />

          {/* Card stack — grows out of the pill's position (Airbnb), scrolls if
              it outgrows the viewport. */}
          <motion.div
            data-lenis-prevent
            className="relative flex-1 overflow-y-auto px-4 pb-6 pt-[13vh]"
            style={{ transformOrigin: originY != null ? `50% ${originY}px` : "50% 82%" }}
            initial={reduce ? false : { opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={
              reduce
                ? { duration: 0 }
                : { type: "spring", stiffness: 380, damping: 34, mass: 0.9 }
            }
          >
            <div className="mx-auto flex w-full max-w-[520px] flex-col gap-3">
              {/* Wohin? */}
              {section === "where" ? (
                <section className="rounded-3xl bg-surface p-5 shadow-float">
                  <p className="text-[17px] font-semibold text-teal">Wohin?</p>
                  <input
                    // eslint-disable-next-line jsx-a11y/no-autofocus
                    autoFocus
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
                    className="search-plain mt-1 w-full border-0 bg-transparent text-[16px] text-ink outline-none ring-0 placeholder:text-muted focus:outline-none focus:ring-0"
                  />
                  <div className="mt-4 max-h-[46vh] overflow-y-auto">
                    {items.length ? (
                      <div className="flex flex-col">
                        {items.map((it) => (
                          <button
                            key={it.key}
                            type="button"
                            onClick={() => pickWhere(it)}
                            className="flex items-center gap-3 rounded-xl px-1.5 py-2.5 text-left transition-colors hover:bg-band active:bg-band"
                          >
                            <span className="flex w-7 shrink-0 justify-center text-ink">
                              {it.kind === "spot" ? (
                                <PinIcon className="text-[22px]" />
                              ) : (
                                <MapIcon className="text-[22px]" />
                              )}
                            </span>
                            <span className="min-w-0">
                              <span className="block truncate text-[16px] font-medium text-ink">
                                {it.label}
                              </span>
                              {it.subtitle && (
                                <span className="block truncate text-[13px] text-muted">
                                  {it.subtitle}
                                </span>
                              )}
                            </span>
                          </button>
                        ))}
                      </div>
                    ) : (
                      <p className="px-1.5 py-2 text-[14px] text-muted">
                        Keine Treffer.
                      </p>
                    )}
                  </div>
                </section>
              ) : (
                <CollapsedRow
                  label="Wohin?"
                  value={whereValue}
                  placeholder="Region oder Spot suchen"
                  onClick={() => setSection("where")}
                />
              )}

              {/* Wann? */}
              {section === "when" ? (
                <section className="rounded-3xl bg-surface p-5 shadow-float">
                  <MobileSearchWhen
                    value={val.when}
                    onChange={(when) => setVal((v) => ({ ...v, when }))}
                  />
                </section>
              ) : (
                <CollapsedRow
                  label="Wann?"
                  value={whenLabel(val.when)}
                  placeholder="Zeitraum auswählen"
                  onClick={() => setSection("when")}
                />
              )}

              {/* Welche Sportart? */}
              {section === "which" ? (
                <section className="rounded-3xl bg-surface p-5 shadow-float">
                  <p className="text-[17px] font-semibold text-teal">Welche Sportart?</p>
                  <div className="mt-3 flex flex-col">
                    {SPORT_OPTIONS.map(({ value: sport, Icon }) => {
                      const selected = val.which.includes(sport);
                      return (
                        <button
                          key={sport}
                          type="button"
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
                          <Icon className="shrink-0 text-[26px] text-ink" />
                          <span className="flex-1 text-[16px] font-medium text-ink">
                            {sportLabel(sport)}
                          </span>
                          <span
                            className={`grid h-6 w-6 shrink-0 place-items-center rounded-full border transition-colors ${
                              selected ? "border-teal" : "border-line"
                            }`}
                          >
                            {selected && <span className="h-3 w-3 rounded-full bg-teal" />}
                          </span>
                        </button>
                      );
                    })}
                  </div>
                </section>
              ) : (
                <CollapsedRow
                  label="Welche Sportart?"
                  value={val.which.map(sportLabel).join(", ")}
                  placeholder="Wähle deine Sportart aus"
                  onClick={() => setSection("which")}
                />
              )}

              {/* Actions */}
              <div className="mt-1 grid grid-cols-2 gap-3">
                <button
                  type="button"
                  onClick={reset}
                  className="min-h-[56px] rounded-3xl bg-surface px-4 text-[15px] font-medium text-ink shadow-float transition-colors hover:bg-band"
                >
                  Alles löschen
                </button>
                <button
                  type="button"
                  onClick={submit}
                  className="inline-flex min-h-[56px] items-center justify-center gap-2 rounded-3xl bg-surface px-4 text-[15px] font-medium text-teal shadow-float transition-colors hover:bg-band"
                >
                  <SearchIcon className="text-[18px]" />
                  Suchen
                </button>
              </div>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>,
    document.body
  );
}

/**
 * A collapsed accordion row: label left, current value (or placeholder) right.
 * Inert when `onClick` is omitted — the state for sections whose picker has not
 * been built yet.
 */
function CollapsedRow({
  label,
  value,
  placeholder,
  onClick,
}: {
  label: string;
  value: string;
  placeholder: string;
  onClick?: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={!onClick}
      className="flex w-full items-center justify-between gap-3 rounded-3xl bg-surface px-5 py-4 text-left shadow-float transition-colors enabled:hover:bg-band disabled:cursor-default"
    >
      <span className="shrink-0 text-[15px] font-medium text-ink">{label}</span>
      <span className="min-w-0 truncate text-[15px] text-muted">
        {value || placeholder}
      </span>
    </button>
  );
}
