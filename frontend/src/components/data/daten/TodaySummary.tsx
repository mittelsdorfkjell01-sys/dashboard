import { useMemo, useRef } from "react";
import type { NormalizedForecastSeries, NormalizedForecastDay } from "../../../lib/forecastNormalization";
import { spotForecastDayHours } from "../../../lib/spotForecastWindow";
import { useSpotDataScope } from "../../../state/SpotDataScope";
import { tempColor } from "../../../lib/tempScale";
import WeatherGlyph, { weatherLabel } from "./WeatherGlyph";

// Celestial-body colours — the only chroma on the sky arc besides the glow.
// Deliberately not data tokens: this is the warm/cool of sun vs moon.
const SUN_CORE = "#FFD79B";
const SUN_GLOW = "rgba(240, 184, 102, 0.55)";
const MOON_CORE = "#CFDAEA";
const MOON_GLOW = "rgba(150, 178, 220, 0.42)";

/**
 * Day-detail view (Daten-page middle band, left column). Content on the page —
 * no card, no border, no surface: the big current temperature (tinted on the
 * absolute temperature scale) with condition and high/low, a sun/moon sky arc,
 * and the day's hourly temperature course. Header, sky body and course marker
 * all resolve to the SAME instant (the shared selection, which defaults to now),
 * so the three parts tell one time. Colour lives only on temperature and on the
 * celestial body's glow; everything else is quiet grey hairlines.
 */
export default function TodaySummary({ forecast }: { forecast: NormalizedForecastSeries }) {
  const { selectedForecast, selectedAtUtc, setSelectedAtUtc } = useSpotDataScope();

  // Resolve to a day that actually carries hourly values — the shared selection
  // can land on a trend day (no hours), which would blank the readouts.
  const day = useMemo<NormalizedForecastDay | null>(() => {
    const hourly = forecast.days.filter((d) => spotForecastDayHours(d).length >= 2);
    const date = selectedForecast?.localDate;
    return (
      hourly.find((d) => (d.local_date ?? d.date) === date) ??
      hourly.find((d) => d.hours.some((h) => h.utcKey === selectedAtUtc)) ??
      hourly[0] ??
      null
    );
  }, [forecast.days, selectedForecast?.localDate, selectedAtUtc]);

  const nextDay = useMemo<NormalizedForecastDay | null>(() => {
    if (!day) return null;
    const key = day.local_date ?? day.date;
    const idx = forecast.days.findIndex((d) => (d.local_date ?? d.date) === key);
    return idx >= 0 ? forecast.days[idx + 1] ?? null : null;
  }, [forecast.days, day]);

  const dayHours = day ? spotForecastDayHours(day) : [];
  // Anchor instant: the shared selection when it belongs to this day, else the
  // day's midpoint — so header / arc / marker stay on one coherent time.
  const anchorUtc =
    (selectedAtUtc && dayHours.some((h) => h.utcKey === selectedAtUtc)
      ? selectedAtUtc
      : dayHours[Math.floor(dayHours.length / 2)]?.utcKey) ?? null;
  const anchorHour = dayHours.find((h) => h.utcKey === anchorUtc) ?? null;

  const current = anchorHour?.air ?? null;
  const hi = day?.summary.air_max ?? day?.summary.temperature_max_c ?? null;
  const lo = day?.summary.air_min ?? day?.summary.temperature_min_c ?? null;
  const condition = anchorHour?.weather_condition ?? day?.summary.weather_condition;

  return (
    <div className="flex flex-col gap-10">
      <div className="flex flex-col gap-6 sm:flex-row sm:items-end sm:justify-between sm:gap-8">
        {/* Header — big current temperature, condition, high/low. */}
        <div className="flex min-w-0 flex-col gap-3">
          {current == null ? (
            <span className="text-muted tabular-nums" style={{ fontSize: 64, fontWeight: 300, lineHeight: 1 }}>—</span>
          ) : (
            <span className="inline-flex flex-col items-start" style={{ color: tempColor(current) }}>
              <span className="tabular-nums" style={{ fontSize: 64, fontWeight: 300, lineHeight: 1, letterSpacing: "-0.02em" }}>
                {Math.round(current)}°
              </span>
              <span className="mt-2 h-[2px] w-full rounded-full bg-current opacity-40" />
            </span>
          )}
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-ui">
            <WeatherGlyph condition={condition} size={26} />
            <span className="text-muted">{condition ? weatherLabel(condition) : "—"}</span>
            <span className="flex items-center gap-3 tabular-nums">
              <span className="font-medium" style={{ color: hi == null ? undefined : tempColor(hi) }}>
                ↑ {hi == null ? "—" : `${Math.round(hi)}°`}
              </span>
              <span className="font-light" style={{ color: lo == null ? undefined : tempColor(lo), opacity: lo == null ? undefined : 0.85 }}>
                ↓ {lo == null ? "—" : `${Math.round(lo)}°`}
              </span>
            </span>
          </div>
        </div>

        {/* Sky arc — sunrise→sunset (sun) or sunset→next sunrise (moon). */}
        <div className="w-full max-w-[320px] shrink-0 max-sm:hidden">
          <SkyArc day={day} nextDay={nextDay} anchorUtc={anchorUtc} timezone={forecast.timezone} />
        </div>
      </div>

      {day && <DayTempCourse day={day} anchorUtc={anchorUtc} onSelect={setSelectedAtUtc} />}
    </div>
  );
}

