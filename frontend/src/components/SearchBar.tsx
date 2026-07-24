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

// Fixed panel height so every segment's dropdown is exactly the same size (no
// jump when switching fields); taller content (e.g. the "Wohin?" list) scrolls
// inside. Capped at 70vh on short screens via maxHeight.
const PANEL_H = 400;

/**
 * Airbnb-style 3-segment search (Frame_2–5). The bar stays crisp above a
 * page-dimming scrim; the active panel opens below it. Scrim + panel are
 * portalled to <body> so no hero `overflow-hidden`/z-index can clip them — the
 * bar's wrapper in Landing carries a z-index above the scrim so it isn't dimmed.
 */
export default function SearchBar() {
  const navigate = useNavigate();
  const reduce = useReducedMotion();
  const [open, setOpen] = useState<Segment | null>(null);
  const [val, setVal] = useState<SearchValue>(EMPTY_SEARCH);
  const barRef = useRef<HTMLDivElement>(null);
  const whereRef = useRef<HTMLButtonElement>(null);
  const [rect, setRect] = useState<DOMRect | null>(null);

  // Panel geometry: "Wann?" needs the full bar width for its two-month calendar;
  // "Wohin?" and "Welche?" only span their own field.
  const openSeg = (s: Segment, el: HTMLElement | null) => {
    const source = s === "when" ? barRef.current : el;
    setRect(source?.getBoundingClientRect() ?? null);
    setOpen(s);
  };
  const close = () => setOpen(null);

  // While open: Esc closes, and scroll/resize collapse the panel (positions are
  // captured at open time).
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && close();
    // Close when the *page* scrolls (the panel is fixed-positioned from a rect
    // captured at open time). No capture, so scrolling *inside* the panel's own
    // list (e.g. the "Wohin?" results) does not bubble here and keep it open.
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

  const dim = (seg: Segment) => !!open && open !== seg;

  return (
    <>
      <div ref={barRef} className="relative">
        <div className="flex flex-col gap-1.5 rounded-3xl bg-white p-2 shadow-card sm:flex-row sm:items-stretch sm:gap-1 sm:rounded-full">
          {/* Wohin? — trigger; the text input lives in the panel below. */}
          <button
            type="button"
            ref={whereRef}
            onClick={() => openSeg("where", whereRef.current)}
            aria-expanded={open === "where"}
            className={`flex flex-1 flex-col items-start rounded-full px-6 py-2 text-left transition-all ${
              open === "where" ? "shadow-pill" : ""
            } ${dim("where") ? "opacity-55" : ""}`}
          >
            <span className="text-[13px] font-semibold text-teal">Wohin?</span>
            <span
              className={`truncate text-[13px] ${
                val.whereText ? "text-ink" : "text-muted"
              }`}
            >
              {val.whereText || "Region oder Spot suchen"}
            </span>
          </button>

          <Divider />

          <Segment
            label="Wann?"
            placeholder="Datum wählen"
            value={whenLabel(val.when)}
            active={open === "when"}
            dim={dim("when")}
            onClick={(el) => openSeg("when", el)}
          />

          <button
            type="button"
            onClick={submit}
            aria-label="Suchen"
            className="my-auto flex h-12 w-full shrink-0 items-center justify-center gap-2 rounded-full bg-teal text-[15px] font-medium text-white transition-colors hover:bg-teal-hover sm:ml-3 sm:mr-1 sm:w-12 sm:gap-0"
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
                // Seed position/width in `initial` too so the panel mounts in
                // place (no fly-in from <body>'s default corner); switching
                // fields keeps the element mounted, so those still morph.
                initial={{
                  opacity: 0,
                  y: reduce ? 0 : -8,
                  top: rect.bottom + 12,
                  left: rect.left,
                  width: rect.width,
                  height: PANEL_H,
                }}
                animate={{
                  opacity: 1,
                  y: 0,
                  top: rect.bottom + 12,
                  left: rect.left,
                  width: rect.width,
                  height: PANEL_H,
                }}
                exit={{ opacity: 0, y: reduce ? 0 : -8 }}
                transition={
                  reduce
                    ? { duration: 0 }
                    : {
                        // Spring the box (position/width/height) between fields;
                        // fade opacity on the quicker linear track.
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
                  maxHeight: "70vh",
                  maxWidth: "calc(100vw - 16px)",
                }}
                className="overflow-hidden rounded-3xl bg-white shadow-card"
              >
                <div className="h-full overflow-auto p-6">
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
                        onQueryChange={(text) =>
                          setVal((v) => ({
                            ...v,
                            whereText: text,
                            whereSel: null,
                            whereOpen: false,
                          }))
                        }
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
  dim,
  onClick,
}: {
  label: string;
  placeholder: string;
  value: string;
  active: boolean;
  dim: boolean;
  onClick: (el: HTMLElement) => void;
}) {
  return (
    <button
      type="button"
      onClick={(e) => onClick(e.currentTarget)}
      aria-expanded={active}
      className={`flex flex-1 flex-col items-start rounded-full px-6 py-2 text-left transition-all ${
        active ? "shadow-pill" : ""
      } ${dim ? "opacity-55" : ""}`}
    >
      <span className="text-[13px] font-semibold text-teal">{label}</span>
      <span className={`truncate text-[13px] ${value ? "text-ink" : "text-muted"}`}>
        {value || placeholder}
      </span>
    </button>
  );
}
