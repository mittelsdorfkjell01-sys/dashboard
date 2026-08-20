// Media picker overlay — ONE component for spots and regions.
//
// The differences between the two are data, not code: the context line, the
// tab order and the search chips all come from props or from the server's
// context endpoint. There is no second code path, and adding a third entity
// type would not create one either.
//
// What makes this worth building is not the image search. It is that adopting
// a photo writes a complete, correct rights record without anybody typing it.

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ApiError,
  adoptMedia,
  getMediaContext,
  searchMedia,
  type MediaContext,
} from "../../../lib/api";
import {
  adoptLabel,
  isUsable,
  masonryColumns,
  nextIndex,
  tabLabel,
  tabOrder,
  type MediaEntityType,
  type MediaItem,
  type MediaRole,
  type ProviderKey,
  type TabState,
} from "../../../lib/mediaPicker";
import Modal from "../../ui/Modal";
import { Button } from "../ui";
import MediaTile from "./MediaTile";
import PreviewPanel from "./PreviewPanel";
import LicenseCard from "./LicenseCard";

const COLUMN_COUNT = 3;
const CHIP_DEBOUNCE_MS = 250;

const EMPTY_TAB: TabState = {
  status: "ok",
  items: [],
  total: 0,
  loading: true,
};

export default function MediaPicker({
  entityType,
  entityId,
  open,
  initialRole = "hero",
  onClose,
  onAdopted,
}: {
  entityType: MediaEntityType;
  entityId: string;
  open: boolean;
  /** Role is fixed by the caller (Header-Bild vs Galerie) — the operator
   *  never toggles inside the picker. In gallery mode multiple tiles can
   *  be picked at once and all get adopted in a single confirm. */
  initialRole?: MediaRole;
  onClose: () => void;
  /** Fired after a successful adoption so the form can reload its record. */
  onAdopted: (result: { role: MediaRole; warnings: string[] }) => void;
}) {
  const providers = useMemo(() => tabOrder(entityType), [entityType]);
  // The parent decides which role — hero is single-select, gallery is
  // multi-select. No in-picker toggle.
  const role: MediaRole = initialRole;

  const [context, setContext] = useState<MediaContext | null>(null);
  const [query, setQuery] = useState("");
  const [freeText, setFreeText] = useState("");
  const [activeTab, setActiveTab] = useState<ProviderKey>(providers[0]);
  const [tabs, setTabs] = useState<Record<string, TabState>>({});
  // Selection is always an array; hero limits it to one, gallery allows many.
  // Order matters for the adopt loop (first pick becomes the preview subject).
  const [selection, setSelection] = useState<MediaItem[]>([]);
  const [focal, setFocal] = useState({ x: 50, y: 50 });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const primary = selection[0] ?? null;
  const itemKey = (item: MediaItem) => `${item.provider}:${item.external_id}`;
  const isPicked = (item: MediaItem) =>
    selection.some((it) => itemKey(it) === itemKey(item));

  const abortRef = useRef<AbortController | null>(null);
  // Separate controller for the per-tab reload button, so reloading one tab
  // never cancels the other tabs' in-flight bulk-search requests.
  const reloadAbortRef = useRef<AbortController | null>(null);
  const resultsRef = useRef<HTMLDivElement>(null);
  const outerScrollRef = useRef<HTMLDivElement>(null);

  // --- context: chips, coordinates, title -----------------------------------
  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    setError(null);
    getMediaContext(entityType, entityId)
      .then((ctx) => {
        if (cancelled) return;
        setContext(ctx);
        // The first chip is active immediately: the operator opens the overlay
        // onto populated tabs and types nothing.
        setQuery(ctx.suggestions[0] ?? ctx.title);
        setFreeText(ctx.suggestions[0] ?? ctx.title);
      })
      .catch((err) =>
        setError(err instanceof ApiError ? err.message : "Kontext konnte nicht geladen werden.")
      );
    return () => {
      cancelled = true;
    };
  }, [open, entityType, entityId]);

  // --- search: every tab, one request each ----------------------------------
  // The chip is shared across tabs, so switching tabs keeps the search and
  // costs nothing. Debounced because each chip change is one upstream request
  // per provider, and Unsplash's demo tier is 50 per hour.
  // One provider's fetch, shared by the bulk search (all tabs at once) and
  // the per-tab reload button (just the active one — for when a provider's
  // tab silently failed to populate after a fast tab switch).
  const fetchProvider = useCallback(
    (provider: ProviderKey, searchQuery: string, ctx: MediaContext, signal: AbortSignal) => {
      const isNearby = provider === "nearby";
      if (isNearby && (ctx.lat == null || ctx.lon == null)) {
        setTabs((prev) => ({
          ...prev,
          [provider]: {
            status: "disabled",
            items: [],
            total: 0,
            loading: false,
            message: "Keine Koordinaten hinterlegt.",
          },
        }));
        return;
      }
      setTabs((prev) => ({ ...prev, [provider]: { ...EMPTY_TAB } }));
      searchMedia(
        {
          provider,
          q: searchQuery,
          role,
          lat: isNearby ? ctx.lat : undefined,
          lon: isNearby ? ctx.lon : undefined,
        },
        signal
      )
        .then((response) => {
          setTabs((prev) => ({
            ...prev,
            [provider]: {
              status: response.status,
              items: response.items,
              total: response.total,
              loading: false,
              message: response.meta.message,
              budget: response.meta.budget,
            },
          }));
        })
        .catch((err) => {
          if (signal.aborted) return;
          setTabs((prev) => ({
            ...prev,
            [provider]: {
              status: "error",
              items: [],
              total: 0,
              loading: false,
              message: err instanceof ApiError ? err.message : "Fehler",
            },
          }));
        });
    },
    // `role` is intentionally excluded: the server does not vary results by
    // role, so toggling Hero/Galerie must not refetch.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    []
  );

  const runSearch = useCallback(
    (searchQuery: string, ctx: MediaContext) => {
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;
      providers.forEach((provider) => fetchProvider(provider, searchQuery, ctx, controller.signal));
    },
    [providers, fetchProvider]
  );

  // Reload just the active tab — its own controller so it can't cancel the
  // other tabs' in-flight requests.
  const reloadActiveTab = () => {
    if (!context || !query) return;
    reloadAbortRef.current?.abort();
    const controller = new AbortController();
    reloadAbortRef.current = controller;
    fetchProvider(activeTab, query, context, controller.signal);
  };

  useEffect(() => {
    if (!open || !context || !query) return;
    const timer = window.setTimeout(() => runSearch(query, context), CHIP_DEBOUNCE_MS);
    return () => window.clearTimeout(timer);
  }, [open, context, query, runSearch]);

  useEffect(() => () => {
    abortRef.current?.abort();
    reloadAbortRef.current?.abort();
  }, []);

  // Switching libraries (tabs) always starts scrolled to the top of the
  // results — otherwise a scroll position from the previous tab carries
  // over and the operator lands mid-grid on an unrelated set of photos.
  useEffect(() => {
    resultsRef.current?.scrollTo({ top: 0 });
    outerScrollRef.current?.scrollTo({ top: 0 });
  }, [activeTab]);

  // Reset transient state whenever the overlay closes, so nothing reopens
  // mid-flow with a stale selection.
  useEffect(() => {
    if (open) return;
    setSelection([]);
    setFocal({ x: 50, y: 50 });
    setError(null);
    setNotice(null);
    setTabs({});
  }, [open]);

  const current = tabs[activeTab];
  // Memoised so the fallback empty array is stable — otherwise a fresh []
  // every render would re-run the masonry distribution on every keystroke.
  const items = useMemo(() => current?.items ?? [], [current]);
  const columns = useMemo(() => masonryColumns(items, COLUMN_COUNT), [items]);

  const selectedIndex = primary
    ? items.findIndex((item) => itemKey(item) === itemKey(primary))
    : -1;

  const onGridKey = (event: React.KeyboardEvent) => {
    if (event.key === "Escape") {
      onClose();
      return;
    }
    if (event.key === "Enter" && selection.length > 0) {
      void adopt();
      return;
    }
    const moved = nextIndex(Math.max(0, selectedIndex), event.key, items.length, COLUMN_COUNT);
    if (moved !== selectedIndex && moved >= 0) {
      event.preventDefault();
      const item = items[moved];
      if (item && isUsable(item, role)) select(item);
    }
  };

  const select = (item: MediaItem) => {
    if (role === "hero") {
      // Hero is single-select — pick replaces.
      setSelection([item]);
    } else {
      // Gallery is multi-select — click toggles membership. Keeping the
      // first-picked as `primary` means the preview does not jump around
      // when the operator ticks additional images.
      setSelection((prev) =>
        prev.some((it) => itemKey(it) === itemKey(item))
          ? prev.filter((it) => itemKey(it) !== itemKey(item))
          : [...prev, item],
      );
    }
    setFocal({ x: 50, y: 50 });
    setError(null);
  };

  const adopt = async () => {
    if (selection.length === 0) return;
    setBusy(true);
    setError(null);
    const collectedWarnings: string[] = [];
    try {
      // Sequential, not parallel: keeps ordering stable (position column) and
      // avoids the provider fetch fanning out into a rate-limit spike.
      for (let index = 0; index < selection.length; index++) {
        const item = selection[index];
        try {
          const result = await adoptMedia({
            entity_type: entityType,
            entity_id: entityId,
            role,
            provider: item.provider,
            external_id: item.external_id,
            // Focal only applies to hero (first + only item); gallery rows
            // ignore it server-side.
            focal: role === "hero" ? focal : undefined,
          });
          for (const w of result.warnings) collectedWarnings.push(w);
        } catch (err) {
          if (err instanceof ApiError && err.status === 409) {
            const outer = err.detail as { detail?: { message?: string } } | undefined;
            const msg = outer?.detail?.message ?? err.message;
            if (role === "gallery") {
              // A duplicate-hero warning is expected for gallery adds — just
              // skip that item and keep going. Hero picks stop on 409.
              collectedWarnings.push(`${item.credit.name}: ${msg}`);
              continue;
            }
            setError(msg);
            return;
          }
          throw err;
        }
      }
      onAdopted({ role, warnings: collectedWarnings });
      onClose();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Übernahme fehlgeschlagen.");
    } finally {
      setBusy(false);
    }
  };

  if (!open) return null;

  const budgetWarning = Object.values(tabs).find((tab) => tab.budget?.warning);

  return (
    <Modal
      open
      onClose={onClose}
      labelledBy="media-picker-title"
      cardClassName="max-w-[1400px] h-[92vh] rounded-lg bg-admin-surface"
    >
      <div className="flex h-full flex-col">
        {/* head: context + free text. No role toggle — the caller decides. */}
        <header className="flex flex-wrap items-center gap-3 border-b border-admin-border px-4 py-3">
          <div className="min-w-0 flex-1">
            <h2 id="media-picker-title" className="truncate text-ui font-semibold text-admin-fg">
              {role === "hero" ? "Hero-Bild" : "Galerie"}
              {context ? ` — ${context.title}` : ""}
              {context?.subtitle ? (
                <span className="font-normal text-admin-muted">, {context.subtitle}</span>
              ) : null}
            </h2>
          </div>

          <form
            onSubmit={(event) => {
              event.preventDefault();
              setQuery(freeText.trim());
            }}
            className="flex items-center gap-2"
          >
            <input
              type="search"
              value={freeText}
              onChange={(event) => setFreeText(event.target.value)}
              placeholder="Eigener Suchbegriff"
              className="h-9 w-56 rounded-md border border-admin-border-strong bg-admin-surface px-3 text-ui text-admin-fg outline-none focus:border-admin-primary"
            />
          </form>

          <button
            type="button"
            onClick={onClose}
            aria-label="Schließen"
            className="rounded-md border border-admin-border px-2.5 py-1 text-label text-admin-fg2 hover:bg-admin-hover"
          >
            ✕
          </button>
        </header>

        {/* chips — the entry point; free text exists but is not it */}
        <div className="flex flex-wrap items-center gap-1.5 border-b border-admin-border px-4 py-2">
          {(context?.suggestions ?? []).map((chip) => (
            <button
              key={chip}
              type="button"
              onClick={() => {
                setQuery(chip);
                setFreeText(chip);
              }}
              className={`rounded-full px-3 py-1 text-label transition-colors ${
                query === chip
                  ? "bg-admin-primary text-admin-primary-fg"
                  : "border border-admin-border text-admin-fg2 hover:bg-admin-hover"
              }`}
            >
              {chip}
            </button>
          ))}
          {context?.lat != null && (
            <span className="ml-1 text-caption text-admin-muted">
              📍 Umkreissuche im Tab „Vor Ort“
            </span>
          )}
        </div>

        {/* tabs with post-filter counts */}
        <div className="flex flex-wrap items-center gap-1 border-b border-admin-border px-4">
          {providers.map((provider) => (
            <button
              key={provider}
              type="button"
              onClick={() => setActiveTab(provider)}
              className={`-mb-px border-b-2 px-3 py-2 text-label font-medium transition-colors ${
                activeTab === provider
                  ? "border-admin-primary text-admin-fg"
                  : "border-transparent text-admin-muted hover:text-admin-fg"
              }`}
            >
              {tabLabel(provider, tabs[provider])}
            </button>
          ))}
          <button
            type="button"
            onClick={reloadActiveTab}
            disabled={current?.loading || !context || !query}
            title="Diese Bibliothek neu laden"
            aria-label="Diese Bibliothek neu laden"
            className="ml-auto rounded-md p-1.5 text-admin-muted transition-colors hover:bg-admin-hover hover:text-admin-fg disabled:opacity-40"
          >
            <svg
              viewBox="0 0 24 24"
              fill="none"
              aria-hidden="true"
              className={`h-4 w-4 ${current?.loading ? "animate-spin" : ""}`}
            >
              <path
                d="M20 12a8 8 0 1 1-2.34-5.66M20 4v5h-5"
                stroke="currentColor"
                strokeWidth="1.8"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </button>
        </div>

        {/* slim indeterminate bar while the active tab is (re)loading */}
        <div className="h-0.5 bg-admin-border">
          {current?.loading && (
            <div className="admin-progress-bar h-full text-admin-primary" />
          )}
        </div>

        {(error || notice || budgetWarning) && (
          <div className="px-4 pt-2">
            {error && (
              <div
                role="alert"
                className="rounded-md border border-admin-danger-border bg-admin-danger-bg px-3 py-2 text-label font-medium text-admin-danger"
              >
                {error}
              </div>
            )}
            {notice && (
              <div className="rounded-md border border-admin-success-border bg-admin-success-bg px-3 py-2 text-label font-medium text-admin-success">
                {notice}
              </div>
            )}
            {!error && budgetWarning && (
              <p className="mt-1 text-caption text-admin-warning">
                Stundenkontingent zu {Math.round(
                  ((budgetWarning.budget?.used ?? 0) /
                    Math.max(1, budgetWarning.budget?.limit ?? 1)) *
                    100
                )}
                % ausgeschöpft.
              </p>
            )}
          </div>
        )}

        {/* body: grid ⅔ / preview ⅓ — stacks on narrow viewports.
            On wide viewports only the grid scrolls; the preview + adopt
            action stays in view (so the operator does not have to scroll
            back up to hit "Als Hero übernehmen"). */}
        <div ref={outerScrollRef} className="flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto p-4 lg:flex-row lg:overflow-hidden">
          <div
            ref={resultsRef}
            className="min-w-0 flex-1 outline-none lg:min-h-0 lg:overflow-y-auto"
            tabIndex={0}
            role="listbox"
            aria-label="Suchergebnisse"
            onKeyDown={onGridKey}
          >
            {current?.loading ? (
              <p className="text-ui text-admin-muted">Lädt…</p>
            ) : current?.status === "disabled" ? (
              <p className="text-ui text-admin-muted">
                {current.message ?? "Diese Quelle ist nicht konfiguriert."}
              </p>
            ) : current?.status === "budget_exhausted" ? (
              <p className="text-ui text-admin-warning">
                {current.message ?? "Stundenkontingent aufgebraucht."}
              </p>
            ) : current?.status === "error" ? (
              <p className="text-ui text-admin-danger">{current.message}</p>
            ) : items.length === 0 ? (
              <p className="text-ui text-admin-muted">
                Keine Treffer — anderen Suchbegriff oder Tab probieren.
              </p>
            ) : (
              <div className="flex gap-3">
                {columns.map((column, index) => (
                  <div key={index} className="flex min-w-0 flex-1 flex-col gap-3">
                    {column.map((item) => (
                      <MediaTile
                        key={itemKey(item)}
                        item={item}
                        role={role}
                        selected={isPicked(item)}
                        onSelect={() => select(item)}
                      />
                    ))}
                  </div>
                ))}
              </div>
            )}
          </div>

          <aside className="w-full shrink-0 lg:flex lg:w-[380px] lg:min-h-0 lg:flex-col">
            {primary ? (
              <>
                <div className="space-y-3 lg:min-h-0 lg:flex-1 lg:overflow-y-auto lg:pr-1">
                  <PreviewPanel
                    item={primary}
                    title={context?.title ?? ""}
                    focal={focal}
                    onFocalChange={setFocal}
                  />
                  {role === "gallery" && selection.length > 1 && (
                    <p className="text-caption text-admin-muted">
                      Vorschau zeigt das erste ausgewählte Bild.
                      Insgesamt {selection.length} Bilder werden zur Galerie hinzugefügt.
                    </p>
                  )}
                  <LicenseCard item={primary} />
                </div>
                <Button
                  variant="primary"
                  block
                  className="mt-3 shrink-0"
                  disabled={busy || selection.length === 0}
                  onClick={() => void adopt()}
                >
                  {busy
                    ? "Übernehme…"
                    : role === "gallery"
                      ? `Zur Galerie hinzufügen (${selection.length})`
                      : adoptLabel(role)}
                </Button>
              </>
            ) : (
              <div className="rounded-lg border border-dashed border-admin-border p-6 text-center">
                <p className="text-ui text-admin-muted">
                  {role === "gallery"
                    ? "Ein oder mehrere Bilder auswählen — Klick fügt zum Stapel hinzu, erneuter Klick entfernt."
                    : "Bild auswählen — die Vorschau zeigt es dann mit Verlauf, Typografie und Bildnachweis, so wie es später erscheint."}
                </p>
              </div>
            )}
          </aside>
        </div>
      </div>
    </Modal>
  );
}
