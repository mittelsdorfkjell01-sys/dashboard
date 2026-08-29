import { useEffect, useMemo, useState } from "react";
import { getSpotTides, type PublicTides, type PublicTideEvent } from "../lib/api";
import { formatTideTime } from "../lib/tideTime";

export { formatTideTime } from "../lib/tideTime";

const PHASE_LABELS: Record<PublicTides["phase"], string> = {
  rising: "Steigend",
  high: "Hochwasser",
  falling: "Fallend",
  low: "Niedrigwasser",
  unavailable: "Nicht verfügbar",
};

function EventTime({ event, timezone, prominent = false }: {
  event: PublicTideEvent; timezone: string; prominent?: boolean;
}) {
  const shown = formatTideTime(event.time, timezone, event.uncertainty_minutes);
  return (
    <div className={prominent ? "min-w-0 border-l-2 border-teal pl-3" : "grid grid-cols-[5.5rem_1fr] items-baseline gap-3"}>
      <p className="text-caption font-medium uppercase text-muted">
        {event.event_type === "high" ? "Hochwasser" : "Niedrigwasser"}
      </p>
      <div className={prominent ? "mt-1" : "min-w-0"}>
        <p className={`${prominent ? "text-ui" : "text-label"} font-semibold text-ink`}>{shown.time}</p>
        <p className="text-caption text-muted">{shown.date}</p>
      </div>
    </div>
  );
}

// Cosine-eased interpolation between consecutive high/low events — the tide
// curve's real shape (two highs, two lows a day), not a straight ramp. There
// is no height reading from the API (events carry only time), so the curve
// is a relative rhythm (0 = low, 1 = high), not an absolute-height chart.
function buildTideCurve(events: PublicTideEvent[], now: Date) {
  const sorted = [...events].sort((a, b) => +new Date(a.time) - +new Date(b.time));
  if (sorted.length < 2) return null;

  const xs = sorted.map((e) => +new Date(e.time));
  const x0 = xs[0], x1 = xs[xs.length - 1];
  const span = Math.max(1, x1 - x0);
  const yFor = (e: PublicTideEvent) => (e.event_type === "high" ? 0 : 1); // SVG y: 0 = top = high

  const points: [number, number][] = [];
  const STEPS = 10;
  for (let i = 0; i < sorted.length - 1; i++) {
    const [xa, ya] = [xs[i], yFor(sorted[i])];
    const [xb, yb] = [xs[i + 1], yFor(sorted[i + 1])];
    for (let s = i === 0 ? 0 : 1; s <= STEPS; s++) {
      const t = s / STEPS;
      const eased = (1 - Math.cos(t * Math.PI)) / 2;
      points.push([xa + (xb - xa) * t, ya + (yb - ya) * eased]);
    }
  }

  const toXY = ([x, y]: [number, number]): [number, number] => [((x - x0) / span) * 100, 10 + y * 80];
  const path = points.map(toXY).map(([x, y], i) => `${i ? "L" : "M"}${x.toFixed(2)},${y.toFixed(2)}`).join(" ");

  const nowMs = Math.min(x1, Math.max(x0, now.getTime()));
  let seg = 0;
  while (seg < sorted.length - 2 && xs[seg + 1] < nowMs) seg++;
  const [xa, ya] = [xs[seg], yFor(sorted[seg])];
  const [xb, yb] = [xs[seg + 1], yFor(sorted[seg + 1])];
  const t = xb === xa ? 0 : Math.min(1, Math.max(0, (nowMs - xa) / (xb - xa)));
  const eased = (1 - Math.cos(t * Math.PI)) / 2;
  const [nowX, nowY] = toXY([xa + (xb - xa) * t, ya + (yb - ya) * eased]);

  return { path, nowX, nowY };
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
        valid_until: null, events: [],
      }))
      .finally(() => active && setLoading(false));
    return () => { active = false; };
  }, [spotId]);

  const next = useMemo(() => ({
    high: data?.events.find((item) => item.event_type === "high"),
    low: data?.events.find((item) => item.event_type === "low"),
  }), [data]);

  const curve = useMemo(() => (data ? buildTideCurve(data.events, new Date()) : null), [data]);

  if (loading) return <div className="h-48 animate-pulse bg-band" role="status" aria-label="Gezeiten werden geladen" />;
  if (!data?.available || !data.timezone) return null;

  return (
    <div>
      <p className="mb-4 text-caption font-medium uppercase tracking-wider text-muted">Gezeiten · 24 h</p>
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
              aria-label={`Gezeitenrhythmus, aktuell ${PHASE_LABELS[data.phase].toLowerCase()}. Werte relativ, keine absolute Höhe.`}
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
          <p className="mt-2 text-caption text-muted">Berechnet mit FES2022, bereitgestellt durch AVISO+ und CNES.</p>
        </div>
        <div className="min-w-0 border-t border-line pt-4 lg:border-l lg:border-t-0 lg:pl-6 lg:pt-0">
          <p className="mb-3 text-caption font-medium uppercase text-muted">Nächste Ereignisse</p>
          <div className="grid gap-3 sm:grid-cols-2">
            {data.events.slice(0, 6).map((event) => (
              <EventTime key={event.id} event={event} timezone={data.timezone!} />
            ))}
          </div>
          {data.last_calculated_at && (
            <p className="mt-4 text-caption text-muted">
              Zuletzt berechnet: {new Intl.DateTimeFormat("de-DE", { dateStyle: "medium", timeStyle: "short", timeZone: data.timezone }).format(new Date(data.last_calculated_at))}
            </p>
          )}
          {data.message && <p className="mt-2 text-caption text-amber-700">{data.message}</p>}
        </div>
      </div>
    </div>
  );
}
