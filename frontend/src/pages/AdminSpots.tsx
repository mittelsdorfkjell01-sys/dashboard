// Admin spot table (Sprint B): filter/search/paginate. Status is a tab bar
// (archived spots live in their own tab, out of the other lists). Lifecycle
// actions (go-live / offline / archive / reactivate) live on the spot editor's
// „Betrieb & Veröffentlichung" panel — each row only links there via Bearbeiten.

import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useLocation, useNavigate, useSearchParams } from "react-router-dom";
import {
  ApiError,
  getAdminSpots,
  getAdminRegionsFlat,
  type AdminSpotsResponse,
  type MediaFilterKey,
  type Region,
  type AdminSpotSummary,
} from "../lib/api";
import { SPORTS, gapAnchor, gapLabel, sportLabel, statusLabel } from "../lib/labels";
import { PageHeader, Badge, Button, type BadgeTone } from "../components/admin/ui";
import { createAdminReturnState } from "../lib/adminNavigation";
import {
  getAdminSpotSearches,
  rememberAdminSpotSearch,
} from "../lib/adminSpotSearchHistory";

const MEDIA_FILTER_LABEL: Record<MediaFilterKey, string> = {
  no_hero: "Kein Hero",
  unverified: "Ortsbezug ungeprüft",
  duplicate: "Bild mehrfach genutzt",
  dead: "Quelle tot",
};
// Status tabs. "" = Alle (everything except archived); "archived" is its own tab.
const STATUS_TABS: { key: string; label: string }[] = [
  { key: "", label: "Alle" },
  { key: "draft", label: "Entwürfe" },
  { key: "published", label: "Veröffentlicht" },
  { key: "archived", label: "Archiviert" },
];
const PAGE = 25;

