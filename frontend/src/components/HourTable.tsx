import { useMemo, useState } from "react";
import type { DayHours, HourRow } from "../lib/types";
import { sunTimes } from "../lib/sunTimes";
import { windColor } from "../lib/windScale";
import WindArrow from "./WindArrow";

type RowKey = "wind" | "gust" | "dir" | "wave" | "swellDir" | "period" | "air" | "water" | "precip";

const ROWS: { key: RowKey; label: string; core: boolean }[] = [
  { key: "wind", label: "Windgeschwindigkeit", core: true },
  { key: "gust", label: "Böen", core: true },
  { key: "dir", label: "Windrichtung", core: true },
  { key: "wave", label: "Wellenhöhe", core: true },
  { key: "swellDir", label: "Swell-Richtung", core: false },
  { key: "period", label: "Swell-Periode", core: false },
  { key: "air", label: "Lufttemperatur", core: false },
  { key: "water", label: "Wassertemperatur", core: false },
  { key: "precip", label: "Niederschlag", core: false },
];

type FlatHour = HourRow & {
  day: string;
  isDayStart: boolean;
  /** Position within its own day's hour list — mobile shows every 3rd of
   *  these (always including index 0, so a day's label column never hides). */
  indexInDay: number;
  isNight: boolean;
};

/** Every hour a bar chart needs is already visible as a colored, scaled bar
 *  — that height *is* the second signal alongside the color (Sprint 2's
 *  "never color alone" rule), so no printed number is needed per cell here. */
function BarCell({ value, max, color }: { value: number | null; max: number; color: string }) {
  if (value == null) return <span className="text-data-value text-line">—</span>;
  const pct = Math.max(4, Math.min(100, (value / max) * 100));
  return (
    <div className="flex h-8 w-full items-end justify-center" title={`${value}`}>
      <div className="w-2.5 rounded-t-[2px]" style={{ height: `${pct}%`, backgroundColor: color }} />
    </div>
  );
}

function NumberCell({ value, decimals = 0, suffix = "" }: { value: number | null; decimals?: number; suffix?: string }) {
  return (
    <span className="text-data-value tabular-nums text-muted">
      {value != null ? `${value.toFixed(decimals)}${suffix}` : "—"}
    </span>
  );
}

function ArrowCell({ dir }: { dir: number | null }) {
  if (dir == null) return <span className="text-data-value text-line">—</span>;
  return (
    <div className="flex justify-center">
      <WindArrow dir={dir} size={14} className="text-muted" />
    </div>
  );
}

/**
 * Die Stundentabelle — the Daten tab's central view. A continuous hour-by-hour
 * grid across all 7 days, 9 rows, horizontally scrollable with the label
 * column pinned. No radius, no shadow, no card — hairlines and spacing only,
 * matching the tab's own visual language (see `DatenSection`).
 *
 * Desktop shows every hour and all 9 rows. Mobile samples every 3rd hour
 * (index 0 of each day always included, so a day's label never disappears)
 * and only the four rows that decide whether to go at all (wind/gust/
 * direction/wave); the rest sit behind "Mehr Zeilen".
 */
