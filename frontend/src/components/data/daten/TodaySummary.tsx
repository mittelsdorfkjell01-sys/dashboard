import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { windColor } from "../../../lib/windScale";
import type { NormalizedForecastSeries, NormalizedForecastDay } from "../../../lib/forecastNormalization";
import { spotForecastDayHours } from "../../../lib/spotForecastWindow";
import { useSpotDataScope, windUnitLabel } from "../../../state/SpotDataScope";
import { tempTone } from "../../../lib/tempScale";
import { useOptionalUnits } from "../../../context/PrefsContext";
import { tempValue, formatWind, formatWave, windValue, waveValue, WAVE_UNIT_SUFFIX } from "../../../lib/units";
import { headlineWaveFromDeg, headlineWaveM, headlineWavePeriodS, primarySwell } from "../../../lib/waveReading";
import { directionName } from "../../../lib/spotConditionHints";
import type { DatenFocus } from "./datenFocus";
import WeatherGlyph, { weatherLabel } from "./WeatherGlyph";

// Celestial-body colours — the only chroma on the sky arc besides the glow:
// the warm/cool of sun vs moon, one tone per theme (daten-theme.css).
const SUN_CORE = "var(--sw-sky-sun)";
const SUN_GLOW = "var(--sw-sky-sun-glow)";
const MOON_CORE = "var(--sw-sky-moon)";
const MOON_GLOW = "var(--sw-sky-moon-glow)";

/**
 * Day-detail view (Daten-page middle band, left column). Content on the page —
 * no card, no border, no surface: the big wind speed of the selected hour with
 * condition and temperature high/low, a sun/moon sky arc,
 * and the day's hourly temperature course. Header, sky body and course marker
 * all resolve to the SAME instant (the shared selection, which defaults to now),
 * so the three parts tell one time. Colour lives only on temperature and on the
 * celestial body's glow; everything else is quiet grey hairlines.
 */
