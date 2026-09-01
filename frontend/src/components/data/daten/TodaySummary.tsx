import { useMemo, useRef } from "react";
import type { NormalizedForecastSeries, NormalizedForecastDay } from "../../../lib/forecastNormalization";
import { useSpotDataScope } from "../../../state/SpotDataScope";
import { sunTimes } from "../../../lib/sunTimes";
import WeatherGlyph from "./WeatherGlyph";

/**
 * Left column of the Daten-page middle band (Figma Frame 67): the big current
 * temperature with condition glyph and today's high/low, a sun-position curve,
 * and a filled temperature-area graph for the selected day whose marker is
 * bound to the shared selection.
 */
export default function TodaySummary({
  forecast,
  lat,
  lng,
}: {
  forecast: NormalizedForecastSeries;
  lat?: number;
  lng?: number;
}) {
  const { selectedForecast, selectedAtUtc, setSelectedAtUtc } = useSpotDataScope();

  // Always resolve to a day that actually carries hourly values — the shared
  // selection can land on a trend day (no hours), which would otherwise blank
  // the high/low and the area graph.
  const day = useMemo<NormalizedForecastDay | null>(() => {
    const hourly = forecast.days.filter((d) => d.hours.length >= 2);
    const date = selectedForecast?.localDate;
    return (
      hourly.find((d) => (d.local_date ?? d.date) === date) ??
      hourly.find((d) => d.hours.some((h) => h.utcKey === selectedAtUtc)) ??
      hourly[0] ??
      null
    );
  }, [forecast.days, selectedForecast?.localDate, selectedAtUtc]);

  const current = selectedForecast?.air ?? day?.hours.find((h) => h.air != null)?.air ?? null;
  const hi = day?.summary.air_max ?? day?.summary.temperature_max_c ?? null;
  const lo = day?.summary.air_min ?? day?.summary.temperature_min_c ?? null;
  const condition = selectedForecast?.weather_condition ?? day?.summary.weather_condition;

  return (
    <div className="flex flex-col gap-8">
      <div className="flex flex-wrap items-center gap-x-5 gap-y-2">
        <span className="font-semibold leading-none tracking-tight text-ink tabular-nums" style={{ fontSize: 56 }}>
          {current == null ? (
            <span className="text-muted">—</span>
          ) : (
            <>
              {Math.round(current)}
              <span className="align-top text-sz-28 text-muted">C</span>
            </>
          )}
        </span>
        <WeatherGlyph condition={condition} size={30} />
        <span className="flex items-center gap-3 text-ui text-muted">
          <span className="tabular-nums">↑ {hi == null ? "—" : Math.round(hi)}C</span>
          <span className="tabular-nums">↓ {lo == null ? "—" : Math.round(lo)}C</span>
        </span>
      </div>

      <SunCurve lat={lat} lng={lng} />

      {day && <DayTempArea day={day} selectedUtc={selectedAtUtc} onSelect={setSelectedAtUtc} />}
    </div>
  );
}

function SunCurve({ lat, lng }: { lat?: number; lng?: number }) {
  const now = new Date();
  const sun = useMemo(
    () => (lat != null && lng != null ? sunTimes(lat, lng, now) : null),
    [lat, lng, now.toDateString()], // eslint-disable-line react-hooks/exhaustive-deps
  );

  const W = 300;
  const H = 120;
  const baseY = 78;
  const peak = 26;
  // Smooth hill above a horizontal baseline (Figma sun-position curve).
  const path = `M0,${baseY} C ${W * 0.28},${baseY} ${W * 0.32},${peak} ${W * 0.5},${peak} S ${W * 0.72},${baseY} ${W},${baseY}`;

  let dot: { x: number; y: number } | null = null;
  if (sun) {
    const utcHour = now.getUTCHours() + now.getUTCMinutes() / 60;
    const localHour = ((utcHour + (lng ?? 0) / 15) % 24 + 24) % 24;
    const progress = Math.min(1, Math.max(0, (localHour - sun.sunrise) / Math.max(0.1, sun.sunset - sun.sunrise)));
    const x = progress * W;
    // Approximate the curve height at x with a sine hump.
    const y = baseY - Math.sin(progress * Math.PI) * (baseY - peak);
    dot = { x, y };
  }

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="h-auto w-full max-w-[320px]" role="img" aria-label="Sonnenstand über den Tag">
      <line x1={0} y1={baseY} x2={W} y2={baseY} stroke="var(--sw-line)" strokeWidth={1.5} />
      <path d={path} fill="none" stroke="var(--sw-ink)" strokeWidth={2} strokeLinecap="round" />
      {dot && <circle cx={dot.x} cy={dot.y} r={6} fill="var(--sw-surface)" stroke="var(--sw-ink)" strokeWidth={2.5} />}
    </svg>
  );
}

