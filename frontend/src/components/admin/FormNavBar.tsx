// A floating bottom-center bar with two actions: a section jump menu and
// a page-wide text find — the pattern Vercel's mobile UI uses. Placed here
// rather than on the page's sticky right rail so it stays reachable on any
// viewport width without the operator scrolling back to the top of a long
// form.
//
// The section list is a fixed set (the tiles the spot form declares), and
// the search is Ctrl+F for THIS page: it walks the form's text nodes,
// wraps each hit in a <mark>, and Enter cycles through them. Closing the
// bar removes every wrapper it added, so the DOM is left exactly as it was.

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

// Hard list so the menu order does not depend on DOM traversal — one place
// to reorder, add or rename an entry. Ids match the CollapsibleSection ids
// in AdminSpotForm.
const SECTIONS: { id: string; label: string }[] = [
  { id: "f-basisdaten", label: "Basisdaten" },
  { id: "f-sportarten", label: "Sportarten" },
  { id: "f-kategorien", label: "Kategorien" },
  { id: "f-ausrichtung", label: "Ausrichtung" },
  { id: "f-facilities", label: "Facilities" },
  { id: "f-hero", label: "Header-Bild" },
  { id: "f-galerie", label: "Galerie" },
  { id: "f-gezeiten", label: "Gezeiten" },
  { id: "f-loeschen", label: "Spot löschen" },
];

// Marker class the find-in-page pass wraps every hit with; the active hit
// gets the "…-active" variant. Scoped so the removal pass on close can find
// exactly the nodes it created and nothing else.
const HIT_CLASS = "swd-find-hit";
const HIT_ACTIVE_CLASS = "swd-find-hit-active";
const MENU_ID = "form-nav-menu";
const SEARCH_ID = "form-nav-search";

function scrollToSection(id: string) {
  const el = document.getElementById(id);
  if (!el) return;
  window.dispatchEvent(new CustomEvent("collapsible:open", { detail: { id } }));
  el.scrollIntoView({ behavior: "smooth", block: "start" });
}

// --- find-in-page -----------------------------------------------------------

function findRoot(): HTMLElement {
  // Restrict the search to the form area so nothing in the floating bar
  // itself, the header or the operator's browser chrome shows up as a hit.
  return document.querySelector("form") || document.body;
}

function isSkippable(node: Node): boolean {
  const parent = node.parentElement;
  if (!parent) return true;
  const tag = parent.tagName;
  if (tag === "SCRIPT" || tag === "STYLE" || tag === "NOSCRIPT") return true;
  if (parent.closest(`.${HIT_CLASS}`)) return true;
  // Elements the operator cannot see anyway.
  if (parent.getAttribute("aria-hidden") === "true") return true;
  return false;
}

function highlight(term: string): HTMLElement[] {
  if (!term) return [];
  const root = findRoot();
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
    acceptNode: (node) =>
      isSkippable(node) || !node.nodeValue?.toLowerCase().includes(term.toLowerCase())
        ? NodeFilter.FILTER_REJECT
        : NodeFilter.FILTER_ACCEPT,
  });
  const targets: Text[] = [];
  let current = walker.nextNode() as Text | null;
  while (current) {
    targets.push(current);
    current = walker.nextNode() as Text | null;
  }
  const created: HTMLElement[] = [];
  const lowerTerm = term.toLowerCase();
  for (const text of targets) {
    const value = text.nodeValue || "";
    const lowerValue = value.toLowerCase();
    let cursor = 0;
    const frag = document.createDocumentFragment();
    let hit = lowerValue.indexOf(lowerTerm, cursor);
    if (hit < 0) continue;
    while (hit >= 0) {
      if (hit > cursor) frag.appendChild(document.createTextNode(value.slice(cursor, hit)));
      const mark = document.createElement("mark");
      mark.className = HIT_CLASS;
      mark.textContent = value.slice(hit, hit + term.length);
      frag.appendChild(mark);
      created.push(mark);
      cursor = hit + term.length;
      hit = lowerValue.indexOf(lowerTerm, cursor);
    }
    if (cursor < value.length) frag.appendChild(document.createTextNode(value.slice(cursor)));
    text.parentNode?.replaceChild(frag, text);
  }
  return created;
}