export default function TodaySummary({ forecast, focus = "wind" }: { forecast: NormalizedForecastSeries; focus?: DatenFocus }) {
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

  const [prevDay, nextDay] = useMemo<[NormalizedForecastDay | null, NormalizedForecastDay | null]>(() => {
    if (!day) return [null, null];
    const key = day.local_date ?? day.date;
    const idx = forecast.days.findIndex((d) => (d.local_date ?? d.date) === key);
    return idx >= 0 ? [forecast.days[idx - 1] ?? null, forecast.days[idx + 1] ?? null] : [null, null];
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
  // "Welle" is the total wave, not the deprecated primary-swell field — the
  // spot page and the weather map used to print different numbers under the
  // same word (see lib/waveReading.ts).
  const swell = headlineWaveM(anchorHour);
  // Wave focus (2026-11-25): the sea's reading leads, the wind follows.
  const period = headlineWavePeriodS(anchorHour);
  const waveFrom = headlineWaveFromDeg(anchorHour);
  const primary = primarySwell(anchorHour);
  const water = anchorHour?.sst ?? null;
  const waveFocus = focus === "wave";

  return (
    <div className="flex flex-col gap-6">
      {/* Header — big wind speed (left) with the selected-hour readouts (gust,
          wave) in one right-aligned row beside it, above a full-width line;
          below the line, the condition icon + name and the day high/low. */}
      <div className="flex flex-col gap-3">
        <div className="flex items-end justify-between gap-4">
          {waveFocus ? (
            swell == null ? (
              <span className="text-muted tabular-nums text-display-lg font-light leading-none">—</span>
            ) : (
              <span className="flex items-baseline gap-1.5 leading-none" aria-label={`Welle ${formatWave(swell, units.wave)}`}>
                <RollingNumber text={waveValue(swell, units.wave)} className="tabular-nums text-display-lg font-light leading-none text-ink" />
                <span className="text-ui text-muted">{WAVE_UNIT_SUFFIX[units.wave]}</span>
              </span>
            )
          ) : wind == null ? (
            <span className="text-muted tabular-nums text-display-lg font-light leading-none">—</span>
          ) : (
            <span className="flex items-baseline gap-1.5 leading-none" aria-label={`Wind ${formatWind(wind, windUnit)}`}>
              <RollingNumber text={String(windValue(wind, windUnit))} className="tabular-nums text-display-lg font-light leading-none text-ink" />
              <span className="text-ui text-muted">{windUnitLabel(windUnit)}</span>
            </span>
          )}

          {/* Böe / Welle — one row, side by side, right-aligned, bottom-aligned
              so they sit directly above the line. */}
          {waveFocus ? (
            <div className="flex min-w-0 flex-wrap items-baseline justify-end gap-x-4 gap-y-1 text-ui tabular-nums">
              <span className="text-muted">Periode <SoftValue className="font-medium text-ink">{period == null ? "—" : `${Math.round(period)} s`}</SoftValue></span>
              <span className="text-muted">aus <SoftValue className="font-medium text-ink">{waveFrom == null ? "—" : directionName(waveFrom)}</SoftValue></span>
              {primary && (
                <span className="text-muted">Dünung <SoftValue className="font-medium text-ink">{`${formatWave(primary.heightM, units.wave)}${primary.periodS == null ? "" : ` · ${Math.round(primary.periodS)} s`}`}</SoftValue></span>
              )}
              {water != null && <span className="text-muted">Wasser <SoftValue className="font-medium text-ink">{`${tempValue(water, units.temp)}°`}</SoftValue></span>}
              <span className="text-muted">Wind <SoftValue className="font-medium text-ink">{wind == null ? "—" : `${formatWind(wind, windUnit)}${anchorHour?.dir == null ? "" : ` aus ${directionName(anchorHour.dir)}`}`}</SoftValue></span>
            </div>
          ) : (
            <div className="flex shrink-0 flex-wrap items-baseline justify-end gap-x-4 gap-y-1 text-ui tabular-nums">
              <span className="text-muted">Böe <SoftValue className="font-medium text-ink">{gust == null ? "—" : formatWind(gust, windUnit)}</SoftValue></span>
              <span className="text-muted">Welle <SoftValue className="font-medium text-ink">{swell == null ? "—" : formatWave(swell, units.wave)}</SoftValue></span>
            </div>
          )}
        </div>

        {/* Full-width divider directly under the big number. */}
        <div className="border-t border-line" />

        {/* Below the line: condition icon + name, and the day high / low. */}
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-ui">
          <SoftValue swapKey={condition ?? "none"} className="flex items-center gap-x-4">
            <WeatherGlyph condition={condition} size={26} />
            <span className="text-muted">{condition ? weatherLabel(condition) : "—"}</span>
          </SoftValue>
          <span className="flex items-center gap-3 tabular-nums">
            <SoftValue className="font-medium" style={{ color: hi == null ? undefined : tempTone(hi) }}>
              {`↑ ${hi == null ? "—" : `${tempValue(hi, units.temp)}°`}`}
            </SoftValue>
            <SoftValue className="swd-today-low font-normal" style={{ color: lo == null ? undefined : tempTone(lo) }}>
              {`↓ ${lo == null ? "—" : `${tempValue(lo, units.temp)}°`}`}
            </SoftValue>
          </span>
        </div>
      </div>

      {/* Sky arc — sunrise→sunset (sun) or sunset→next sunrise (moon). Full width,
          so it reads exactly as wide as the temperature course directly below it. */}
      <div className="w-full max-w-[900px]">
        <SkyArc day={day} prevDay={prevDay} nextDay={nextDay} anchorUtc={anchorUtc} timezone={forecast.timezone} />
      </div>

      {day && <DayWindBand day={day} anchorUtc={anchorUtc} timezone={forecast.timezone} onSelect={setSelectedAtUtc} focus={focus} />}
    </div>
  );
}

// ── Changing readings ─────────────────────────────────────────────────────────

/**
 * The big wind number rolls like a counter to its new value, digit by digit
 * (chosen 2026-11-25, "Zahl rollt"): you see that it changed and in which
 * direction. Each digit is a 0–9 column clipped to one figure; `clip-path`
 * (not overflow) keeps the figure's baseline for the unit beside it. The
 * text itself is read from the parent's label.
 */
function RollingNumber({ text, className }: { text: string; className: string }) {
  const chars = text.split("");
  return (
    <span className={`inline-flex ${className}`} aria-hidden="true">
      {chars.map((char, i) => {
        // Keyed from the right, so 9 → 12 keeps the ones column in place.
        const slot = chars.length - i;
        if (!/\d/.test(char)) return <span key={`c${slot}`}>{char}</span>;
        return (
          <span key={`d${slot}`} className="relative inline-block [clip-path:inset(0)]">
            <span className="invisible">0</span>
            <span
              className="absolute inset-x-0 top-0 flex flex-col items-center transition-transform duration-slow ease-switch motion-reduce:transition-none"
              style={{ transform: `translateY(-${Number(char) * 10}%)` }}
            >
              {DIGITS.map((digit) => (
                <span key={digit} className="h-[1em]">{digit}</span>
              ))}
            </span>
          </span>
        );
      })}
    </span>
  );
}
const DIGITS = ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9"];

/**
 * Every other reading that follows the selection blends softly into its new
 * value (300 ms, a short fade out of a slight blur) instead of snapping, so
 * scrubbing the meteogram reads calm. Re-keying replays the animation.
 */
function SoftValue({
  children,
  swapKey,
  className,
  style,
}: {
  children: ReactNode;
  swapKey?: string;
  className?: string;
  style?: React.CSSProperties;
}) {
  const key = swapKey ?? (typeof children === "string" ? children : "");
  return (
    <span key={key} className={`swd-soft-swap ${className ?? ""}`} style={style}>
      {children}
    </span>
  );
}

/**
 * Follows a number with a short delay and a braking glide instead of
 * jumping (the sun on its arc, 2026-11-25). An interrupted glide continues
 * from wherever it is. A `resetKey` change jumps straight to the target
 * (sun <-> moon). Reduced motion: no glide.
 */
function useGlide(target: number, resetKey: string, ms = 650, delay = 90): number {
  const [shown, setShown] = useState(target);
  const current = useRef(target);
  const lastKey = useRef(resetKey);
  useEffect(() => {
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const jump = reduced || lastKey.current !== resetKey;
    lastKey.current = resetKey;
    const from = current.current;
    let frame = 0;
    const start = performance.now() + (jump ? 0 : delay);
    const tick = (now: number) => {
      const t = jump ? 1 : Math.max(0, Math.min(1, (now - start) / ms));
      const value = from + (target - from) * (1 - (1 - t) ** 3);
      current.current = value;
      setShown(value);
      if (t < 1) frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [target, resetKey, ms, delay]);
  return shown;
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
  prevDay,
  nextDay,
  anchorUtc,
  timezone,
}: {
  day: NormalizedForecastDay | null;
  prevDay: NormalizedForecastDay | null;
  nextDay: NormalizedForecastDay | null;
  anchorUtc: string | null;
  timezone?: string;
}) {
  const riseIso = day?.summary.sunrise_at ?? null;
  const setIso = day?.summary.sunset_at ?? null;
  // Moon rise/set is not in the data model — the night arc is built purely from
  // sun data; the moon body carries no invented times. An hour after sunset
  // belongs to the night into the next morning, an hour before sunrise to the
  // night that began the evening before.
  const prevSetIso = prevDay?.summary.sunset_at ?? null;
  const nextRiseIso = nextDay?.summary.sunrise_at ?? null;

  const target = useMemo(() => {
    if (!riseIso || !setIso || !anchorUtc) return null;
    const rise = new Date(riseIso).getTime();
    const set = new Date(setIso).getTime();
    const now = new Date(anchorUtc).getTime();
    if (Number.isNaN(rise) || Number.isNaN(set) || set <= rise) return null;

    const isNight = now < rise || now >= set;
    let start: number, end: number | null, leftIso: string | null, rightIso: string | null;
    if (!isNight) {
      start = rise; end = set; leftIso = riseIso; rightIso = setIso;
    } else if (now >= set) {
      start = set;
      const nextRise = nextRiseIso ? new Date(nextRiseIso).getTime() : NaN;
      end = Number.isNaN(nextRise) ? null : nextRise;
      leftIso = setIso; rightIso = nextRiseIso;
    } else {
      // Before sunrise: last evening's sunset → this morning's sunrise. On the
      // first forecast day there is no previous day; the position then uses
      // this evening's sunset a day earlier (minutes apart), but no time is
      // printed for it.
      const prevSet = prevSetIso ? new Date(prevSetIso).getTime() : NaN;
      start = Number.isNaN(prevSet) ? set - 86_400_000 : prevSet;
      end = rise;
      leftIso = Number.isNaN(prevSet) ? null : prevSetIso; rightIso = riseIso;
    }
    // frac unknown (last day, no next sunrise) → rest at apex rather than guess.
    const frac = end == null ? 0.5 : clamp01((now - start) / (end - start));
    // One arc per day or night: the body glides inside it and jumps to a new one.
    return { isNight, frac, leftIso, rightIso, arcKey: `${isNight ? "n" : "d"}${start}` };
  }, [riseIso, setIso, prevSetIso, nextRiseIso, anchorUtc]);

  // The body wanders to a new hour with a slight delay instead of jumping;
  // the brighter traveled arc follows it.
  const frac = useGlide(target?.frac ?? 0.5, target?.arcKey ?? "none");
  const geom = useMemo(() => {
    if (!target) return null;
    const [cx, cy] = cube(frac);
    const traveled: string[] = [];
    const steps = 40;
    for (let i = 0; i <= steps * frac; i++) {
      const [x, y] = cube(i / steps);
      traveled.push(`${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`);
    }
    traveled.push(`L${cx.toFixed(1)},${cy.toFixed(1)}`);
    return { ...target, cx, cy, traveled: traveled.join(" ") };
  }, [target, frac]);

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
          <stop offset="0%" stopColor="var(--sw-ink)" stopOpacity={0.05} />
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
      <path d={fullArc} fill="none" stroke="var(--sw-ink)" strokeOpacity={0.16} strokeWidth={1.5} strokeLinecap="round" />
      <path d={geom.traveled} fill="none" stroke="var(--sw-ink)" strokeOpacity={0.45} strokeWidth={1.5} strokeLinecap="round" />

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
        {geom.leftIso ? fmtHM(geom.leftIso, timezone) : ""}
      </text>
      {geom.rightIso && (
        <text x={P3[0]} y={HORIZON + 14} textAnchor="middle" fontSize={9} className="tabular-nums" fill="var(--sw-muted)">
          {fmtHM(geom.rightIso, timezone)}
        </text>
      )}
    </svg>
  );
}

// ── Day wind band ────────────────────────────────────────────────────────────

/**
 * The day's wind as one bar per hour in the wind-scale colours, laid over a
 * faint band for daylight (chosen 2026-11-24, "Tagesband mit Licht"). The
 * sunrise and sunset times sit on the axis at their place, so the band and
 * the sky arc above tell the same day. Tapping or dragging picks an hour —
 * the shared selection, so the big number above and the meteogram follow.
 */
function DayWindBand({
  day,
  anchorUtc,
  timezone,
  onSelect,
  focus = "wind",
}: {
  day: NormalizedForecastDay;
  anchorUtc: string | null;
  timezone: string;
  onSelect: (utc: string | null) => void;
  focus?: DatenFocus;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const { windUnit } = useSpotDataScope();
  const units = useOptionalUnits();
  const hours = spotForecastDayHours(day);
  if (hours.length < 2) return null;

  // Wave focus: the same band carries the total wave in the sea's colour,
  // scaled to the day's highest wave (at least 1 m).
  const waveFocus = focus === "wave";
  const waves = hours.map((h) => headlineWaveM(h));
  const winds = waveFocus ? waves.map((w) => w ?? 0) : hours.map((h) => h.wind ?? 0);
  const peak = Math.max(...hours.map((h) => h.gust ?? h.wind ?? 0), 1);
  const scaleMax = waveFocus
    ? Math.max(1, Math.ceil(Math.max(...winds) * 2) / 2)
    : Math.max(20, Math.ceil(peak / 10) * 10);
  const barColor = (i: number) => waveFocus
    ? (waves[i] == null ? "var(--sw-line)" : "var(--sw-data-swell)")
    : (hours[i].wind == null ? "var(--sw-line)" : windColor(hours[i].wind as number));
  const first = +new Date(hours[0].time);
  const last = +new Date(hours[hours.length - 1].time);
  const slot = (last - first) / (hours.length - 1);
  // Position of an instant along the band, 0–100 %, centred on hourly slots.
  const at = (iso: string | null | undefined) => {
    if (!iso || !slot) return null;
    const t = +new Date(iso);
    const pct = ((t - first + slot / 2) / (slot * hours.length)) * 100;
    return Math.max(0, Math.min(100, pct));
  };
  const rise = at(day.summary.sunrise_at);
  const set = at(day.summary.sunset_at);
  const selected = hours.findIndex((h) => h.utcKey === anchorUtc);

  const pick = (clientX: number) => {
    const rect = ref.current?.getBoundingClientRect();
    if (!rect) return;
    const idx = Math.min(hours.length - 1, Math.max(0, Math.floor(((clientX - rect.left) / rect.width) * hours.length)));
    onSelect(hours[idx]?.utcKey ?? null);
  };
  const onKeyDown = (event: React.KeyboardEvent<HTMLDivElement>) => {
    const step = event.key === "ArrowRight" ? 1 : event.key === "ArrowLeft" ? -1 : 0;
    if (!step) return;
    event.preventDefault();
    const next = Math.min(hours.length - 1, Math.max(0, (selected < 0 ? 0 : selected) + step));
    onSelect(hours[next].utcKey);
  };
  const current = selected >= 0 ? hours[selected] : null;

  return (
    <div className="w-full max-w-[900px]">
      <div
        ref={ref}
        role="slider"
        tabIndex={0}
        aria-label={waveFocus ? "Welle des Tages — Stunde wählen" : "Wind des Tages — Stunde wählen"}
        aria-valuemin={1}
        aria-valuemax={hours.length}
        aria-valuenow={selected >= 0 ? selected + 1 : undefined}
        aria-valuetext={current ? `${current.localTime.slice(0, 5)} Uhr, ${
          waveFocus
            ? (waves[selected] == null ? "keine Angabe" : formatWave(waves[selected], units.wave))
            : (current.wind == null ? "keine Angabe" : formatWind(current.wind, windUnit))
        }` : undefined}
        onPointerDown={(e) => {
          e.currentTarget.setPointerCapture?.(e.pointerId);
          pick(e.clientX);
        }}
        onPointerMove={(e) => {
          if (e.buttons === 1) pick(e.clientX);
        }}
        onKeyDown={onKeyDown}
        className="relative h-28 cursor-pointer touch-pan-y"
      >
        {rise != null && set != null && set > rise && (
          <span
            aria-hidden="true"
            className="absolute inset-y-0 rounded-card bg-ink/5"
            style={{ left: `${rise}%`, width: `${set - rise}%` }}
          />
        )}
        <div className="absolute inset-0 grid items-end gap-[3px]" style={{ gridTemplateColumns: `repeat(${hours.length}, minmax(0, 1fr))` }} aria-hidden="true">
          {hours.map((h, i) => (
            <span
              key={h.utcKey}
              className="rounded-t-[3px] transition-[height] duration-base ease-brand motion-reduce:transition-none"
              style={{
                height: `${Math.max(2, (winds[i] / scaleMax) * 100)}%`,
                background: barColor(i),
              }}
            />
          ))}
        </div>
        {/* The selection ring glides from bar to bar and takes the new bar's
            height, instead of jumping (2026-11-25). Position = i columns plus
            i 3px gaps. */}
        {selected >= 0 && (
          <span
            aria-hidden="true"
            className="pointer-events-none absolute bottom-0 rounded-t-[3px] outline outline-2 outline-offset-1 outline-ink transition-[left,height] duration-base ease-brand motion-reduce:transition-none"
            style={{
              left: `calc(${selected} * ((100% - ${(hours.length - 1) * 3}px) / ${hours.length} + 3px))`,
              width: `calc((100% - ${(hours.length - 1) * 3}px) / ${hours.length})`,
              height: `${Math.max(2, (winds[selected] / scaleMax) * 100)}%`,
            }}
          />
        )}
      </div>
      {/* The hour of every bar, directly under it. */}
      <div
        className="mt-1 grid gap-[3px] text-center text-micro tabular-nums text-muted sm:text-data-caption"
        style={{ gridTemplateColumns: `repeat(${hours.length}, minmax(0, 1fr))` }}
        aria-hidden="true"
      >
        {hours.map((h, i) => (
          <span key={h.utcKey} className={`transition-colors duration-base ${i === selected ? "font-semibold text-ink" : ""}`}>{h.localTime.slice(0, 2)}</span>
        ))}
      </div>
      <div className="relative mt-1.5 h-5 text-data-caption tabular-nums text-muted" aria-hidden="true">
        {rise != null && (
          <span className="absolute whitespace-nowrap" style={{ left: `${rise}%` }}>↑ {fmtHM(day.summary.sunrise_at!, timezone)}</span>
        )}
        {set != null && (
          <span className="absolute whitespace-nowrap" style={{ right: `${100 - set}%` }}>{fmtHM(day.summary.sunset_at!, timezone)} ↓</span>
        )}
      </div>
    </div>
  );
}

/**
 * Loading placeholder in the section's final size (2026-11-25): the big
 * number line, the divider and condition line, the sky arc's frame and the
 * day band with its two label rows, so the readings replace it in place.
 */
export function TodaySummarySkeleton() {
  return (
    <div className="flex animate-pulse flex-col gap-6 motion-reduce:animate-none" role="status" aria-label="Tagesübersicht wird geladen">
      <div className="flex flex-col gap-3">
        <span className="text-display-lg font-light leading-none text-line">—</span>
        <div className="border-t border-line" />
        <span className="flex h-[26px] items-center text-ui text-line">—</span>
      </div>
      <svg viewBox={`0 -10 ${AW} 140`} className="h-auto w-full max-w-[900px]" aria-hidden="true">
        <path d={`M${P0[0]},${P0[1]} C${P1[0]},${P1[1]} ${P2[0]},${P2[1]} ${P3[0]},${P3[1]}`} fill="none" stroke="var(--sw-line)" strokeWidth={1.5} />
        <line x1={P0[0]} y1={HORIZON} x2={P3[0]} y2={HORIZON} stroke="var(--sw-line)" strokeWidth={1} />
      </svg>
      <div className="w-full max-w-[900px]" aria-hidden="true">
        <div className="h-28 rounded-card bg-line-soft" />
        <div className="mt-1 text-micro text-transparent sm:text-data-caption">00</div>
        <div className="mt-1.5 h-5" />
      </div>
    </div>
  );
}
