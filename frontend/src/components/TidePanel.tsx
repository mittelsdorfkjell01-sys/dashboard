import { useEffect, useMemo, useState } from "react";
import {
  getSpotTides,
  type PublicTides,
  type PublicTideEvent,
  type PublicTideSeriesPoint,
} from "../lib/api";
import { formatTideTime } from "../lib/tideTime";

export { formatTideTime } from "../lib/tideTime";

const PHASE_LABELS: Record<PublicTides["phase"], string> = {
  rising: "Steigend",
  high: "Hochwasser",
  falling: "Fallend",
  low: "Niedrigwasser",
  unavailable: "Nicht verfügbar",
};

const QUALITY_LABELS: Record<PublicTides["quality"], string> = {
  unavailable: "Nicht verfügbar",
  model_only: "Modell",
  reviewed_anchor: "Geprüfter Modellpunkt",
  manual_calibrated: "Lokal kalibriert",
  gauge_calibrated: "Messstation-kalibriert",
};

function EventTime({ event, timezone, prominent = false }: {
  event: PublicTideEvent; timezone: string; prominent?: boolean;
}) {
  const shown = formatTideTime(event.time, timezone, event.uncertainty_minutes);
  return (
    <div className={prominent ? "min-w-0 border-l-2 border-ink pl-3" : "grid grid-cols-[5.5rem_1fr] items-baseline gap-3"}>
      <p className="text-caption font-medium uppercase text-muted">
        {event.event_type === "high" ? "Hochwasser" : "Niedrigwasser"}
      </p>
      <div className={prominent ? "mt-1" : "min-w-0"}>
        <p className={`${prominent ? "text-ui" : "text-ui"} font-semibold text-ink`}>{shown.time}</p>
        <p className="text-caption text-muted">{shown.date}</p>
      </div>
    </div>
  );
}

function buildTideCurve(series: PublicTideSeriesPoint[]) {
  const visible = series.slice(0, 49);
  if (visible.length < 2) return null;
  const x0 = +new Date(visible[0].time);
  const x1 = +new Date(visible[visible.length - 1].time);
  const span = Math.max(1, x1 - x0);
  const points = visible.map((point) => ({
    x: ((+new Date(point.time) - x0) / span) * 100,
    y: 10 + (1 - point.level_normalized) * 80,
  }));
  return {
    path: points.map(({ x, y }, index) => `${index ? "L" : "M"}${x.toFixed(2)},${y.toFixed(2)}`).join(" "),
    nowX: points[0].x,
    nowY: points[0].y,
  };
}

export default function TidePanel({ spotId }: { spotId: string }) {
  const [data, setData] = useState<PublicTides | null>(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    let active = true;
    setLoading(true);
    getSpotTides(spotId)
      .then((result) => active && setData(result))
      .catch(() => active && setData({
        available: false,
        message: "Für diesen Spot sind derzeit keine verlässlichen Gezeitenangaben verfügbar.",
        timezone: null, phase: "unavailable", cycle_position: null,
        quality: "unavailable", approximate: true, last_calculated_at: null,
        valid_until: null, forecast_start: null, forecast_end: null,
        horizon_days: 0, partial: false, datum: "relative_low_high",
        model_name: null, model_version: null, events: [], series: [],
      }))
      .finally(() => active && setLoading(false));
    return () => { active = false; };
  }, [spotId]);

  const futureEvents = useMemo(() => {
    const now = Date.now();
    return data?.events.filter((item) => +new Date(item.time) >= now) ?? [];
  }, [data]);
  const next = useMemo(() => ({
    high: futureEvents.find((item) => item.event_type === "high"),
    low: futureEvents.find((item) => item.event_type === "low"),
  }), [futureEvents]);

  const curve = useMemo(() => (data ? buildTideCurve(data.series) : null), [data]);

  if (loading) return <div className="h-48 animate-pulse bg-band" role="status" aria-label="Gezeiten werden geladen" />;
  if (!data?.available || !data.timezone) return null;

  return (
    <section aria-label="Gezeitenvorhersage" className="mt-12 border-t border-line pt-8">
      <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-caption font-medium uppercase tracking-wider text-muted">Gezeiten · 10 Tage</p>
          <h2 className="mt-1 text-subtitle font-semibold text-ink">Astronomische Tide</h2>
        </div>
        <p className="text-caption text-muted">{QUALITY_LABELS[data.quality]} · relativer Pegelstand</p>
      </div>
      <div className="grid gap-6 lg:grid-cols-[1fr_1fr]">
        <div className="min-w-0">
          <div className="flex items-center justify-between gap-4 border-b border-line pb-3">
            <div>
              <p className="text-caption uppercase text-muted">Aktuelle Tide</p>
              <p className="mt-1 text-ui font-semibold text-ink">{PHASE_LABELS[data.phase]}</p>
            </div>
          </div>

          {curve && (
            <svg
              viewBox="0 0 100 100"
              preserveAspectRatio="none"
              className="mt-3 h-20 w-full"
              role="img"
              aria-label={`Gezeitenrhythmus der nächsten 48 Stunden, aktuell ${PHASE_LABELS[data.phase].toLowerCase()}. Werte relativ, keine absolute Höhe.`}
            >
              <path d={curve.path} fill="none" stroke="var(--sw-teal)" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" vectorEffect="non-scaling-stroke" />
              <circle cx={curve.nowX} cy={curve.nowY} r={2.2} fill="var(--sw-surface)" stroke="var(--sw-teal)" strokeWidth={1.6} vectorEffect="non-scaling-stroke" />
            </svg>
          )}

          <div className="mt-4 grid gap-5 sm:grid-cols-2">
            {next.high && <EventTime event={next.high} timezone={data.timezone} prominent />}
            {next.low && <EventTime event={next.low} timezone={data.timezone} prominent />}
          </div>
          <p className="mt-4 text-caption leading-relaxed text-muted">
            Astronomische Prognose, ungefähr und gegebenenfalls lokal korrigiert. Wetter, Sturmflut, Abfluss und Strömung können abweichen.
          </p>
          <p className="mt-2 text-caption text-muted">
            Modell: {data.model_name ?? "FES2022"}{data.model_version ? ` ${data.model_version}` : ""}. Keine Navigations- oder Sturmflutwarnung.
          </p>
        </div>
        <div className="min-w-0 border-t border-line pt-4 lg:border-l lg:border-t-0 lg:pl-6 lg:pt-0">
          <p className="mb-3 text-caption font-medium uppercase text-muted">Nächste Ereignisse</p>
          <div className="grid gap-3 sm:grid-cols-2">
            {futureEvents.slice(0, 12).map((event) => (
              <EventTime key={event.id} event={event} timezone={data.timezone!} />
            ))}
          </div>
          {data.last_calculated_at && (
            <p className="mt-4 text-caption text-muted">
              Zuletzt berechnet: {new Intl.DateTimeFormat("de-DE", { dateStyle: "medium", timeStyle: "short", timeZone: data.timezone }).format(new Date(data.last_calculated_at))}
            </p>
          )}
          {data.message && <p className="mt-2 text-caption text-warning">{data.message}</p>}
        </div>
      </div>
    </section>
  );
}
