import { useCallback, useEffect, useMemo, useState } from "react";

import { Badge, Button, PageHeader, type BadgeTone } from "../components/admin/ui";
import {
  ApiError,
  enqueueWeatherFieldShadowValidation,
  getWeatherFieldShadowMetrics,
  getWeatherFieldShadowRuns,
  getWeatherFieldShadowStatus,
  type WeatherFieldShadowMetric,
  type WeatherFieldShadowRun,
  type WeatherFieldShadowStatus,
} from "../lib/api";

const statusTone: Record<string, BadgeTone> = {
  succeeded: "success",
  processing: "info",
  no_data: "warning",
  failed: "danger",
};

const number = (value: number | null | undefined, digits = 2) =>
  value == null ? "—" : value.toLocaleString("de-DE", { maximumFractionDigits: digits });

const dateTime = (value: string | null | undefined) =>
  value ? new Date(value).toLocaleString("de-DE", { dateStyle: "short", timeStyle: "short" }) : "—";

const dimensions = (value: Record<string, string>) =>
  Object.entries(value)
    .map(([key, item]) => `${key}: ${item}`)
    .join(" · ");

export default function AdminWeatherFields() {
  const [status, setStatus] = useState<WeatherFieldShadowStatus | null>(null);
  const [runs, setRuns] = useState<WeatherFieldShadowRun[]>([]);
  const [metrics, setMetrics] = useState<WeatherFieldShadowMetric[]>([]);
  const [selectedRun, setSelectedRun] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [queueing, setQueueing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const load = useCallback(async (preferredRun?: string | null) => {
    setError(null);
    try {
      const [nextStatus, nextRuns] = await Promise.all([
        getWeatherFieldShadowStatus(),
        getWeatherFieldShadowRuns(),
      ]);
      const runId = preferredRun ?? nextRuns.runs[0]?.id ?? null;
      const nextMetrics = await getWeatherFieldShadowMetrics(runId ?? undefined);
      setStatus(nextStatus);
      setRuns(nextRuns.runs);
      setSelectedRun(nextMetrics.run_id);
      setMetrics(nextMetrics.metrics);
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : "Shadow-Auswertung konnte nicht geladen werden.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const onSelectRun = async (runId: string) => {
    setSelectedRun(runId);
    setError(null);
    try {
      const next = await getWeatherFieldShadowMetrics(runId);
      setMetrics(next.metrics);
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : "Metriken konnten nicht geladen werden.");
    }
  };

  const onQueue = async () => {
    setQueueing(true);
    setError(null);
    setMessage(null);
    try {
      const result = await enqueueWeatherFieldShadowValidation();
      setMessage(result.status === "deduplicated" ? "Der Lauf ist bereits eingereiht." : "Shadowlauf wurde eingereiht.");
      await load(selectedRun);
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : "Shadowlauf konnte nicht eingereiht werden.");
    } finally {
      setQueueing(false);
    }
  };

  const overall = useMemo(
    () => metrics.find((metric) => metric.dimensions.scope === "overall"),
    [metrics],
  );

  if (loading) return <div role="status" className="text-label text-admin-muted">Windfeld-Evidenz wird geladen…</div>;
  if (!status) return <div role="alert" className="text-label text-admin-danger">{error ?? "Keine Statusdaten verfügbar."}</div>;

  return (
    <div className="max-w-7xl">
      <PageHeader title="Windfeld-Shadow" />
      <h1 className="sr-only">Windfeld-Shadow-Validierung</h1>

      <div className="flex flex-col gap-4 border-b border-admin-border pb-6 lg:flex-row lg:items-end lg:justify-between">
        <div className="max-w-3xl">
          <p className="text-lg font-semibold text-admin-fg">Bestehender Spotforecast gegen veröffentlichtes Modellfeld</p>
          <p className="mt-2 text-ui leading-6 text-admin-fg2">
            Die Auswertung speichert Abweichungen als interne Evidenz. Sie verändert weder Spotforecasts noch Feldpublikationen und autorisiert keinen Cutover.
          </p>
        </div>
        <Button onClick={onQueue} disabled={!status.enabled || !status.active_publication_id || queueing}>
          {queueing ? "Wird eingereiht…" : "Shadowlauf einreihen"}
        </Button>
      </div>

      {error && <div role="alert" className="mt-4 rounded-md border border-admin-danger-border bg-admin-danger-bg px-4 py-3 text-label text-admin-danger">{error}</div>}
      {message && <div role="status" className="mt-4 rounded-md border border-admin-border bg-admin-surface px-4 py-3 text-label text-admin-fg">{message}</div>}

      <dl className="mt-6 grid gap-x-8 gap-y-5 border-b border-admin-border pb-6 sm:grid-cols-2 lg:grid-cols-4">
        <div><dt className="text-caption uppercase tracking-wide text-admin-muted">Betriebsstatus</dt><dd className="mt-1"><Badge tone={status.enabled ? "success" : "neutral"}>{status.enabled ? "Aktiviert" : "Deaktiviert"}</Badge></dd></div>
        <div><dt className="text-caption uppercase tracking-wide text-admin-muted">Pilotgruppe</dt><dd className="admin-mono mt-1 text-ui text-admin-fg">{status.pilot.group} · max. {status.pilot.max_spots} Spots</dd></div>
        <div><dt className="text-caption uppercase tracking-wide text-admin-muted">Horizont</dt><dd className="admin-mono mt-1 text-ui text-admin-fg">T+0 bis T+{status.pilot.max_horizon_hours}</dd></div>
        <div><dt className="text-caption uppercase tracking-wide text-admin-muted">Cutover</dt><dd className="mt-1"><Badge tone="warning">Nicht autorisiert</Badge></dd></div>
      </dl>

      {!status.enabled && (
        <p className="mt-5 text-label text-admin-muted">
          Zum Sammeln neuer Evidenz muss <span className="admin-mono text-admin-fg">WEATHER_FIELD_SHADOW_ENABLED=true</span> im Worker gesetzt sein. Bestehende Ergebnisse bleiben lesbar.
        </p>
      )}

      <section className="mt-8" aria-labelledby="shadow-runs-title">
        <div className="flex items-center justify-between gap-4">
          <h2 id="shadow-runs-title" className="text-lg font-semibold text-admin-fg">Läufe</h2>
          <Button variant="secondary" onClick={() => void load(selectedRun)}>Aktualisieren</Button>
        </div>
        <div tabIndex={0} aria-label="Shadowläufe horizontal scrollen" className="mt-3 overflow-x-auto rounded-lg border border-admin-border bg-admin-surface focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-admin-primary">
          <table className="w-full min-w-[900px] text-left text-ui">
            <thead className="border-b border-admin-border bg-admin-hover text-caption uppercase text-admin-muted"><tr>{["Status", "Start", "Pilotspots", "Samples", "Evidenz", "Profil", "Auswertung"].map((heading) => <th key={heading} className="px-3 py-2 font-semibold">{heading}</th>)}</tr></thead>
            <tbody className="divide-y divide-admin-border-subtle">
              {runs.length === 0 ? <tr><td colSpan={7} className="px-4 py-8 text-center text-admin-muted">Noch keine Shadow-Evidenz. Aktive ForecastSnapshots werden für den ersten Lauf benötigt.</td></tr> : runs.map((run) => (
                <tr key={run.id}>
                  <td className="px-3 py-3"><Badge tone={statusTone[run.status] ?? "neutral"}>{run.status}</Badge></td>
                  <td className="px-3 py-3 text-caption">{dateTime(run.started_at)}</td>
                  <td className="admin-mono px-3 py-3">{run.diagnostics.pilot_spots ?? 0}</td>
                  <td className="admin-mono px-3 py-3">{run.diagnostics.samples ?? 0}</td>
                  <td className="px-3 py-3">{run.diagnostics.evidence_status ?? "—"}</td>
                  <td className="admin-mono px-3 py-3 text-caption">{run.profile_version}</td>
                  <td className="px-3 py-3"><Button variant={selectedRun === run.id ? "primary" : "secondary"} onClick={() => void onSelectRun(run.id)}>Anzeigen</Button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="mt-8" aria-labelledby="shadow-metrics-title">
        <h2 id="shadow-metrics-title" className="text-lg font-semibold text-admin-fg">Abweichungsmetriken</h2>
        <p className="mt-1 max-w-3xl text-caption text-admin-muted">Positive Bias-Werte bedeuten: Das Windfeld liegt über dem bestehenden Spotforecast. Diese Differenz ist noch keine Messgüte und kein Confidence Score.</p>
        {overall && (
          <dl className="mt-4 grid gap-x-8 gap-y-4 border-y border-admin-border py-5 sm:grid-cols-2 lg:grid-cols-4">
            <div><dt className="text-caption text-admin-muted">Samples</dt><dd className="admin-mono mt-1 text-sz-20 font-semibold text-admin-fg">{overall.sample_count}</dd></div>
            <div><dt className="text-caption text-admin-muted">Wind MAE</dt><dd className="admin-mono mt-1 text-sz-20 font-semibold text-admin-fg">{number(overall.metrics.speed?.mae_ms)} m/s</dd></div>
            <div><dt className="text-caption text-admin-muted">Wind Bias</dt><dd className="admin-mono mt-1 text-sz-20 font-semibold text-admin-fg">{number(overall.metrics.speed?.bias_ms)} m/s</dd></div>
            <div><dt className="text-caption text-admin-muted">Richtung MAE</dt><dd className="admin-mono mt-1 text-sz-20 font-semibold text-admin-fg">{number(overall.metrics.direction_mae_deg, 1)}°</dd></div>
          </dl>
        )}
        <div tabIndex={0} aria-label="Shadowmetriken horizontal scrollen" className="mt-4 overflow-x-auto rounded-lg border border-admin-border bg-admin-surface focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-admin-primary">
          <table className="w-full min-w-[880px] text-left text-ui">
            <thead className="border-b border-admin-border bg-admin-hover text-caption uppercase text-admin-muted"><tr>{["Segment", "N", "Wind MAE", "Wind Bias", "RMSE", "Richtung MAE", "Böen MAE"].map((heading) => <th key={heading} className="px-3 py-2 font-semibold">{heading}</th>)}</tr></thead>
            <tbody className="divide-y divide-admin-border-subtle">
              {metrics.length === 0 ? <tr><td colSpan={7} className="px-4 py-8 text-center text-admin-muted">Für diesen Lauf liegen noch keine Vergleichssamples vor.</td></tr> : metrics.map((metric) => (
                <tr key={JSON.stringify(metric.dimensions)}>
                  <td className="px-3 py-3 text-caption text-admin-fg2">{dimensions(metric.dimensions)}</td>
                  <td className="admin-mono px-3 py-3">{metric.sample_count}</td>
                  <td className="admin-mono px-3 py-3">{number(metric.metrics.speed?.mae_ms)}</td>
                  <td className="admin-mono px-3 py-3">{number(metric.metrics.speed?.bias_ms)}</td>
                  <td className="admin-mono px-3 py-3">{number(metric.metrics.speed?.rmse_ms)}</td>
                  <td className="admin-mono px-3 py-3">{number(metric.metrics.direction_mae_deg, 1)}</td>
                  <td className="admin-mono px-3 py-3">{number(metric.metrics.gust?.mae_ms)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
