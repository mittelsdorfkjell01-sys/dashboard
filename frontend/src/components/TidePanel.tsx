import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { getSpotTides, type PublicTides, type PublicTideSeriesPoint } from "../lib/api/tides";

export { formatTideTime } from "../lib/tideTime";

// The graph spans a week (2026-11-24: one week instead of one day).
const SPAN_HOURS = 7 * 24;
const VB_W = 1000;
const VB_H = 160;

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

type Chart = {
  path: string;
  area: string;
  /** Y ticks: value label and position (0–100 % from top). */
  yTicks: { label: string; top: number }[];
  /** Day starts along the X axis (0–100 % from left). */
  days: { label: string; left: number }[];
  unit: "m" | "relativ";
  /** The level right now, at the left edge (0–100 % from top). */
  nowTop: number;
  /** Every hour of the span, for scrubbing: place (0–100 %) and reading. */
  points: { left: number; top: number; label: string; time: number }[];
};

function buildChart(series: PublicTideSeriesPoint[] | undefined, timezone: string): Chart | null {
  // A response without a series is out of contract — but a missing curve must
  // never cost the visitor the whole Daten page. No points, no chart.
  const all = series ?? [];
  if (all.length < 2) return null;
  const t0 = +new Date(all[0].time);
  const tEnd = t0 + SPAN_HOURS * 3_600_000;
  const pts = all.filter((p) => +new Date(p.time) <= tEnd);
  if (pts.length < 2) return null;
  const t1 = +new Date(pts[pts.length - 1].time);

  // Metres when every point carries them (modelled sea level); otherwise the
  // relative 0–1 level of the astronomical tide.
  const metres = pts.every((p) => p.level_m != null);
  const values = pts.map((p) => (metres ? (p.level_m as number) : p.level_normalized));
  let lo = 0;
  let hi = 1;
  if (metres) {
    lo = Math.floor(Math.min(...values) * 2) / 2;
    hi = Math.ceil(Math.max(...values) * 2) / 2;
    if (hi - lo < 0.5) hi = lo + 0.5;
  }

  const x = (t: number) => ((t - t0) / Math.max(1, t1 - t0)) * VB_W;
  const y = (v: number) => (1 - (v - lo) / (hi - lo)) * VB_H;
  const path = pts.map((p, i) => `${i ? "L" : "M"}${x(+new Date(p.time)).toFixed(1)},${y(values[i]).toFixed(1)}`).join(" ");
  const area = `${path} L${x(t1).toFixed(1)},${VB_H} L0,${VB_H} Z`;

  const yTicks = metres
    ? [hi, (hi + lo) / 2, lo].map((v) => ({
        // `+ 0` turns -0 into 0, so the axis never prints "-0,0".
        label: (Math.round(v * 10) / 10 + 0).toLocaleString("de-DE", { minimumFractionDigits: 1, maximumFractionDigits: 1 }),
        top: (y(v) / VB_H) * 100,
      }))
    : [
        { label: "hoch", top: 0 },
        { label: "niedrig", top: 100 },
      ];

  // Local midnights inside the span, labelled with the weekday.
  const dayFmt = new Intl.DateTimeFormat("de-DE", { weekday: "short", timeZone: timezone });
  const hourFmt = new Intl.DateTimeFormat("de-DE", { hour: "2-digit", hourCycle: "h23", timeZone: timezone });
  const days: Chart["days"] = [];
  for (const p of pts) {
    const t = +new Date(p.time);
    const hour = hourFmt.formatToParts(t).find((part) => part.type === "hour")?.value;
    if (hour === "00" || hour === "24") days.push({ label: dayFmt.format(t).replace(".", ""), left: (x(t) / VB_W) * 100 });
  }

  const points = pts.map((p, i) => {
    const t = +new Date(p.time);
    const v = values[i];
    return {
      left: (x(t) / VB_W) * 100,
      top: (y(v) / VB_H) * 100,
      // Metres to the centimetre; the relative curve as a share of its range.
      label: metres
        ? `${(Math.round(v * 100) / 100 + 0).toLocaleString("de-DE", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} m`
        : `${Math.round(v * 100)} %`,
      time: t,
    };
  });

  return { path, area, yTicks, days, unit: metres ? "m" : "relativ", nowTop: (y(values[0]) / VB_H) * 100, points };
}

/**
 * Tide on the Daten tab (2026-11-24): one week as a plain chart with an X
 * axis (days) and a Y axis (level), "jetzt" at its left edge. The event
 * list, model notes and source moved to "Daten & Fragen", which explains how
 * the values are made and that they are not for navigation — one link here
 * leads there.
 */
