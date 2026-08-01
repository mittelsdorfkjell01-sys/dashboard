import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useNavigate } from "react-router-dom";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { SearchIcon } from "../lib/icons";
import SearchWhere, { type WherePick } from "./search/SearchWhere";
import SearchWhen from "./search/SearchWhen";
import { addRecent } from "../lib/recentSearches";
import {
  buildSearchParams,
  EMPTY_SEARCH,
  whenLabel,
  type SearchValue,
} from "../lib/searchSubmit";

type Segment = "where" | "when";

/**
 * Airbnb-style search. The "Wohin?" text field (the Tippleiste) lives directly
 * in the bar; typing opens a panel below with the matching Spots/Regionen. Both
 * panels span the full bar width and size to their content (dynamic height,
 * capped at 70vh). Fields never dim — the bar stays crisp above the scrim.
 */
export default function SearchBar() {
  const navigate = useNavigate();
  const reduce = useReducedMotion();
  const [open, setOpen] = useState<Segment | null>(null);
  const [val, setVal] = useState<SearchValue>(EMPTY_SEARCH);
  const barRef = useRef<HTMLDivElement>(null);
  const [rect, setRect] = useState<DOMRect | null>(null);

  // Both panels span the full bar width (measured at open time).
  const openSeg = (s: Segment) => {
    setRect(barRef.current?.getBoundingClientRect() ?? null);
    setOpen(s);
  };
  const close = () => setOpen(null);

  // While open: Esc closes, and page scroll/resize collapse the panel (its
  // position is captured from a rect at open time).
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && close();
    const onScroll = () => close();
    const onResize = () => close();
    window.addEventListener("keydown", onKey);
    window.addEventListener("scroll", onScroll);
    window.addEventListener("resize", onResize);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onResize);
    };
  }, [open]);

  const submit = () => {
    navigate(`/search?${buildSearchParams(val).toString()}`);
    close();
  };

  const pickWhere = (pick: WherePick) => {
    addRecent({ label: pick.label, kind: pick.kind, id: pick.id, country: pick.country });
    setVal((v) => ({
      ...v,
      whereSel: { label: pick.label, kind: pick.kind, id: pick.id },
      whereText: pick.label,
      whereOpen: false,
    }));
    close();
  };

  // Open place axis ("unentschlossen").
  const openWherePlace = () => {
    setVal((v) => ({ ...v, whereOpen: true, whereSel: null, whereText: "unentschlossen" }));
    close();
  };

  return (
    <>
      <div ref={barRef} className="relative">
        <div className="flex flex-col gap-1.5 rounded-3xl border border-line bg-white p-2 sm:flex-row sm:items-stretch sm:gap-1 sm:rounded-2xl">
          {/* Wohin? — the Tippleiste. A <label> so a click anywhere in the field
              (not just on the text) focuses the input; no active tint/box, the
              bar stays white and the input has no border. */}
          <label className="flex flex-1 cursor-text flex-col items-start rounded-2xl px-6 py-2">
            <span className="text-[13px] font-semibold text-teal">Wohin?</span>
            <input
              value={val.whereText}
              onFocus={() => openSeg("where")}
              onChange={(e) => {
                const text = e.target.value;
                setVal((v) => ({ ...v, whereText: text, whereSel: null, whereOpen: false }));
                if (open !== "where") openSeg("where");
              }}
              placeholder="Region oder Spot suchen"
              aria-label="Region oder Spot suchen"
              aria-expanded={open === "where"}
              className="w-full truncate border-0 bg-transparent text-[13px] text-ink outline-none ring-0 placeholder:text-muted focus:outline-none focus:ring-0"
            />
          </label>

          <Divider />

          <Segment
            label="Wann?"
            placeholder="Datum wählen"
            value={whenLabel(val.when)}
            active={open === "when"}
            onClick={() => openSeg("when")}
          />

          <button
            type="button"
            onClick={submit}
            aria-label="Suchen"
            className="my-auto flex h-12 w-full shrink-0 items-center justify-center gap-2 rounded-2xl bg-teal text-[15px] font-medium text-white transition-colors hover:bg-teal-hover sm:ml-3 sm:mr-1 sm:w-12 sm:gap-0"
          >
            <SearchIcon className="text-[20px]" />
            <span className="sm:hidden">Suchen</span>
          </button>
        </div>
      </div>

      {createPortal(
        <AnimatePresence>
          {open && rect && (
            <>
              <motion.div
                key="scrim"
                className="scrim fixed inset-0 z-[1100]"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.18 }}
                onClick={close}
              />
              <motion.div
                key="panel"
                role="dialog"
                aria-modal="false"
                // Seed position/width in `initial` so the panel mounts in place;
                // height is left to the content (dynamic), capped by maxHeight.
                initial={{
                  opacity: 0,
                  y: reduce ? 0 : -8,
                  top: rect.bottom + 12,
                  left: rect.left,
                  width: rect.width,
                }}
                animate={{
                  opacity: 1,
                  y: 0,
                  top: rect.bottom + 12,
                  left: rect.left,
                  width: rect.width,
                }}
                exit={{ opacity: 0, y: reduce ? 0 : -8 }}
                transition={
                  reduce
                    ? { duration: 0 }
                    : {
                        type: "spring",
                        stiffness: 420,
                        damping: 40,
                        mass: 0.7,
                        opacity: { duration: 0.18, ease: "easeOut" },
                      }
                }
                style={{
                  position: "fixed",
                  zIndex: 1150,
                  maxWidth: "calc(100vw - 16px)",
                }}
                className="overflow-hidden rounded-3xl border border-line bg-white"
              >
                <div className="max-h-[46vh] overflow-auto p-5">
                  <motion.div
                    key={open}
                    initial={reduce ? false : { opacity: 0, y: 6 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.18, ease: "easeOut" }}
                  >
                    {open === "where" && (
                      <SearchWhere
                        query={val.whereText}
                        onPick={pickWhere}
                        onOpen={openWherePlace}
                      />
                    )}
                    {open === "when" && (
                      <SearchWhen
                        value={val.when}
                        onChange={(when) => setVal((v) => ({ ...v, when }))}
                      />
                    )}
                  </motion.div>
                </div>
              </motion.div>
            </>
          )}
        </AnimatePresence>,
        document.body
      )}
    </>
  );
}

function Divider() {
  // Vertical hairline between segments on desktop; hidden when the bar stacks.
  return <span className="my-2 hidden w-px self-stretch bg-line sm:block" />;
}

function Segment({
  label,
  placeholder,
  value,
  active,
  onClick,
}: {
  label: string;
  placeholder: string;
  value: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-expanded={active}
      className="flex flex-1 flex-col items-start rounded-2xl px-6 py-2 text-left"
    >
      <span className="text-[13px] font-semibold text-teal">{label}</span>
      <span className={`truncate text-[13px] ${value ? "text-ink" : "text-muted"}`}>
        {value || placeholder}
      </span>
    </button>
  );
}