// ── Sky arc ────────────────────────────────────────────────────────────────

const AW = 330;
const HORIZON = 112;
// Cubic Bézier control points; endpoints sit on the horizon.
const P0 = [38, HORIZON] as const;
const P1 = [112, 20] as const;
const P2 = [242, 20] as const;
const P3 = [316, HORIZON] as const;
const cube = (t: number): readonly [number, number] => {
  const m = 1 - t;
  return [
    m * m * m * P0[0] + 3 * m * m * t * P1[0] + 3 * m * t * t * P2[0] + t * t * t * P3[0],
    m * m * m * P0[1] + 3 * m * m * t * P1[1] + 3 * m * t * t * P2[1] + t * t * t * P3[1],
  ];
};
const clamp01 = (v: number) => Math.max(0, Math.min(1, v));

function fmtHM(iso: string, timezone?: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return new Intl.DateTimeFormat("de-DE", { hour: "2-digit", minute: "2-digit", hour12: false, timeZone: timezone || "UTC" }).format(d);
}

function SkyArc({
  day,
  nextDay,
  anchorUtc,
  timezone,
}: {
  day: NormalizedForecastDay | null;
  nextDay: NormalizedForecastDay | null;
  anchorUtc: string | null;
  timezone?: string;
}) {
  const riseIso = day?.summary.sunrise_at ?? null;
  const setIso = day?.summary.sunset_at ?? null;
  // Moon rise/set is not in the data model — the night arc is built purely from
  // sun data (sunset → next sunrise); the moon body carries no invented times.
  const nextRiseIso = nextDay?.summary.sunrise_at ?? null;

  const geom = useMemo(() => {
    if (!riseIso || !setIso || !anchorUtc) return null;
    const rise = new Date(riseIso).getTime();
    const set = new Date(setIso).getTime();
    const now = new Date(anchorUtc).getTime();
    if (Number.isNaN(rise) || Number.isNaN(set) || set <= rise) return null;

    const isNight = now < rise || now >= set;
    let start: number, end: number | null, leftIso: string, rightIso: string | null;
    if (!isNight) {
      start = rise; end = set; leftIso = riseIso; rightIso = setIso;
    } else {
      start = set;
      const nextRise = nextRiseIso ? new Date(nextRiseIso).getTime() : NaN;
      end = Number.isNaN(nextRise) ? null : nextRise;
      leftIso = setIso; rightIso = nextRiseIso;
    }
    // frac unknown (last day, no next sunrise) → rest at apex rather than guess.
    const frac = end == null ? 0.5 : clamp01((now - start) / (end - start));
    const [cx, cy] = cube(frac);
    const traveled: string[] = [];
    const steps = 40;
    for (let i = 0; i <= steps * frac; i++) {
      const [x, y] = cube(i / steps);
      traveled.push(`${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`);
    }
    return { isNight, cx, cy, traveled: traveled.join(" "), leftIso, rightIso };
  }, [riseIso, setIso, nextRiseIso, anchorUtc]);

  const fullArc = `M${P0[0]},${P0[1]} C${P1[0]},${P1[1]} ${P2[0]},${P2[1]} ${P3[0]},${P3[1]}`;
  const dayArea = `${fullArc} L${P3[0]},${HORIZON} L${P0[0]},${HORIZON} Z`;

  if (!geom) {
    // Partial data (missing/polar sun times): keep the horizon hairline only —
    // still content, not a card.
    return (
      <svg viewBox={`0 -10 ${AW} 140`} className="h-auto w-full" role="img" aria-label="Sonnenstand nicht verfügbar">
        <line x1={P0[0]} y1={HORIZON} x2={P3[0]} y2={HORIZON} stroke="var(--sw-line)" strokeWidth={1} />
      </svg>
    );
  }

  const core = geom.isNight ? MOON_CORE : SUN_CORE;
  const glow = geom.isNight ? MOON_GLOW : SUN_GLOW;
  const label = geom.isNight ? "Mondstand über die Nacht" : "Sonnenstand über den Tag";

  return (
    <svg viewBox={`0 -10 ${AW} 140`} className="h-auto w-full" role="img" aria-label={label}>
      <defs>
        <radialGradient id="sky-bloom" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor={glow} />
          <stop offset="100%" stopColor="transparent" />
        </radialGradient>
        <linearGradient id="sky-day" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="rgba(255,255,255,0.06)" />
          <stop offset="100%" stopColor="transparent" />
        </linearGradient>
        <filter id="sky-soft" x="-60%" y="-60%" width="220%" height="220%">
          <feGaussianBlur stdDeviation="2.2" />
        </filter>
      </defs>

      {/* Day area fading to the horizon. */}
      <path d={dayArea} fill="url(#sky-day)" />
      {/* Horizon (data hairline, not a card edge). */}
      <line x1={P0[0]} y1={HORIZON} x2={P3[0]} y2={HORIZON} stroke="var(--sw-line)" strokeWidth={1} />
      {/* Full arc (remaining) then the brighter traveled part on top. */}
      <path d={fullArc} fill="none" stroke="rgba(255,255,255,0.14)" strokeWidth={1.5} strokeLinecap="round" />
      <path d={geom.traveled} fill="none" stroke="rgba(255,255,255,0.42)" strokeWidth={1.5} strokeLinecap="round" />

      {/* Celestial body: bloom + soft core + sharp core (no hard circle). */}
      <circle cx={geom.cx} cy={geom.cy} r={22} fill="url(#sky-bloom)" />
      <circle cx={geom.cx} cy={geom.cy} r={7} fill={core} filter="url(#sky-soft)" opacity={0.9} />
      <circle cx={geom.cx} cy={geom.cy} r={4.5} fill={core} />

      {/* Edge time marks. */}
      <text x={P0[0]} y={HORIZON + 14} textAnchor="middle" fontSize={9} className="tabular-nums" fill="var(--sw-muted)">
        {fmtHM(geom.leftIso, timezone)}
      </text>
      {geom.rightIso && (
        <text x={P3[0]} y={HORIZON + 14} textAnchor="middle" fontSize={9} className="tabular-nums" fill="var(--sw-muted)">
          {fmtHM(geom.rightIso, timezone)}
        </text>
      )}
    </svg>
  );
}

