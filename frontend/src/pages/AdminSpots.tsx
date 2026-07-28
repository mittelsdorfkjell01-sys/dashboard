// Admin spot table (Sprint B): filter/search/paginate, plus per-row actions —
// edit, go-live (surfaces the readiness gap list on 409), and ERA5 trigger.

import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import {
  ApiError,
  archiveSpot,
  getAdminSpots,
  getRegions,
  goLiveSpot,
  unpublishSpot,
  type AdminSpotsResponse,
  type Region,
  type SpotSummary,
} from "../lib/api";
import { gapLabel, sportLabel, statusLabel } from "../lib/labels";

const SPORTS = ["kitesurf", "wavekite", "windsurf", "wing", "surf"];
const STATUSES = ["draft", "published", "archived"];
const PAGE = 25;

export default function AdminSpots() {
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
    getRegions().then(setRegions).catch(() => setRegions([]));
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
    "rounded-lg border border-line bg-white px-3 py-2 text-ui text-ink outline-none focus:border-teal/50";

  const total = data?.total ?? 0;
  const shown = data?.items.length ?? 0;

  return (
    <div>
      <div className="flex items-center justify-between gap-4">
        <h1 className="text-2xl font-semibold text-ink">Spots</h1>
        <Link
          to="/admin/spot/new"
          className="rounded-lg bg-teal px-4 py-2 text-ui font-medium text-white hover:bg-teal-hover"
        >
          + Neuer Spot
        </Link>
      </div>

      {/* Filters */}
      <div className="mt-4 flex flex-wrap gap-2">
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
          className="mt-4 rounded-lg bg-green/10 px-3 py-2 text-label font-medium text-green"
        >
          {notice}
        </div>
      )}
      {error && (
        <div
          role="alert"
          className="mt-4 rounded-lg bg-red-50 px-3 py-2 text-label font-medium text-red-700"
        >
          {error}
        </div>
      )}

      <div className="mt-4 overflow-x-auto rounded-2xl border border-line bg-white">
        <table className="w-full min-w-[820px] text-left text-ui">
          <thead className="bg-ink/5 text-caption uppercase tracking-wide text-muted">
            <tr>
              <th className="px-4 py-3 font-semibold">Name</th>
              <th className="px-4 py-3 font-semibold">Region</th>
              <th className="px-4 py-3 font-semibold">Sportarten</th>
              <th className="px-4 py-3 font-semibold">Status</th>
              <th className="px-4 py-3 font-semibold">Conf.</th>
              <th className="px-4 py-3 font-semibold">Aktionen</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {!data ? (
              <tr>
                <td colSpan={6} className="px-4 py-6 text-center text-muted">
                  Lädt…
                </td>
              </tr>
            ) : data.items.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-4 py-6 text-center text-muted">
                  Keine Spots gefunden.
                </td>
              </tr>
            ) : (
              data.items.map((s) => (
                <tr key={s.id}>
                  <td className="px-4 py-3">
                    <Link
                      to={`/admin/spot/${s.id}/edit`}
                      className="font-medium text-ink hover:underline"
                    >
                      {s.name}
                    </Link>
                    <div className="text-caption text-muted">{s.slug}</div>
                  </td>
                  <td className="px-4 py-3 text-ink">
                    {s.region_id ? regionName(s.region_id) : "— ohne Region"}
                  </td>
                  <td className="px-4 py-3 text-ink">
                    {(s.sports ?? []).map(sportLabel).join(", ") || "—"}
                  </td>
                  <td className="px-4 py-3">
                    <StatusBadge status={s.status} />
                  </td>
                  <td className="px-4 py-3 text-ink">
                    {s.confidence != null ? s.confidence.toFixed(2) : "—"}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex flex-wrap gap-2">
                      <Link
                        to={`/admin/spot/${s.id}/edit`}
                        className="rounded-lg border border-teal/30 px-2.5 py-1 text-label font-medium text-teal hover:bg-teal/5"
                      >
                        Bearbeiten
                      </Link>
                      <a
                        href={`/spot/${s.id}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="rounded-lg border border-teal/30 px-2.5 py-1 text-label font-medium text-teal hover:bg-teal/5"
                      >
                        Ansehen ↗
                      </a>
                      {s.status !== "published" && (
                        <button
                          type="button"
                          disabled={busyId === s.id}
                          onClick={() => onGoLive(s)}
                          className="rounded-lg bg-green px-2.5 py-1 text-label font-medium text-white hover:opacity-90 disabled:opacity-50"
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
                          className="rounded-lg border border-teal/30 px-2.5 py-1 text-label font-medium text-teal hover:bg-teal/5 disabled:opacity-50"
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
                          className="rounded-lg border border-line px-2.5 py-1 text-label font-medium text-muted hover:bg-teal/5 disabled:opacity-50"
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
      <div className="mt-4 flex items-center justify-between text-label text-muted">
        <span>
          {total === 0 ? "0" : `${offset + 1}–${offset + shown}`} von {total}
        </span>
        <div className="flex gap-2">
          <button
            type="button"
            disabled={offset === 0}
            onClick={() => setOffset(Math.max(0, offset - PAGE))}
            className="rounded-lg border border-teal/30 px-3 py-1.5 font-medium text-teal hover:bg-teal/5 disabled:opacity-40"
          >
            Zurück
          </button>
          <button
            type="button"
            disabled={offset + shown >= total}
            onClick={() => setOffset(offset + PAGE)}
            className="rounded-lg border border-teal/30 px-3 py-1.5 font-medium text-teal hover:bg-teal/5 disabled:opacity-40"
          >
            Weiter
          </button>
        </div>
      </div>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    published: "bg-green/10 text-green",
    draft: "bg-ink/5 text-muted",
    archived: "bg-muted/10 text-muted",
  };
  return (
    <span
      className={`inline-block rounded-2xl px-2 py-0.5 text-caption font-medium ${
        styles[status] ?? "bg-ink/5 text-muted"
      }`}
    >
      {statusLabel(status)}
    </span>
  );
}
