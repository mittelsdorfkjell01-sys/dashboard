import { useEffect, useMemo, useRef, useState } from "react";
import { useReducedMotion } from "framer-motion";
import type { ForecastSeries } from "../lib/api";
import type { DayDetail } from "../lib/types";
import { forecastToBlocks, forecastToDetailBlocks, forecastToHourly } from "../lib/seasonView";
import { usePersistedState } from "../lib/hooks";
import { sunTimes } from "../lib/sunTimes";
import { windColor } from "../lib/windScale";
import { degToCompass } from "./WindRose";
import WindArrow from "./WindArrow";
import WindScaleLegend from "./WindScaleLegend";
import HourTable from "./HourTable";

type WindUnit = "kts" | "ms" | "kmh";
const WIND_ORDER: WindUnit[] = ["kts", "ms", "kmh"];
const WIND_FACTOR: Record<WindUnit, number> = { kts: 1, ms: 0.514444, kmh: 1.852 };
const WIND_SHORT: Record<WindUnit, string> = { kts: "kts", ms: "m/s", kmh: "km/h" };

const L2_W = 640;
const L2_H = 120;
const L2_PAD_TOP = 12;
const L2_PAD_BOTTOM = 10;

/** One day's collapsible detail graph (Ebene 2): 8 average-wind bars with a
 *  dashed gust curve over them (one shared scale — no second y-axis), a
 *  15kt reference line, daylight shading at the edges, and direction arrows
 *  below the axis. Wave/period/air only ever appear as the text row above —
 *  never plotted. */
function DayDetailChart({
  day,
  date,
  coords,
  convert,
  windUnit,
  scrollRef,
}: {
  day: DayDetail;
  date?: string;
  coords?: [number, number];
  convert: (kts: number) => number;
  windUnit: string;
  scrollRef: (el: HTMLDivElement | null) => void;
}) {
  const n = day.blocks.length;
  const colW = L2_W / n;
  const barW = colW * 0.5;

  const windVals = day.blocks.map((b) => b.windAvg).filter((v): v is number => v != null);
  const gustVals = day.blocks.map((b) => b.gustMax).filter((v): v is number => v != null);
  const vMax = Math.max(15, 1, ...windVals, ...gustVals);
  const y = (v: number) => L2_PAD_TOP + (1 - v / vMax) * (L2_H - L2_PAD_TOP - L2_PAD_BOTTOM);

  const gustPoints = day.blocks
    .map((b, i) => (b.gustMax == null ? null : { x: colW * i + colW / 2, y: y(b.gustMax) }))
    .filter((p): p is { x: number; y: number } => p != null);
  const gustPath = gustPoints.map((p, i) => `${i === 0 ? "M" : "L"} ${p.x} ${p.y}`).join(" ");

  const parsedDate = date ? new Date(date) : null;
  const sun =
    coords && parsedDate && !Number.isNaN(parsedDate.getTime())
      ? sunTimes(coords[0], coords[1], parsedDate)
      : null;
  const hourToX = (h: number) => Math.max(0, Math.min(L2_W, ((h - 6) / 16) * L2_W));

  return (
    <div ref={scrollRef} className="scroll-mt-24 border-t border-line pt-4">
      <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
        <span className="text-body font-semibold text-ink">
          {day.day} {day.date}
        </span>
        <span className="text-caption text-muted">
          {day.waveHeight != null ? day.waveHeight.toFixed(1) : "—"} m Welle
        </span>
        <span className="text-caption text-muted">
          {day.wavePeriod != null ? day.wavePeriod : "—"} s Periode
        </span>
        <span className="text-caption text-muted">
          {day.airTemp != null ? Math.round(day.airTemp) : "—"}° Luft
        </span>
      </div>

      <svg viewBox={`0 0 ${L2_W} ${L2_H}`} width="100%" className="mt-3 block overflow-visible" aria-hidden="true">
        {sun && sun.sunrise > 6 && <rect x={0} y={0} width={hourToX(sun.sunrise)} height={L2_H} fill="rgba(36,28,23,0.06)" />}
        {sun && sun.sunset < 22 && (
          <rect x={hourToX(sun.sunset)} y={0} width={L2_W - hourToX(sun.sunset)} height={L2_H} fill="rgba(36,28,23,0.06)" />
        )}

        <line x1={0} y1={y(15)} x2={L2_W} y2={y(15)} stroke="rgba(107,119,135,0.4)" strokeWidth={1} strokeDasharray="3 3" />

        {day.blocks.map((b, i) => {
          const v = b.windAvg;
          const barTop = v == null ? L2_H - L2_PAD_BOTTOM - 2 : y(v);
          const barH = Math.max(2, L2_H - L2_PAD_BOTTOM - barTop);
          return (
            <rect key={i} x={colW * i + (colW - barW) / 2} y={barTop} width={barW} height={barH} rx={2} fill={windColor(v)}>
              <title>
                {`${b.label} Uhr — Ø ${v != null ? convert(v) : "—"} ${windUnit}, Böen ${
                  b.gustMax != null ? convert(b.gustMax) : "—"
                } ${windUnit}`}
              </title>
            </rect>
          );
        })}

        {gustPoints.length > 1 && (
          <path d={gustPath} fill="none" stroke="#241C17" strokeWidth={1.5} strokeDasharray="4 3" strokeLinecap="round" />
        )}
      </svg>

      <div className="mt-1 grid" style={{ gridTemplateColumns: `repeat(${n}, minmax(0,1fr))` }}>
        {day.blocks.map((b, i) => (
          <div key={i} className="flex flex-col items-center gap-1">
            {b.dir != null ? (
              <WindArrow dir={b.dir} size={14} className="text-muted" />
            ) : (
              <span className="text-caption text-line">—</span>
            )}
            <span className="text-caption text-muted">{b.label}</span>
          </div>
        ))}
      </div>

      <p className="mt-2 text-caption text-muted">
        Balken = Ø Wind ({windUnit}) · gestrichelte Linie = Böen · dünne Linie = 15 kt Referenz
      </p>
    </div>
  );
}

