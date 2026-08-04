// Admin spot table (Sprint B): filter/search/paginate. Status is a tab bar
// (archived spots live in their own tab, out of the other lists). Lifecycle
// actions (go-live / offline / archive / reactivate) live on the spot editor's
// „Betrieb & Veröffentlichung" panel — each row only links there via Bearbeiten.

import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import {
  ApiError,
  getAdminSpots,
  getAdminRegionsFlat,
  type AdminSpotsResponse,
  type Region,
  type SpotSummary,
} from "../lib/api";
import { sportLabel, statusLabel } from "../lib/labels";
import { PageHeader, Badge, type BadgeTone } from "../components/admin/ui";

const SPORTS = ["kitesurf", "wavekite", "windsurf", "wing", "surf"];
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
  const [params, setParams] = useSearchParams();
  const status = params.get("status") ?? "";
  const regionId = params.get("region_id") ?? "";
  const sport = params.get("sport") ?? "";
  const q = params.get("q") ?? "";
  const offset = Number(params.get("offset") ?? "0") || 0;

  const [data, setData] = useState<AdminSpotsResponse | null>(null);
  const [regions, setRegions] = useState<Region[]>([]);
  const [error, setError] = useState<string | null>(null);

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
          limit: PAGE,
          offset,
        })
      );
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Laden fehlgeschlagen.");
    }
  }, [status, regionId, sport, q, offset]);

  useEffect(() => {
    void load();
  }, [load]);

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
  const rowActions = (s: SpotSummary) => (
    <div className="flex flex-wrap gap-2" onClick={(e) => e.stopPropagation()}>
      <Link
        to={`/admin/spot/${s.id}/edit`}
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
        description="Surfspots verwalten, veröffentlichen und archivieren."
        actions={
          <Link
            to="/admin/spot/new"
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
        <input
          type="search"
          placeholder="Suche Name / Slug"
          defaultValue={q}
          onChange={(e) => setFilter("q", e.target.value)}
          className={`${selectCls} w-full sm:min-w-[220px] sm:flex-1`}
        />
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
              onClick={() => navigate(`/admin/spot/${s.id}/edit`)}
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
              <th className="px-4 py-2.5 text-right font-semibold">Conf.</th>
              <th className="px-4 py-2.5 font-semibold">Aktionen</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-admin-border-subtle">
            {!data ? (
              <tr>
                <td colSpan={6} className="px-4 py-6 text-center text-admin-muted">
                  Lädt…
                </td>
              </tr>
            ) : data.items.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-4 py-10 text-center text-admin-muted">
                  Keine Spots gefunden. Filter anpassen.
                </td>
              </tr>
            ) : (
              data.items.map((s) => (
                <tr
                  key={s.id}
                  onClick={() => navigate(`/admin/spot/${s.id}/edit`)}
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
          <button
            type="button"
            disabled={offset === 0}
            onClick={() => setOffset(Math.max(0, offset - PAGE))}
            className="rounded-md border border-admin-border bg-admin-surface px-3 py-1.5 font-medium text-admin-fg2 transition-colors hover:bg-admin-hover hover:text-admin-fg disabled:opacity-40"
          >
            Zurück
          </button>
          <button
            type="button"
            disabled={offset + shown >= total}
            onClick={() => setOffset(offset + PAGE)}
            className="rounded-md border border-admin-border bg-admin-surface px-3 py-1.5 font-medium text-admin-fg2 transition-colors hover:bg-admin-hover hover:text-admin-fg disabled:opacity-40"
          >
            Weiter
          </button>
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
