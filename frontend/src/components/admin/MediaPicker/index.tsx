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
  initialRole?: MediaRole;
  onClose: () => void;
  /** Fired after a successful adoption so the form can reload its record. */
  onAdopted: (result: { role: MediaRole; warnings: string[] }) => void;
}) {
  const providers = useMemo(() => tabOrder(entityType), [entityType]);

  const [context, setContext] = useState<MediaContext | null>(null);
  const [role, setRole] = useState<MediaRole>(initialRole);
  const [query, setQuery] = useState("");
  const [freeText, setFreeText] = useState("");
  const [activeTab, setActiveTab] = useState<ProviderKey>(providers[0]);
  const [tabs, setTabs] = useState<Record<string, TabState>>({});
  const [selected, setSelected] = useState<MediaItem | null>(null);
  const [focal, setFocal] = useState({ x: 50, y: 50 });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const abortRef = useRef<AbortController | null>(null);

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
  const runSearch = useCallback(
    (searchQuery: string, ctx: MediaContext) => {
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      setTabs(Object.fromEntries(providers.map((p) => [p, { ...EMPTY_TAB }])));

      providers.forEach((provider) => {
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
        searchMedia(
          {
            provider,
            q: searchQuery,
            role,
            lat: isNearby ? ctx.lat : undefined,
            lon: isNearby ? ctx.lon : undefined,
          },
          controller.signal
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
            if (controller.signal.aborted) return;
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
      });
    },
    // `role` is intentionally excluded: the server does not vary results by
    // role, so toggling Hero/Galerie must not refetch.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [providers]
  );

  useEffect(() => {
    if (!open || !context || !query) return;
    const timer = window.setTimeout(() => runSearch(query, context), CHIP_DEBOUNCE_MS);
    return () => window.clearTimeout(timer);
  }, [open, context, query, runSearch]);

  useEffect(() => () => abortRef.current?.abort(), []);

  // Reset transient state whenever the overlay closes, so nothing reopens
  // mid-flow with a stale selection.
  useEffect(() => {
    if (open) return;
    setSelected(null);
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

  const selectedIndex = selected
    ? items.findIndex(
        (item) =>
          item.provider === selected.provider && item.external_id === selected.external_id
      )
    : -1;

  const onGridKey = (event: React.KeyboardEvent) => {
    if (event.key === "Escape") {
      onClose();
      return;
    }
    if (event.key === "Enter" && selected) {
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
    setSelected(item);
    setFocal({ x: 50, y: 50 });
    setError(null);
  };

  const adopt = async () => {
    if (!selected) return;
    setBusy(true);
    setError(null);
    try {
      const result = await adoptMedia({
        entity_type: entityType,
        entity_id: entityId,
        role,
        provider: selected.provider,
        external_id: selected.external_id,
        focal,
      });
      onAdopted({ role, warnings: result.warnings });
      onClose();
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        // FastAPI wraps our detail payload under `.detail` on the response body,
        // and ApiError.detail carries the *whole* body. The message we want is
        // one level deeper — without unwrapping we would hide the server's
        // reason ("bereits Hero bei Los Lances") behind a generic fallback.
        const outer = err.detail as { detail?: { message?: string } } | undefined;
        setError(outer?.detail?.message ?? err.message);
      } else {
        setError(err instanceof ApiError ? err.message : "Übernahme fehlgeschlagen.");
      }
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
        {/* head: context, mode switch, free text */}
        <header className="flex flex-wrap items-center gap-3 border-b border-admin-border px-4 py-3">
          <div className="min-w-0 flex-1">
            <h2 id="media-picker-title" className="truncate text-ui font-semibold text-admin-fg">
              {role === "hero" ? "Hero-Bild" : "Galeriebild"}
              {context ? ` — ${context.title}` : ""}
              {context?.subtitle ? (
                <span className="font-normal text-admin-muted">, {context.subtitle}</span>
              ) : null}
            </h2>
          </div>

          <div className="flex rounded-md border border-admin-border p-0.5">
            {(["hero", "gallery"] as MediaRole[]).map((value) => (
              <button
                key={value}
                type="button"
                onClick={() => setRole(value)}
                className={`rounded px-3 py-1 text-label font-medium transition-colors ${
                  role === value
                    ? "bg-admin-primary text-admin-primary-fg"
                    : "text-admin-fg2 hover:bg-admin-hover"
                }`}
              >
                {value === "hero" ? "Hero" : "Galerie"}
              </button>
            ))}
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
        <div className="flex flex-wrap gap-1 border-b border-admin-border px-4">
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

        {/* body: grid ⅔ / preview ⅓ — stacks on narrow viewports */}
        <div className="flex min-h-0 flex-1 flex-col gap-4 overflow-auto p-4 lg:flex-row">
          <div
            className="min-w-0 flex-1 outline-none"
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
                        key={`${item.provider}:${item.external_id}`}
                        item={item}
                        role={role}
                        selected={
                          selected?.provider === item.provider &&
                          selected?.external_id === item.external_id
                        }
                        onSelect={() => select(item)}
                      />
                    ))}
                  </div>
                ))}
              </div>
            )}
          </div>

          <aside className="w-full shrink-0 space-y-3 lg:w-[380px]">
            {selected ? (
              <>
                <PreviewPanel
                  item={selected}
                  title={context?.title ?? ""}
                  kicker={context?.subtitle || undefined}
                  focal={focal}
                  onFocalChange={setFocal}
                />
                <LicenseCard item={selected} />
                <button
                  type="button"
                  disabled={busy || !isUsable(selected, role)}
                  onClick={() => void adopt()}
                  className="w-full rounded-md bg-admin-primary px-3.5 py-2 text-label font-medium text-admin-primary-fg transition-colors hover:bg-admin-primary-hover disabled:opacity-50"
                >
                  {busy ? "Übernehme…" : adoptLabel(role)}
                </button>
              </>
            ) : (
              <div className="rounded-lg border border-dashed border-admin-border p-6 text-center">
                <p className="text-ui text-admin-muted">
                  Bild auswählen — die Vorschau zeigt es dann mit Verlauf,
                  Typografie und Bildnachweis, so wie es später erscheint.
                </p>
              </div>
            )}
          </aside>
        </div>
      </div>
    </Modal>
  );
}
