// Consolidated operations view: climatology freshness, queue depth and the
// recent ERA5 runs in one place, so an operator can answer "why has this spot
// no wind data — and is a retry already running?" without log access. Reads the
// existing job/freshness state; the only action is a safe per-spot retry (the
// same idempotent endpoint the editor uses).

import { useCallback, useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import {
  ApiError,
  getOperations,
  triggerEra5,
  type AdminOperations as Ops,
  type OpsJob,
} from "../lib/api";
import { PageHeader, Badge, Button, type BadgeTone } from "../components/admin/ui";
import { createAdminReturnState } from "../lib/adminNavigation";

const STATUS_TONE: Record<string, BadgeTone> = {
  current: "success",
  derived: "success",
  ok: "success",
  queued: "info",
  processing: "info",
  extracting: "info",
  stale: "warning",
  missing: "neutral",
  failed: "danger",
};

const ERROR_LABEL: Record<string, string> = {
  quota: "Kontingent/Rate",
  coordinates: "Koordinaten",
  validation: "Validierung",
  provider: "Anbieter",
  unknown: "Unbekannt",
};

const fmtTime = (iso: string | null) =>
  iso ? new Date(iso).toLocaleString("de-DE", { dateStyle: "short", timeStyle: "short" }) : "—";

export default function AdminOperations() {
  const location = useLocation();
  const editorState = createAdminReturnState(location, "Betrieb");
  const [data, setData] = useState<Ops | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [retrying, setRetrying] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      setData(await getOperations());
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Laden fehlgeschlagen.");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const onRetry = async (spotId: string) => {
    setRetrying(spotId);
    setError(null);
    try {
      await triggerEra5(spotId);
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Retry fehlgeschlagen.");
    } finally {
      setRetrying(null);
    }
  };

  if (error && !data)
    return (
      <div role="alert" className="rounded-md border border-admin-danger-border bg-admin-danger-bg px-4 py-3 text-label text-admin-danger">
        {error}
      </div>
    );
  if (!data) return <div role="status" className="text-label text-admin-muted">Lädt…</div>;

  const f = data.freshness;
  const tiles: { label: string; value: number; tone: BadgeTone }[] = [
    { label: "Aktuell", value: f.current, tone: "success" },
    { label: "Veraltet", value: f.stale, tone: "warning" },
    { label: "Fehlend", value: f.missing, tone: "neutral" },
    { label: "Fehlgeschlagen", value: f.failed, tone: "danger" },
  ];

  return (
    <div>
      <PageHeader title="Betrieb" />
      <h1 className="sr-only">Betrieb</h1>

      {error && (
        <div role="alert" className="mb-4 rounded-md border border-admin-danger-border bg-admin-danger-bg px-3 py-2 text-label text-admin-danger">
          {error}
        </div>
      )}

      {/* Climatology freshness — the health of the public wind/climate data. */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {tiles.map((t) => (
          <div key={t.label} className="rounded-lg border border-admin-border bg-admin-surface p-4">
            <Badge tone={t.tone}>{t.label}</Badge>
            <div className="admin-mono mt-2 text-[20px] font-semibold leading-none text-admin-fg">
              {t.value}
            </div>
          </div>
        ))}
      </div>

      {/* Operational context: queue depth + when a fix goes public. */}
      <div className="mt-4 flex flex-wrap items-center gap-x-6 gap-y-1 rounded-lg border border-admin-border bg-admin-surface px-4 py-3 text-caption text-admin-muted">
        <span>
          Warteschlange: <span className="admin-mono text-admin-fg">{data.queue_depth}</span>
        </span>
        <span>Neuberechnung: {data.public_update.climatology_cron}</span>
        <span>{data.public_update.edge_cache}</span>
      </div>

      {/* Recent ERA5 runs. */}
      <h2 className="mt-8 text-label font-semibold text-admin-fg">Letzte Läufe</h2>
      <div
        tabIndex={0}
        aria-label="Tabelle der Betriebsläufe horizontal scrollen"
        className="mt-3 overflow-x-auto rounded-lg border border-admin-border bg-admin-surface focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-admin-primary focus-visible:ring-offset-2 focus-visible:ring-offset-admin-bg"
      >
        <table className="w-full min-w-[820px] text-left text-ui">
          <thead className="border-b border-admin-border bg-admin-hover text-caption uppercase tracking-wide text-admin-muted">
            <tr>
              <th className="px-4 py-2.5 font-semibold">Spot</th>
              <th className="px-4 py-2.5 font-semibold">Status</th>
              <th className="px-4 py-2.5 font-semibold">Grund</th>
              <th className="px-4 py-2.5 font-semibold">Dauer</th>
              <th className="px-4 py-2.5 font-semibold">Fehler</th>
              <th className="px-4 py-2.5 font-semibold">Erstellt</th>
              <th className="px-4 py-2.5 font-semibold">Aktion</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-admin-border-subtle">
            {data.recent_jobs.length === 0 ? (
              <tr>
                <td colSpan={7} className="px-4 py-10 text-center text-admin-muted">
                  Keine Läufe erfasst.
                </td>
              </tr>
            ) : (
              data.recent_jobs.map((j: OpsJob) => (
                <tr key={j.job_id} className="align-top">
                  <td className="px-4 py-3">
                    {j.spot_id ? (
                      <Link
                        to={`/admin/spot/${j.spot_id}/edit`}
                        state={editorState}
                        className="font-medium text-admin-fg hover:text-admin-primary"
                      >
                        {j.spot_name ?? j.spot_id}
                      </Link>
                    ) : (
                      <span className="text-admin-muted">—</span>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <Badge tone={STATUS_TONE[j.status] ?? "neutral"}>{j.status}</Badge>
                  </td>
                  <td className="px-4 py-3 text-label text-admin-fg2">{j.reason ?? "—"}</td>
                  <td className="admin-mono px-4 py-3 text-label text-admin-fg2">
                    {j.duration_s != null ? `${j.duration_s}s` : "—"}
                  </td>
                  <td className="px-4 py-3 text-label">
                    {j.error_category ? (
                      <span className="text-admin-danger" title={j.error ?? undefined}>
                        {ERROR_LABEL[j.error_category] ?? j.error_category}
                      </span>
                    ) : (
                      <span className="text-admin-muted">—</span>
                    )}
                  </td>
                  <td className="admin-mono px-4 py-3 text-label text-admin-muted">
                    {fmtTime(j.created_at)}
                  </td>
                  <td className="px-4 py-3">
                    {j.spot_id && (
                      <Button
                        variant="secondary"
                        onClick={() => onRetry(j.spot_id!)}
                        disabled={retrying === j.spot_id}
                      >
                        {retrying === j.spot_id ? "…" : "Neu berechnen"}
                      </Button>
                    )}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
