import { startTransition, useEffect, useMemo, useRef } from "react";
import type { NormalizedForecastSeries } from "../../../lib/forecastNormalization";
import { isSpotForecastDisplayHour } from "../../../lib/spotForecastWindow";
import { buildMeteogramModel } from "../meteogramModel";
import { useSpotDataScope, formatWind, windUnitLabel } from "../../../state/SpotDataScope";
import { tempColor } from "../../../lib/tempScale";
import { useOptionalUnits } from "../../../context/PrefsContext";
import { waveValue, tempValue } from "../../../lib/units";
import WeatherGlyph from "./WeatherGlyph";
import MeteogramWindBar, {
  METEOGRAM_COLUMN_WIDTH,
  METEOGRAM_WIND_BASE_HEIGHT,
  METEOGRAM_WIND_HEADROOM,
  useMeteogramWindHeight,
} from "../../forecast/MeteogramWindBar";

const COL_W = METEOGRAM_COLUMN_WIDTH; // 22px bar + 3px gap
// Fixed plinth under every wind bar, tall enough for its 10px value — so a
// sub-5 kn bar still holds its number.
const WIND_BASE_H = METEOGRAM_WIND_BASE_HEIGHT;
const WIND_HEADROOM = METEOGRAM_WIND_HEADROOM; // air between the temperature row and the tallest bar
const WAVE_H = 34; // wave bar band height
const WAVE_ROW_H = WAVE_H + 6;
const GLYPH = 26; // weather-icon box size (24×24 viewBox scaled)
// The glyph art sits in the upper ~16/24 of its box (cloud/sun/moon base ≈ y16),
// leaving whitespace below; the WETTER icon label centres on that glyph.
const WELLE_WETTER_GAP = 16;
// The tail below the glyph holds the precip value + stub (up to ~27px), so the
// heaviest rain hour still clears the temperature row.
const WETTER_ROW_H = WELLE_WETTER_GAP + GLYPH + 28;
// Temperature stays a compact text-only row. It carries no bar or chip shape;
// the number itself is the reading, while the fixed row height keeps every
// downstream axis aligned.
const TEMP_ROW_H = 24;
const RICHT_ROW_H = 30;
const ZEIT_ROW_H = 26; // room for the small caption under the clock icon

/**
 * The Daten-page meteogram (Figma Frame 67, Group 66). A horizontally
 * scrollable instrument strip: wave-height bars, a weather-glyph + precip row,
 * a compact row of temperature values coloured by the temperature scale,
 * wind-speed bars coloured by the shared wind scale with a darker gust cap,
 * wind-direction arrows and a time axis. Faint vertical day separators sit
 * behind the data for orientation. Pointer interaction over the strip picks the
 * nearest hour and writes it to the shared SpotDataScope selection, so every
 * other module on the page moves together; the selected hour is a soft column.
 */
