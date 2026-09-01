import { useId, useMemo, useRef, useState } from "react";
import type { NormalizedForecastSeries, NormalizedForecastHour } from "../../../lib/forecastNormalization";
import { closestForecastUtc } from "../../../lib/forecastNormalization";
import { buildMeteogramModel } from "../meteogramModel";
import { useSpotDataScope, formatWind, windUnitLabel } from "../../../state/SpotDataScope";
import { windColor } from "../../../lib/windScale";
import WeatherGlyph from "./WeatherGlyph";

const COL_W = 46;
const BAR_H = 118; // wind bar band height
const WAVE_H = 34; // wave bar band height
const WAVE_ROW_H = WAVE_H + 6;
const GLYPH = 26; // weather-icon box size (24×24 viewBox scaled)
// The glyph art sits in the upper ~16/24 of its box (cloud/sun/moon base ≈ y16),
// leaving whitespace below; anchor the WETTER label to that visual base so the
// icons close on the word rather than floating above it.
const GLYPH_INK = Math.round((GLYPH * 16) / 24);
const WELLE_WETTER_GAP = 16;
const WETTER_ROW_H = WELLE_WETTER_GAP + GLYPH + 16;
const TEMP_H = 108; // temperature band height — more room for the curve
const ROW_LABELS = ["WELLE", "WETTER", "TEMP.", "WIND", "RICHT.", "ZEIT"] as const;

function darken(hex: string, factor = 0.62): string {
  const m = /^#?([\da-f]{2})([\da-f]{2})([\da-f]{2})$/i.exec(hex);
  if (!m) return hex;
  const [r, g, b] = [m[1], m[2], m[3]].map((h) => Math.round(parseInt(h, 16) * factor));
  return `rgb(${r}, ${g}, ${b})`;
}

/**
 * The Daten-page meteogram (Figma Frame 67, Group 66). A horizontally
 * scrollable instrument strip: wave-height bars, a weather-glyph + precip
 * row, a temperature line with a draggable marker, wind-speed bars coloured by
 * the shared wind scale with a darker gust cap, wind-direction arrows and a
 * time axis with per-day separators. Pointer interaction over the strip picks
 * the nearest hour and writes it to the shared SpotDataScope selection, so the
 * marker here and every other module on the page move together.
 */