export default function HourTable({
  days,
  coords,
  convert,
  windUnit,
}: {
  days: DayHours[];
  coords?: [number, number];
  convert: (kts: number) => number;
  windUnit: string;
}) {
  const [showAllRows, setShowAllRows] = useState(false);

  const flat: FlatHour[] = useMemo(() => {
    return days.flatMap((d) => {
      const parsed = new Date(d.isoDate);
      const sun =
        coords && !Number.isNaN(parsed.getTime()) ? sunTimes(coords[0], coords[1], parsed) : null;
      return d.hours.map((h, i) => ({
        ...h,
        day: d.day,
        isDayStart: i === 0,
        indexInDay: i,
        isNight: sun ? h.hour < sun.sunrise || h.hour >= sun.sunset : false,
      }));
    });
  }, [days, coords]);

  if (flat.length === 0) return null;

  const windMax = Math.max(20, ...flat.map((h) => h.wind ?? 0), ...flat.map((h) => h.gust ?? 0));
  const precipMax = Math.max(1, ...flat.map((h) => h.precip ?? 0));

  const cellClass = (h: FlatHour) =>
    `border-line px-2 py-1.5 text-center ${h.isDayStart ? "border-l-2 border-l-ink/25" : ""} ${
      h.indexInDay % 3 !== 0 ? "hidden sm:table-cell" : ""
    } ${h.isNight ? "bg-ink/[0.03]" : ""}`;

  const rowClass = (core: boolean) => (!core && !showAllRows ? "hidden sm:table-row" : "");

  return (
    <div>
      <div className="overflow-x-auto">
        <table className="w-full border-collapse">
          <caption className="sr-only">
            Stundenvorhersage, 7 Tage, stündlich: Wind, Böen, Windrichtung, Wellenhöhe, Swell-Richtung,
            Swell-Periode, Lufttemperatur, Wassertemperatur, Niederschlag
          </caption>
          <thead>
            <tr className="bg-white">
              <th scope="col" className="sticky left-0 z-20 bg-white px-2 py-1.5 text-left" />
              {flat.map((h, i) => (
                <th
                  key={`day-${i}`}
                  scope="col"
                  className={`whitespace-nowrap px-2 py-1.5 text-left text-data-label uppercase text-muted ${
                    h.isDayStart ? "border-l-2 border-l-ink/25" : ""
                  } ${h.indexInDay % 3 !== 0 ? "hidden sm:table-cell" : ""}`}
                >
                  {h.isDayStart ? h.day : " "}
                </th>
              ))}
            </tr>
            <tr className="bg-white">
              <th scope="col" className="sticky left-0 z-20 bg-white px-2 py-1.5 text-left" />
              {flat.map((h, i) => (
                <th key={`hr-${i}`} scope="col" className={cellClass(h)}>
                  <span className="text-data-caption tabular-nums text-muted">{h.time.slice(0, 2)}</span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {ROWS.map((row) => (
              <tr key={row.key} className={`border-t border-line ${rowClass(row.core)}`}>
                <th
                  scope="row"
                  className="sticky left-0 z-10 whitespace-nowrap bg-white px-2 py-1.5 text-left text-data-label uppercase text-muted"
                >
                  {row.label}
                </th>
                {flat.map((h, i) => (
                  <td key={i} className={cellClass(h)}>
                    {row.key === "wind" && <BarCell value={h.wind} max={windMax} color={windColor(h.wind)} />}
                    {row.key === "gust" && <NumberCell value={h.gust != null ? convert(h.gust) : null} />}
                    {row.key === "dir" && <ArrowCell dir={h.dir} />}
                    {row.key === "wave" && <NumberCell value={h.waveHeight} decimals={1} suffix=" m" />}
                    {row.key === "swellDir" && <ArrowCell dir={h.swellDir} />}
                    {row.key === "period" && <NumberCell value={h.period} suffix=" s" />}
                    {row.key === "air" && <NumberCell value={h.air} suffix="°" />}
                    {row.key === "water" && <NumberCell value={h.water} suffix="°" />}
                    {row.key === "precip" && (
                      <BarCell value={h.precip} max={precipMax} color="#3F7F9B" />
                    )}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <p className="mt-2 text-data-caption text-muted">
        Wind in {windUnit} · getönte Spalten = Nacht (vor Sonnenauf- bzw. nach Sonnenuntergang)
      </p>

      <div className="mt-3 sm:hidden">
        <button
          type="button"
          onClick={() => setShowAllRows((v) => !v)}
          aria-expanded={showAllRows}
          className="rounded-full border border-teal/30 px-4 py-2 text-label font-medium text-teal transition-colors hover:bg-teal/5"
        >
          {showAllRows ? "Weniger Zeilen" : "Mehr Zeilen"}
        </button>
      </div>
    </div>
  );
}