function DayTempArea({
  day,
  selectedUtc,
  onSelect,
}: {
  day: NormalizedForecastDay;
  selectedUtc: string | null;
  onSelect: (utc: string | null) => void;
}) {
  const ref = useRef<SVGSVGElement>(null);
  const hours = day.hours.filter((h) => h.air != null);
  const W = 620;
  const H = 150;
  const padB = 22;
  const padT = 14;

  const geom = useMemo(() => {
    if (hours.length < 2) return null;
    const temps = hours.map((h) => h.air as number);
    const min = Math.min(...temps);
    const max = Math.max(...temps);
    const span = Math.max(1, max - min);
    const x = (i: number) => (i / (hours.length - 1)) * W;
    const y = (t: number) => padT + (1 - (t - min) / span) * (H - padT - padB);
    const line = hours.map((h, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(h.air as number).toFixed(1)}`).join(" ");
    const area = `${line} L${W},${H - padB} L0,${H - padB} Z`;
    return { x, y, line, area };
  }, [hours]);

  if (!geom) return null;

  const selIdx = hours.findIndex((h) => h.utcKey === selectedUtc);
  const pick = (clientX: number) => {
    const el = ref.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const ratio = (clientX - rect.left) / rect.width;
    const idx = Math.min(hours.length - 1, Math.max(0, Math.round(ratio * (hours.length - 1))));
    onSelect(hours[idx]?.utcKey ?? null);
  };

  return (
    <svg
      ref={ref}
      viewBox={`0 0 ${W} ${H}`}
      className="h-auto w-full max-w-[640px] cursor-pointer touch-none"
      role="group"
      aria-label="Temperaturverlauf des Tages — Zeitpunkt wählen"
      onPointerDown={(e) => {
        (e.currentTarget as unknown as HTMLElement).setPointerCapture?.(e.pointerId);
        pick(e.clientX);
      }}
      onPointerMove={(e) => {
        if (e.buttons === 1) pick(e.clientX);
      }}
    >
      <line x1={0} y1={H - padB} x2={W} y2={H - padB} stroke="var(--sw-line)" strokeWidth={1} />
      {hours.map((h, i) =>
        h.localHour % 2 === 0 ? (
          <g key={i}>
            <line x1={geom.x(i)} y1={padT} x2={geom.x(i)} y2={H - padB} stroke="var(--sw-line-soft)" strokeWidth={1} />
            <text x={geom.x(i)} y={H - 6} textAnchor="middle" fontSize={9} fill="var(--sw-muted)">
              {h.localTime.slice(0, 2)}
            </text>
          </g>
        ) : null,
      )}
      <path d={geom.area} fill="var(--sw-data-temp)" opacity={0.1} />
      <path d={geom.line} fill="none" stroke="var(--sw-data-temp)" strokeWidth={2} strokeLinejoin="round" />
      {selIdx >= 0 && (
        <circle cx={geom.x(selIdx)} cy={geom.y(hours[selIdx].air as number)} r={6} fill="var(--sw-surface)" stroke="var(--sw-data-temp)" strokeWidth={2.5} />
      )}
    </svg>
  );
}
