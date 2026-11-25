import { startTransition, useEffect, useMemo, useRef, useState } from "react";
import type { NormalizedForecastSeries } from "../../../lib/forecastNormalization";
import { isSpotForecastDisplayHour } from "../../../lib/spotForecastWindow";
import { buildMeteogramModel } from "../meteogramModel";
import { useSpotDataScope, formatWind, windUnitLabel } from "../../../state/SpotDataScope";
import { tempTone } from "../../../lib/tempScale";
import { useOptionalUnits } from "../../../context/PrefsContext";
import { waveValue, tempValue, windValue } from "../../../lib/units";
import { windColor } from "../../../lib/windScale";
import { headlineWaveFromDeg, headlineWaveM, headlineWavePeriodS, primarySwell } from "../../../lib/waveReading";
import type { DatenFocus } from "./datenFocus";
import WeatherGlyph from "./WeatherGlyph";
import { SizedWaveIcon, WAVE_PATH } from "../../../lib/icons";
import MeteogramWindBar, {
  METEOGRAM_COLUMN_WIDTH,
  METEOGRAM_WIND_BASE_HEIGHT,
  METEOGRAM_WIND_HEADROOM,
  useMeteogramWindHeight,
} from "../../forecast/MeteogramWindBar";

const COL_W = METEOGRAM_COLUMN_WIDTH; // 22px bar + 3px gap
// Wave row: a wave glyph that grows and rolls over with the wave height
// (lib/icons SizedWaveIcon, at most 24px), with the metres underneath. The
// row keeps room for 26px.
const WAVE_ICON_MAX = 26;
const WAVE_ICON_ROW_H = WAVE_ICON_MAX + 16;
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
// Wave focus rows (2026-11-25).
const PERIOD_ROW_H = 16;
const WAVE_DIR_ROW_H = 22;
const SWELL_ROW_H = 26;
// Both layouts are the same height (2026-11-25, "gleich groß"): switching
// Wind ↔ Welle never moves the page below. The wave band gives up what the
// wave layout's extra rows take.
const WAVE_BAND_TRIM = PERIOD_ROW_H + WAVE_DIR_ROW_H + 2 * SWELL_ROW_H - (RICHT_ROW_H + WAVE_ICON_ROW_H);

/**
 * The Daten-page meteogram. A horizontally scrollable instrument strip, one
 * column per hour: wind bars whose height and wind-scale colour both carry
 * the strength, with the gust translucent behind in its own colour;
 * direction arrows; a wave glyph that grows with the wave, its height
 * underneath; a weather-glyph + precip row; temperature as a number; and a
 * time axis. Faint vertical day separators sit
 * behind the data for orientation. Pointer interaction over the strip picks the
 * nearest hour and writes it to the shared SpotDataScope selection, so every
 * other module on the page moves together; the selected hour is a soft column.
 */
