import { useMemo } from "react";
import type { ForecastHour, ForecastSeries } from "../../lib/api";
import { windColor } from "../../lib/windScale";
import { formatWind, useSpotDataScope, windUnitLabel } from "../../state/SpotDataScope";

const DAY_WIDTH = 140;
const BAR_WIDTH = 13;
const BARS_PER_DAY = 8;
const DAYS = 10;
const WIDTH = DAY_WIDTH * DAYS;
const SLOT_WIDTH = DAY_WIDTH / BARS_PER_DAY;
type Slot = { date: string; hour: number; data: ForecastHour | null };

export default function Meteogram({ forecast }: { forecast: ForecastSeries }) {
  const { selectedHour, windUnit } = useSpotDataScope();
  const slots = useMemo(() => buildSlots(forecast), [forecast]);
  const selectedX = (selectedHour / 3) * SLOT_WIDTH + BAR_WIDTH / 2;
  const tempPath = buildTemperaturePath(slots, "air");

  return (
    <div className="grid grid-cols-[62px_minmax(0,1fr)]">
      <div className="z-10 border-r border-line-soft bg-surface py-1 pl-3 pr-1">
        <AxisRow height={30}>Wetter</AxisRow>
        <AxisRow height={30}>Regen <small>mm</small></AxisRow>
        <AxisRow height={50}>Temp <small>°C</small></AxisRow>
        <AxisRow height={80} top>Wind <small>{windUnitLabel(windUnit)}</small></AxisRow>
        <AxisRow height={28}>Richt.</AxisRow>
        <AxisRow height={22}>Zeit</AxisRow>
        <AxisRow height={20}>Tag</AxisRow>
      </div>
      <div className="overflow-x-auto overflow-y-hidden">
        <div style={{ width: WIDTH }}>
          <svg viewBox={`0 0 ${WIDTH} 280`} className="block h-[280px] w-full" role="img" aria-label="Zehn-Tage-Meteogramm">
            {Array.from({ length: DAYS - 1 }, (_, index) => <line key={index} x1={(index + 1) * DAY_WIDTH} y1={0} x2={(index + 1) * DAY_WIDTH} y2={280} stroke="var(--sw-line-soft)" strokeWidth={0.5} />)}

            {slots.map((slot, index) => slot.data?.precip != null && slot.data.precip > 0 ? (
              <WeatherIcon key={`weather-${index}`} x={x(index) + BAR_WIDTH / 2} y={15} rain={slot.data.precip} />
            ) : null)}

            <line x1={0} y1={58} x2={WIDTH} y2={58} stroke="var(--sw-line)" strokeWidth={0.5} />
            {slots.map((slot, index) => {
              const rain = slot.data?.precip;
              if (rain == null || rain <= 0) return null;
              const height = Math.min(22, rain * 8);
              return <g key={`rain-${index}`}><rect x={x(index)} y={58 - height} width={BAR_WIDTH} height={height} fill="#7A9BB8" opacity={0.8} />{rain >= 0.5 && <text x={x(index) + BAR_WIDTH / 2} y={55 - height} fontFamily="Poppins" fontSize={8} fill="var(--sw-ink-soft)" textAnchor="middle">{rain.toFixed(1)}</text>}</g>;
            })}

            {[65, 85].map((y) => <line key={y} x1={0} y1={y} x2={WIDTH} y2={y} stroke="var(--sw-line)" strokeWidth={0.4} strokeDasharray="2 3" />)}
            <line x1={0} y1={108} x2={WIDTH} y2={108} stroke="var(--sw-line)" strokeWidth={0.5} />
            {tempPath && <path d={tempPath} stroke="var(--sw-orange)" strokeWidth={1.4} fill="none" />}
            {slots.map((slot, index) => slot.data?.air == null ? null : <text key={`temp-${index}`} x={x(index) + BAR_WIDTH / 2} y={tempY(slot.data.air) - 4} fontFamily="Poppins" fontSize={8} fill="var(--sw-ink)" textAnchor="middle" fontWeight={500}>{Math.round(slot.data.air)}</text>)}

            {[118, 140, 162].map((y) => <line key={y} x1={0} y1={y} x2={WIDTH} y2={y} stroke="var(--sw-line)" strokeWidth={0.4} strokeDasharray="2 3" />)}
            <line x1={0} y1={196} x2={WIDTH} y2={196} stroke="var(--sw-ink)" strokeWidth={0.5} />
            {slots.map((slot, index) => {
              const wind = slot.data?.wind;
              if (wind == null) return null;
              const gust = slot.data?.gust ?? wind;
              const height = Math.min(78, wind * 3.2);
              const gustHeight = Math.min(78, Math.max(height, gust * 3.2));
              const color = windColor(wind);
              return <g key={`wind-${index}`}>
                {gustHeight > height && <rect x={x(index)} y={196 - gustHeight} width={BAR_WIDTH} height={gustHeight - height} fill={color} opacity={0.35} />}
                <rect x={x(index)} y={196 - height} width={BAR_WIDTH} height={height} fill={color} />
                <text x={x(index) + BAR_WIDTH / 2} y={Math.min(192, 196 - height + 11)} fontFamily="Poppins" fontSize={8} fill={wind >= 13 ? "white" : "var(--sw-ink)"} textAnchor="middle" fontWeight={500}>{formatWind(wind, windUnit)}</text>
              </g>;
            })}

            {slots.map((slot, index) => slot.data?.dir == null ? null : <g key={`direction-${index}`} transform={`translate(${x(index) + BAR_WIDTH / 2}, 212) rotate(${slot.data.dir})`}><line x1={0} y1={-6} x2={0} y2={6} stroke="var(--sw-ink-soft)" /><polyline points="-3,3 0,6 3,3" fill="none" stroke="var(--sw-ink-soft)" /></g>)}
            {slots.map((slot, index) => <text key={`time-${index}`} x={x(index) + BAR_WIDTH / 2} y={240} fontFamily="Poppins" fontSize={9} fill="var(--sw-muted)" textAnchor="middle">{String(slot.hour).padStart(2, "0")}</text>)}
            {Array.from({ length: DAYS }, (_, dayIndex) => {
              const date = slots[dayIndex * BARS_PER_DAY]?.date;
              return <text key={dayIndex} x={dayIndex * DAY_WIDTH + DAY_WIDTH / 2} y={264} textAnchor="middle" fontFamily="Poppins"><tspan fontWeight={600} fontSize={12} fill="var(--sw-ink)">{formatDay(date)}</tspan><tspan fontSize={10} fill="var(--sw-muted)" dx={4}>{formatDate(date)}</tspan></text>;
            })}
            <line x1={selectedX} y1={0} x2={selectedX} y2={274} stroke="var(--sw-orange)" strokeWidth={1} strokeDasharray="3 3" />
          </svg>
        </div>
      </div>
    </div>
  );
}

