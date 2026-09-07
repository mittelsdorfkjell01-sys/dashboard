import { startTransition, useEffect, useId, useMemo, useRef, useState } from "react";
import { flushSync } from "react-dom";
import type { NormalizedForecastSeries, NormalizedForecastHour } from "../../../lib/forecastNormalization";
import { isSpotForecastDisplayHour } from "../../../lib/spotForecastWindow";
import { buildMeteogramModel } from "../meteogramModel";
import { useSpotDataScope, formatWind, windUnitLabel } from "../../../state/SpotDataScope";
import { windColor } from "../../../lib/windScale";
import WeatherGlyph from "./WeatherGlyph";

const COL_W = 30;
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

function fade(hex: string, alpha = 0.45): string {
  const m = /^#?([\da-f]{2})([\da-f]{2})([\da-f]{2})$/i.exec(hex);
  if (!m) return hex;
  const [r, g, b] = [m[1], m[2], m[3]].map((h) => parseInt(h, 16));
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
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
  const model = useMemo(() => buildMeteogramModel(forecast, isSpotForecastDisplayHour), [forecast]);
  const slots = model.slots;
  const scrollRef = useRef<HTMLDivElement>(null);

  const uid = useId(); // base for the active-point gradients/clips/filters
  // Continuous drag position in strip-content pixels; null after the gesture,
  // when the marker resolves to the persistent selected hour.
  const [hoverX, setHoverX] = useState<number | null>(null);
  const rafRef = useRef<number | null>(null);
  const pendingXRef = useRef<number | null>(null);
  useEffect(() => () => { if (rafRef.current != null) cancelAnimationFrame(rafRef.current); }, []);

  // Real wall-clock "now", refreshed each minute so the now-hero stays current
  // without a heavier tick. Drives the row's three-zone split and the marker.
  const [nowMs, setNowMs] = useState(() => Date.now());
  useEffect(() => {
    const id = setInterval(() => setNowMs(Date.now()), 60_000);
    return () => clearInterval(id);
  }, []);

  // The scroll content is exactly the data width — no trailing empty room. An
  // extra trailing area (to let the last day scroll to the viewport's left edge)
  // created a dead zone the cursor could enter, where the marker clamped to the
  // last column and appeared to lag further the more you scrolled right.
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

  // The single wandering, glowing point that anchors the whole TEMP row: the
  // inspected time (the cursor while dragging, else the persistent selection),
  // or "now" when nothing is being inspected. One glowing marker that rests at
  // now and follows the cursor — it replaces the old fixed now-bloom plus a
  // separate selection dot. Null only when there is no readable point at all
  // (e.g. now at night / out of window and nothing selected).
  const activeF: number | null =
    hoverX != null ? hoverX / COL_W - 0.5
    : selectedIndex >= 0 ? selectedIndex
    : nowIndex(slots, nowMs);
  const active = useMemo(() => {
    if (activeF == null) return null;
    const s = sampleCurve(slots, activeF);
    if (!s) return null;
    const ahead = sampleCurve(slots, Math.min(slots.length - 1, activeF + 3));
    const d3 = ahead ? ahead.air - s.air : 0;
    const trend: "up" | "down" | "flat" = d3 > 0.4 ? "up" : d3 < -0.4 ? "down" : "flat";
    const idx = Math.min(slots.length - 1, Math.max(0, Math.round(activeF)));
    const label = slots[idx]?.localTime ?? null;
    return { x: s.x, y: tempY(s.air), air: s.air, trend, label };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- tempY derives from tScale, tracked
  }, [activeF, slots, tScale.min, tScale.max]);
  // Closed area under the curve (per run), for the glow fill; clipped to the
  // past at render so it lights only the elapsed part and stays inside the band.
  // eslint-disable-next-line react-hooks/exhaustive-deps -- cx/tempY derive from COL_W + tScale, tracked here
  const tempArea = useMemo(() => areaRuns(runs, cx, tempY, TEMP_H), [runs, tScale.min, tScale.max]);

  // The wave/weather rows and the wind/direction/time rows don't depend on the
  // hover position — memoise them so a pointer move only re-renders the small
  // temperature-marker overlay, not the hundreds of bar/glyph cells (which is
  // what made the marker visibly lag the cursor).
  const topRows = useMemo(() => (
    <>
      {/* WELLE — wave-height bars. */}
      <Row h={WAVE_ROW_H}>
        {slots.map((s, i) => (
          <Cell key={i}>
            {s.swell != null && (
              <>
                <span className="mb-0.5 leading-none text-white" style={{ fontSize: 10 }}>{s.swell.toFixed(1)}</span>
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
    </>
  ), [slots, waveMax, precipMax]);

  const bottomRows = useMemo(() => (
    <>
      {/* WIND — the foreground (wind) bar is the full wind-scale colour; the
          gust bar behind rises to the gust height in the *wind's* hue at 45%
          opacity (not the gust's own colour). Wind and gust values are
          labelled on their own bars (Figma Frame 67 / node 504-9). */}
      <Row h={BAR_H + 16} align="end">
        {slots.map((s, i) => {
          const wind = s.wind;
          if (wind == null) return <Cell key={i} />;
          const gust = s.gust ?? wind;
          const windH = Math.max(4, (wind / windMax) * BAR_H);
          const gustH = Math.max(windH, (gust / windMax) * BAR_H);
          // Only label the gust when it clears the wind bar with room to read.
          const showGust = gust > wind + 0.5 && gustH - windH >= 14;
          return (
            <Cell key={i} align="end">
              <span
                className="relative w-[22px] rounded-[5px]"
                style={{ height: gustH, background: fade(windColor(wind)) }}
              >
                {showGust && <BarValue>{Math.round(gust)}</BarValue>}
                <span
                  className="absolute inset-x-0 bottom-0 rounded-[5px]"
                  style={{ height: windH, background: windColor(wind) }}
                >
                  <BarValue>{Math.round(wind)}</BarValue>
                </span>
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
    </>
  ), [slots, windMax]);

  if (!slots.length) {
    return (
      <div className="px-4 py-6 text-ui text-muted">
        Für diesen Zeitraum sind keine Stundenwerte verfügbar.
      </div>
    );
  }

  // Track the cursor for the local marker and sync the shared selection to the
  // nearest hour when that column changes. During a fast drag the browser fires
  // many pointermove events per frame; handling each one (a forced layout via
  // getBoundingClientRect + a state update + an SVG repaint) saturates the main
  // thread and the marker falls behind the cursor. So coalesce to at most one
  // update per animation frame: events just stash the latest clientX, and a
  // single rAF applies it. The shared selection write is a transition so its
  // heavier page-wide fan-out never blocks the marker paint.
  const pickAt = (clientX: number) => {
    pendingXRef.current = clientX;
    if (rafRef.current != null) return;
    rafRef.current = requestAnimationFrame(() => {
      rafRef.current = null;
      const cx = pendingXRef.current;
      const el = scrollRef.current;
      if (cx == null || !el) return;
      const rect = el.getBoundingClientRect();
      // The meteogram sits under a CSS `zoom` (lg:zoom-0.85, see DatenPage):
      // getBoundingClientRect is in zoomed screen px, but scrollLeft and the SVG
      // viewBox are unzoomed CSS px. Divide the pointer offset by the zoom before
      // adding scrollLeft, or the marker drifts left by (1-zoom)·x — the further
      // right, the worse. zoom = 1 when no zoom is applied, so this is a no-op then.
      const zoom = el.offsetWidth ? rect.width / el.offsetWidth : 1;
      const x = Math.max(0, Math.min(width, (cx - rect.left) / zoom + el.scrollLeft));
      // Commit the marker synchronously so it paints this frame — React's default
      // deferred commit leaves the marker a constant frame (~16ms) behind the
      // cursor during a drag. The selection fan-out below stays a transition.
      flushSync(() => setHoverX(x));
      const idx = Math.min(slots.length - 1, Math.max(0, Math.round(x / COL_W - 0.5)));
      const slot = slots[idx];
      if (slot && slot.utcKey !== selectedAtUtc) {
        startTransition(() => setSelectedAtUtc(slot.utcKey));
      }
    });
  };

  const resetToNow = () => {
    if (rafRef.current != null) { cancelAnimationFrame(rafRef.current); rafRef.current = null; }
    pendingXRef.current = null;
    setHoverX(null);
    setSelectedAtUtc(null);
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
        id="spot-meteogram-scroll"
        ref={scrollRef}
        tabIndex={0}
        className="min-w-0 flex-1 overflow-x-auto overflow-y-hidden pb-1 [scrollbar-width:thin] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink"
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
          {model.dayGroups.map((group) => (
            <span
              key={group.date}
              data-forecast-day={group.date}
              className="pointer-events-none absolute top-0 h-px w-px"
              style={{ left: group.start * COL_W }}
              aria-hidden="true"
            />
          ))}
          {/* Selection highlight — a soft column of light, no separators. */}
          {selectedIndex >= 0 && (
            <div
              className="absolute top-0 bottom-0 rounded bg-ink/[0.06]"
              style={{ left: selectedIndex * COL_W, width: COL_W }}
              aria-hidden
            />
          )}

          {topRows}

          {/* TEMP — a now-anchored timeline. The solid past brightens toward the
              now point (it "collects light"), a stepped bloom marks now, and the
              dotted future dims to the right. A soft glow area lights the past
              under the line, and a handoff glow bleeds from now into the first
              dotted hours. The drag/hover selection is a quieter secondary
              marker. */}
          <div className="relative" style={{ height: TEMP_H, width }}>
            <svg viewBox={`0 0 ${width} ${TEMP_H}`} width={width} height={TEMP_H} preserveAspectRatio="none" className="absolute inset-0" aria-hidden>
              <defs>
                {active && (
                  <>
                    <clipPath id={`${uid}-cp`} clipPathUnits="userSpaceOnUse">
                      <rect x={0} y={0} width={Math.max(0, active.x)} height={TEMP_H} />
                    </clipPath>
                    <clipPath id={`${uid}-cf`} clipPathUnits="userSpaceOnUse">
                      <rect x={active.x} y={0} width={Math.max(0, width - active.x)} height={TEMP_H} />
                    </clipPath>
                    <linearGradient id={`${uid}-gp`} gradientUnits="userSpaceOnUse" x1={0} y1={0} x2={active.x} y2={0}>
                      <stop offset="0%" stopColor="#eef1f4" stopOpacity={0.42} />
                      <stop offset="100%" stopColor="#eef1f4" stopOpacity={1} />
                    </linearGradient>
                    <linearGradient id={`${uid}-gf`} gradientUnits="userSpaceOnUse" x1={active.x} y1={0} x2={width} y2={0}>
                      <stop offset="0%" stopColor="#eef1f4" stopOpacity={0.85} />
                      <stop offset="100%" stopColor="#eef1f4" stopOpacity={0.24} />
                    </linearGradient>
                    <linearGradient id={`${uid}-gh`} gradientUnits="userSpaceOnUse" x1={active.x} y1={0} x2={active.x + 3 * COL_W} y2={0} spreadMethod="pad">
                      <stop offset="0%" stopColor="#eef1f4" stopOpacity={0.55} />
                      <stop offset="100%" stopColor="#eef1f4" stopOpacity={0} />
                    </linearGradient>
                    <linearGradient id={`${uid}-ga`} gradientUnits="userSpaceOnUse" x1={0} y1={8} x2={0} y2={TEMP_H}>
                      <stop offset="0%" stopColor="#eef1f4" stopOpacity={0.28} />
                      <stop offset="100%" stopColor="#eef1f4" stopOpacity={0} />
                    </linearGradient>
                    <radialGradient id={`${uid}-bloom`} cx="50%" cy="50%" r="50%">
                      <stop offset="0%" stopColor="#eef1f4" stopOpacity={0.55} />
                      <stop offset="100%" stopColor="#eef1f4" stopOpacity={0} />
                    </radialGradient>
                    <filter id={`${uid}-blur`} x="-50%" y="-50%" width="200%" height="200%">
                      <feGaussianBlur stdDeviation="3" />
                    </filter>
                  </>
                )}
              </defs>

              {active ? (
                <>
                  {/* Glow area under the past line, capped to the band bottom. */}
                  {tempArea && <path d={tempArea} fill={`url(#${uid}-ga)`} clipPath={`url(#${uid}-cp)`} />}

                  {/* Future — dotted, dimming to the right. */}
                  {tempPath && (
                    <path
                      d={tempPath}
                      fill="none"
                      stroke={`url(#${uid}-gf)`}
                      strokeWidth={2}
                      strokeLinecap="round"
                      strokeDasharray="0.1 7"
                      clipPath={`url(#${uid}-cf)`}
                    />
                  )}
                  {/* Handoff glow — bleeds from now into the first dotted hours. */}
                  {tempPath && (
                    <path
                      d={tempPath}
                      fill="none"
                      stroke={`url(#${uid}-gh)`}
                      strokeWidth={7}
                      strokeLinecap="round"
                      clipPath={`url(#${uid}-cf)`}
                      filter={`url(#${uid}-blur)`}
                    />
                  )}

                  {/* Past — a soft wide glow under a bright line that brightens to now. */}
                  {tempPath && (
                    <>
                      <path
                        d={tempPath}
                        fill="none"
                        stroke="rgba(243,240,234,0.22)"
                        strokeWidth={6}
                        strokeLinejoin="round"
                        strokeLinecap="round"
                        clipPath={`url(#${uid}-cp)`}
                      />
                      <path
                        d={tempPath}
                        fill="none"
                        stroke={`url(#${uid}-gp)`}
                        strokeWidth={2.4}
                        strokeLinejoin="round"
                        strokeLinecap="round"
                        clipPath={`url(#${uid}-cp)`}
                        pathLength={1}
                        className="daten-draw-line"
                      />
                    </>
                  )}
                </>
              ) : (
                // Now outside the loaded window → a quiet dotted curve, no hero.
                tempPath && (
                  <path d={tempPath} fill="none" stroke="rgba(243,240,234,0.5)" strokeWidth={2} strokeLinecap="round" strokeDasharray="0.1 7" />
                )
              )}

              {/* The one wandering point — a small crisp dot with just a faint
                  halo (kept subtle: no large bloom). Rests at now, follows the
                  cursor/selection. */}
              {active && (
                <>
                  <circle cx={active.x} cy={active.y} r={11} fill={`url(#${uid}-bloom)`} opacity={0.4} className="daten-now-pulse" />
                  <circle cx={active.x} cy={active.y} r={3.6} fill="#ffffff" />
                </>
              )}
            </svg>

            {/* Detail tile at the glowing point — the one allowed card: time +
                temp + trend. Sits in the band, flips to the left near the right
                edge, and follows the wandering point. */}
            {active && (() => {
              const tw = 118;
              const th = 44;
              const pad = 14;
              const placeRight = active.x + pad + tw <= width;
              const tx = placeRight ? active.x + pad : active.x - pad - tw;
              const ty = active.y < th + 14 ? Math.min(TEMP_H - th - 2, active.y + 12) : Math.max(2, active.y - th - 8);
              const trendChar = active.trend === "up" ? "↗" : active.trend === "down" ? "↘" : "→";
              const trendColor = active.trend === "up" ? "var(--sw-orange)" : active.trend === "down" ? "var(--sw-teal)" : "var(--sw-muted)";
              return (
                <div
                  className="pointer-events-none absolute flex flex-col justify-center gap-0.5 rounded-lg border border-white/15 bg-white/10 px-2.5 py-1 backdrop-blur-sm"
                  style={{ left: tx, top: ty, width: tw, height: th }}
                >
                  <span className="leading-none tabular-nums text-white/70" style={{ fontSize: 10 }}>{active.label ?? "—"} Uhr</span>
                  <span className="flex items-center gap-1.5 leading-none">
                    <span className="font-semibold tabular-nums text-white" style={{ fontSize: 18 }}>{Math.round(active.air)}°</span>
                    <span className="font-medium" style={{ fontSize: 13, color: trendColor }}>{trendChar}</span>
                  </span>
                </div>
              );
            })()}
          </div>

          {bottomRows}
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

// Closed filled area under each smooth run (top edge = the curve, bottom edge =
// the band floor `bottomY`), so the glow fill stays inside the TEMP band and
// never bleeds into the WIND row. One sub-path per run keeps gaps open.
function areaRuns(
  runs: { i: number; air: number }[][],
  cx: (i: number) => number,
  cy: (air: number) => number,
  bottomY: number,
): string {
  let d = "";
  for (const run of runs) {
    if (run.length < 2) continue;
    const pts = run.map((p) => [cx(p.i), cy(p.air)] as [number, number]);
    const curve = catmullRom(pts); // "Mx0,y0 C.. C.."
    const sp = curve.indexOf(" ");
    const segs = sp >= 0 ? curve.slice(sp + 1) : "";
    const x0 = pts[0][0];
    const xN = pts[pts.length - 1][0];
    d += `${d ? " " : ""}M${x0.toFixed(1)},${bottomY} L${pts[0][0].toFixed(1)},${pts[0][1].toFixed(1)} ${segs} L${xN.toFixed(1)},${bottomY} Z`;
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

// Fractional slot index for the wall-clock instant `nowMs`, or null when it
// lies before the first slot, after the last, or inside an inter-day night gap
// (the display window is 06–22, so consecutive days are >1h apart in real time —
// interpolating across that gap would place "now" on a line that isn't drawn).
function nowIndex(slots: NormalizedForecastHour[], nowMs: number): number | null {
  for (let i = 0; i < slots.length - 1; i++) {
    const t0 = Date.parse(slots[i].utcKey);
    const t1 = Date.parse(slots[i + 1].utcKey);
    if (!(t1 > t0) || t1 - t0 > 90 * 60 * 1000) continue; // gap between days
    if (nowMs >= t0 && nowMs < t1) return i + (nowMs - t0) / (t1 - t0);
  }
  return null;
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

// A wind/gust value sitting at the top of its bar, white with a soft shadow so
// it stays legible on every scale colour (Figma node 504-9).
function BarValue({ children }: { children: React.ReactNode }) {
  return (
    <span
      className="pointer-events-none absolute inset-x-0 top-0.5 text-center leading-none text-white"
      style={{ fontSize: 10, textShadow: "0 1px 2px rgba(0, 0, 0, 0.35)" }}
    >
      {children}
    </span>
  );
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