export default function MeteoChart({ forecast, focus = "wind" }: { forecast: NormalizedForecastSeries; focus?: DatenFocus }) {
  const { selectedAtUtc, setSelectedAtUtc, windUnit } = useSpotDataScope();
  const units = useOptionalUnits();
  const model = useMemo(() => buildMeteogramModel(forecast, isSpotForecastDisplayHour), [forecast]);
  const slots = model.slots;
  const scrollRef = useRef<HTMLDivElement>(null);
  const dataRef = useRef<HTMLDivElement>(null);
  // The row icons stand at the start; once the strip is swiped sideways they
  // fade away so the data gets the full width, and return at the start
  // (2026-11-25).
  const [labelsHidden, setLabelsHidden] = useState(false);
  // On phones the wind band shrinks so the whole instrument fits at a glance.
  const barH = useMeteogramWindHeight();
  const windBandH = METEOGRAM_WIND_HEADROOM + METEOGRAM_WIND_BASE_HEIGHT + barH;

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
  // Bars scale to the strongest reading in view (wind or gust), floored so a
  // calm day isn't amplified into noise.
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

  // Rows by focus (2026-11-25, "Wellenzeilen statt Windzeilen"): the wind
  // layout is the default; the wave layout puts the sea on top — total wave as
  // bars, its period and direction, the primary swell — and the wind below as
  // a number with its arrow. Weather, temperature and time stay at the foot.
  const rows = useMemo(() => {
    const windRow = (
    <>
      {/* WIND — a bar whose height and colour both carry the strength; the
          gust rises behind it, translucent in the gust's own scale colour, so
          a gusty hour shows both readings at once (2026-11-24). */}
      <Row h={windBandH} align="end">
        {slots.map((s, i) => (
          <Cell key={i}>
            {s.wind != null && (
              <MeteogramWindBar wind={s.wind} gust={s.gust} maximum={windMax} windUnit={windUnit} proportionalHeight={barH} gustTone="gust" />
            )}
          </Cell>
        ))}
      </Row>

    </>
  );
    const dirRow = (
    <>
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

    </>
  );
    const waveIconRow = (
    <>
      {/* WELLE — a wave glyph that grows with the wave, its height in metres
          underneath (total wave, see lib/waveReading.ts). No chip behind it. */}
      <Row h={WAVE_ICON_ROW_H} align="end">
        {slots.map((s, i) => {
          const wave = headlineWaveM(s);
          return (
            <Cell key={i}>
              {wave != null && (
                <span className="flex flex-col items-center gap-0.5 pb-0.5">
                  {/* Flat for a small sea, the full crest for a big one. */}
                  <SizedWaveIcon heightM={wave} className="text-[color:var(--sw-data-swell)]" />
                  <span className="font-figures text-micro font-semibold leading-none tabular-nums text-ink">{waveValue(wave, units.wave)}</span>
                </span>
              )}
            </Cell>
          );
        })}
      </Row>

    </>
  );
    const weatherRow = (
    <>
      {/* WETTER — glyph + precipitation stub. */}
      <Row h={WETTER_ROW_H}>
        {slots.map((s, i) => (
          <Cell key={i} justify="start">
            <div aria-hidden style={{ height: WELLE_WETTER_GAP }} />
            <WeatherGlyph condition={s.weather_condition} isDay={s.is_day ?? true} size={GLYPH} />
            {s.precip != null && s.precip > 0 && (
              <span className="mt-0.5 flex flex-col items-center leading-none">
                <span className="text-micro font-medium text-muted">{s.precip.toFixed(1)}</span>
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
  );
    const tempRow = (
    <>
      {/* TEMP — value only. Temperature deliberately has no bar/chip encoding. */}
      <Row h={TEMP_ROW_H}>
        {slots.map((s, i) => (
          <Cell key={i} justify="center">
            {s.air != null && (
              <span
                className="swd-meteogram-temperature text-caption font-semibold tabular-nums leading-none"
                style={{ color: tempTone(s.air) }}
              >
                {tempValue(s.air, units.temp)}°
              </span>
            )}
          </Cell>
        ))}
      </Row>

    </>
  );
    const timeRow = (
    <>
      {/* ZEIT — hour axis, labelled on even hours + day starts. */}
      <Row h={ZEIT_ROW_H}>
        {slots.map((s, i) => {
          const show = s.localHour % 2 === 0;
          return (
            <Cell key={i}>
              {show && <span className="text-micro font-medium tabular-nums text-muted">{s.localTime.slice(0, 2)}</span>}
            </Cell>
          );
        })}
      </Row>
    </>
  );

    // WELLE as bars — height and number carry the total wave.
    const waveBarRow = (
      <Row h={windBandH - WAVE_BAND_TRIM} align="end">
        {slots.map((s, i) => {
          const wave = headlineWaveM(s);
          return (
            <Cell key={i}>
              {wave != null && (
                <span className="flex flex-col items-center">
                  <span className="mb-0.5 font-figures text-micro font-semibold leading-none tabular-nums text-ink">{waveValue(wave, units.wave)}</span>
                  <span
                    className="w-[22px] rounded-t-[4px]"
                    style={{ height: Math.max(3, (wave / Math.max(waveMax, 0.5)) * (windBandH - WAVE_BAND_TRIM - 14)), background: "var(--sw-data-swell)" }}
                  />
                </span>
              )}
            </Cell>
          );
        })}
      </Row>
    );
    // PERIODE — the sea's period in seconds.
    const periodRow = (
      <Row h={PERIOD_ROW_H}>
        {slots.map((s, i) => {
          const period = headlineWavePeriodS(s);
          return (
            <Cell key={i} justify="center">
              {period != null && <span className="font-figures text-micro font-semibold leading-none tabular-nums text-ink">{Math.round(period)}</span>}
            </Cell>
          );
        })}
      </Row>
    );
    // RICHTUNG der Welle — same arrow as the wind's, in the sea's colour.
    const waveDirRow = (
      <Row h={WAVE_DIR_ROW_H}>
        {slots.map((s, i) => {
          const from = headlineWaveFromDeg(s);
          return (
            <Cell key={i}>
              {from != null && (
                <svg width={16} height={16} viewBox="0 0 16 16" style={{ transform: `rotate(${from}deg)` }} aria-hidden className="text-[color:var(--sw-data-swell)]">
                  <path d="M8 2 L8 13 M4.5 6 L8 2 L11.5 6" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              )}
            </Cell>
          );
        })}
      </Row>
    );
    // 1. DÜNUNG — height over period; empty where the model has no partition.
    const swellRow = (
      <Row h={SWELL_ROW_H}>
        {slots.map((s, i) => {
          const swell = primarySwell(s);
          return (
            <Cell key={i} justify="center">
              {swell && (
                <span className="flex flex-col items-center gap-0.5 leading-none">
                  <span className="font-figures text-micro font-semibold tabular-nums text-ink">{waveValue(swell.heightM, units.wave)}</span>
                  {swell.periodS != null && <span className="font-figures text-micro tabular-nums text-muted">{Math.round(swell.periodS)}s</span>}
                </span>
              )}
            </Cell>
          );
        })}
      </Row>
    );
    // WIND, compact — the number in its scale colour over its arrow.
    const windCompactRow = (
      <Row h={SWELL_ROW_H}>
        {slots.map((s, i) => (
          <Cell key={i} justify="center">
            {s.wind != null && (
              <span className="flex flex-col items-center gap-0.5 leading-none">
                <span className="font-figures text-micro font-semibold tabular-nums" style={{ color: windColor(s.wind) }}>{windValue(s.wind, windUnit)}</span>
                {s.dir != null && (
                  <svg width={11} height={11} viewBox="0 0 16 16" style={{ transform: `rotate(${s.dir}deg)` }} aria-hidden className="text-ink">
                    <path d="M8 2 L8 13 M4.5 6 L8 2 L11.5 6" fill="none" stroke="currentColor" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                )}
              </span>
            )}
          </Cell>
        ))}
      </Row>
    );

    return focus === "wave"
      ? <>{waveBarRow}{periodRow}{waveDirRow}{swellRow}{windCompactRow}{weatherRow}{tempRow}{timeRow}</>
      : <>{windRow}{dirRow}{waveIconRow}{weatherRow}{tempRow}{timeRow}</>;
  }, [slots, waveMax, precipMax, units.wave, units.temp, windUnit, windMax, barH, windBandH, focus]);

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
        onScroll={(e) => {
          const hidden = e.currentTarget.scrollLeft > 8;
          if (hidden !== labelsHidden) setLabelsHidden(hidden);
        }}
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
        <div className="flex w-max gap-1">
          <RowLabels windBandH={windBandH} hidden={labelsHidden} focus={focus} />

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
          {/* Day anchors for scroll-to-day (ForecastDayStrip → scrollMeteogramToDay). */}
          {model.dayGroups.map((group) => (
            <span
              key={group.date}
              data-forecast-day={group.date}
              // The first day is the strip's start; it needs no snap point.
              data-snap={group.start > 0 ? "" : undefined}
              className="pointer-events-none absolute top-0 h-px w-px"
              style={{ left: group.start * COL_W }}
              aria-hidden="true"
            />
          ))}

          {/* Data rows — wrapped in a positioned layer so they paint over the
              raster behind them. */}
          {/* A switch of focus fades the new rows in where they stand; the
              strip keeps its scroll position. */}
          <div key={focus} className="swd-view-in relative">
            {rows}
          </div>

          {/* Selection highlight — a soft column of light on top, no separators. */}
          {/* It glides to the new hour (150 ms) rather than jumping, so a tap
              on a day above or a drag reads as one movement. */}
          {selectedIndex >= 0 && (
            <div
              className="pointer-events-none absolute top-0 bottom-0 left-0 rounded bg-ink/[0.06] transition-transform duration-fast ease-brand motion-reduce:transition-none"
              style={{ width: COL_W, transform: `translateX(${selectedIndex * COL_W}px)` }}
              aria-hidden
            />
          )}
          </div>
        </div>
      </div>


      {/* Screen-reader summary of the current selection. The big reading under
          the meteogram (Heute) shows the same hour for the eye. */}
      <p className="sr-only" aria-live="polite">
        {selectedSlot
          ? `Ausgewählt ${selectedSlot.localDate} ${selectedSlot.localTime}: ${selectedSlot.air == null ? "Temperatur unbekannt" : `${Math.round(selectedSlot.air)} Grad`}, Wind ${selectedSlot.wind == null ? "unbekannt" : `${formatWind(selectedSlot.wind, windUnit)} ${windUnitLabel(windUnit)}`}.`
          : ""}
      </p>
    </div>
  );
}

// Row labels (2026-11-25): symbols only, in a narrow column that stays at
// the left edge while the strip scrolls underneath, so the data gets nearly
// the full width. The word stays for screen readers.
function RowLabels({ windBandH, hidden = false, focus = "wind" }: { windBandH: number; hidden?: boolean; focus?: DatenFocus }) {
  return (
    <div
      className={`pointer-events-none sticky left-0 z-10 w-6 shrink-0 select-none text-muted transition-[opacity,background-color] duration-base ease-brand motion-reduce:transition-none ${
        hidden ? "bg-transparent opacity-0" : "bg-page opacity-100"
      }`}
    >
      {focus === "wave" ? (
        <>
          <RowLabel h={windBandH - WAVE_BAND_TRIM} align="center" label="Welle" icon={<LabelWave />} />
          <RowLabel h={PERIOD_ROW_H} align="center" label="Periode" icon={<LabelPeriod />} />
          <RowLabel h={WAVE_DIR_ROW_H} align="end" label="Wellenrichtung" icon={<LabelCompass />} />
          <RowLabel h={SWELL_ROW_H} align="center" label="1. Dünung" icon={<LabelSwell />} />
          <RowLabel h={SWELL_ROW_H} align="center" label="Wind" icon={<LabelWind />} />
        </>
      ) : (
        <>
          <RowLabel h={windBandH} align="center" label="Wind" icon={<LabelWind />} />
          <RowLabel h={RICHT_ROW_H} align="end" label="Richt" icon={<LabelCompass />} />
          <RowLabel h={WAVE_ICON_ROW_H} align="end" label="Welle" icon={<LabelWave />} />
        </>
      )}
      <RowLabel h={WETTER_ROW_H} align="center" label="Wetter" icon={<LabelWeather />} />
      <RowLabel h={TEMP_ROW_H} align="center" label="Temp" icon={<LabelThermo />} />
      <RowLabel h={ZEIT_ROW_H} align="end" label="Zeit" icon={<LabelClock />} />
    </div>
  );
}

function RowLabel({ icon, label, h, align = "center" }: { icon: React.ReactNode; label: string; h: number; align?: "start" | "center" | "end" }) {
  const items = align === "start" ? "items-start" : align === "end" ? "items-end" : "items-center";
  return (
    <div className={`flex pl-1 ${items}`} style={{ height: h }}>
      {icon}
      <span data-meteogram-row-label className="sr-only text-micro">{label}</span>
    </div>
  );
}

/**
 * Loading placeholder in the meteogram's final size (chosen 2026-11-25,
 * "Platzhalter in Endgröße"): the same label column and the same row
 * heights, so the chart replaces it without moving anything below.
 */
export function MeteoChartSkeleton() {
  const barH = useMeteogramWindHeight();
  const windBandH = METEOGRAM_WIND_HEADROOM + METEOGRAM_WIND_BASE_HEIGHT + barH;
  const cols = 40;
  const windH = (i: number) => 0.25 + (((i * 5) % 7) / 7) * 0.6;
  return (
    <div className="flex min-w-0 gap-1 overflow-hidden pb-1" role="status" aria-label="Meteogramm wird geladen">
      <RowLabels windBandH={windBandH} />
      <div className="flex animate-pulse motion-reduce:animate-none" aria-hidden="true">
        {Array.from({ length: cols }).map((_, i) => (
          <div key={i} className="flex flex-col items-center" style={{ width: COL_W }}>
            <div className="flex w-full items-end justify-center" style={{ height: windBandH }}>
              <span className="w-[22px] rounded-t-[3px] bg-line" style={{ height: windH(i) * barH }} />
            </div>
            <div style={{ height: RICHT_ROW_H }} />
            <div className="flex items-end pb-1" style={{ height: WAVE_ICON_ROW_H }}>
              <span className="h-2 w-3.5 rounded-full bg-line-soft" />
            </div>
            <div className="flex items-start" style={{ height: WETTER_ROW_H, paddingTop: WELLE_WETTER_GAP }}>
              <span className="size-5 rounded-full bg-line-soft" />
            </div>
            <div style={{ height: TEMP_ROW_H + ZEIT_ROW_H }} />
          </div>
        ))}
      </div>
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
      <path d={WAVE_PATH} />
    </svg>
  );
}

function LabelPeriod() {
  return (
    <svg {...ICON} aria-hidden>
      <path d="M3 11c2.5-6 5.5-6 9 0s6.5 6 9 0" />
      <path d="M3 19h18M3 17v4M21 17v4" />
    </svg>
  );
}

function LabelSwell() {
  return (
    <svg {...ICON} aria-hidden>
      <path d="M2 15c3 0 3-6 7-6s4 6 7 6 3-3 6-3" />
      <path d="M2 20h20" />
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