/**
 * Two-layer forecast: an always-visible weekly overview (5 three-hour blocks
 * per day, each showing its *best* hour — the point is "when's the peak
 * window today", not a smoothed average), and a collapsible per-day detail
 * graph (8 two-hour blocks, an honest average, plus a gust curve, daylight
 * shading and direction arrows). Headless: the section heading lives in the
 * caller's `SectionBand`.
 */
export default function Forecast({ forecast, coords }: { forecast: ForecastSeries; coords?: [number, number] }) {
  const [wu, setWu] = usePersistedState<WindUnit>("swd.forecastWindUnit", "kts");
  const reduce = useReducedMotion();
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [pendingScrollTo, setPendingScrollTo] = useState<number | null>(null);
  const dayRefs = useRef<(HTMLDivElement | null)[]>([]);

  const blocks = useMemo(() => forecastToBlocks(forecast), [forecast]);
  const detailBlocks = useMemo(() => forecastToDetailBlocks(forecast), [forecast]);
  const hourlyRows = useMemo(() => forecastToHourly(forecast), [forecast]);

  const convert = (kts: number) => Math.round(kts * WIND_FACTOR[wu]);
  const windUnit = WIND_SHORT[wu];
  const weekMaxKts = Math.max(1, ...blocks.flatMap((d) => d.blocks.map((b) => b.wind ?? 0)));

  const openDetailsAndScrollTo = (i: number) => {
    setDetailsOpen(true);
    setPendingScrollTo(i);
  };

  useEffect(() => {
    if (pendingScrollTo == null || !detailsOpen) return;
    dayRefs.current[pendingScrollTo]?.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "center" });
    setPendingScrollTo(null);
  }, [pendingScrollTo, detailsOpen, reduce]);

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <p className="text-caption text-muted">Beste Stunde je 3-Stunden-Block</p>
        <div className="inline-flex rounded-full bg-ink/5 p-1">
          {WIND_ORDER.map((u) => (
            <button
              key={u}
              type="button"
              onClick={() => setWu(u)}
              aria-pressed={u === wu}
              className={`flex min-h-[44px] min-w-[44px] items-center justify-center rounded-2xl px-3 text-label font-medium transition-colors ${
                u === wu ? "bg-white text-teal" : "text-muted hover:text-teal"
              }`}
            >
              {WIND_SHORT[u]}
            </button>
          ))}
        </div>
      </div>

      {/* Screen-reader alternative for the Wochenüberblick's bars (Stundentabelle
          below is itself a real table — it doesn't need a second sr-only shadow). */}
      <table className="sr-only">
        <caption>Wind- und Wellenvorhersage, 7 Tage, je 2-Stunden-Fenster</caption>
        <thead>
          <tr>
            <th scope="col">Tag</th>
            <th scope="col">Zeitfenster</th>
            <th scope="col">Ø Wind ({windUnit})</th>
            <th scope="col">Böen ({windUnit})</th>
            <th scope="col">Richtung</th>
            <th scope="col">Welle (m)</th>
            <th scope="col">Periode (s)</th>
            <th scope="col">Luft (°C)</th>
          </tr>
        </thead>
        <tbody>
          {detailBlocks.map((d) =>
            d.blocks.map((b, i) => (
              <tr key={`${d.day}-${d.date}-${i}`}>
                <td>
                  {d.day} {d.date}
                </td>
                <td>{b.label} Uhr</td>
                <td>{b.windAvg != null ? convert(b.windAvg) : "—"}</td>
                <td>{b.gustMax != null ? convert(b.gustMax) : "—"}</td>
                <td>{b.dir != null ? degToCompass(b.dir) : "—"}</td>
                <td>{d.waveHeight != null ? d.waveHeight.toFixed(1) : "—"}</td>
                <td>{d.wavePeriod ?? "—"}</td>
                <td>{d.airTemp != null ? Math.round(d.airTemp) : "—"}</td>
              </tr>
            ))
          )}
        </tbody>
      </table>

      {/* Ebene 1 — Wochenüberblick, always visible */}
      <div className="min-w-0 max-w-full overflow-x-auto no-scrollbar snap-x-mandatory">
        <div className="grid grid-flow-col auto-cols-[minmax(112px,1fr)] divide-x divide-line">
          {blocks.map((d, i) => (
            <button
              key={`${d.day}-${d.date}`}
              type="button"
              onClick={() => openDetailsAndScrollTo(i)}
              aria-label={`Details für ${d.day} ${d.date} anzeigen`}
              className="flex snap-start flex-col items-center gap-2 px-3 py-3 text-center"
            >
              <div>
                <div className="text-caption font-semibold text-ink">{d.day}</div>
                <div className="text-caption text-muted">{d.date}</div>
              </div>
              <div aria-hidden="true" className="flex h-20 items-end gap-1">
                {d.blocks.map((b, j) => {
                  const pct = b.wind == null ? 4 : Math.max(6, (b.wind / weekMaxKts) * 100);
                  return (
                    <div key={j} className="flex h-full w-3 flex-col justify-end" title={`${b.label} Uhr`}>
                      <div className="w-full rounded-t-[3px]" style={{ height: `${pct}%`, backgroundColor: windColor(b.wind) }} />
                    </div>
                  );
                })}
              </div>
              <div className="flex flex-col items-center gap-1 border-t border-line pt-2">
                {d.windDir != null ? (
                  <WindArrow dir={d.windDir} size={16} className="text-ink-soft" />
                ) : (
                  <span className="text-line" aria-hidden="true">
                    —
                  </span>
                )}
                <span className="text-body font-semibold tabular-nums text-ink">
                  {d.maxWind != null ? convert(d.maxWind) : "—"}
                </span>
              </div>
            </button>
          ))}
        </div>
      </div>

      <div className="mt-3">
        <WindScaleLegend />
      </div>

      {/* Stundentabelle — the central view, directly below the week overview */}
      <div className="mt-8">
        <HourTable days={hourlyRows} coords={coords} convert={convert} windUnit={windUnit} />
      </div>

      <div className="mt-6 flex justify-center">
        <button
          type="button"
          onClick={() => setDetailsOpen((v) => !v)}
          aria-expanded={detailsOpen}
          className="rounded-2xl border border-teal/30 px-5 py-2 text-label font-medium text-teal transition-colors hover:bg-teal/5"
        >
          {detailsOpen ? "Details ausblenden" : "Details anzeigen"}
        </button>
      </div>

      {/* Ebene 2 — Tagesdetails, aufklappbar */}
      {detailsOpen && (
        <div className="mt-6 space-y-6">
          {detailBlocks.map((d, i) => (
            <DayDetailChart
              key={`${d.day}-${d.date}`}
              day={d}
              date={forecast.days[i]?.date}
              coords={coords}
              convert={convert}
              windUnit={windUnit}
              scrollRef={(el) => {
                dayRefs.current[i] = el;
              }}
            />
          ))}
        </div>
      )}
    </div>
  );
}