export default function MeteoChart({ forecast }: { forecast: NormalizedForecastSeries }) {
  const { selectedAtUtc, setSelectedAtUtc, windUnit } = useSpotDataScope();
  const units = useOptionalUnits();
  const model = useMemo(() => buildMeteogramModel(forecast, isSpotForecastDisplayHour), [forecast]);
  const slots = model.slots;
  const scrollRef = useRef<HTMLDivElement>(null);
  const dataRef = useRef<HTMLDivElement>(null);

  // On phones the wind band shrinks so the whole instrument fits at a glance.
  // Only vertical scale changes — COL_W and all horizontal math stay identical,
  // so the pointer picking is untouched.
  const barH = useMeteogramWindHeight();
  const windBandH = WIND_HEADROOM + WIND_BASE_H + barH;

  // Coalesce pointer moves to one selection write per animation frame — during a
  // fast drag the browser fires many pointermove events, and handling each one
  // (a forced layout via getBoundingClientRect + a page-wide selection fan-out)
  // saturates the main thread.
  const rafRef = useRef<number | null>(null);
  const pendingXRef = useRef<number | null>(null);
  useEffect(() => () => { if (rafRef.current != null) cancelAnimationFrame(rafRef.current); }, []);

  const width = Math.max(slots.length * COL_W, 1);
  const selectedIndex = slots.findIndex((s) => s.utcKey === selectedAtUtc);
  const selectedSlot = selectedIndex >= 0 ? slots[selectedIndex] : null;

  // Scale the wind bars to the actual max reading (wind or gust) in view — with a
  // small floor so a near-calm day isn't amplified into noise — so the tallest bar
  // fills the band instead of leaving a large empty gap under the temperature row.
  const windMax = useMemo(() => {
    let m = 0;
    for (const s of slots) {
      if (s.wind != null && s.wind > m) m = s.wind;
      if (s.gust != null && s.gust > m) m = s.gust;
    }
    return Math.max(m, 5);
  }, [slots]);
  const waveMax = model.scales.wave.max;
  const precipMax = model.scales.precipitation.max;

  const topRows = useMemo(() => (
    <>
      {/* WELLE — wave-height bars. */}
      <Row h={WAVE_ROW_H}>
        {slots.map((s, i) => (
          <Cell key={i}>
            {s.swell != null && (
              <>
                <span className="mb-0.5 leading-none text-white" style={{ fontSize: 10 }}>{waveValue(s.swell, units.wave)}</span>
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
  ), [slots, waveMax, precipMax, units.wave]);

  // TEMP — value only. Temperature deliberately has no bar/chip encoding.
  const tempRow = useMemo(() => (
    <Row h={TEMP_ROW_H}>
      {slots.map((s, i) => (
        <Cell key={i} justify="center">
          {s.air != null && (
            <span
              className="swd-meteogram-temperature font-semibold tabular-nums leading-none"
              style={{ color: tempColor(s.air), fontSize: 11 }}
            >
              {tempValue(s.air, units.temp)}°
            </span>
          )}
        </Cell>
      ))}
    </Row>
  ), [slots, units.temp]);

  const bottomRows = useMemo(() => (
    <>
      {/* WIND — the foreground (wind) bar is the full wind-scale colour; the
          gust bar behind rises to the gust height in the *wind's* hue at 45%
          opacity (not the gust's own colour). Wind and gust values are
          labelled on their own bars (Figma Frame 67 / node 504-9). */}
      <Row h={windBandH} align="end">
        {slots.map((s, i) => {
          const wind = s.wind;
          if (wind == null) return <Cell key={i} />;
          return (
            <Cell key={i}>
              <MeteogramWindBar wind={wind} gust={s.gust} maximum={windMax} windUnit={windUnit} proportionalHeight={barH} />
            </Cell>
          );
        })}
      </Row>

      {/* RICHT — wind-direction arrows. */}
      <Row h={RICHT_ROW_H}>
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
      <Row h={ZEIT_ROW_H}>
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
  ), [slots, windMax, barH, windBandH, windUnit]);

  if (!slots.length) {
    return (
      <div className="px-4 py-6 text-ui text-muted">
        Für diesen Zeitraum sind keine Stundenwerte verfügbar.
      </div>
    );
  }

  // Sync the shared selection to the hour under the cursor when that column
  // changes. The write is a transition so its page-wide fan-out never blocks the
  // scroll/paint. See the coalescing note on rafRef above.
  const pickAt = (clientX: number) => {
    pendingXRef.current = clientX;
    if (rafRef.current != null) return;
    rafRef.current = requestAnimationFrame(() => {
      rafRef.current = null;
      const px = pendingXRef.current;
      const data = dataRef.current;
      if (px == null || !data) return;
      // Measure against the data content itself: its left edge already moves with
      // the scroll (and now with the leading label gutter that scrolls off), so
      // the pointer offset maps straight onto the columns without adding
      // scrollLeft. The meteogram sits under a CSS `zoom` (lg:zoom-0.85, see
      // DatenPage): getBoundingClientRect is in zoomed screen px while the content
      // coords are unzoomed CSS px, so divide by the zoom (1 = no-op when unzoomed).
      const rect = data.getBoundingClientRect();
      const zoom = data.offsetWidth ? rect.width / data.offsetWidth : 1;
      const x = Math.max(0, Math.min(width, (px - rect.left) / zoom));
      const idx = Math.min(slots.length - 1, Math.max(0, Math.round(x / COL_W - 0.5)));
      const slot = slots[idx];
      if (slot && slot.utcKey !== selectedAtUtc) {
        startTransition(() => setSelectedAtUtc(slot.utcKey));
      }
    });
  };

  const clearPointerPreview = () => {
    if (rafRef.current != null) { cancelAnimationFrame(rafRef.current); rafRef.current = null; }
    pendingXRef.current = null;
  };

  return (
    <div className="min-w-0">
      <div
        id="spot-meteogram-scroll"
        ref={scrollRef}
        tabIndex={0}
        className="overflow-x-auto overflow-y-hidden pb-1 [scrollbar-width:thin] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink"
        onPointerDown={(e) => {
          (e.currentTarget as HTMLElement).setPointerCapture?.(e.pointerId);
          pickAt(e.clientX);
        }}
        onPointerMove={(e) => pickAt(e.clientX)}
        onPointerLeave={clearPointerPreview}
        role="group"
        aria-label="Meteogramm — Zeitpunkt wählen"
      >
        <div className="flex w-max gap-2 sm:gap-3">
          {/* Icon gutter — a leading column that scrolls WITH the strip, so it
              slides off to the left when you scroll right and returns at the far
              left. Each icon sits at the same vertical anchor as its row's data —
              bar rows align to the baseline, the glyph row centres — so the label
              reads directly in front of its thing. */}
          <div className="shrink-0 select-none px-0.5 text-muted">
            <RowLabel h={WAVE_ROW_H} align="end" label="Welle" icon={<LabelWave />} />
            <RowLabel h={WETTER_ROW_H} align="center" label="Wetter" icon={<LabelWeather />} />
            <RowLabel h={TEMP_ROW_H} align="center" label="Temp" icon={<LabelThermo />} />
            <RowLabel h={windBandH} align="center" label="Wind" icon={<LabelWind />} />
            <RowLabel h={RICHT_ROW_H} align="end" label="Richt" icon={<LabelCompass />} />
            <RowLabel h={ZEIT_ROW_H} align="end" label="Zeit" icon={<LabelClock />} />
          </div>

          <div ref={dataRef} className="relative shrink-0" style={{ width }}>
          {/* Raster — a faint vertical separator at each day boundary so it's
              clear which day a column belongs to. */}
          {model.dayGroups.map((group) =>
            group.start > 0 ? (
              <span
                key={`sep-${group.date}`}
                aria-hidden="true"
                className="pointer-events-none absolute top-0 bottom-0 w-px"
                style={{ left: group.start * COL_W, background: "var(--sw-line)", opacity: 0.7 }}
              />
            ) : null,
          )}
          {/* Raster — faint horizontal gridlines across the wind band (plus its
              baseline) so bar heights can be read against a reference. */}
          {(() => {
            const baseline = WAVE_ROW_H + WETTER_ROW_H + TEMP_ROW_H + windBandH;
            return [0, 0.33, 0.66, 1].map((f) => (
              <span
                key={`grid-${f}`}
                aria-hidden="true"
                className="pointer-events-none absolute left-0 h-px"
                style={{ top: baseline - (f === 0 ? 0 : WIND_BASE_H + f * barH), width, background: "var(--sw-line)", opacity: f === 0 ? 0.7 : 0.4 }}
              />
            ));
          })()}
          {/* Day anchors for scroll-to-day (ForecastDayStrip → scrollMeteogramToDay). */}
          {model.dayGroups.map((group) => (
            <span
              key={group.date}
              data-forecast-day={group.date}
              className="pointer-events-none absolute top-0 h-px w-px"
              style={{ left: group.start * COL_W }}
              aria-hidden="true"
            />
          ))}

          {/* Data rows — wrapped in a positioned layer so they paint over the
              raster behind them. */}
          <div className="relative">
            {topRows}
            {tempRow}
            {bottomRows}
          </div>

          {/* Selection highlight — a soft column of light on top, no separators. */}
          {selectedIndex >= 0 && (
            <div
              className="pointer-events-none absolute top-0 bottom-0 rounded bg-ink/[0.06]"
              style={{ left: selectedIndex * COL_W, width: COL_W }}
              aria-hidden
            />
          )}
          </div>
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

function RowLabel({ icon, label, h, align = "center" }: { icon: React.ReactNode; label: string; h: number; align?: "start" | "center" | "end" }) {
  const items = align === "start" ? "items-start" : align === "end" ? "items-end" : "items-center";
  return (
    <div className={`flex justify-center ${items}`} style={{ height: h }}>
      <span className="flex flex-col items-center gap-px leading-none">
        {icon}
        <span className="uppercase text-muted" style={{ fontSize: 8, letterSpacing: "0.04em", lineHeight: 1 }}>{label}</span>
      </span>
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
}: {
  children?: React.ReactNode;
  justify?: "start" | "end" | "center";
}) {
  const jc = justify === "start" ? "flex-start" : justify === "center" ? "center" : "flex-end";
  return (
    <div
      className="flex flex-col items-center"
      style={{ width: COL_W, height: "100%", justifyContent: jc }}
    >
      {children}
    </div>
  );
}

// Row-label glyphs — one per instrument row, authored on a 24×24 viewBox at
// 16px, stroked in the inherited `currentColor` (the muted gutter tone).
const ICON = { width: 16, height: 16, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: 1.6, strokeLinecap: "round" as const, strokeLinejoin: "round" as const };

function LabelWave() {
  return (
    <svg {...ICON} aria-hidden>
      <path d="M2 9c2 0 2 2 4 2s2-2 4-2 2 2 4 2 2-2 4-2 2 2 4 2" />
      <path d="M2 15c2 0 2 2 4 2s2-2 4-2 2 2 4 2 2-2 4-2 2 2 4 2" />
    </svg>
  );
}

function LabelWeather() {
  return (
    <svg {...ICON} aria-hidden>
      <circle cx="9" cy="8" r="3" />
      <path d="M7 18a3.5 3.5 0 0 1 .4-7 5 5 0 0 1 9.2 1.2A3.2 3.2 0 0 1 16 18Z" />
    </svg>
  );
}

function LabelThermo() {
  return (
    <svg {...ICON} aria-hidden>
      <path d="M12 3a2.2 2.2 0 0 1 2.2 2.2v8.4a4 4 0 1 1-4.4 0V5.2A2.2 2.2 0 0 1 12 3Z" />
      <path d="M12 16.4v-6" />
    </svg>
  );
}

function LabelWind() {
  return (
    <svg {...ICON} aria-hidden>
      <path d="M4 8h10a2.4 2.4 0 1 0-2.4-2.4" />
      <path d="M4 12h14a2.4 2.4 0 1 1-2.4 2.4" />
      <path d="M4 16h7" />
    </svg>
  );
}

function LabelCompass() {
  return (
    <svg {...ICON} aria-hidden>
      <circle cx="12" cy="12" r="9" />
      <path d="M9.5 14.5 12 7 14.5 14.5 12 12.6Z" />
    </svg>
  );
}

function LabelClock() {
  return (
    <svg {...ICON} aria-hidden>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7.5V12l3.2 1.9" />
    </svg>
  );
}
