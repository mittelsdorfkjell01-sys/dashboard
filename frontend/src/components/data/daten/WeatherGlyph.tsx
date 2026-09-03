import type { WeatherCondition } from "../../../lib/api";

/**
 * Weather-condition → colored glyph for the Daten page (Figma Frame 67:
 * WETTER row + the 8-day forecast grid). Outline clouds in the light "ink"
 * tone, sun/lightning in orange, precipitation/snow in blue — matching the
 * mockup's icon set.
 *
 * Every glyph is authored on the same 24×24 viewBox and rendered into a square
 * box sized by `size`, so a whole row/grid of them is optically uniform with
 * only the numeric `size` to change (the caller's uniformity requirement).
 */
export default function WeatherGlyph({
  condition,
  isDay = true,
  size = 40,
  className = "",
}: {
  condition: WeatherCondition | null | undefined;
  isDay?: boolean;
  size?: number;
  className?: string;
}) {
  const sun = "#E7A33A";
  const cloud = "var(--sw-ink)";
  const rain = "var(--sw-data-rain)";
  const snow = "#8FC4E6";
  const bolt = "#E7A33A";
  const stroke = 1.6;

  // Bottom edge fixed at CLOUD_BOTTOM for every case that draws one — this is
  // the shared baseline every glyph aligns to, so a whole row reads flush
  // along the bottom regardless of which condition is showing.
  const CLOUD_BOTTOM = 15;
  const Cloud = () => (
    <path
      d={`M7 ${CLOUD_BOTTOM}a3.4 3.4 0 0 1 .3-6.78 4.6 4.6 0 0 1 8.87-1.2A3.6 3.6 0 0 1 17.4 ${CLOUD_BOTTOM}Z`}
      fill="none"
      stroke={cloud}
      strokeWidth={stroke}
      strokeLinejoin="round"
    />
  );

  // Six-spoke snowflake: three crossing lines through the centre, each with a
  // short V-tick near both ends.
  const Snowflake = ({ cx, cy, r, color = snow, width = stroke }: { cx: number; cy: number; r: number; color?: string; width?: number }) => (
    <g stroke={color} strokeWidth={width} strokeLinecap="round">
      {[0, 60, 120].map((deg) => {
        const rad = (deg * Math.PI) / 180;
        const dx = Math.cos(rad) * r;
        const dy = Math.sin(rad) * r;
        const tickR = r * 0.42;
        const tick = (sign: 1 | -1) => {
          const bx = cx + dx * sign * 0.62;
          const by = cy + dy * sign * 0.62;
          const perpX = -dy;
          const perpY = dx;
          const norm = Math.hypot(perpX, perpY) || 1;
          const ux = (perpX / norm) * tickR * 0.5;
          const uy = (perpY / norm) * tickR * 0.5;
          const ix = (dx / r) * tickR * 0.5 * sign;
          const iy = (dy / r) * tickR * 0.5 * sign;
          return (
            <path
              key={sign}
              d={`M${bx - ux + ix},${by - uy + iy} L${bx},${by} L${bx + ux + ix},${by + uy + iy}`}
              fill="none"
            />
          );
        };
        return (
          <g key={deg}>
            <line x1={cx - dx} y1={cy - dy} x2={cx + dx} y2={cy + dy} />
            {tick(1)}
            {tick(-1)}
          </g>
        );
      })}
    </g>
  );

  const Sun = ({ cx, cy, r, rayLen = 2, color = sun, width = stroke }: { cx: number; cy: number; r: number; rayLen?: number; color?: string; width?: number }) => (
    <g>
      <circle cx={cx} cy={cy} r={r} fill="none" stroke={color} strokeWidth={width} />
      {[0, 45, 90, 135, 180, 225, 270, 315].map((a) => {
        const rad = (a * Math.PI) / 180;
        return (
          <line
            key={a}
            x1={cx + Math.cos(rad) * (r + 1.4)}
            y1={cy + Math.sin(rad) * (r + 1.4)}
            x2={cx + Math.cos(rad) * (r + 1.4 + rayLen)}
            y2={cy + Math.sin(rad) * (r + 1.4 + rayLen)}
            stroke={color}
            strokeWidth={width}
            strokeLinecap="round"
          />
        );
      })}
    </g>
  );

  const Bolt = ({ x = 12.5, y = 15.5, scale = 1, color = bolt }: { x?: number; y?: number; scale?: number; color?: string }) => (
    <path
      d={`M${x} ${y} L${x - 2.5} ${y + 3.5} H${x - 0.5} L${x - 1.5} ${y + 7} L${x + 1.5} ${y + 3.5} H${x - 0.5} Z`}
      fill={color}
      stroke={color}
      strokeWidth={0.8}
      strokeLinejoin="round"
      transform={scale !== 1 ? `scale(${scale})` : undefined}
    />
  );

  let content: JSX.Element;
  switch (condition) {
    case "clear":
    case "mainly_clear":
      content = isDay ? (
        // Disc bottom pinned to CLOUD_BOTTOM so a sunny day sits on the same
        // baseline as every cloud-bearing condition.
        <Sun cx={12} cy={CLOUD_BOTTOM - 4.4} r={4.4} rayLen={2.2} />
      ) : (
        <path
          d="M16.5 10.77A6 6 0 0 1 9 3.27a6 6 0 1 0 7.5 7.5Z"
          fill="none"
          stroke={cloud}
          strokeWidth={stroke}
          strokeLinejoin="round"
        />
      );
      break;
    case "partly_cloudy":
      content = (
        <g>
          <Sun cx={8.7} cy={6.6} r={2.3} rayLen={1.4} />
          <Cloud />
        </g>
      );
      break;
    case "fog":
      content = (
        <g>
          <Cloud />
          {[18.3, 21].map((y) => (
            <line key={y} x1="6" y1={y} x2="18" y2={y} stroke={cloud} strokeWidth={stroke} strokeLinecap="round" opacity={0.7} />
          ))}
        </g>
      );
      break;
    case "drizzle":
      // Light rain: a loose scatter of small dots beneath the cloud, bottom
      // dot on the shared ACCENT_BOTTOM line.
      content = (
        <g>
          <Cloud />
          {[
            [9, 17.9],
            [12.5, 19.9],
            [16, 17.9],
          ].map(([cx, cy]) => (
            <circle key={cx} cx={cx} cy={cy} r={1.1} fill={rain} />
          ))}
        </g>
      );
      break;
    case "rain":
      // Steady rain: three parallel diagonal streaks reaching ACCENT_BOTTOM.
      content = (
        <g>
          <Cloud />
          {[8.5, 12, 15.5].map((x) => (
            <line key={x} x1={x} y1={16.5} x2={x - 1.4} y2={21} stroke={rain} strokeWidth={1.8} strokeLinecap="round" />
          ))}
        </g>
      );
      break;
    case "rain_showers":
      // Bursty showers: a short wavy trail flanked by two drops.
      content = (
        <g>
          <Cloud />
          <path d="M12 16.3 q-1.2 1.18 0 2.35 q1.2 1.18 0 2.35" fill="none" stroke={rain} strokeWidth={stroke} strokeLinecap="round" />
          <circle cx={8.3} cy={20} r={1} fill={rain} />
          <circle cx={15.7} cy={20} r={1} fill={rain} />
        </g>
      );
      break;
    case "snow":
      content = (
        <g>
          <Cloud />
          <Snowflake cx={12} cy={18.7} r={2.6} />
        </g>
      );
      break;
    case "snow_showers":
      // Heavier snow: one large flake, no cloud — the fall dominates the
      // glyph, but its lowest point still lands on ACCENT_BOTTOM.
      content = <Snowflake cx={12} cy={14} r={7} width={1.7} />;
      break;
    case "thunderstorm":
      content = (
        <g>
          <Cloud />
          <Bolt x={12.5} y={14.5} />
          {[9.2, 15.8].map((x) => (
            <line key={x} x1={x} y1={19} x2={x - 0.9} y2={21.5} stroke={rain} strokeWidth={stroke} strokeLinecap="round" />
          ))}
        </g>
      );
      break;
    case "overcast":
      content = (
        <g>
          <Cloud />
        </g>
      );
      break;
    default:
      content = (
        <g>
          <Cloud />
        </g>
      );
  }

  return (
    <svg
      viewBox="0 0 24 24"
      width={size}
      height={size}
      role="img"
      aria-label={weatherLabel(condition)}
      className={className}
      style={{ display: "block" }}
    >
      {content}
    </svg>
  );
}

export function weatherLabel(condition: WeatherCondition | null | undefined): string {
  switch (condition) {
    case "clear": return "Klar";
    case "mainly_clear": return "Überwiegend klar";
    case "partly_cloudy": return "Teils bewölkt";
    case "overcast": return "Bedeckt";
    case "fog": return "Nebel";
    case "drizzle": return "Nieselregen";
    case "rain": return "Regen";
    case "rain_showers": return "Regenschauer";
    case "snow": return "Schnee";
    case "snow_showers": return "Schneeschauer";
    case "thunderstorm": return "Gewitter";
    default: return "Wetter unbekannt";
  }
}