export default function MeteoChart({ forecast }: { forecast: NormalizedForecastSeries }) {
  const { selectedAtUtc, setSelectedAtUtc, windUnit } = useSpotDataScope();
  const model = useMemo(() => buildMeteogramModel(forecast), [forecast]);
  const slots = model.slots;
  const scrollRef = useRef<HTMLDivElement>(null);

  const clipId = useId();
  // Continuous drag position in strip-content pixels; null after the gesture,
  // when the marker resolves to the persistent selected hour.
  const [hoverX, setHoverX] = useState<number | null>(null);

  const width = Math.max(slots.length * COL_W, 1);
  const selectedIndex = slots.findIndex((s) => s.utcKey === selectedAtUtc);
  const selectedSlot = selectedIndex >= 0 ? slots[selectedIndex] : null;

  const windMax = model.scales.wind.max;
  const waveMax = model.scales.wave.max;
  const precipMax = model.scales.precipitation.max;

  // Temperature scale fitted to the actual readings (not rounded to 5°), so a
  // small-but-real diurnal swing fills the band instead of collapsing to a flat
  // line. A minimum span keeps a near-constant day from being over-amplified.
  const tScale = useMemo(() => temperatureBounds(slots), [slots]);
  const tempY = (air: number) => {
    const t = (air - tScale.min) / (tScale.max - tScale.min);
    return TEMP_H - 10 - t * (TEMP_H - 26);
  };
  const cx = (i: number) => i * COL_W + COL_W / 2;

  // Temperature curve as smooth beziers. `runs` splits the horizon on any
  // missing hour so gaps stay open; each contiguous run is one smooth path.
  const runs = useMemo(() => temperatureRuns(slots), [slots]);
  // eslint-disable-next-line react-hooks/exhaustive-deps -- cx/tempY derive from COL_W + tScale, tracked here
  const tempPath = useMemo(() => smoothRuns(runs, cx, tempY), [runs, tScale.min, tScale.max]);

  // Marker: the interpolated point under the cursor while hovering, otherwise
  // the "now" slot. `air` is read off the same curve so the readout is exact at
  // any instant — not just on the 2-hour data columns.
  const marker = useMemo(() => {
    if (hoverX != null) {
      const s = sampleCurve(slots, hoverX / COL_W - 0.5);
      return s ? { x: s.x, y: tempY(s.air), air: s.air } : null;
    }
    if (selectedSlot?.air != null) return { x: cx(selectedIndex), y: tempY(selectedSlot.air), air: selectedSlot.air };
    return null;
    // eslint-disable-next-line react-hooks/exhaustive-deps -- cx/tempY derive from COL_W + tScale, tracked here
  }, [hoverX, slots, selectedIndex, selectedSlot?.air, tScale.min, tScale.max]);
  const revealW = marker ? marker.x : 0;

  if (!slots.length) {
    return (
      <div className="px-4 py-6 text-ui text-muted">
        Für diesen Zeitraum sind keine Stundenwerte verfügbar.
      </div>
    );
  }

  // Track the cursor for the local marker (every pixel) and sync the shared
  // selection to the nearest hour only when that column changes, so the map and
  // sidebar follow without a state write on every mouse move.
  const pickAt = (clientX: number) => {
    const el = scrollRef.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const x = Math.max(0, Math.min(width, clientX - rect.left + el.scrollLeft));
    setHoverX(x);
    const idx = Math.min(slots.length - 1, Math.max(0, Math.round(x / COL_W - 0.5)));
    const slot = slots[idx];
    if (slot && slot.utcKey !== selectedAtUtc) setSelectedAtUtc(slot.utcKey);
  };

  const resetToNow = () => {
    setHoverX(null);
    setSelectedAtUtc(closestForecastUtc(forecast));
  };

  return (
    <div className="flex min-w-0 gap-3">
      {/* Fixed row-label gutter (stays put while the strip scrolls). */}
      <div className="shrink-0 select-none pt-1 text-data-caption uppercase tracking-[0.14em] text-muted">
        <RowLabel h={WAVE_ROW_H}>{ROW_LABELS[0]}</RowLabel>
        <RowLabel h={WETTER_ROW_H} anchorH={WELLE_WETTER_GAP + GLYPH_INK}>{ROW_LABELS[1]}</RowLabel>
        <RowLabel h={TEMP_H}>{ROW_LABELS[2]}</RowLabel>
        <RowLabel h={BAR_H + 16}>{ROW_LABELS[3]}</RowLabel>
        <RowLabel h={26}>{ROW_LABELS[4]}</RowLabel>
        <RowLabel h={22}>{ROW_LABELS[5]}</RowLabel>
      </div>

      <div
        ref={scrollRef}
        tabIndex={0}
        className="min-w-0 flex-1 overflow-x-auto overflow-y-hidden pb-1 [scrollbar-width:thin] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal"
        onPointerDown={(e) => {
          (e.currentTarget as HTMLElement).setPointerCapture?.(e.pointerId);
          pickAt(e.clientX);
        }}
        onPointerMove={(e) => pickAt(e.clientX)}
        onPointerLeave={resetToNow}
        role="group"
        aria-label="Meteogramm — Zeitpunkt wählen"
      >
        <div className="relative" style={{ width }}>
          {/* Selection highlight — a soft column of light, no separators. */}
          {selectedIndex >= 0 && (
            <div
              className="absolute top-0 bottom-0 rounded bg-ink/[0.06]"
              style={{ left: selectedIndex * COL_W, width: COL_W }}
              aria-hidden
            />
          )}

          {/* WELLE — wave-height bars. */}
          <Row h={WAVE_ROW_H}>
            {slots.map((s, i) => (
              <Cell key={i}>
                {s.swell != null && (
                  <>
                    <span className="mb-0.5 leading-none text-muted" style={{ fontSize: 10 }}>{s.swell.toFixed(1)}</span>
                    <span
                      className="w-[22px] rounded-[4px]"
                      style={{ height: Math.max(3, (s.swell / waveMax) * WAVE_H), background: "var(--sw-data-swell)" }}
                    />
                  </>
                )}
              </Cell>
            ))}
          </Row>

          {/* WETTER — glyph + precipitation stub. */}
          <Row h={WETTER_ROW_H}>
            {slots.map((s, i) => (
              <Cell key={i} justify="start">
                <div aria-hidden style={{ height: WELLE_WETTER_GAP }} />
                <WeatherGlyph condition={s.weather_condition} isDay={s.is_day ?? true} size={GLYPH} />
                {s.precip != null && s.precip > 0 && (
                  <span className="mt-0.5 flex flex-col items-center leading-none">
                    <span className="text-muted" style={{ fontSize: 9 }}>{s.precip.toFixed(1)}</span>
                    <span
                      className="mt-0.5 w-[20px] rounded-[3px]"
                      style={{ height: Math.max(2, (s.precip / precipMax) * 14), background: "var(--sw-data-rain)" }}
                    />
                  </span>
                )}
              </Cell>
            ))}
          </Row>

          {/* TEMP — smooth curve; a white "reveal" runs from the left to the
              marker, which tracks the cursor and reads the interpolated value. */}
          <div className="relative" style={{ height: TEMP_H, width }}>
            <svg viewBox={`0 0 ${width} ${TEMP_H}`} width={width} height={TEMP_H} preserveAspectRatio="none" className="absolute inset-0" aria-hidden>
              <defs>
                <clipPath id={clipId} clipPathUnits="userSpaceOnUse">
                  <rect x={0} y={0} width={Math.max(0, revealW)} height={TEMP_H} />
                </clipPath>
              </defs>
              {tempPath && (
                <path
                  d={tempPath}
                  fill="none"
                  stroke="var(--sw-data-temp)"
                  strokeWidth={2}
                  strokeLinejoin="round"
                  strokeLinecap="round"
                  style={{ filter: "drop-shadow(0 0 5px rgba(215,163,93,0.5))" }}
                />
              )}
              {tempPath && revealW > 0 && (
                <path
                  d={tempPath}
                  fill="none"
                  stroke="#F3F0EA"
                  strokeWidth={2.4}
                  strokeLinejoin="round"
                  strokeLinecap="round"
                  clipPath={`url(#${clipId})`}
                  style={{ filter: "drop-shadow(0 0 4px rgba(243,240,234,0.55))" }}
                />
              )}
              {marker && <circle cx={marker.x} cy={marker.y} r={5} fill="#F3F0EA" />}
            </svg>
            {marker && (
              <span
                className="pointer-events-none absolute -translate-x-1/2 font-medium text-ink"
                style={{ fontSize: 11, left: marker.x, top: Math.max(0, marker.y - 20) }}
              >
                {Math.round(marker.air)}
              </span>
            )}
          </div>

          {/* WIND — coloured bars with a darker gust cap. */}
          <Row h={BAR_H + 16} align="end">
            {slots.map((s, i) => {
              const wind = s.wind;
              const gust = s.gust ?? wind;
              if (wind == null) return <Cell key={i} />;
              const windH = Math.max(4, (wind / windMax) * BAR_H);
              const gustH = Math.max(windH, ((gust ?? wind) / windMax) * BAR_H);
              return (
                <Cell key={i} align="end">
                  <span className="mb-1 leading-none text-muted" style={{ fontSize: 10 }}>{Math.round(wind)}</span>
                  <span className="relative w-[22px] rounded-[5px]" style={{ height: gustH, background: darken(windColor(gust)) }}>
                    <span
                      className="absolute inset-x-0 bottom-0 rounded-[5px]"
                      style={{ height: windH, background: windColor(wind) }}
                    />
                  </span>
                </Cell>
              );
            })}
          </Row>

          {/* RICHT — wind-direction arrows. */}
          <Row h={26}>
            {slots.map((s, i) => (
              <Cell key={i}>
                {s.dir != null && (
                  <svg width={16} height={16} viewBox="0 0 16 16" style={{ transform: `rotate(${s.dir}deg)` }} aria-hidden className="text-ink">
                    <path d="M8 2 L8 13 M4.5 6 L8 2 L11.5 6" fill="none" stroke="currentColor" strokeWidth={1.4} strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                )}
              </Cell>
            ))}
          </Row>

          {/* ZEIT — hour axis, labelled on even hours + day starts. */}
          <Row h={22}>
            {slots.map((s, i) => {
              const show = s.localHour % 2 === 0;
              return (
                <Cell key={i}>
                  {show && <span className="tabular-nums text-muted" style={{ fontSize: 10 }}>{s.localTime.slice(0, 2)}</span>}
                </Cell>
              );
            })}
          </Row>
        </div>
      </div>

      {/* Screen-reader summary of the current selection. */}
      <p className="sr-only" aria-live="polite">
        {selectedSlot
          ? `Ausgewählt ${selectedSlot.localDate} ${selectedSlot.localTime}: ${selectedSlot.air == null ? "Temperatur unbekannt" : `${Math.round(selectedSlot.air)} Grad`}, Wind ${selectedSlot.wind == null ? "unbekannt" : `${formatWind(selectedSlot.wind, windUnit)} ${windUnitLabel(windUnit)}`}.`
          : ""}
      </p>
    </div>
  );
}

