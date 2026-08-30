import type { WeatherCondition } from "../../../lib/api";

/**
 * Weather-condition → colored glyph for the Daten page (Figma Frame 67:
 * WETTER row + the 8-day forecast grid). Outline clouds in the light "ink"
 * tone, sun/lightning in orange, precipitation in blue — matching the mockup.
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
  const rain = "#4F97D8";
  const snow = "#8FC4E6";
  const bolt = "#E7A33A";
  const stroke = 1.6;

  const Cloud = ({ y = 0 }: { y?: number }) => (
    <path
      d={`M7 ${15 + y}a3.4 3.4 0 0 1 .3-6.78 4.6 4.6 0 0 1 8.87-1.2A3.6 3.6 0 0 1 17.4 ${15 + y}Z`}
      fill="none"
      stroke={cloud}
      strokeWidth={stroke}
      strokeLinejoin="round"
    />
  );

  const drops = (color: string, xs: number[], y0 = 16.5, len = 3) =>
    xs.map((x, i) => (
      <line
        key={i}
        x1={x}
        y1={y0}
        x2={x - 1}
        y2={y0 + len}
        stroke={color}
        strokeWidth={stroke}
        strokeLinecap="round"
      />
    ));

  let content: JSX.Element;
  switch (condition) {
    case "clear":
    case "mainly_clear":
      content = isDay ? (
        <g>
          <circle cx="12" cy="12" r="4.4" fill="none" stroke={sun} strokeWidth={stroke} />
          {[0, 45, 90, 135, 180, 225, 270, 315].map((a) => {
            const r = (a * Math.PI) / 180;
            return (
              <line
                key={a}
                x1={12 + Math.cos(r) * 7}
                y1={12 + Math.sin(r) * 7}
                x2={12 + Math.cos(r) * 9}
                y2={12 + Math.sin(r) * 9}
                stroke={sun}
                strokeWidth={stroke}
                strokeLinecap="round"
              />
            );
          })}
        </g>
      ) : (
        <path
          d="M16.5 15.5A6 6 0 0 1 9 8a6 6 0 1 0 7.5 7.5Z"
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
          <circle cx="9" cy="8.5" r="3.1" fill="none" stroke={sun} strokeWidth={stroke} />
          {[210, 250, 290, 330].map((a) => {
            const r = (a * Math.PI) / 180;
            return (
              <line
                key={a}
                x1={9 + Math.cos(r) * 4.6}
                y1={8.5 + Math.sin(r) * 4.6}
                x2={9 + Math.cos(r) * 6}
                y2={8.5 + Math.sin(r) * 6}
                stroke={sun}
                strokeWidth={stroke}
                strokeLinecap="round"
              />
            );
          })}
          <Cloud y={1.5} />
        </g>
      );
      break;
    case "fog":
      content = (
        <g>
          <Cloud />
          {[18.5, 20.5].map((y) => (
            <line key={y} x1="6" y1={y} x2="18" y2={y} stroke={cloud} strokeWidth={stroke} strokeLinecap="round" opacity={0.7} />
          ))}
        </g>
      );
      break;
    case "drizzle":
      content = (
        <g>
          <Cloud />
          {drops(rain, [9, 12.5, 16], 16.5, 2.4)}
        </g>
      );
      break;
    case "rain":
    case "rain_showers":
      content = (
        <g>
          <Cloud />
          {drops(rain, [8.5, 12, 15.5], 16.5, 3.4)}
        </g>
      );
      break;
    case "snow":
    case "snow_showers":
      content = (
        <g>
          <Cloud />
          {[9, 12.5, 16].map((x) => (
            <g key={x} stroke={snow} strokeWidth={stroke} strokeLinecap="round">
              <line x1={x - 1.4} y1={18.2} x2={x + 1.4} y2={18.2} />
              <line x1={x} y1={16.8} x2={x} y2={19.6} />
            </g>
          ))}
        </g>
      );
      break;
    case "thunderstorm":
      content = (
        <g>
          <Cloud />
          <path d="M12.5 16 L10 19.5 H12 L11 22.5 L14 18.5 H12 Z" fill={bolt} stroke={bolt} strokeWidth={0.8} strokeLinejoin="round" />
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
