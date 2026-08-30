import { useMemo, useRef } from "react";
import type { NormalizedForecastSeries, NormalizedForecastHour } from "../../../lib/forecastNormalization";
import { buildMeteogramModel } from "../meteogramModel";
import { useSpotDataScope, formatWind, windUnitLabel } from "../../../state/SpotDataScope";
import { windColor } from "../../../lib/windScale";
import WeatherGlyph from "./WeatherGlyph";

const COL_W = 46;
const BAR_H = 118; // wind bar band height
const WAVE_H = 40; // wave bar band height
const TEMP_H = 74; // temperature band height

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

  const width = Math.max(slots.length * COL_W, 1);
  const selectedIndex = slots.findIndex((s) => s.utcKey === selectedAtUtc);
  const selectedSlot = selectedIndex >= 0 ? slots[selectedIndex] : null;

  const tScale = model.scales.temperature;
  const windMax = model.scales.wind.max;
  const waveMax = model.scales.wave.max;
  const precipMax = model.scales.precipitation.max;

  const tempY = (air: number) => {
    const t = (air - tScale.min) / Math.max(1, tScale.max - tScale.min);
    return TEMP_H - 8 - t * (TEMP_H - 20);
  };
  const cx = (i: number) => i * COL_W + COL_W / 2;

  // Full temperature polyline (blue) + the selected day drawn white on top.
  // eslint-disable-next-line react-hooks/exhaustive-deps -- tempY/cx derive from tScale + COL_W, tracked below
  const tempPath = useMemo(() => pathFrom(slots, cx, tempY), [slots, tScale.min, tScale.max]);
  const selDate = selectedSlot?.localDate;
  const selDayPath = useMemo(
    () => (selDate ? pathFrom(slots, cx, tempY, (s) => s.localDate === selDate) : ""),
    // eslint-disable-next-line react-hooks/exhaustive-deps -- tempY/cx derive from tScale + COL_W, tracked here
    [slots, selDate, tScale.min, tScale.max],
  );

  if (!slots.length) {
    return (
      <div className="border-y border-line bg-band/40 px-4 py-6 text-ui text-muted">
        Für diesen Zeitraum sind keine Stundenwerte verfügbar.
      </div>
    );
  }

  const pickAt = (clientX: number) => {
    const el = scrollRef.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const x = clientX - rect.left + el.scrollLeft;
    const idx = Math.min(slots.length - 1, Math.max(0, Math.floor(x / COL_W)));
    const slot = slots[idx];
    if (slot) setSelectedAtUtc(slot.utcKey);
  };

  return (
    <div className="flex min-w-0 gap-3">
      {/* Fixed row-label gutter (stays put while the strip scrolls). */}
      <div className="shrink-0 select-none pt-1 text-data-caption uppercase tracking-[0.14em] text-muted">
        <RowLabel h={WAVE_H + 18}>{ROW_LABELS[0]}</RowLabel>
        <RowLabel h={56}>{ROW_LABELS[1]}</RowLabel>
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
        onPointerMove={(e) => {
          if (e.buttons === 1) pickAt(e.clientX);
        }}
        role="group"
        aria-label="Meteogramm — Zeitpunkt wählen"
      >
        <div className="relative" style={{ width }}>
          {/* Day separators + selection highlight. */}
          {model.dayGroups.map((g) =>
            g.start === 0 ? null : (
              <div key={g.date} className="absolute top-0 bottom-0 border-l border-line" style={{ left: g.start * COL_W }} aria-hidden />
            ),
          )}
          {selectedIndex >= 0 && (
            <div
              className="absolute top-0 bottom-0 rounded bg-ink/[0.06]"
              style={{ left: selectedIndex * COL_W, width: COL_W }}
              aria-hidden
            />
          )}

          {/* WELLE — wave-height bars. */}
          <Row h={WAVE_H + 18}>
            {slots.map((s, i) => (
              <Cell key={i}>
                {s.swell != null && (
                  <>
                    <span className="mb-0.5 leading-none text-muted" style={{ fontSize: 10 }}>{s.swell.toFixed(1)}</span>
                    <span
                      className="w-[22px] rounded-[4px]"
                      style={{ height: Math.max(3, (s.swell / waveMax) * WAVE_H), background: "#5B7A99" }}
                    />
                  </>
                )}
              </Cell>
            ))}
          </Row>

          {/* WETTER — glyph + precipitation stub. */}
          <Row h={56}>
            {slots.map((s, i) => (
              <Cell key={i} justify="start">
                <WeatherGlyph condition={s.weather_condition} isDay={s.is_day ?? true} size={26} />
                {s.precip != null && s.precip > 0 && (
                  <span className="mt-0.5 flex flex-col items-center leading-none">
                    <span className="text-muted" style={{ fontSize: 9 }}>{s.precip.toFixed(1)}</span>
                    <span
                      className="mt-0.5 w-[20px] rounded-[3px]"
                      style={{ height: Math.max(2, (s.precip / precipMax) * 14), background: "#4F97D8" }}
                    />
                  </span>
                )}
              </Cell>
            ))}
          </Row>

          {/* TEMP — line across the whole horizon; selected day drawn white. */}
          <div className="relative" style={{ height: TEMP_H, width }}>
            <svg viewBox={`0 0 ${width} ${TEMP_H}`} width={width} height={TEMP_H} preserveAspectRatio="none" className="absolute inset-0" aria-hidden>
              {tempPath && <path d={tempPath} fill="none" stroke="#4F97D8" strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />}
              {selDayPath && (
                <path
                  d={selDayPath}
                  fill="none"
                  stroke="#F3F0EA"
                  strokeWidth={2.4}
                  strokeLinejoin="round"
                  strokeLinecap="round"
                  style={{ filter: "drop-shadow(0 0 4px rgba(243,240,234,0.55))" }}
                />
              )}
              {selectedSlot?.air != null && (
                <circle cx={cx(selectedIndex)} cy={tempY(selectedSlot.air)} r={5} fill="#F3F0EA" />
              )}
            </svg>
            {selectedSlot?.air != null && (
              <span
                className="absolute -translate-x-1/2 font-medium text-ink"
                style={{ fontSize: 11, left: cx(selectedIndex), top: Math.max(0, tempY(selectedSlot.air) - 20) }}
              >
                {Math.round(selectedSlot.air)}
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

function pathFrom(
  slots: NormalizedForecastHour[],
  cx: (i: number) => number,
  cy: (air: number) => number,
  filter?: (s: NormalizedForecastHour) => boolean,
): string {
  let d = "";
  let pen = false;
  slots.forEach((s, i) => {
    if (s.air == null || (filter && !filter(s))) {
      pen = false;
      return;
    }
    d += `${pen ? "L" : "M"}${cx(i).toFixed(1)},${cy(s.air).toFixed(1)} `;
    pen = true;
  });
  return d.trim();
}

function RowLabel({ children, h }: { children: string; h: number }) {
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