// Contiguous runs of hours with a temperature reading. Each run carries the
// slot's own index so the horizontal position survives the split.
function temperatureRuns(slots: NormalizedForecastHour[]): { i: number; air: number }[][] {
  const runs: { i: number; air: number }[][] = [];
  let current: { i: number; air: number }[] = [];
  slots.forEach((s, i) => {
    if (s.air == null) {
      if (current.length) runs.push(current);
      current = [];
      return;
    }
    current.push({ i, air: s.air });
  });
  if (current.length) runs.push(current);
  return runs;
}

// Smooth every run into a single Catmull-Rom → cubic-bezier path — no straight
// segments, so the line only ever curves.
function smoothRuns(
  runs: { i: number; air: number }[][],
  cx: (i: number) => number,
  cy: (air: number) => number,
): string {
  let d = "";
  for (const run of runs) {
    const pts = run.map((p) => [cx(p.i), cy(p.air)] as [number, number]);
    if (!pts.length) continue;
    d += `${d ? " " : ""}${catmullRom(pts)}`;
  }
  return d;
}

// Temperature band bounds fitted to the readings, with a small pad and a floor
// on the span so a nearly-constant day doesn't get stretched into noise.
function temperatureBounds(slots: NormalizedForecastHour[]): { min: number; max: number } {
  const airs = slots.map((s) => s.air).filter((a): a is number => a != null && Number.isFinite(a));
  if (!airs.length) return { min: 0, max: 30 };
  let min = Math.min(...airs);
  let max = Math.max(...airs);
  const MIN_SPAN = 6;
  if (max - min < MIN_SPAN) {
    const mid = (min + max) / 2;
    min = mid - MIN_SPAN / 2;
    max = mid + MIN_SPAN / 2;
  }
  const pad = (max - min) * 0.12;
  return { min: min - pad, max: max + pad };
}

