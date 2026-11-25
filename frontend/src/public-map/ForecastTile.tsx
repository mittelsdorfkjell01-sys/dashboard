import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { ChevronRightIcon, CloseIcon, WaveIcon, WindIcon } from "../lib/icons";
import { windValue, waveValue, type WaveUnit, type WindUnit } from "../lib/units";
import { directionName } from "../lib/spotConditionHints";
import { css, waveRgb, windRgb } from "./fieldColors";
import { CalmMark, TravelArrow } from "./TravelArrow";
import { CALM_KN } from "./ArrowLayer";

export const COLUMN_PX = 30;
const HOUR_MS = 3_600_000;
const WEEKDAY = new Intl.DateTimeFormat("de-DE", { weekday: "short" });
const TIME = new Intl.DateTimeFormat("de-DE", { hour: "2-digit", minute: "2-digit" });
const weekday = (at: number) => WEEKDAY.format(new Date(at)).replace(".", "");

export function timeLabel(at: number): string {
  return `${weekday(at)} ${TIME.format(new Date(at))}`;
}

/** One hour of the selected place's forecast, as the tile draws it. */
export interface TileHour {
  wind?: number | null;
  gust?: number | null;
  windFrom?: number | null;
  wave?: number | null;
  period?: number | null;
  waveFrom?: number | null;
}

// Row key for the wave layout: a wave crest over a span (the period).
function PeriodIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.7} strokeLinecap="round" aria-hidden="true" className={className}>
      <path d="M3 11c2.5-6 5.5-6 9 0s6.5 6 9 0" />
      <path d="M3 19h18M3 17v4M21 17v4" />
    </svg>
  );
}

/**
 * The bottom tile of the wind and wave map. The strip IS the clock: whatever
 * sits under the needle is the instant the map shows, continuously — the field
 * blends between published hours, so a swipe plays the wind or the sea
 * forward on the map.
 *
 * With a place selected (a spot or any tapped point, 2026-11-21 "vereinfachen,
 * nicht so viel vom Bildschirm") the forecast lives IN the strip: every hour
 * column carries its wind bar (gust behind), wind value and direction, and the
 * wave height and direction. One instrument instead of a meteogram above a
 * slider — the same on the wind and the wave map, about a third of the
 * meteogram's height, and the clock needs no second scroller to stay in sync.
 */
