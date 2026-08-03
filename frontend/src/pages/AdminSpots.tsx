// Admin spot table (Sprint B): filter/search/paginate, plus per-row actions —
// edit, go-live (surfaces the readiness gap list on 409), and ERA5 trigger.

import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import {
  ApiError,
  archiveSpot,
  getAdminSpots,
  getAdminRegionsFlat,
  goLiveSpot,
  unpublishSpot,
  type AdminSpotsResponse,
  type Region,
  type SpotSummary,
} from "../lib/api";
import { gapLabel, sportLabel, statusLabel } from "../lib/labels";
import { PageHeader, Badge, type BadgeTone } from "../components/admin/ui";

const SPORTS = ["kitesurf", "wavekite", "windsurf", "wing", "surf"];
const STATUSES = ["draft", "published", "archived"];
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
  const [notice, setNotice] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

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

  const flash = (msg: string) => {
    setNotice(msg);
    setTimeout(() => setNotice(null), 3000);
  };

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

  const onGoLive = async (spot: SpotSummary) => {
    setBusyId(spot.id);
    setError(null);
    try {
      await goLiveSpot(spot.id);
      flash(`„${spot.name}" ist jetzt live.`);
      await load();
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) {
        const detail = (e.detail as { detail?: { gaps?: string[] } } | null)?.detail;
        const gaps = detail?.gaps ?? [];
        setError(
          `„${spot.name}" ist noch nicht bereit. Fehlt: ${gaps
            .map(gapLabel)
            .join(", ")}`
        );
      } else {
        setError(e instanceof ApiError ? e.message : "Aktion fehlgeschlagen.");
      }
    } finally {
      setBusyId(null);
    }
  };

  const runStatus = async (
    spot: SpotSummary,
    fn: (id: string) => Promise<unknown>,
    msg: string
  ) => {
    setBusyId(spot.id);
    setError(null);
    try {
      await fn(spot.id);
      flash(msg);
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Aktion fehlgeschlagen.");
    } finally {
      setBusyId(null);
    }
  };

  const selectCls =
    "h-9 rounded-md border border-admin-border-strong bg-admin-surface px-3 text-ui text-admin-fg outline-none transition-colors placeholder:text-admin-faint focus:border-admin-primary";

  const total = data?.total ?? 0;
  const shown = data?.items.length ?? 0;

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

      {/* Filters */}
      <div className="flex flex-wrap gap-2">
        <input
          type="search"
          placeholder="Suche Name / Slug"
          defaultValue={q}
          onChange={(e) => setFilter("q", e.target.value)}
          className={`${selectCls} min-w-[200px] flex-1`}
        />
        <select
          value={status}
          onChange={(e) => setFilter("status", e.target.value)}
          className={selectCls}
          aria-label="Status"
        >
          <option value="">Alle Status</option>
          {STATUSES.map((s) => (
            <option key={s} value={s}>
              {statusLabel(s)}
            </option>
          ))}
        </select>
        <select
          value={regionId}
          onChange={(e) => setFilter("region_id", e.target.value)}
          className={selectCls}
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
          className={selectCls}
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

      {notice && (
        <div
          role="status"
          className="mt-4 rounded-md border border-admin-success-border bg-admin-success-bg px-3 py-2 text-label font-medium text-admin-success"
        >
          {notice}
        </div>
      )}
      {error && (
        <div
          role="alert"
          className="mt-4 rounded-md border border-admin-danger-border bg-admin-danger-bg px-3 py-2 text-label font-medium text-admin-danger"
        >
          {error}
        </div>
      )}

      <div className="mt-4 overflow-x-auto rounded-lg border border-admin-border bg-admin-surface">
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
                  <td className="px-4 py-3" onClick={(e) => e.stopPropagation()}>
                    <div className="flex flex-wrap gap-2">
                      <Link
                        to={`/admin/spot/${s.id}/edit`}
                        className="rounded-md border border-admin-border bg-admin-surface px-2.5 py-1 text-label font-medium text-admin-fg2 transition-colors hover:bg-admin-hover hover:text-admin-fg"
                      >
                        Bearbeiten
                      </Link>
                      <a
                        href={`/spot/${s.id}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="rounded-md border border-admin-border bg-admin-surface px-2.5 py-1 text-label font-medium text-admin-fg2 transition-colors hover:bg-admin-hover hover:text-admin-fg"
                      >
                        Ansehen ↗
                      </a>
                      {s.status !== "published" && (
                        <button
                          type="button"
                          disabled={busyId === s.id}
                          onClick={() => onGoLive(s)}
                          className="rounded-md bg-admin-primary px-2.5 py-1 text-label font-medium text-admin-primary-fg transition-colors hover:bg-admin-primary-hover disabled:opacity-50"
                        >
                          Go-Live
                        </button>
                      )}
                      {s.status === "published" && (
                        <button
                          type="button"
                          disabled={busyId === s.id}
                          onClick={() =>
                            runStatus(s, unpublishSpot, `„${s.name}" ist offline.`)
                          }
                          className="rounded-md border border-admin-border bg-admin-surface px-2.5 py-1 text-label font-medium text-admin-fg2 transition-colors hover:bg-admin-hover hover:text-admin-fg disabled:opacity-50"
                        >
                          Offline
                        </button>
                      )}
                      {s.status !== "archived" && (
                        <button
                          type="button"
                          disabled={busyId === s.id}
                          onClick={() =>
                            runStatus(s, archiveSpot, `„${s.name}" archiviert.`)
                          }
                          className="rounded-md border border-admin-border bg-admin-surface px-2.5 py-1 text-label font-medium text-admin-muted transition-colors hover:bg-admin-hover hover:text-admin-fg disabled:opacity-50"
                        >
                          Archivieren
                        </button>
                      )}
                    </div>
                  </td>
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