// ── Hourly temperature course ────────────────────────────────────────────────

const CW = 900; // course viewBox width — wide aspect so the chart can stretch to
                // the full column width (right edge flush with the sky arc)
                // without growing tall.
const CH = 180; // course viewBox height
const C_PAD_T = 30; // headroom for value labels
const C_PAD_B = 24; // footer for hour marks
const C_BASE_Y = CH - C_PAD_B;

function smoothPath(pts: { x: number; y: number }[]): string {
  if (pts.length < 2) return "";
  let d = `M${pts[0].x.toFixed(1)},${pts[0].y.toFixed(1)}`;
  for (let i = 0; i < pts.length - 1; i++) {
    const p0 = pts[i - 1] ?? pts[i];
    const p1 = pts[i];
    const p2 = pts[i + 1];
    const p3 = pts[i + 2] ?? p2;
    const c1x = p1.x + (p2.x - p0.x) / 6;
    const c1y = p1.y + (p2.y - p0.y) / 6;
    const c2x = p2.x - (p3.x - p1.x) / 6;
    const c2y = p2.y - (p3.y - p1.y) / 6;
    d += ` C${c1x.toFixed(1)},${c1y.toFixed(1)} ${c2x.toFixed(1)},${c2y.toFixed(1)} ${p2.x.toFixed(1)},${p2.y.toFixed(1)}`;
  }
  return d;
}