export default function ForecastTile({
  hours,
  value,
  nowAt,
  onChange,
  spotHref,
  spotName,
  forecast,
  loading,
  windUnit,
  waveUnit,
  place,
  source,
  onClose,
  focus = "wind",
}: {
  hours: number[];
  value?: number;
  nowAt?: number;
  onChange: (at: number, how: { scrub: boolean }) => void;
  /** With a spot selected the right end leads to its Daten tab (2026-11-20:
   *  in place of the play button). */
  spotHref?: string;
  spotName?: string;
  /** Forecast by hour (ms); undefined = no place selected → bare strip. */
  forecast?: Map<number, TileHour>;
  loading?: boolean;
  windUnit: WindUnit;
  waveUnit: WaveUnit;
  /** A tapped point's label (when no spot is selected). */
  place?: string;
  /** Model and run behind the forecast, always shown with it. */
  source?: string;
  onClose?: () => void;
  /** The wave map lays the strip out for the sea (2026-11-25, like the Daten
   *  tab's wave focus): wave bar, height, direction and period on top, the
   *  wind below as a number with its arrow. */
  focus?: "wind" | "wave";
}) {
  const strip = useRef<HTMLDivElement>(null);
  const userUntil = useRef(0);
  const frame = useRef(0);
  const first = hours[0] ?? 0;
  const last = hours[hours.length - 1] ?? 0;
  const offsetFor = (at: number) => ((at - first) / HOUR_MS) * COLUMN_PX;

  // Follow the clock (play, a tap on the map, a new selection) unless a finger
  // or wheel is on the strip right now.
  useEffect(() => {
    const element = strip.current;
    if (!element || value === undefined || performance.now() < userUntil.current) return;
    const target = offsetFor(value);
    if (Math.abs(element.scrollLeft - target) < 1) return;
    element.scrollTo({ left: target, behavior: "auto" });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value, first, Boolean(forecast)]);

  const markUser = () => { userUntil.current = performance.now() + 600; };

  // Desktop (2026-11-21, "ich kann den Forecast nicht scrollen"): a mouse
  // cannot pan an overflow strip by itself, and an ordinary wheel only scrolls
  // vertically. So: drag with the mouse, and turn a vertical wheel into time.
  // Touch keeps the browser's native pan (touch-action: pan-x).
  const drag = useRef<{ x: number; left: number; id: number } | null>(null);
  const [dragging, setDragging] = useState(false);
  useEffect(() => {
    const element = strip.current;
    if (!element) return;
    const onWheel = (event: WheelEvent) => {
      if (Math.abs(event.deltaY) <= Math.abs(event.deltaX)) { markUser(); return; }
      event.preventDefault();
      markUser();
      element.scrollLeft += event.deltaY;
    };
    element.addEventListener("wheel", onWheel, { passive: false });
    return () => element.removeEventListener("wheel", onWheel);
  }, []);
  const onPointerDown = (event: React.PointerEvent<HTMLDivElement>) => {
    markUser();
    if (event.pointerType !== "mouse" || event.button !== 0) return;
    drag.current = { x: event.clientX, left: event.currentTarget.scrollLeft, id: event.pointerId };
    event.currentTarget.setPointerCapture(event.pointerId);
    setDragging(true);
  };
  const onPointerMove = (event: React.PointerEvent<HTMLDivElement>) => {
    if (event.buttons) markUser();
    if (!drag.current || drag.current.id !== event.pointerId) return;
    event.currentTarget.scrollLeft = drag.current.left - (event.clientX - drag.current.x);
  };
  const endDrag = (event: React.PointerEvent<HTMLDivElement>) => {
    if (!drag.current || drag.current.id !== event.pointerId) return;
    drag.current = null;
    setDragging(false);
    if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId);
  };
  const onScroll = () => {
    if (performance.now() >= userUntil.current) return;
    cancelAnimationFrame(frame.current);
    frame.current = requestAnimationFrame(() => {
      const element = strip.current;
      if (!element || !hours.length) return;
      const at = Math.min(last, Math.max(first, first + (element.scrollLeft / COLUMN_PX) * HOUR_MS));
      onChange(at, { scrub: true });
    });
  };

  const scale = useMemo(() => {
    let wind = 10, wave = 1, hasWave = false;
    for (const hour of forecast?.values() ?? []) {
      wind = Math.max(wind, hour.gust ?? 0, hour.wind ?? 0);
      if (hour.wave != null) { hasWave = true; wave = Math.max(wave, hour.wave); }
    }
    return { wind, wave, hasWave };
  }, [forecast]);
  // Without any wave reading the sea layout would be empty rows.
  const waveFocus = focus === "wave" && scale.hasWave;
  const isNow = value !== undefined && nowAt !== undefined && Math.abs(value - nowAt) < 31 * 60_000;

  if (forecast) {
    return (
      <ForecastMeteogram
        hours={hours}
        value={value}
        isNow={isNow}
        onChange={onChange}
        forecast={forecast}
        loading={loading}
        windUnit={windUnit}
        waveUnit={waveUnit}
        spotHref={spotHref}
        spotName={spotName}
        place={place}
        source={source}
        onClose={onClose}
        waveFocus={waveFocus}
        scale={scale}
      />
    );
  }

  return (
    <section className="swd-pm-tile" aria-label="Zeit">
      <div className="swd-pm-tile-head">
        <p className="min-w-0 flex-1 truncate">
          {value !== undefined && <span className="font-num text-caption tabular-nums text-ink">{timeLabel(value)}</span>}
          {isNow && <span className="ml-2 text-caption text-accent">Jetzt</span>}
          {loading && <span className="ml-2 text-caption text-muted">Vorhersage lädt …</span>}
        </p>
        {!spotHref && place && <span className="swd-pm-tile-spot truncate text-caption text-ink">{place}</span>}
        {spotHref && (
          <Link to={spotHref} className="swd-pm-bar-link text-caption font-medium text-accent" aria-label={spotName ? `Zum Spot ${spotName}, Daten` : "Zum Spot, Daten"}>
            {spotName && <span className="swd-pm-tile-spot truncate text-ink">{spotName}</span>}
            <span>Zum Spot</span>
            <ChevronRightIcon className="text-ui" />
          </Link>
        )}
        {onClose && (
          <button type="button" className="swd-pm-close" aria-label="Vorhersage schließen" onClick={onClose}>
            <CloseIcon className="text-ui" />
          </button>
        )}
      </div>
      <div className="swd-pm-tile-strip-wrap">
        <div
          ref={strip}
          className={`swd-pm-tile-strip no-scrollbar${dragging ? " is-dragging" : ""}`}
          onScroll={onScroll}
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={endDrag}
          onPointerCancel={endDrag}
          onTouchMove={markUser}
          tabIndex={0}
          aria-label="Durch die Stunden wischen"
          onKeyDown={(event) => {
            if (value === undefined) return;
            if (event.key === "ArrowRight") { event.preventDefault(); onChange(Math.min(last, Math.round(value / HOUR_MS) * HOUR_MS + HOUR_MS), { scrub: false }); }
            if (event.key === "ArrowLeft") { event.preventDefault(); onChange(Math.max(first, Math.round(value / HOUR_MS) * HOUR_MS - HOUR_MS), { scrub: false }); }
          }}
        >
          <span className="swd-pm-tile-pad" />
          {hours.map((hour) => {
            const h = new Date(hour).getHours();
            const label = h === 0 ? weekday(hour) : h % 3 === 0 ? String(h).padStart(2, "0") : "";
            return (
              <span key={hour} className={`swd-pm-tile-col${h === 0 ? " is-midnight" : ""}${nowAt !== undefined && Math.abs(hour - nowAt) < 31 * 60_000 ? " is-now" : ""}`}>
                <span className={`font-num text-micro ${h === 0 ? "font-bold text-ink" : "text-muted"}`}>{label}</span>
                <span className="swd-pm-tile-tick" aria-hidden="true" />
              </span>
            );
          })}
          <span className="swd-pm-tile-pad" />
        </div>
        <span className="swd-pm-tile-needle" aria-hidden="true" />
      </div>
    </section>
  );
}