function clearHighlights() {
  const root = findRoot();
  const hits = root.querySelectorAll<HTMLElement>(`.${HIT_CLASS}`);
  hits.forEach((mark) => {
    const parent = mark.parentNode;
    if (!parent) return;
    parent.replaceChild(document.createTextNode(mark.textContent || ""), mark);
    parent.normalize();
  });
}

// --- icons ------------------------------------------------------------------

function IconMenu() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true" className="h-5 w-5">
      <path d="M4 7h16M4 12h16M4 17h16" strokeLinecap="round" />
    </svg>
  );
}

function IconSearch() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true" className="h-5 w-5">
      <circle cx="11" cy="11" r="7" />
      <path d="M20 20l-3.5-3.5" strokeLinecap="round" />
    </svg>
  );
}

function IconClose() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true" className="h-4 w-4">
      <path d="M6 6l12 12M18 6L6 18" strokeLinecap="round" />
    </svg>
  );
}

function IconChevron({ up = false }: { up?: boolean }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true" className={`h-4 w-4 ${up ? "rotate-180" : ""}`}>
      <path d="M6 9l6 6 6-6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

// --- component --------------------------------------------------------------

export default function FormNavBar() {
  const [mode, setMode] = useState<"closed" | "menu" | "search">("closed");
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<HTMLElement[]>([]);
  const [activeIndex, setActiveIndex] = useState(0);
  const searchInputRef = useRef<HTMLInputElement>(null);

  // Rebuild highlights whenever the term changes. The clear pass runs first
  // so a slower typist does not stack multiple <mark> layers.
  useEffect(() => {
    if (mode !== "search") return;
    clearHighlights();
    const term = q.trim();
    if (!term) {
      setHits([]);
      setActiveIndex(0);
      return;
    }
    const created = highlight(term);
    setHits(created);
    setActiveIndex(0);
  }, [q, mode]);

  // Highlight one match at a time and scroll it into view. Kept separate from
  // the build step so cycling with Enter does not rebuild the DOM.
  useEffect(() => {
    if (!hits.length) return;
    hits.forEach((h, i) => {
      if (i === activeIndex) h.classList.add(HIT_ACTIVE_CLASS);
      else h.classList.remove(HIT_ACTIVE_CLASS);
    });
    hits[activeIndex]?.scrollIntoView({ behavior: "smooth", block: "center" });
  }, [hits, activeIndex]);

  // Close cleans everything the search pass added to the DOM.
  const close = useCallback(() => {
    setMode("closed");
    clearHighlights();
    setHits([]);
    setActiveIndex(0);
    setQ("");
  }, []);

  useEffect(() => () => clearHighlights(), []);

  useEffect(() => {
    if (mode === "closed") return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        close();
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [mode, close]);

  useEffect(() => {
    if (mode === "search") setTimeout(() => searchInputRef.current?.focus(), 0);
  }, [mode]);

  const total = hits.length;
  const positionLabel = useMemo(
    () => (total ? `${activeIndex + 1} / ${total}` : q ? "0 / 0" : ""),
    [activeIndex, total, q],
  );

  const jumpTo = (id: string) => {
    setMode("closed");
    setTimeout(() => scrollToSection(id), 0);
  };

  const cycle = (dir: 1 | -1) => {
    if (!hits.length) return;
    setActiveIndex((idx) => (idx + dir + hits.length) % hits.length);
  };

  return (
    <>
      {/* Inline style so the find-in-page marks land in the cascade regardless
          of Tailwind's purge — the classes are dynamic and would otherwise be
          stripped from the production build. */}
      <style>{`
        .${HIT_CLASS} {
          background-color: rgba(250, 204, 21, 0.55);
          color: inherit;
          border-radius: 2px;
          padding: 0 1px;
        }
        .${HIT_ACTIVE_CLASS} {
          background-color: rgba(251, 146, 60, 0.9);
          outline: 1px solid rgba(154, 52, 18, 0.9);
        }
        .swd-find-input:focus { outline: none; box-shadow: none; }
      `}</style>

      {mode === "menu" && (
        <div
          role="dialog"
          aria-modal="false"
          aria-label="Abschnittsmenü"
          id={MENU_ID}
          className="fixed bottom-24 left-1/2 z-[1001] w-[min(92vw,340px)] -translate-x-1/2 rounded-xl border border-admin-border bg-admin-surface p-2 shadow-xl"
        >
          <div className="flex items-center justify-between gap-2 px-2 py-1">
            <span className="text-caption font-semibold uppercase tracking-wide text-admin-muted">
              Springe zu
            </span>
            <button
              type="button"
              onClick={close}
              aria-label="Schließen"
              className="rounded p-1 text-admin-fg2 hover:bg-admin-hover"
            >
              <IconClose />
            </button>
          </div>
          <ul>
            {SECTIONS.map((it) => (
              <li key={it.id}>
                <button
                  type="button"
                  onClick={() => jumpTo(it.id)}
                  className="flex w-full items-center justify-between rounded-md px-3 py-2 text-left text-ui text-admin-fg transition-colors hover:bg-admin-hover"
                >
                  <span>{it.label}</span>
                  <span aria-hidden className="text-caption text-admin-muted">↵</span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}

      {mode === "search" && (
        <div
          role="dialog"
          aria-modal="false"
          aria-label="Suche"
          id={SEARCH_ID}
          className="fixed bottom-24 left-1/2 z-[1001] flex w-[min(92vw,420px)] -translate-x-1/2 items-center gap-2 rounded-full border border-admin-border bg-admin-surface px-3 py-1.5 shadow-xl"
        >
          <IconSearch />
          <input
            ref={searchInputRef}
            type="text"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                cycle(e.shiftKey ? -1 : 1);
              }
            }}
            placeholder="Auf der Seite suchen"
            className="swd-find-input flex-1 border-0 bg-transparent py-1 text-ui text-admin-fg placeholder:text-admin-muted"
          />
          {positionLabel && (
            <span className="shrink-0 text-caption tabular-nums text-admin-muted">{positionLabel}</span>
          )}
          <div className="flex shrink-0 items-center gap-0.5">
            <button
              type="button"
              onClick={() => cycle(-1)}
              disabled={!hits.length}
              aria-label="Vorheriger Treffer"
              className="grid h-7 w-7 place-items-center rounded text-admin-fg2 hover:bg-admin-hover disabled:opacity-40"
            >
              <IconChevron up />
            </button>
            <button
              type="button"
              onClick={() => cycle(1)}
              disabled={!hits.length}
              aria-label="Nächster Treffer"
              className="grid h-7 w-7 place-items-center rounded text-admin-fg2 hover:bg-admin-hover disabled:opacity-40"
            >
              <IconChevron />
            </button>
            <button
              type="button"
              onClick={close}
              aria-label="Schließen"
              className="grid h-7 w-7 place-items-center rounded text-admin-fg2 hover:bg-admin-hover"
            >
              <IconClose />
            </button>
          </div>
        </div>
      )}

      <div className="pointer-events-none fixed bottom-6 left-0 right-0 z-[1000] flex justify-center px-4">
        <div className="pointer-events-auto flex items-center gap-1 rounded-full border border-admin-border bg-admin-surface p-1 shadow-lg">
          <button
            type="button"
            onClick={() => setMode(mode === "menu" ? "closed" : "menu")}
            aria-label="Abschnittsmenü öffnen"
            aria-expanded={mode === "menu"}
            aria-controls={MENU_ID}
            className={`grid h-10 w-10 place-items-center rounded-full transition-colors ${
              mode === "menu" ? "bg-admin-hover text-admin-fg" : "text-admin-fg2 hover:bg-admin-hover"
            }`}
          >
            <IconMenu />
          </button>
          <button
            type="button"
            onClick={() => setMode(mode === "search" ? "closed" : "search")}
            aria-label="Suche öffnen"
            aria-expanded={mode === "search"}
            aria-controls={SEARCH_ID}
            className={`grid h-10 w-10 place-items-center rounded-full transition-colors ${
              mode === "search" ? "bg-admin-hover text-admin-fg" : "text-admin-fg2 hover:bg-admin-hover"
            }`}
          >
            <IconSearch />
          </button>
        </div>
      </div>
    </>
  );
}
