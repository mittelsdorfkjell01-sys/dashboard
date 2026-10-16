import { useMemo } from "react";
import { Link } from "react-router-dom";
import MeteogramWindBar, {
  METEOGRAM_COLUMN_WIDTH,
  METEOGRAM_WIND_BASE_HEIGHT,
  METEOGRAM_WIND_HEADROOM,
  useMeteogramWindHeight,
} from "../../components/forecast/MeteogramWindBar";
import { CloseIcon } from "../../lib/icons";
import { tempValue, waveValue, windValue, WAVE_UNIT_SUFFIX, WIND_UNIT_SUFFIX, type TempUnit, type WaveUnit, type WindUnit } from "../../lib/units";
import { dayRuns, type MapForecastSlot } from "./slots";
// The sheet borrows the spot Daten page's dark instrument palette by class, so
// the wind bars, captions and values read exactly as they do in the Spot-Daten
// forecast instead of being a second, slightly different dark.
import "../../components/data/daten/daten-theme.css";

const WEEKDAY = new Intl.DateTimeFormat("de-DE", { weekday: "short" });
const LONG_WEEKDAY = new Intl.DateTimeFormat("de-DE", { weekday: "long" });

const COL_W = METEOGRAM_COLUMN_WIDTH;
const TEMP_ROW_H = 24;

/**
 * The map's one panel: a quiet dark sheet docked at the bottom edge, opened by
 * tapping the map — open water (a coordinate) or a spot dot. It is a forecast
 * and nothing else: a caption line saying WHERE, one fine line saying what the
 * selected hour holds, and the hourly wind bars.
 *
 * Wind uses the same full-size bar primitive and geometry as the Spot-Daten
 * meteogram, including its values inside the wind and gust bands.
 */
export default function MapForecastSheet({
  title,
  titleHref,
  meta,
  slots,
  selectedUtcKey,
  onSelect,
  onClose,
  loading = false,
  windUnit,
  tempUnit,
  waveUnit,
  product = "wind",
}: {
  /** Where this forecast is for — a spot name, or the tapped coordinate. */
  title: string;
  /** Spots link on to their own page; a coordinate has nowhere to go. */
  titleHref?: string;
  /** Second, quieter line: the spot's region, or the coordinate's model. */
  meta?: string;
  slots: MapForecastSlot[];
  selectedUtcKey: string | null;
  onSelect: (utcKey: string) => void;
  onClose: () => void;
  loading?: boolean;
  windUnit: WindUnit;
  tempUnit: TempUnit;
  waveUnit: WaveUnit;
  product?: "wind" | "waves";
}) {
  const runs = useMemo(() => dayRuns(slots), [slots]);
  const selected = useMemo(
    () => slots.find((slot) => slot.utcKey === selectedUtcKey) ?? null,
    [slots, selectedUtcKey],
  );
  const windHeight = useMeteogramWindHeight();
  const windMaximum = useMemo(() => Math.max(
    5,
    ...slots.flatMap((slot) => [slot.wind ?? 0, slot.gust ?? 0]),
  ), [slots]);

  return (
    <aside className="swd-wx-sheet daten-dark" aria-label={`Vorhersage ${title}`}>
      <div className="flex items-start gap-3 px-3 pt-2.5">
        <div className="min-w-0 flex-1">
          <p className="truncate text-caption font-medium text-ink">
            {titleHref
              ? <Link to={titleHref} className="underline decoration-line underline-offset-2 hover:decoration-ink">{title}</Link>
              : title}
          </p>
          {/* Selected hour, in one fine line — the only numbers spelled out. */}
          <p className="mt-0.5 truncate text-micro tabular-nums text-muted" role="status">
            {loading && !slots.length
              ? "Vorhersage wird geladen …"
              : selected
                ? <>
                    <span className="text-ink-soft">{WEEKDAY.format(new Date(selected.utcKey)).replace(".", "")} {selected.localTime}</span>
                    {selected.wind != null && <> · {windValue(selected.wind, windUnit)} {WIND_UNIT_SUFFIX[windUnit]}</>}
                    {selected.gust != null && <> · Böen {windValue(selected.gust, windUnit)}</>}
                    {selected.air != null && <> · {tempValue(selected.air, tempUnit)}°</>}
                    {selected.swell != null && <> · Welle {waveValue(selected.swell, waveUnit)} {WAVE_UNIT_SUFFIX[waveUnit]}</>}
                    {selected.period != null && <> · {selected.period.toFixed(1).replace(".", ",")} s</>}
                    {selected.swellDirection != null && <> · aus {Math.round(selected.swellDirection)}°</>}
                    {meta && <> · {meta}</>}
                  </>
                : "Keine Vorhersage für diesen Punkt"}
          </p>
        </div>
        <button
          type="button"
          aria-label="Vorhersage schließen"
          onClick={onClose}
          className="-mr-1 -mt-0.5 grid h-7 w-7 shrink-0 place-items-center rounded-card text-muted transition-colors hover:text-ink focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal"
        >
          <CloseIcon className="text-caption" />
        </button>
      </div>

      {slots.length > 0 && (
        <div
          className="overflow-x-auto px-3 pb-1.5 pt-1 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
          role="group"
          aria-label="Stundenvorhersage — Stunde wählen"
        >
          <div className="w-max">
            {product === "wind"
              ? <MapWindBars
                  slots={slots}
                  selectedUtcKey={selectedUtcKey}
                  onSelect={onSelect}
                  windUnit={windUnit}
                  tempUnit={tempUnit}
                  maximum={windMaximum}
                  proportionalHeight={windHeight}
                />
              : <WaveForecastBars slots={slots} selectedUtcKey={selectedUtcKey} onSelect={onSelect} waveUnit={waveUnit} />}
            {/* Time belongs to each column; the full weekday sits directly
                underneath its run instead of floating above the forecast. */}
            <div className="mt-1 flex" aria-hidden="true">
              {runs.map((run) => (
                <span
                  key={run.date}
                  className="shrink-0 truncate text-center text-micro leading-none text-muted"
                  style={{ width: run.count * COL_W }}
                >
                  {LONG_WEEKDAY.format(new Date(`${run.date}T12:00:00`))}
                </span>
              ))}
            </div>
          </div>
        </div>
      )}
    </aside>
  );
}