export default function TidePanel({ spotId }: { spotId: string }) {
  const [data, setData] = useState<PublicTides | null>(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    let active = true;
    setLoading(true);
    getSpotTides(spotId)
      .then((result) => active && setData(result))
      .catch(() => active && setData(null))
      .finally(() => active && setLoading(false));
    return () => { active = false; };
  }, [spotId]);

  const chart = useMemo(
    () => (data?.available && data.timezone ? buildChart(data.series, data.timezone) : null),
    [data],
  );

  // Scrubbing (2026-11-25): mouse or finger along the curve picks an hour;
  // its level stands at the left edge, its time above the line.
  const [scrub, setScrub] = useState<number | null>(null);
  const plotRef = useRef<HTMLDivElement>(null);

  if (loading) return <TideSkeleton />;
  if (!data?.available || !data.timezone || !chart) {
    return (
      <section aria-label="Gezeitenvorhersage nicht verfügbar" className="mt-12 border-t border-line pt-8">
        <h2 className="text-lead font-semibold text-ink">Gezeiten</h2>
        <p className="mt-2 max-w-2xl text-ui text-muted">
          {data?.message ?? "Für diesen Küstenpunkt liegen derzeit keine belastbaren Modelldaten vor."}
        </p>
      </section>
    );
  }

  const isAstronomical = data.product_type === "astronomical_tide";
  const title = isAstronomical ? "Astronomische Tide" : "Modellierter Meeresspiegel";
  const phase = PHASE_LABELS[data.phase].toLowerCase();
  const timeFmt = new Intl.DateTimeFormat("de-DE", { weekday: "short", hour: "2-digit", minute: "2-digit", hourCycle: "h23", timeZone: data.timezone });
  const scrubbed = scrub == null ? null : chart.points[scrub] ?? null;
  const pickAt = (clientX: number) => {
    const rect = plotRef.current?.getBoundingClientRect();
    if (!rect || !rect.width) return;
    const pct = Math.max(0, Math.min(100, ((clientX - rect.left) / rect.width) * 100));
    let best = 0;
    for (let i = 1; i < chart.points.length; i++) {
      if (Math.abs(chart.points[i].left - pct) < Math.abs(chart.points[best].left - pct)) best = i;
    }
    setScrub(best);
  };
  const onKeyDown = (event: React.KeyboardEvent<HTMLDivElement>) => {
    const step = event.key === "ArrowRight" ? 1 : event.key === "ArrowLeft" ? -1 : 0;
    if (!step) return;
    event.preventDefault();
    setScrub((current) => Math.max(0, Math.min(chart.points.length - 1, (current ?? 0) + step)));
  };

  return (
    <section aria-label="Gezeitenvorhersage" className="swd-fade-in mt-12 border-t border-line pt-8">
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <h2 className="text-lead font-semibold text-ink">{title}</h2>
        <p className="text-data-caption text-muted">
          Jetzt {phase} · {QUALITY_LABELS[data.quality]} ·{" "}
          <Link to="/fragen" className="underline decoration-muted/50 underline-offset-4 hover:text-ink">
            Wie entsteht der Wert?
          </Link>
        </p>
      </div>

      <div className="mt-8">
        <div className="min-w-0">
          <div
            ref={plotRef}
            className="relative h-40 cursor-crosshair touch-pan-y focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink"
            role="slider"
            tabIndex={0}
            aria-label={`${title}, Verlauf der nächsten 7 Tage, aktuell ${phase}. Pfeiltasten wählen eine Stunde.`}
            aria-valuemin={0}
            aria-valuemax={chart.points.length - 1}
            aria-valuenow={scrub ?? 0}
            aria-valuetext={scrubbed ? `${timeFmt.format(scrubbed.time)} Uhr, ${scrubbed.label}` : `jetzt, ${chart.points[0]?.label ?? ""}`}
            onPointerDown={(e) => pickAt(e.clientX)}
            onPointerMove={(e) => {
              if (e.pointerType === "mouse" || e.buttons === 1) pickAt(e.clientX);
            }}
            onPointerLeave={() => setScrub(null)}
            onPointerCancel={() => setScrub(null)}
            onKeyDown={onKeyDown}
            onBlur={() => setScrub(null)}
          >
            {chart.yTicks.map((tick) => (
              <span key={tick.label} aria-hidden="true" className="absolute inset-x-0 border-t border-line" style={{ top: `${tick.top}%` }} />
            ))}
            {chart.days.map((day) => (
              <span key={day.left} aria-hidden="true" className="absolute inset-y-0 border-l border-line-soft" style={{ left: `${day.left}%` }} />
            ))}
            <svg viewBox={`0 0 ${VB_W} ${VB_H}`} preserveAspectRatio="none" className="absolute inset-0 h-full w-full" aria-hidden="true">
              <path d={chart.area} fill="var(--sw-teal)" fillOpacity={0.14} />
              <path d={chart.path} fill="none" stroke="var(--sw-teal)" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" vectorEffect="non-scaling-stroke" />
            </svg>
            <span aria-hidden="true" className="absolute inset-y-0 left-0 border-l border-dashed border-ink/60" />
            {/* "Jetzt" as a point on the curve that sends out a quiet ring
                (chosen 2026-11-25, "Jetzt-Punkt atmet"), so now is always
                findable. Centred with margins, not a transform. */}
            <span aria-hidden="true" className="absolute left-0 -ml-1 -mt-1 size-2" style={{ top: `${chart.nowTop}%` }}>
              <span className="swd-breathe absolute inset-0 rounded-full bg-teal" />
              <span className="absolute inset-0 rounded-full bg-teal" />
            </span>
            {/* Axis values on their gridline inside the plot ("Werte in der
                Fläche", 2026-11-24): no gutter, the curve runs full width;
                the top value carries the unit. */}
            {chart.yTicks.map((tick, i) => (
              // A fixed value near the moving one steps aside.
              scrubbed && Math.abs(scrubbed.top - tick.top) < 14 ? null :
              <span
                key={`label-${tick.label}`}
                aria-hidden="true"
                className="pointer-events-none absolute left-1 bg-page pr-1 font-figures text-data-caption leading-none tabular-nums text-muted"
                style={{ top: `calc(${tick.top}% - ${tick.top >= 99 ? "0.875rem" : "1rem"})` }}
              >
                {tick.label}{i === 0 && chart.unit === "m" ? " m" : ""}
              </span>
            ))}
            {scrubbed && (
              <>
                <span aria-hidden="true" className="pointer-events-none absolute inset-y-0 border-l border-ink/70" style={{ left: `${scrubbed.left}%` }} />
                <span
                  aria-hidden="true"
                  className="pointer-events-none absolute -ml-[5px] -mt-[5px] size-2.5 rounded-full border-2 border-page bg-teal"
                  style={{ left: `${scrubbed.left}%`, top: `${scrubbed.top}%` }}
                />
                {/* The level at the left edge, at its own height. */}
                <span
                  aria-hidden="true"
                  className="pointer-events-none absolute left-1 rounded-full bg-ink px-1.5 py-0.5 font-figures text-data-caption font-semibold leading-none tabular-nums text-page"
                  style={{ top: `calc(${Math.min(92, Math.max(4, scrubbed.top))}% - 0.55rem)` }}
                >
                  {scrubbed.label}
                </span>
                {/* Its time above the line, on the side with room. */}
                <span
                  aria-hidden="true"
                  className="pointer-events-none absolute -top-5 whitespace-nowrap px-1 text-data-caption tabular-nums text-ink"
                  style={scrubbed.left > 70 ? { right: `${100 - scrubbed.left}%` } : { left: `${scrubbed.left}%` }}
                >
                  {timeFmt.format(scrubbed.time).replace(".,", "")}
                </span>
              </>
            )}
          </div>
          {/* X axis: "jetzt" at the start, then one label per day at its midnight. */}
          <div className="relative mt-1.5 h-5 text-data-caption tabular-nums text-muted" aria-hidden="true">
            <span className="absolute left-0">jetzt</span>
            {/* A midnight right after "jetzt" keeps its gridline but not its label. */}
            {chart.days.filter((day) => day.left > 8).map((day) => (
              <span key={day.left} className="absolute whitespace-nowrap pl-1" style={{ left: `${day.left}%` }}>
                {day.label}
              </span>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}

/**
 * Loading placeholder in the panel's final size (2026-11-25): the same rule,
 * title line, chart height and day axis, so the tide replaces it in place.
 */
function TideSkeleton() {
  return (
    <section role="status" aria-label="Gezeiten werden geladen" className="mt-12 border-t border-line pt-8">
      <h2 className="text-lead font-semibold text-transparent">Gezeiten</h2>
      <div className="mt-8 h-40 animate-pulse rounded-card bg-line-soft motion-reduce:animate-none" />
      <div className="mt-1.5 h-5" />
    </section>
  );
}