function AxisRow({ height, top = false, children }: { height: number; top?: boolean; children: React.ReactNode }) {
  return <div style={{ height }} className={`flex text-caption font-medium uppercase tracking-wider text-muted ${top ? "items-start pt-2" : "items-center"}`}>{children}</div>;
}

function buildSlots(forecast: ForecastSeries): Slot[] {
  const dates = Array.from({ length: DAYS }, (_, index) => forecast.days[index]?.date ?? addDays(forecast.days[0]?.date, index));
  return dates.flatMap((date, dayIndex) => Array.from({ length: BARS_PER_DAY }, (_, slotIndex) => {
    const hour = slotIndex * 3;
    const data = forecast.days[dayIndex]?.hours.find((item) => Number(item.time.slice(11, 13)) === hour) ?? null;
    return { date, hour, data };
  }));
}

const x = (index: number) => index * SLOT_WIDTH + (SLOT_WIDTH - BAR_WIDTH) / 2;
const tempY = (temp: number) => 108 - Math.max(0, Math.min(1, (temp - 15) / 15)) * 48;
function buildTemperaturePath(slots: Slot[], key: "air"): string {
  let path = "";
  let open = false;
  slots.forEach((slot, index) => {
    const value = slot.data?.[key];
    if (value == null) { open = false; return; }
    path += `${open ? " L" : "M"} ${x(index) + BAR_WIDTH / 2} ${tempY(value)}`;
    open = true;
  });
  return path;
}
function addDays(date: string | undefined, days: number): string {
  const value = date ? new Date(`${date}T12:00:00`) : new Date();
  value.setDate(value.getDate() + days);
  return value.toISOString().slice(0, 10);
}
function formatDay(date: string): string { return new Intl.DateTimeFormat("de-DE", { weekday: "short" }).format(new Date(`${date}T12:00:00`)).replace(".", "").toUpperCase(); }
function formatDate(date: string): string { return new Intl.DateTimeFormat("de-DE", { day: "2-digit", month: "2-digit" }).format(new Date(`${date}T12:00:00`)); }
function WeatherIcon({ x: cx, y, rain }: { x: number; y: number; rain: number }) {
  return <g transform={`translate(${cx},${y})`} aria-label={rain >= 5 ? "Starker Regen" : "Regen"}><path d="M-5 1a4 4 0 0 1 7-3 4 4 0 0 1 1 7h-8a3 3 0 0 1 0-6" fill="#7A9BB8" /><line x1={-3} y1={7} x2={-4} y2={10} stroke="#2F6FB0" /><line x1={1} y1={7} x2={0} y2={10} stroke="#2F6FB0" /></g>;
}
