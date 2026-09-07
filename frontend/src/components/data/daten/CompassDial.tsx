import { motion, useReducedMotion } from "framer-motion";
import { degreesToCompass } from "../../../lib/directionSnapshot";

// Instrument geometry (centre 120, ring radius 100). The viewBox carries a
// margin around the ring so the outer cardinal letters are never clipped.
const C = 120;
const R = 100;
const rad = (d: number) => (d * Math.PI) / 180;
const pt = (deg: number, r: number): [number, number] => [C + Math.sin(rad(deg)) * r, C - Math.cos(rad(deg)) * r];

// Page accent (the Daten blue). Needle + bearing mark use it; warm is reserved
// for temperature elsewhere, so the compass stays cool. No glow.
const ACCENT = "var(--sw-teal)";

/**
 * Wind-direction instrument (Daten map band, bottom-right). A fine tick ring
 * (minor every 3°, major every 45°, bright cardinals), N/E/S/W outside and a
 * faint crosshair, with a balanced blue needle that pivots around the centre
 * like a real compass. `fromDeg` is the meteorological "wind from" bearing;
 * `pointTo` defaults to "source" so the needle points the way the text reads
 * ("Aus NW"); pass "target" to point where the wind blows (fromDeg + 180°).
 */
export default function CompassDial({
  fromDeg,
  pointTo = "source",
}: {
  fromDeg: number | null;
  pointTo?: "source" | "target";
}) {
  const reduced = useReducedMotion() === true;
  const label = fromDeg == null ? "Windrichtung nicht verfügbar" : `Wind aus ${degreesToCompass(fromDeg)}, ${Math.round(fromDeg)} Grad`;
  const bearing = fromDeg == null ? null : ((pointTo === "target" ? fromDeg + 180 : fromDeg) % 360 + 360) % 360;

  const ticks: React.ReactNode[] = [];
  for (let d = 0; d < 360; d += 3) {
    const cardinal = d % 90 === 0;
    const major = d % 45 === 0;
    const inner = cardinal ? R - 14 : major ? R - 11 : R - 6;
    const [x1, y1] = pt(d, inner);
    const [x2, y2] = pt(d, R);
    ticks.push(
      <line
        key={d}
        x1={x1} y1={y1} x2={x2} y2={y2}
        stroke={cardinal ? "var(--sw-ink)" : "var(--sw-muted)"}
        strokeWidth={cardinal ? 1.6 : major ? 1.2 : 0.8}
        opacity={cardinal ? 0.9 : major ? 0.55 : 0.28}
        strokeLinecap="round"
      />,
    );
  }

  const cardinals: Array<[string, number]> = [["N", 0], ["E", 90], ["S", 180], ["W", 270]];

  return (
    <svg viewBox="-12 -12 264 264" width="100%" className="mx-auto block h-auto max-w-[280px]" role="img" aria-label={label}>
      {ticks}

      {/* Cardinal letters (outside) + faint crosshair. */}
      {cardinals.map(([ch, deg]) => {
        const [x, y] = pt(deg, R + 16);
        return (
          <text key={ch} x={x} y={y} textAnchor="middle" dominantBaseline="central" fontSize={13} fontWeight={600} fill="var(--sw-ink)">
            {ch}
          </text>
        );
      })}
      <line x1={C - 8} y1={C} x2={C + 8} y2={C} stroke="var(--sw-line)" strokeWidth={1} />
      <line x1={C} y1={C - 8} x2={C} y2={C + 8} stroke="var(--sw-line)" strokeWidth={1} />

      {bearing != null && (
        <>
          {/* Bearing mark on the ring, exactly on the reading. */}
          {(() => {
            const [x1, y1] = pt(bearing, R);
            const [x2, y2] = pt(bearing, R - 18);
            return <line x1={x1} y1={y1} x2={x2} y2={y2} stroke={ACCENT} strokeWidth={2.4} strokeLinecap="round" />;
          })()}

          {/* A balanced needle centred on the pivot: bright front arm to the
              bearing, dim back arm opposite — it spins around the middle like a
              real compass needle. No glow. */}
          <motion.g
            initial={false}
            animate={{ rotate: bearing }}
            transition={{ duration: reduced ? 0 : 0.5, ease: [0.16, 1, 0.3, 1] }}
            style={{ transformOrigin: `${C}px ${C}px` }}
          >
            <path d={`M${C} ${C - 72} L${C + 5} ${C} L${C - 5} ${C} Z`} fill={ACCENT} />
            <path d={`M${C} ${C + 72} L${C + 5} ${C} L${C - 5} ${C} Z`} fill={ACCENT} opacity={0.4} />
          </motion.g>
          {/* Hub. */}
          <circle cx={C} cy={C} r={3.4} fill="var(--sw-ink)" />
        </>
      )}
    </svg>
  );
}
