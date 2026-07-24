/** German 16-point compass abbreviations (O = Ost). */
const DIRS16 = [
  "N", "NNO", "NO", "ONO", "O", "OSO", "SO", "SSO",
  "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW",
];

/** Degrees → nearest 16-point German compass label, e.g. 315 → "NW". */
export function degToCompass(deg: number): string {
  const i = Math.round(((deg % 360) + 360) / 22.5) % 16;
  return DIRS16[i];
}

const C = 100;
const R = 86;

/** Needle pointing "up" (towards the source direction); rotated by `deg`. */
function Needle({ deg, color, length, width }: { deg: number; color: string; length: number; width: number }) {
  const tipY = C - length;
  const headBase = tipY + 16;
  return (
    <g transform={`rotate(${deg} ${C} ${C})`}>
      <line
        x1={C}
        y1={C}
        x2={C}
        y2={headBase}
        stroke={color}
        strokeWidth={width}
        strokeLinecap="round"
      />
      <polygon points={`${C},${tipY} ${C - 8},${headBase + 2} ${C + 8},${headBase + 2}`} fill={color} />
    </g>
  );
}

/**
 * Compass wind rose in the app's ink/blue palette. Shows the direction the
 * wind (ink) and swell (blue) come FROM — matching the arrows drawn on the
 * spot map. Meteorological convention: needle points towards the source.
 */
export default function WindRose({
  windDir,
  waveDir,
  className = "",
}: {
  windDir: number;
  waveDir?: number;
  className?: string;
}) {
  const minorTicks = Array.from({ length: 16 }, (_, i) => i).filter((i) => i % 4 !== 0);
  const cardinals: [string, number, number][] = [
    ["N", C, C - (R - 24)],
    ["O", C + (R - 24), C],
    ["S", C, C + (R - 24)],
    ["W", C - (R - 24), C],
  ];

  return (
    <svg
      viewBox="0 0 200 200"
      className={className}
      role="img"
      aria-label={`Windrose: Wind aus ${degToCompass(windDir)}${
        waveDir != null ? `, Welle aus ${degToCompass(waveDir)}` : ""
      }`}
    >
      <circle cx={C} cy={C} r={R} fill="#fff" stroke="#E6E1DA" strokeWidth={2} />
      <circle cx={C} cy={C} r={R - 22} fill="none" stroke="#E6E1DA" strokeWidth={1} />

      {/* Cardinal ticks (ink) */}
      {[0, 4, 8, 12].map((i) => {
        const a = (i * 22.5 * Math.PI) / 180;
        return (
          <line
            key={`c${i}`}
            x1={C + R * Math.sin(a)}
            y1={C - R * Math.cos(a)}
            x2={C + (R - 16) * Math.sin(a)}
            y2={C - (R - 16) * Math.cos(a)}
            stroke="#241C17"
            strokeWidth={2}
          />
        );
      })}
      {/* Minor ticks */}
      {minorTicks.map((i) => {
        const a = (i * 22.5 * Math.PI) / 180;
        return (
          <line
            key={`m${i}`}
            x1={C + R * Math.sin(a)}
            y1={C - R * Math.cos(a)}
            x2={C + (R - 8) * Math.sin(a)}
            y2={C - (R - 8) * Math.cos(a)}
            stroke="#B9C4D4"
            strokeWidth={1}
          />
        );
      })}

      {/* Cardinal labels */}
      {cardinals.map(([label, x, y]) => (
        <text
          key={label}
          x={x}
          y={y}
          textAnchor="middle"
          dominantBaseline="central"
          fontSize={13}
          fontWeight={label === "N" ? 700 : 500}
          fill={label === "N" ? "#241C17" : "#7A6F66"}
        >
          {label}
        </text>
      ))}

      {/* Swell needle behind, wind needle in front */}
      {waveDir != null && <Needle deg={waveDir} color="#2F6FB0" length={48} width={4} />}
      <Needle deg={windDir} color="#241C17" length={60} width={5} />

      <circle cx={C} cy={C} r={6} fill="#241C17" stroke="#fff" strokeWidth={2} />
    </svg>
  );
}