// Interpolate the temperature curve at fractional column `f` (0 = first hour).
// Returns the on-curve x plus the exact temperature there, evaluated with the
// same Catmull-Rom→bezier weights the drawn path uses, so the marker sits on
// the line. Null inside a gap (missing hour on either side).
function sampleCurve(
  slots: NormalizedForecastHour[],
  f: number,
): { x: number; air: number } | null {
  const n = slots.length;
  if (!n) return null;
  const fc = Math.max(0, Math.min(n - 1, f));
  const i = Math.floor(fc);
  const t = fc - i;
  const a1 = slots[i]?.air;
  if (a1 == null) return null;
  const x = i * COL_W + COL_W / 2 + t * COL_W;
  if (t === 0 || i >= n - 1) return { x, air: a1 };
  const a2 = slots[i + 1]?.air;
  if (a2 == null) return null;
  const a0 = slots[i - 1]?.air ?? a1;
  const a3 = slots[i + 2]?.air ?? a2;
  const c1 = a1 + (a2 - a0) / 6;
  const c2 = a2 - (a3 - a1) / 6;
  const u = 1 - t;
  const air = u * u * u * a1 + 3 * u * u * t * c1 + 3 * u * t * t * c2 + t * t * t * a2;
  return { x, air };
}

function catmullRom(pts: [number, number][]): string {
  if (pts.length === 1) return `M${pts[0][0].toFixed(1)},${pts[0][1].toFixed(1)}`;
  let d = `M${pts[0][0].toFixed(1)},${pts[0][1].toFixed(1)}`;
  for (let i = 0; i < pts.length - 1; i++) {
    const p0 = pts[i - 1] ?? pts[i];
    const p1 = pts[i];
    const p2 = pts[i + 1];
    const p3 = pts[i + 2] ?? p2;
    const c1x = p1[0] + (p2[0] - p0[0]) / 6;
    const c1y = p1[1] + (p2[1] - p0[1]) / 6;
    const c2x = p2[0] - (p3[0] - p1[0]) / 6;
    const c2y = p2[1] - (p3[1] - p1[1]) / 6;
    d += ` C${c1x.toFixed(1)},${c1y.toFixed(1)} ${c2x.toFixed(1)},${c2y.toFixed(1)} ${p2[0].toFixed(1)},${p2[1].toFixed(1)}`;
  }
  return d;
}

function RowLabel({ children, h, anchorH }: { children: string; h: number; anchorH?: number }) {
  // `anchorH` bottom-aligns the label to a box of that height measured from the
  // row top — used to sit a label on an element's bottom edge (e.g. the glyph
  // bottom) regardless of font metrics. Otherwise plain vertical alignment.
  if (anchorH != null) {
    return (
      <div style={{ height: h }}>
        <div className="flex items-end" style={{ height: anchorH }}>{children}</div>
      </div>
    );
  }
  return (
    <div className="flex items-center" style={{ height: h }}>
      {children}
    </div>
  );
}

function Row({ children, h, align = "start" }: { children: React.ReactNode; h: number; align?: "start" | "end" }) {
  return (
    <div className="flex" style={{ height: h, alignItems: align === "end" ? "flex-end" : "flex-start" }}>
      {children}
    </div>
  );
}

function Cell({
  children,
  justify = "end",
  align = "center",
}: {
  children?: React.ReactNode;
  justify?: "start" | "end";
  align?: "center" | "end";
}) {
  return (
    <div
      className="flex flex-col"
      style={{
        width: COL_W,
        height: "100%",
        alignItems: align === "end" ? "center" : "center",
        justifyContent: justify === "end" ? "flex-end" : "flex-start",
      }}
    >
      {children}
    </div>
  );
}