// ── Forecast as a meteogram (chosen 2026-11-25, "A · Meteogramm wie auf Daten") ──

type Row = { key: string; h: number; icon: React.ReactNode; label: string; cell: (data: TileHour | undefined, hour: number) => React.ReactNode };

/**
 * With a place selected the tile is the Daten tab's meteogram in small: row
 * symbols pinned left, one column per hour, the chosen hour tinted and its
 * readings spelled out in the head. A tap (or a mouse drag) on a column picks
 * the hour and the map follows; swiping and the wheel only page through the
 * hours. The wind map leads with the wind, the wave map with the sea (height,
 * period, direction), the other reading small underneath — the same order as
 * the Daten tab's wind and wave focus.
 */
function ForecastMeteogram({
  hours,
  value,
  isNow,
  onChange,
  forecast,
  loading,
  windUnit,
  waveUnit,
  spotHref,
  spotName,
  place,
  source,
  onClose,
  waveFocus,
  scale,
}: {
  hours: number[];
  value?: number;
  isNow: boolean;
  onChange: (at: number, how: { scrub: boolean }) => void;
  forecast: Map<number, TileHour>;
  loading?: boolean;
  windUnit: WindUnit;
  waveUnit: WaveUnit;
  spotHref?: string;
  spotName?: string;
  place?: string;
  source?: string;
  onClose?: () => void;
  waveFocus: boolean;
  scale: { wind: number; wave: number; hasWave: boolean };
}) {
  const strip = useRef<HTMLDivElement>(null);
  const cols = useRef<HTMLDivElement>(null);
  const dragging = useRef(false);
  const pointerType = useRef<string>("mouse");
  const first = hours[0] ?? 0;
  const index = value === undefined ? -1 : Math.max(0, Math.min(hours.length - 1, Math.round((value - first) / HOUR_MS)));
  const selected = index >= 0 ? forecast.get(hours[index]) : undefined;

  // Keep the chosen hour in view: on opening it sits a third in from the left;
  // later only when it would leave the visible part (play, a tap on the map).
  const placed = useRef(false);
  useEffect(() => {
    const element = strip.current;
    if (!element || index < 0) return;
    const x = index * COLUMN_PX;
    const visible = x >= element.scrollLeft + 24 && x + COLUMN_PX <= element.scrollLeft + element.clientWidth;
    if (placed.current && visible) return;
    placed.current = true;
    element.scrollTo({ left: Math.max(0, x - element.clientWidth / 3), behavior: "auto" });
  }, [index]);

  // A plain vertical wheel pages sideways (a mouse cannot pan by itself).
  useEffect(() => {
    const element = strip.current;
    if (!element) return;
    const onWheel = (event: WheelEvent) => {
      if (Math.abs(event.deltaY) <= Math.abs(event.deltaX)) return;
      event.preventDefault();
      element.scrollLeft += event.deltaY;
    };
    element.addEventListener("wheel", onWheel, { passive: false });
    return () => element.removeEventListener("wheel", onWheel);
  }, []);

  const pickAt = (clientX: number) => {
    const box = cols.current?.getBoundingClientRect();
    if (!box || !hours.length) return;
    const i = Math.max(0, Math.min(hours.length - 1, Math.floor((clientX - box.left) / COLUMN_PX)));
    if (i !== index) onChange(hours[i], { scrub: true });
  };

  const windArrow = (data?: TileHour) => data?.wind != null && data.windFrom != null
    ? (data.wind < CALM_KN ? <CalmMark size={10} className="text-muted" /> : <TravelArrow bearing={(data.windFrom + 180) % 360} size={11} className="text-ink-soft" />)
    : null;
  const waveArrow = (data?: TileHour) => data?.wave != null && data.waveFrom != null
    ? <TravelArrow bearing={(data.waveFrom + 180) % 360} size={11} className="text-ink-soft" />
    : null;
  const windBars = (data?: TileHour) => data?.wind != null && (
    <>
      {data.gust != null && data.gust > data.wind && <span className="swd-pm-tile-gust" style={{ height: 3 + (data.gust / scale.wind) * 25, background: css(windRgb(data.wind)) }} />}
      <span className="swd-pm-tile-bar" style={{ height: 3 + (data.wind / scale.wind) * 25, background: css(windRgb(data.wind)) }} />
    </>
  );
  const waveBar = (data?: TileHour) => data?.wave != null && (
    <span className="swd-pm-tile-bar" style={{ height: 3 + (data.wave / scale.wave) * 25, background: css(waveRgb(data.wave)) }} />
  );

  const windRows: Row[] = [
    { key: "wind", h: 30, icon: <WindIcon />, label: "Wind", cell: (d) => <span className="swd-pm-tile-bars">{windBars(d)}</span> },
    { key: "wind-v", h: 13, icon: null, label: "Wind in Knoten", cell: (d) => <span className="font-num text-micro font-semibold text-ink">{d?.wind != null ? windValue(d.wind, windUnit) : ""}</span> },
    { key: "wind-d", h: 14, icon: null, label: "Windrichtung", cell: (d) => windArrow(d) },
    ...(scale.hasWave ? [
      // Height over period: the same total height as the wave layout, so
      // switching Wind ↔ Wellen never resizes the tile (2026-11-25).
      { key: "wave-v", h: 28, icon: <WaveIcon />, label: "Welle", cell: (d: TileHour | undefined) => (
        <span className="flex flex-col items-center leading-none">
          <span className="font-num text-micro text-ink" style={{ height: 13 }}>{d?.wave != null ? waveValue(d.wave, waveUnit) : ""}</span>
          <span className="font-num text-micro text-muted" style={{ height: 13 }}>{d?.period != null ? `${Math.round(d.period)}s` : ""}</span>
        </span>
      ) },
      { key: "wave-d", h: 14, icon: null, label: "Wellenrichtung", cell: (d: TileHour | undefined) => waveArrow(d) },
    ] : []),
  ];
  const waveRows: Row[] = [
    { key: "wave", h: 30, icon: <WaveIcon />, label: "Welle", cell: (d) => <span className="swd-pm-tile-bars">{waveBar(d)}</span> },
    { key: "wave-v", h: 13, icon: null, label: "Wellenhöhe", cell: (d) => <span className="font-num text-micro font-semibold text-ink">{d?.wave != null ? waveValue(d.wave, waveUnit) : ""}</span> },
    { key: "period", h: 13, icon: <PeriodIcon />, label: "Periode", cell: (d) => <span className="font-num text-micro text-muted">{d?.period != null ? `${Math.round(d.period)}s` : ""}</span> },
    { key: "wave-d", h: 14, icon: null, label: "Wellenrichtung", cell: (d) => waveArrow(d) },
    { key: "wind-v", h: 13, icon: <WindIcon />, label: "Wind", cell: (d) => <span className="font-num text-micro text-ink">{d?.wind != null ? windValue(d.wind, windUnit) : ""}</span> },
    { key: "wind-d", h: 14, icon: null, label: "Windrichtung", cell: (d) => windArrow(d) },
  ];
  const rows = waveFocus ? waveRows : windRows;

  // The chosen hour, spelled out — the map's reading first.
  const windText = selected?.wind != null
    ? `${windValue(selected.wind, windUnit)} kn${selected.gust != null ? ` · Böen ${windValue(selected.gust, windUnit)}` : ""}${selected.windFrom != null ? ` · aus ${directionName(selected.windFrom)}` : ""}`
    : null;
  const waveText = selected?.wave != null
    ? `${waveValue(selected.wave, waveUnit)} m${selected.period != null ? ` · ${Math.round(selected.period)} s` : ""}${selected.waveFrom != null ? ` · aus ${directionName(selected.waveFrom)}` : ""}`
    : null;
  const reading = (waveFocus ? [waveText && `Welle ${waveText}`, windText && `Wind ${windText}`] : [windText && `Wind ${windText}`, waveText && `Welle ${waveText}`])
    .filter(Boolean).join("  ·  ");

  return (
    <section className="swd-pm-tile has-forecast" aria-label="Vorhersage und Zeit">
      <div className="swd-pm-tile-head">
        <p className="min-w-0 flex-1 truncate">
          {value !== undefined && <span className="font-num text-caption tabular-nums text-ink">{timeLabel(value)}</span>}
          {isNow && <span className="ml-2 text-caption text-accent">Jetzt</span>}
          {loading && <span className="ml-2 text-caption text-muted">Vorhersage lädt …</span>}
        </p>
        {!spotHref && place && <span className="swd-pm-tile-spot truncate text-caption text-ink">{place}</span>}
        {spotHref && (
          <Link to={spotHref} className="swd-pm-bar-link text-caption font-medium text-accent" aria-label={spotName ? `Zum Spot ${spotName}, Daten` : "Zum Spot, Daten"}>
            {spotName && <span className="swd-pm-tile-spot truncate text-ink">{spotName}</span>}
            <span>Zum Spot</span>
            <ChevronRightIcon className="text-ui" />
          </Link>
        )}
        {onClose && (
          <button type="button" className="swd-pm-close" aria-label="Vorhersage schließen" onClick={onClose}>
            <CloseIcon className="text-ui" />
          </button>
        )}
      </div>
      <p className="swd-pm-tile-read truncate font-num text-micro tabular-nums text-muted" role="status">{reading || " "}</p>
      <div
        ref={strip}
        className="swd-pm-tile-strip swd-pm-meteo no-scrollbar"
        tabIndex={0}
        aria-label="Stunde wählen"
        onKeyDown={(event) => {
          if (index < 0) return;
          if (event.key === "ArrowRight" && index < hours.length - 1) { event.preventDefault(); onChange(hours[index + 1], { scrub: false }); }
          if (event.key === "ArrowLeft" && index > 0) { event.preventDefault(); onChange(hours[index - 1], { scrub: false }); }
        }}
      >
        {/* Row symbols, pinned left while the hours page underneath. */}
        <div className="swd-pm-meteo-labels" aria-hidden="true">
          <span style={{ height: 13 }} />
          {rows.map((row) => <span key={row.key} style={{ height: row.h }}>{row.icon}</span>)}
        </div>
        <div
          ref={cols}
          className="swd-pm-meteo-cols"
          onPointerDown={(event) => {
            pointerType.current = event.pointerType;
            if (event.pointerType !== "mouse" || event.button !== 0) return;
            dragging.current = true;
            event.currentTarget.setPointerCapture(event.pointerId);
            pickAt(event.clientX);
          }}
          onPointerMove={(event) => { if (dragging.current) pickAt(event.clientX); }}
          onPointerUp={() => { dragging.current = false; }}
          onPointerCancel={() => { dragging.current = false; }}
          // A finger taps to pick; a swipe pans natively and picks nothing.
          onClick={(event) => { if (pointerType.current !== "mouse") pickAt(event.clientX); }}
        >
          {index >= 0 && <span className="swd-pm-meteo-sel" style={{ transform: `translateX(${index * COLUMN_PX}px)` }} aria-hidden="true" />}
          {hours.map((hour) => {
            const h = new Date(hour).getHours();
            const data = forecast.get(hour);
            const label = h === 0 ? weekday(hour) : h % 3 === 0 ? String(h).padStart(2, "0") : "";
            return (
              <span key={hour} className={`swd-pm-tile-col${h === 0 ? " is-midnight" : ""}`}>
                <span className={`font-num text-micro ${h === 0 ? "font-bold text-ink" : "text-muted"}`} style={{ height: 13 }}>{label}</span>
                {rows.map((row) => (
                  <span key={row.key} className="swd-pm-meteo-cell" style={{ height: row.h }}>{row.cell(data, hour)}</span>
                ))}
              </span>
            );
          })}
        </div>
      </div>
      {source && <p className="swd-pm-tile-source truncate text-micro text-muted" title={source}>{source}</p>}
    </section>
  );
}
