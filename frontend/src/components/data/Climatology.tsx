import type { Spot } from "../../lib/types";
import { climatologyToPercentile } from "../../lib/seasonView";
import { windColor } from "../../lib/windScale";

const MONTHS = ["JAN", "FEB", "MÄR", "APR", "MAI", "JUN", "JUL", "AUG", "SEP", "OKT", "NOV", "DEZ"];

/** Compact 12 × 4 weekly climatology for the technical data tab.
 * Existing real weekly values are grouped by calendar display month. Short
 * groups repeat their monthly mean; they are never linearly interpolated. */
export default function Climatology({ spot }: { spot: Spot }) {
  const monthly = climatologyToPercentile(spot.climatology, 75);
  if (!monthly) return null;
  // TODO(backend): expose a stable 48-value weekly climatology contract.
  const weeks = monthly.flatMap((month) => {
    if (month.weeks.length >= 4) return month.weeks.slice(0, 4);
    const mean = month.weeks.reduce((sum, value) => sum + value, 0) / month.weeks.length;
    return Array(4).fill(mean);
  });
  const today = new Date();
  const current = Math.min(47, today.getMonth() * 4 + Math.floor((today.getDate() - 1) / 8));

  return (
    <div className="overflow-x-auto px-4 py-3">
      <svg viewBox="0 0 640 130" className="h-[130px] min-w-[640px] w-full" role="img" aria-label="Windklimatologie mit vier Wochen je Monat">
        {[20, 55, 90].map((y) => <line key={y} x1={24} y1={y} x2={620} y2={y} stroke="var(--sw-line)" strokeWidth={0.5} strokeDasharray="2 4" />)}
        <line x1={24} y1={108} x2={620} y2={108} stroke="var(--sw-ink)" strokeWidth={0.5} />
        {[24, 16, 8, 0].map((value, index) => <text key={value} x={0} y={[24, 59, 94, 112][index]} fontSize={9} fontFamily="Poppins" fill="var(--sw-muted)">{value}</text>)}
        {MONTHS.map((month, monthIndex) => {
          const start = 30 + monthIndex * 50;
          return <g key={month}>{weeks.slice(monthIndex * 4, monthIndex * 4 + 4).map((value, weekIndex) => {
            const height = Math.min(88, value * 4.1);
            const x = start + weekIndex * 11;
            const active = monthIndex * 4 + weekIndex === current;
            return <g key={weekIndex}><rect x={x} y={108 - height} width={9} height={height} fill={windColor(value)} />{active && <rect x={x - 1} y={107 - height} width={11} height={height + 2} fill="none" stroke="var(--sw-orange)" strokeWidth={1.2} />}</g>;
          })}{monthIndex < 11 && <line x1={start + 45} y1={16} x2={start + 45} y2={108} stroke="var(--sw-line)" strokeWidth={0.5} />}<text x={start + 22} y={126} fontFamily="Poppins" fontSize={9} fontWeight={500} fill="var(--sw-muted)" letterSpacing={1} textAnchor="middle">{month}</text></g>;
        })}
      </svg>
    </div>
  );
}
