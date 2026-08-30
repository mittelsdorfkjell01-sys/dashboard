import { motion, useReducedMotion } from "framer-motion";
import { degreesToCompass } from "../../../lib/directionSnapshot";

/**
 * Minimal wind-direction dial (Figma Frame 67, bottom-right): a light disc
 * with a dark navigation arrow that points the way the wind blows. `fromDeg`
 * is the meteorological "wind from" bearing, so the arrow rotates to
 * `fromDeg + 180` (the direction of travel).
 */
export default function CompassDial({ fromDeg, size = 132 }: { fromDeg: number | null; size?: number }) {
  const reduced = useReducedMotion() === true;
  const label = fromDeg == null ? "Windrichtung nicht verfügbar" : `Wind aus ${degreesToCompass(fromDeg)}, ${Math.round(fromDeg)} Grad`;
  return (
    <svg viewBox="0 0 100 100" width={size} height={size} role="img" aria-label={label}>
      <circle cx="50" cy="50" r="48" fill="#E9E9EA" />
      {fromDeg != null && (
        <motion.g
          initial={false}
          animate={{ rotate: fromDeg + 180 }}
          transition={{ duration: reduced ? 0 : 0.45, ease: [0.16, 1, 0.3, 1] }}
          style={{ transformOrigin: "50px 50px" }}
        >
          {/* Navigation arrow — a slim kite pointing "up" before rotation. */}
          <path d="M50 26 L61 68 L50 60 L39 68 Z" fill="#15181C" stroke="#15181C" strokeWidth="1.5" strokeLinejoin="round" />
        </motion.g>
      )}
    </svg>
  );
}