export default function AdminSpots() {
  const navigate = useNavigate();
  const location = useLocation();
  const [params, setParams] = useSearchParams();
  const editorState = createAdminReturnState(location, "Spots");
  const status = params.get("status") ?? "";
  const regionId = params.get("region_id") ?? "";
  const sport = params.get("sport") ?? "";
  const sort = params.get("sort") ?? "name";
  const q = params.get("q") ?? "";
  const completeness = params.get("completeness") ?? "";
  const media = (params.get("media") ?? "") as MediaFilterKey | "";
  const offset = Number(params.get("offset") ?? "0") || 0;

  const [data, setData] = useState<AdminSpotsResponse | null>(null);
  const [regions, setRegions] = useState<Region[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [searchText, setSearchText] = useState(q);
  const [recentSearches, setRecentSearches] = useState(getAdminSpotSearches);

  const regionName = useMemo(() => {
    const m = new Map(regions.map((r) => [r.id, r.name]));
    return (id: string) => m.get(id) ?? "—";
  }, [regions]);

  useEffect(() => {
    getAdminRegionsFlat().then(setRegions).catch(() => setRegions([]));
  }, []);

  const load = useCallback(async () => {
    setError(null);
    try {
      setData(
        await getAdminSpots({
          status: status || undefined,
          // "Alle" (no status) hides archived; archived has its own tab.
          exclude_status: status ? undefined : "archived",
          region_id: regionId || undefined,
          sport: sport || undefined,
          q: q || undefined,
          sort,
          completeness: completeness === "complete" || completeness === "incomplete" ? completeness : undefined,
          media: media || undefined,
          limit: PAGE,
          offset,
        })
      );
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Laden fehlgeschlagen.");
    }
  }, [status, regionId, sport, sort, completeness, media, q, offset]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => setSearchText(q), [q]);

  useEffect(() => {
    if (q) setRecentSearches(rememberAdminSpotSearch(q));
  }, [q]);

  useEffect(() => {
    if (searchText === q) return;
    const timer = window.setTimeout(() => {
      const next = new URLSearchParams(params);
      if (searchText.trim()) next.set("q", searchText.trim());
      else next.delete("q");
      next.delete("offset");
      setParams(next);
    }, 300);
    return () => window.clearTimeout(timer);
  }, [searchText, q, params, setParams]);

  const setFilter = (key: string, value: string) => {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    next.delete("offset"); // reset to first page on filter change
    setParams(next);
  };

  const setOffset = (value: number) => {
    const next = new URLSearchParams(params);
    if (value > 0) next.set("offset", String(value));
    else next.delete("offset");
    setParams(next);
  };

  const selectCls =
    "h-9 rounded-md border border-admin-border-strong bg-admin-surface px-3 text-ui text-admin-fg outline-none transition-colors placeholder:text-admin-faint focus:border-admin-primary";

  const total = data?.total ?? 0;
  const shown = data?.items.length ?? 0;

  // Per-row action — only „Bearbeiten". Lifecycle actions (go-live / offline /
  // archive / reactivate) live on the editor's „Betrieb & Veröffentlichung" panel.
  const rowActions = (s: AdminSpotSummary) => (
    <div className="flex flex-wrap gap-2" onClick={(e) => e.stopPropagation()}>
      <Link
        to={`/admin/spot/${s.id}/edit`}
        state={editorState}
        className="rounded-md border border-admin-border bg-admin-surface px-2.5 py-1 text-label font-medium text-admin-fg2 transition-colors hover:bg-admin-hover hover:text-admin-fg"
      >
        Bearbeiten
      </Link>
    </div>
  );

  return (
    <div>
      <PageHeader
        title="Spots"
        actions={
          <Link
            to="/admin/spot/new"
            state={editorState}
            className="inline-flex items-center gap-1.5 rounded-md bg-admin-primary px-3.5 py-2 text-label font-medium text-admin-primary-fg transition-colors hover:bg-admin-primary-hover"
          >
            <span aria-hidden className="text-[15px] leading-none">+</span> Neuer Spot
          </Link>
        }
      />

      {/* Status tabs — archived spots live in their own tab, out of the others. */}
      <div className="mb-4 flex flex-wrap gap-1 border-b border-admin-border">
        {STATUS_TABS.map((t) => {
          const active = status === t.key;
          return (
            <button
              key={t.key || "all"}
              type="button"
              onClick={() => setFilter("status", t.key)}
              className={`-mb-px border-b-2 px-3 py-2 text-label font-medium transition-colors ${
                active
                  ? "border-admin-primary text-admin-fg"
                  : "border-transparent text-admin-muted hover:text-admin-fg"
              }`}
            >
              {t.label}
            </button>
          );
        })}
      </div>

      {/* Filters — full-width stack on mobile, flowing row on sm+. */}
      <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap">
        <label className="w-full text-label font-medium text-admin-fg sm:min-w-[220px] sm:flex-1">
          Suche
          <input
            type="search"
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
            className={`${selectCls} mt-1 w-full`}
          />
        </label>
        <div className="grid grid-cols-2 gap-2 sm:contents">
          <select
            value={regionId}
            onChange={(e) => setFilter("region_id", e.target.value)}
            className={`${selectCls} w-full min-w-0 sm:w-auto`}
            aria-label="Region"
          >
            <option value="">Alle Regionen</option>
            {regions.map((r) => (
              <option key={r.id} value={r.id}>
                {r.name}
              </option>
            ))}
          </select>
          <select
            value={sport}
            onChange={(e) => setFilter("sport", e.target.value)}
            className={`${selectCls} col-span-2 w-full min-w-0 sm:col-span-1 sm:w-auto`}
            aria-label="Sportart"
          >
            <option value="">Alle Sportarten</option>
            {SPORTS.map((s) => (
              <option key={s} value={s}>
                {sportLabel(s)}
              </option>
            ))}
          </select>
          <select
            value={completeness}
            onChange={(e) => setFilter("completeness", e.target.value)}
            className={`${selectCls} w-full min-w-0 sm:w-auto`}
            aria-label="Vollständigkeit"
          >
            <option value="">Alle Vollständigkeiten</option>
            <option value="complete">Vollständig</option>
            <option value="incomplete">Unvollständig</option>
          </select>
          <select
            value={media}
            onChange={(e) => setFilter("media", e.target.value)}
            className={`${selectCls} w-full min-w-0 sm:w-auto`}
            aria-label="Bildstatus"
          >
            <option value="">Alle Bildstatus</option>
            {(Object.entries(MEDIA_FILTER_LABEL) as [MediaFilterKey, string][]).map(
              ([key, filterLabel]) => (
                <option key={key} value={key}>
                  {filterLabel}
                </option>
              )
            )}
          </select>
          <select
            value={sort}
            onChange={(e) => setFilter("sort", e.target.value)}
            className={`${selectCls} w-full min-w-0 sm:w-auto`}
            aria-label="Sortierung"
          >
            <option value="name">Name A–Z</option>
            <option value="-updated">Zuletzt bearbeitet</option>
          </select>
          <select
            value=""
            onChange={(e) => {
              if (!e.target.value) return;
              setSearchText(e.target.value);
              setFilter("q", e.target.value);
            }}
            disabled={recentSearches.length === 0}
            className={`${selectCls} w-full min-w-0 sm:w-auto disabled:opacity-50`}
            aria-label="Zuletzt gesucht"
          >
            <option value="">Zuletzt gesucht</option>
            {recentSearches.map((query) => (
              <option key={query} value={query}>
                {query}
              </option>
            ))}
          </select>
        </div>
      </div>

      {error && (
        <div
          role="alert"
          className="mt-4 rounded-md border border-admin-danger-border bg-admin-danger-bg px-3 py-2 text-label font-medium text-admin-danger"
        >
          {error}
        </div>
      )}

      {/* Mobile / tablet: card list — every action stays visible, no side-scroll. */}
      <div className="mt-4 space-y-2 lg:hidden">
        {!data ? (
          <div className="rounded-lg border border-admin-border bg-admin-surface px-4 py-6 text-center text-admin-muted">
            Lädt…
          </div>
        ) : data.items.length === 0 ? (
          <div className="rounded-lg border border-dashed border-admin-border bg-admin-surface px-4 py-10 text-center text-admin-muted">
            Keine Spots gefunden. Filter anpassen.
          </div>
        ) : (
          data.items.map((s) => (
            <div
              key={s.id}
              onClick={() => navigate(`/admin/spot/${s.id}/edit`, { state: editorState })}
              className="cursor-pointer rounded-lg border border-admin-border bg-admin-surface p-4 transition-colors hover:border-admin-border-strong"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="font-medium text-admin-fg">{s.name}</div>
                  <div className="admin-mono truncate text-caption text-admin-muted">{s.slug}</div>
                </div>
                <StatusBadge status={s.status} />
              </div>
              <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-label text-admin-fg2">
                <span>{s.region_id ? regionName(s.region_id) : "— ohne Region"}</span>
                <span className="text-admin-muted">
                  {(s.sports ?? []).map(sportLabel).join(", ") || "—"}
                </span>
                <span className="admin-mono text-admin-muted">
                  Conf. {s.confidence != null ? s.confidence.toFixed(2) : "—"}
                </span>
              </div>
              <div className="mt-3" onClick={(event) => event.stopPropagation()}>
                <ReadinessStatus spot={s} editorState={editorState} />
              </div>
              <MediaFlagBadges spot={s} />
              <div className="mt-3">{rowActions(s)}</div>
            </div>
          ))
        )}
      </div>

      {/* Desktop: dense table. */}
      <div className="mt-4 hidden overflow-x-auto rounded-lg border border-admin-border bg-admin-surface lg:block">
        <table className="w-full min-w-[820px] text-left text-ui">
          <thead className="border-b border-admin-border bg-admin-hover text-caption uppercase tracking-wide text-admin-muted">
            <tr>
              <th className="px-4 py-2.5 font-semibold">Name</th>
              <th className="px-4 py-2.5 font-semibold">Region</th>
              <th className="px-4 py-2.5 font-semibold">Sportarten</th>
              <th className="px-4 py-2.5 font-semibold">Status</th>
              <th className="px-4 py-2.5 font-semibold">Vollständigkeit</th>
              <th className="px-4 py-2.5 text-right font-semibold">Conf.</th>
              <th className="px-4 py-2.5 font-semibold">Aktionen</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-admin-border-subtle">
            {!data ? (
              <tr>
                <td colSpan={7} className="px-4 py-6 text-center text-admin-muted">
                  Lädt…
                </td>
              </tr>
            ) : data.items.length === 0 ? (
              <tr>
                <td colSpan={7} className="px-4 py-10 text-center text-admin-muted">
                  Keine Spots gefunden. Filter anpassen.
                </td>
              </tr>
            ) : (
              data.items.map((s) => (
                <tr
                  key={s.id}
                  onClick={() => navigate(`/admin/spot/${s.id}/edit`, { state: editorState })}
                  className="group cursor-pointer transition-colors hover:bg-admin-hover"
                >
                  <td className="px-4 py-3">
                    <span className="font-medium text-admin-fg group-hover:text-admin-primary">
                      {s.name}
                    </span>
                    <div className="admin-mono text-caption text-admin-muted">{s.slug}</div>
                  </td>
                  <td className="px-4 py-3 text-admin-fg2">
                    {s.region_id ? regionName(s.region_id) : "— ohne Region"}
                  </td>
                  <td className="px-4 py-3 text-admin-fg2">
                    {(s.sports ?? []).map(sportLabel).join(", ") || "—"}
                  </td>
                  <td className="px-4 py-3">
                    <StatusBadge status={s.status} />
                  </td>
                  <td className="px-4 py-3" onClick={(event) => event.stopPropagation()}>
                    <ReadinessStatus spot={s} editorState={editorState} />
                    <MediaFlagBadges spot={s} />
                  </td>
                  <td className="admin-mono px-4 py-3 text-right text-admin-fg2">
                    {s.confidence != null ? s.confidence.toFixed(2) : "—"}
                  </td>
                  <td className="px-4 py-3">{rowActions(s)}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      <div className="mt-4 flex items-center justify-between text-label text-admin-muted">
        <span className="admin-mono">
          {total === 0 ? "0" : `${offset + 1}–${offset + shown}`} von {total}
        </span>
        <div className="flex gap-2">
          <Button
            variant="secondary"
            disabled={offset === 0}
            onClick={() => setOffset(Math.max(0, offset - PAGE))}
          >
            Zurück
          </Button>
          <Button
            variant="secondary"
            disabled={offset + shown >= total}
            onClick={() => setOffset(offset + PAGE)}
          >
            Weiter
          </Button>
        </div>
      </div>
    </div>
  );
}

const STATUS_TONE: Record<string, BadgeTone> = {
  published: "success",
  draft: "neutral",
  archived: "neutral",
};

function StatusBadge({ status }: { status: string }) {
  return <Badge tone={STATUS_TONE[status] ?? "neutral"}>{statusLabel(status)}</Badge>;
}

const MEDIA_FLAG_TONE: Record<MediaFilterKey, BadgeTone> = {
  no_hero: "warning",
  unverified: "info",
  duplicate: "warning",
  dead: "danger",
};

/** Media problems as small badges — the same four states the filter offers,
 *  so a row is never flagged for a reason nobody can look up. */
function MediaFlagBadges({ spot }: { spot: AdminSpotSummary }) {
  const active = (Object.keys(MEDIA_FLAG_TONE) as MediaFilterKey[]).filter(
    (key) => spot.media_flags?.[key]
  );
  if (active.length === 0) return null;
  return (
    <div className="mt-1.5 flex flex-wrap gap-1">
      {active.map((key) => (
        <Badge key={key} tone={MEDIA_FLAG_TONE[key]}>
          {MEDIA_FILTER_LABEL[key]}
        </Badge>
      ))}
    </div>
  );
}

function ReadinessStatus({
  spot,
  editorState,
}: {
  spot: AdminSpotSummary;
  editorState: ReturnType<typeof createAdminReturnState>;
}) {
  if (spot.readiness.ready) return <Badge tone="success">Vollständig</Badge>;
  return (
    <details className="group min-w-[160px]">
      <summary className="cursor-pointer list-none">
        <Badge tone="warning">
          {spot.readiness.missing_count === 1
            ? "1 Angabe fehlt"
            : `${spot.readiness.missing_count} Angaben fehlen`}
        </Badge>
      </summary>
      <ul className="mt-2 space-y-1 text-caption text-admin-fg2">
        {spot.readiness.gaps.map((gap) => (
          <li key={gap}>
            <Link
              to={`/admin/spot/${spot.id}/edit#${gapAnchor(gap)}`}
              state={editorState}
              className="text-admin-primary hover:underline"
            >
              {gapLabel(gap)}
            </Link>
          </li>
        ))}
      </ul>
    </details>
  );
}