function DayTempCourse({
  day,
  anchorUtc,
  onSelect,
}: {
  day: NormalizedForecastDay;
  anchorUtc: string | null;
  onSelect: (utc: string | null) => void;
}) {
  const ref = useRef<SVGSVGElement>(null);
  const hours = spotForecastDayHours(day).filter((h) => h.air != null);
  const W = CW;
  const H = CH;
  const baseY = C_BASE_Y;

  const geom = useMemo(() => {
    if (hours.length < 2) return null;
    const temps = hours.map((h) => h.air as number);
    const min = Math.min(...temps);
    const max = Math.max(...temps);
    const span = Math.max(1, max - min);
    const step = CW / (hours.length - 1);
    const x = (i: number) => i * step;
    const y = (t: number) => C_PAD_T + (1 - (t - min) / span) * (C_BASE_Y - C_PAD_T);
    const pts = hours.map((h, i) => ({ x: x(i), y: y(h.air as number) }));
    const line = smoothPath(pts);
    const area = `${line} L${x(hours.length - 1).toFixed(1)},${C_BASE_Y} L0,${C_BASE_Y} Z`;

    // Night bands from is_day (before sunrise / after sunset within the window).
    const bands: { x: number; w: number }[] = [];
    let s = -1;
    hours.forEach((h, i) => {
      const night = h.is_day === false;
      if (night && s < 0) s = i;
      if ((!night || i === hours.length - 1) && s >= 0) {
        const e = night ? i : i - 1;
        const left = Math.max(0, x(s) - step / 2);
        const right = Math.min(CW, x(e) + step / 2);
        bands.push({ x: left, w: right - left });
        s = -1;
      }
    });

    return { x, y, line, area, bands, step };
  }, [hours]);

  if (!geom) return null;

  const selIdx = hours.findIndex((h) => h.utcKey === anchorUtc);
  const pick = (clientX: number) => {
    const el = ref.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const ratio = (clientX - rect.left) / rect.width;
    const idx = Math.min(hours.length - 1, Math.max(0, Math.round(ratio * (hours.length - 1))));
    onSelect(hours[idx]?.utcKey ?? null);
  };

  const gradientId = "course-temp";

  return (
    <svg
      ref={ref}
      viewBox={`0 0 ${W} ${H}`}
      className="h-auto w-full max-w-[900px] cursor-pointer touch-none"
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
      <defs>
        <linearGradient id={gradientId} gradientUnits="userSpaceOnUse" x1={0} y1={0} x2={W} y2={0}>
          {hours.map((h, i) => (
            <stop key={i} offset={hours.length > 1 ? i / (hours.length - 1) : 0} stopColor={tempColor(h.air as number)} />
          ))}
        </linearGradient>
        <linearGradient id={`${gradientId}-fill`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="rgba(255,255,255,0.08)" />
          <stop offset="100%" stopColor="transparent" />
        </linearGradient>
      </defs>

      {/* Night bands (very low opacity). */}
      {geom.bands.map((b, i) => (
        <rect key={i} x={b.x} y={0} width={b.w} height={baseY} fill="var(--sw-ink)" opacity={0.04} />
      ))}

      {/* Baseline (data hairline). */}
      <line x1={0} y1={baseY} x2={W} y2={baseY} stroke="var(--sw-line)" strokeWidth={1} />

      {/* Faint depth fill + the temperature-tinted line (drawn once on load). */}
      <path d={geom.area} fill={`url(#${gradientId}-fill)`} />
      <path
        d={geom.line}
        fill="none"
        stroke={`url(#${gradientId})`}
        strokeWidth={2.5}
        strokeLinecap="round"
        strokeLinejoin="round"
        pathLength={1}
        className="daten-draw-line"
      />

      {/* Hollow nodes every 3 hours: value above, drop line, hour mark below. */}
      {hours.map((h, i) => {
        if (h.localHour % 3 !== 0) return null;
        const cx = geom.x(i);
        const cy = geom.y(h.air as number);
        return (
          <g key={i}>
            <line x1={cx} y1={cy} x2={cx} y2={baseY} stroke="var(--sw-line-soft)" strokeWidth={1} />
            <circle cx={cx} cy={cy} r={3.5} fill="var(--sw-page)" stroke="var(--sw-ink-soft)" strokeWidth={1.5} />
            <text x={cx} y={cy - 9} textAnchor="middle" fontSize={12} className="tabular-nums" fill="var(--sw-ink-soft)">
              {Math.round(h.air as number)}°
            </text>
            <text x={cx} y={H - 7} textAnchor="middle" fontSize={10} className="tabular-nums" fill="var(--sw-muted)">
              {h.localTime.slice(0, 2)}
            </text>
          </g>
        );
      })}

      {/* Now / selection marker: tinted filled dot with aura + guide line. */}
      {selIdx >= 0 && (() => {
        const cx = geom.x(selIdx);
        const cy = geom.y(hours[selIdx].air as number);
        const c = tempColor(hours[selIdx].air as number);
        return (
          <g>
            <line x1={cx} y1={cy} x2={cx} y2={baseY} stroke={c} strokeWidth={1} opacity={0.5} />
            <circle cx={cx} cy={cy} r={9} fill={c} opacity={0.22} />
            <circle cx={cx} cy={cy} r={4.5} fill={c} />
          </g>
        );
      })()}
    </svg>
  );
}