function MapWindBars({
  slots,
  selectedUtcKey,
  onSelect,
  windUnit,
  tempUnit,
  maximum,
  proportionalHeight,
}: {
  slots: MapForecastSlot[];
  selectedUtcKey: string | null;
  onSelect: (utcKey: string) => void;
  windUnit: WindUnit;
  tempUnit: TempUnit;
  maximum: number;
  proportionalHeight: number;
}) {
  return (
    <div className="flex w-max items-end">
      {slots.map((slot) => {
        const selected = slot.utcKey === selectedUtcKey;
        return (
          <button
            key={slot.utcKey}
            type="button"
            aria-pressed={selected}
            aria-label={`${slot.localTime} Uhr${slot.wind == null ? "" : ` — Wind ${windValue(slot.wind, windUnit)} ${WIND_UNIT_SUFFIX[windUnit]}${slot.gust == null ? "" : `, Böen ${windValue(slot.gust, windUnit)}`}`}`}
            onClick={() => onSelect(slot.utcKey)}
            className={`flex shrink-0 flex-col items-center rounded-card ${selected ? "bg-white/10" : ""} focus-visible:outline focus-visible:outline-2 focus-visible:outline-teal`}
            style={{ width: COL_W }}
          >
            <span className="flex items-center justify-center font-semibold tabular-nums leading-none" style={{ height: TEMP_ROW_H, fontSize: 11 }}>
              {slot.air == null ? "" : `${tempValue(slot.air, tempUnit)}°`}
            </span>
            <span className="flex items-end" style={{ height: METEOGRAM_WIND_BASE_HEIGHT + proportionalHeight + METEOGRAM_WIND_HEADROOM, paddingTop: METEOGRAM_WIND_HEADROOM }}>
              {slot.wind != null && <MeteogramWindBar wind={slot.wind} gust={slot.gust} maximum={maximum} windUnit={windUnit} proportionalHeight={proportionalHeight} />}
            </span>
            <span className="mt-1 leading-none tabular-nums text-on-photo-muted text-micro" style={{ height: 10 }}>
              {slot.localHour % 2 === 0 ? slot.localTime.slice(0, 2) : ""}
            </span>
          </button>
        );
      })}
    </div>
  );
}

function WaveForecastBars({
  slots,
  selectedUtcKey,
  onSelect,
  waveUnit,
}: {
  slots: MapForecastSlot[];
  selectedUtcKey: string | null;
  onSelect: (utcKey: string) => void;
  waveUnit: WaveUnit;
}) {
  const maximum = Math.max(0.5, ...slots.map((slot) => slot.swell ?? 0));
  return (
    <div className="flex w-max items-end">
      {slots.map((slot) => {
        const height = slot.swell == null ? 0 : Math.max(3, (slot.swell / maximum) * 31);
        const selected = slot.utcKey === selectedUtcKey;
        return (
          <button
            key={slot.utcKey}
            type="button"
            aria-pressed={selected}
            aria-label={`${slot.localTime} Uhr${slot.swell == null ? "" : ` — ${waveValue(slot.swell, waveUnit)} ${WAVE_UNIT_SUFFIX[waveUnit]}`}`}
            onClick={() => onSelect(slot.utcKey)}
            className={`flex shrink-0 flex-col items-center rounded-card ${selected ? "bg-white/10" : ""} focus-visible:outline focus-visible:outline-2 focus-visible:outline-teal`}
            style={{ width: COL_W }}
          >
            <span className="mb-0.5 leading-none tabular-nums text-on-photo-muted text-micro" style={{ height: 10 }}>
              {slot.swell == null ? "" : waveValue(slot.swell, waveUnit)}
            </span>
            <span className="flex items-end" style={{ height: 31 }}>
              {slot.swell != null && <span className="w-2.5 rounded-card bg-teal" style={{ height }} />}
            </span>
            <span className="mt-1 leading-none tabular-nums text-on-photo-muted text-micro" style={{ height: 10 }}>
              {slot.localHour % 2 === 0 ? slot.localTime.slice(0, 2) : ""}
            </span>
          </button>
        );
      })}
    </div>
  );
}
