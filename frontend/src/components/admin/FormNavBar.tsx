// A floating bottom-center bar with two actions: a section jump menu and
// a section search — the pattern Vercel's mobile UI uses. Placed here rather
// than on the page's sticky right rail so it stays reachable on any viewport
// width without the operator scrolling back to the top of a long form.
//
// The section list is discovered at open-time by scanning the DOM for the
// ids the form's CollapsibleSection blocks carry (`f-*`). No registry: the
// form declares its sections once (as normal DOM), the nav reads them.

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

type Item = { id: string; label: string };

const MENU_ID = "form-nav-menu";
const SEARCH_ID = "form-nav-search";

function collectSections(): Item[] {
  if (typeof document === "undefined") return [];
  const nodes = document.querySelectorAll<HTMLElement>('section[id^="f-"], [id^="f-"]');
  const seen = new Set<string>();
  const out: Item[] = [];
  nodes.forEach((el) => {
    const id = el.id;
    if (!id || seen.has(id)) return;
    seen.add(id);
    const h = el.querySelector("h2, h3");
    const label = (h?.textContent || id.replace(/^f-/, "")).trim();
    if (label) out.push({ id, label });
  });
  return out;
}

function scrollToSection(id: string) {
  const el = document.getElementById(id);
  if (!el) return;
  // Nudge CollapsibleSection to expand before we scroll — landing on a
  // collapsed block would show only a header.
  window.dispatchEvent(new CustomEvent("collapsible:open", { detail: { id } }));
  el.scrollIntoView({ behavior: "smooth", block: "start" });
}

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

export default function FormNavBar() {
  const [mode, setMode] = useState<"closed" | "menu" | "search">("closed");
  const [q, setQ] = useState("");
  const [items, setItems] = useState<Item[]>([]);
  const searchInputRef = useRef<HTMLInputElement>(null);

  const refresh = useCallback(() => setItems(collectSections()), []);

  useEffect(() => {
    if (mode === "closed") return;
    refresh();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setMode("closed");
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [mode, refresh]);

  useEffect(() => {
    if (mode === "search") {
      // Autofocus so the operator can start typing immediately.
      setTimeout(() => searchInputRef.current?.focus(), 0);
    }
    if (mode === "closed") setQ("");
  }, [mode]);

  const filtered = useMemo(() => {
    const term = q.trim().toLowerCase();
    if (!term) return items;
    return items.filter((it) => it.label.toLowerCase().includes(term));
  }, [items, q]);

  const jumpTo = (id: string) => {
    setMode("closed");
    // Delay so the panel unmount doesn't fight the scroll target.
    setTimeout(() => scrollToSection(id), 0);
  };

  return (
    <>
      {mode !== "closed" && (
        <div
          role="dialog"
          aria-modal="false"
          aria-label={mode === "menu" ? "Abschnittsmenü" : "Abschnittssuche"}
          id={mode === "menu" ? MENU_ID : SEARCH_ID}
          className="fixed bottom-24 left-1/2 z-50 w-[min(92vw,380px)] -translate-x-1/2 rounded-xl border border-admin-border bg-admin-surface p-2 shadow-xl"
        >
          <div className="flex items-center justify-between gap-2 px-2 py-1">
            <span className="text-caption font-semibold uppercase tracking-wide text-admin-muted">
              {mode === "menu" ? "Springe zu" : "Suche im Formular"}
            </span>
            <button
              type="button"
              onClick={() => setMode("closed")}
              aria-label="Schließen"
              className="rounded p-1 text-admin-fg2 hover:bg-admin-hover"
            >
              <IconClose />
            </button>
          </div>
          {mode === "search" && (
            <input
              ref={searchInputRef}
              type="search"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Abschnitt suchen…"
              className="mb-2 w-full rounded-md border border-admin-border bg-admin-bg px-3 py-1.5 text-ui text-admin-fg outline-none focus:border-admin-primary"
            />
          )}
          <ul className="max-h-[50vh] overflow-y-auto">
            {filtered.length === 0 ? (
              <li className="px-3 py-4 text-center text-caption text-admin-muted">
                Nichts gefunden.
              </li>
            ) : (
              filtered.map((it) => (
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
              ))
            )}
          </ul>
        </div>
      )}

      <div className="pointer-events-none fixed bottom-6 left-0 right-0 z-40 flex justify-center px-4">
        <div className="pointer-events-auto flex items-center gap-1 rounded-full border border-admin-border bg-admin-surface p-1 shadow-lg">
          <button
            type="button"
            onClick={() => setMode(mode === "menu" ? "closed" : "menu")}
            aria-label="Abschnittsmenü öffnen"
            aria-expanded={mode === "menu"}
            aria-controls={MENU_ID}
            className={`grid h-10 w-10 place-items-center rounded-full transition-colors ${
              mode === "menu" ? "bg-admin-primary text-admin-primary-fg" : "text-admin-fg2 hover:bg-admin-hover"
            }`}
          >
            <IconMenu />
          </button>
          <button
            type="button"
            onClick={() => setMode(mode === "search" ? "closed" : "search")}
            aria-label="Abschnittssuche öffnen"
            aria-expanded={mode === "search"}
            aria-controls={SEARCH_ID}
            className={`grid h-10 w-10 place-items-center rounded-full transition-colors ${
              mode === "search" ? "bg-admin-primary text-admin-primary-fg" : "text-admin-fg2 hover:bg-admin-hover"
            }`}
          >
            <IconSearch />
          </button>
        </div>
      </div>
    </>
  );
}
