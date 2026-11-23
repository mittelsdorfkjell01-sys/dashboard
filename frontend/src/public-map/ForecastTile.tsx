import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { ChevronRightIcon, CloseIcon, WaveIcon, WindIcon } from "../lib/icons";
import { windValue, waveValue, type WaveUnit, type WindUnit } from "../lib/units";
import { css, windRgb } from "./fieldColors";
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
    let wind = 10, hasWave = false;
    for (const hour of forecast?.values() ?? []) {
      wind = Math.max(wind, hour.gust ?? 0, hour.wind ?? 0);
      if (hour.wave != null) hasWave = true;
    }
    return { wind, hasWave };
  }, [forecast]);
  const isNow = value !== undefined && nowAt !== undefined && Math.abs(value - nowAt) < 31 * 60_000;

  return (
    <section className={`swd-pm-tile${forecast ? " has-forecast" : ""}`} aria-label={forecast ? "Vorhersage und Zeit" : "Zeit"}>
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
            const data = forecast?.get(hour);
            const label = h === 0 ? weekday(hour) : h % 3 === 0 ? String(h).padStart(2, "0") : "";
            return (
              <span key={hour} className={`swd-pm-tile-col${h === 0 ? " is-midnight" : ""}${nowAt !== undefined && Math.abs(hour - nowAt) < 31 * 60_000 ? " is-now" : ""}`}>
                <span className={`font-num text-micro ${h === 0 ? "font-bold text-ink" : "text-muted"}`}>{label}</span>
                {forecast && (
                  <>
                    <span className="swd-pm-tile-bars">
                      {data?.wind != null && (
                        <>
                          {data.gust != null && data.gust > data.wind && <span className="swd-pm-tile-gust" style={{ height: 3 + (data.gust / scale.wind) * 25, background: css(windRgb(data.wind)) }} />}
                          <span className="swd-pm-tile-bar" style={{ height: 3 + (data.wind / scale.wind) * 25, background: css(windRgb(data.wind)) }} />
                        </>
                      )}
                    </span>
                    <span className="font-num text-micro font-semibold text-ink">{data?.wind != null && h % 2 === 0 ? windValue(data.wind, windUnit) : ""}</span>
                    <span className="swd-pm-tile-dir">
                      {data?.wind != null && data.windFrom != null && (data.wind < CALM_KN ? <CalmMark size={10} className="text-muted" /> : <TravelArrow bearing={(data.windFrom + 180) % 360} size={11} className="text-ink-soft" />)}
                    </span>
                    {scale.hasWave && (
                      <>
                        <span className="font-num text-micro text-ink">{data?.wave != null && h % 2 === 0 ? waveValue(data.wave, waveUnit) : ""}</span>
                        <span className="swd-pm-tile-dir">
                          {data?.wave != null && data.waveFrom != null && <TravelArrow bearing={(data.waveFrom + 180) % 360} size={11} className="text-ink-soft" />}
                        </span>
                      </>
                    )}
                  </>
                )}
                {!forecast && <span className="swd-pm-tile-tick" aria-hidden="true" />}
              </span>
            );
          })}
          <span className="swd-pm-tile-pad" />
        </div>
        <span className="swd-pm-tile-needle" aria-hidden="true" />
        {forecast && (
          <span className="swd-pm-tile-legend" aria-hidden="true">
            <WindIcon className="swd-pm-tile-legend-wind" />
            {scale.hasWave && <WaveIcon className="swd-pm-tile-legend-wave" />}
          </span>
        )}
      </div>
      {forecast && source && <p className="swd-pm-tile-source truncate text-micro text-muted" title={source}>{source}</p>}
    </section>
  );
}
