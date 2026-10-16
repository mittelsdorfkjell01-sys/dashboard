import { useMemo, useRef } from "react";
import type { NormalizedForecastSeries, NormalizedForecastDay } from "../../../lib/forecastNormalization";
import { spotForecastDayHours } from "../../../lib/spotForecastWindow";
import { useSpotDataScope, windUnitLabel } from "../../../state/SpotDataScope";
import { tempColor } from "../../../lib/tempScale";
import { useOptionalUnits } from "../../../context/PrefsContext";
import { tempValue, formatWind, formatWave, windValue } from "../../../lib/units";
import WeatherGlyph, { weatherLabel } from "./WeatherGlyph";

// Celestial-body colours — the only chroma on the sky arc besides the glow.
// Deliberately not data tokens: this is the warm/cool of sun vs moon.
const SUN_CORE = "#FFD79B";
const SUN_GLOW = "rgba(240, 184, 102, 0.55)";
const MOON_CORE = "#CFDAEA";
const MOON_GLOW = "rgba(150, 178, 220, 0.42)";

/**
 * Day-detail view (Daten-page middle band, left column). Content on the page —
 * no card, no border, no surface: the big wind speed of the selected hour with
 * condition and temperature high/low, a sun/moon sky arc,
 * and the day's hourly temperature course. Header, sky body and course marker
 * all resolve to the SAME instant (the shared selection, which defaults to now),
 * so the three parts tell one time. Colour lives only on temperature and on the
 * celestial body's glow; everything else is quiet grey hairlines.
 */
export default function TodaySummary({ forecast }: { forecast: NormalizedForecastSeries }) {
  const { selectedForecast, selectedAtUtc, setSelectedAtUtc, windUnit } = useSpotDataScope();
  const units = useOptionalUnits();

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

  const hi = day?.summary.air_max ?? day?.summary.temperature_max_c ?? null;
  const lo = day?.summary.air_min ?? day?.summary.temperature_min_c ?? null;
  const condition = anchorHour?.weather_condition ?? day?.summary.weather_condition;
  const wind = anchorHour?.wind ?? null;
  const gust = anchorHour?.gust ?? null;
  const swell = anchorHour?.swell ?? null;

  return (
    <div className="flex flex-col gap-6">
      {/* Header — big wind speed (left) with the selected-hour readouts (gust,
          wave) in one right-aligned row beside it, above a full-width line;
          below the line, the condition icon + name and the day high/low. */}
      <div className="flex flex-col gap-3">
        <div className="flex items-end justify-between gap-4">
          {wind == null ? (
            <span className="text-muted tabular-nums text-display-lg font-light leading-none">—</span>
          ) : (
            <span className="flex items-baseline gap-1.5 leading-none" aria-label={`Wind ${formatWind(wind, windUnit)}`}>
              <span className="tabular-nums text-display-lg font-light leading-none text-ink">{windValue(wind, windUnit)}</span>
              <span className="text-ui text-muted">{windUnitLabel(windUnit)}</span>
            </span>
          )}

          {/* Böe / Welle — one row, side by side, right-aligned, bottom-aligned
              so they sit directly above the line. */}
          <div className="flex shrink-0 flex-wrap items-baseline justify-end gap-x-4 gap-y-1 text-ui tabular-nums">
            <span className="text-muted">Böe <span className="font-medium text-ink">{gust == null ? "—" : formatWind(gust, windUnit)}</span></span>
            <span className="text-muted">Welle <span className="font-medium text-ink">{swell == null ? "—" : formatWave(swell, units.wave)}</span></span>
          </div>
        </div>

        {/* Full-width divider directly under the big number. */}
        <div className="border-t border-line" />

        {/* Below the line: condition icon + name, and the day high / low. */}
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-ui">
          <WeatherGlyph condition={condition} size={26} />
          <span className="text-muted">{condition ? weatherLabel(condition) : "—"}</span>
          <span className="flex items-center gap-3 tabular-nums">
            <span className="font-medium" style={{ color: hi == null ? undefined : tempColor(hi) }}>
              ↑ {hi == null ? "—" : `${tempValue(hi, units.temp)}°`}
            </span>
            <span className="font-light" style={{ color: lo == null ? undefined : tempColor(lo), opacity: lo == null ? undefined : 0.85 }}>
              ↓ {lo == null ? "—" : `${tempValue(lo, units.temp)}°`}
            </span>
          </span>
        </div>
      </div>

      {/* Sky arc — sunrise→sunset (sun) or sunset→next sunrise (moon). Full width,
          so it reads exactly as wide as the temperature course directly below it. */}
      <div className="w-full max-w-[900px]">
        <SkyArc day={day} nextDay={nextDay} anchorUtc={anchorUtc} timezone={forecast.timezone} />
      </div>

      {day && <DayTempCourse day={day} anchorUtc={anchorUtc} onSelect={setSelectedAtUtc} />}
    </div>
  );
}

// ── Sky arc ────────────────────────────────────────────────────────────────

// Wide, flat viewBox so the arc scales to the full column width (matching the
// temperature course's 900-wide viewBox) without becoming tall.
const AW = 900;
const HORIZON = 112;
// Cubic Bézier control points; endpoints sit on the horizon.
const P0 = [60, HORIZON] as const;
const P1 = [300, 20] as const;
const P2 = [600, 20] as const;
const P3 = [840, HORIZON] as const;
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

      {/* Celestial body. The daytime sun is a bright bloom + soft/sharp core; the
          night moon is a dim crescent (carved by an offset disc in the sky colour)
          that glows much less than the sun. */}
      {geom.isNight ? (
        <>
          <circle cx={geom.cx} cy={geom.cy} r={13} fill="url(#sky-bloom)" opacity={0.6} />
          <g>
            <circle cx={geom.cx} cy={geom.cy} r={6} fill={core} />
            <circle cx={geom.cx + 2.8} cy={geom.cy - 1.8} r={6} fill="var(--sw-page)" />
          </g>
        </>
      ) : (
        <>
          <circle cx={geom.cx} cy={geom.cy} r={22} fill="url(#sky-bloom)" />
          <circle cx={geom.cx} cy={geom.cy} r={7} fill={core} filter="url(#sky-soft)" opacity={0.9} />
          <circle cx={geom.cx} cy={geom.cy} r={4.5} fill={core} />
        </>
      )}

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
  const units = useOptionalUnits();
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
              {tempValue(h.air as number, units.temp)}°
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
