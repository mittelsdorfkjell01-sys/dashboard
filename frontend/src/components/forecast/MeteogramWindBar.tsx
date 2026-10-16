import { useEffect, useState } from "react";
import { windColor } from "../../lib/windScale";
import { windValue, type WindUnit } from "../../lib/units";

export const METEOGRAM_COLUMN_WIDTH = 25;
export const METEOGRAM_BAR_WIDTH = 22;
export const METEOGRAM_WIND_BASE_HEIGHT = 15;
export const METEOGRAM_WIND_HEIGHT = 72;
export const METEOGRAM_MOBILE_WIND_HEIGHT = 64;
export const METEOGRAM_WIND_HEADROOM = 8;

const MOBILE_QUERY = "(max-width: 639.98px)";

/** Keeps every consumer on the same responsive bar height as Spot-Daten. */
export function useMeteogramWindHeight(): number {
  const [height, setHeight] = useState(() => (
    typeof window !== "undefined" && window.matchMedia(MOBILE_QUERY).matches
      ? METEOGRAM_MOBILE_WIND_HEIGHT
      : METEOGRAM_WIND_HEIGHT
  ));
  useEffect(() => {
    const query = window.matchMedia(MOBILE_QUERY);
    const update = () => setHeight(query.matches ? METEOGRAM_MOBILE_WIND_HEIGHT : METEOGRAM_WIND_HEIGHT);
    update();
    query.addEventListener("change", update);
    return () => query.removeEventListener("change", update);
  }, []);
  return height;
}

function fade(hex: string, alpha = 0.45): string {
  const match = /^#?([\da-f]{2})([\da-f]{2})([\da-f]{2})$/i.exec(hex);
  if (!match) return hex;
  const [red, green, blue] = [match[1], match[2], match[3]].map((part) => parseInt(part, 16));
  return `rgba(${red}, ${green}, ${blue}, ${alpha})`;
}

/** The full-size wind/gust bar shared by the Spot-Daten meteogram and map sheet. */
export default function MeteogramWindBar({
  wind,
  gust,
  maximum,
  windUnit,
  proportionalHeight = METEOGRAM_WIND_HEIGHT,
}: {
  wind: number;
  gust?: number | null;
  maximum: number;
  windUnit: WindUnit;
  proportionalHeight?: number;
}) {
  const safeMaximum = Math.max(maximum, 5);
  const gustValue = Math.max(gust ?? wind, wind);
  const windHeight = METEOGRAM_WIND_BASE_HEIGHT + (wind / safeMaximum) * proportionalHeight;
  const gustHeight = METEOGRAM_WIND_BASE_HEIGHT + (gustValue / safeMaximum) * proportionalHeight;
  const showGust = gustValue > wind + 0.5 && gustHeight - windHeight >= 14;

  return (
    <span
      data-wind-bar="gust"
      className="relative rounded-[5px]"
      style={{ width: METEOGRAM_BAR_WIDTH, height: gustHeight, background: fade(windColor(wind)) }}
    >
      {showGust && <BarValue>{windValue(gustValue, windUnit)}</BarValue>}
      <span
        data-wind-bar="wind"
        className="absolute inset-x-0 bottom-0 rounded-[5px]"
        style={{ height: windHeight, background: windColor(wind) }}
      >
        <BarValue>{windValue(wind, windUnit)}</BarValue>
      </span>
    </span>
  );
}

function BarValue({ children }: { children: React.ReactNode }) {
  return (
    <span
      className="pointer-events-none absolute inset-x-0 top-0.5 text-center leading-none text-white"
      style={{ fontSize: 10, textShadow: "0 1px 2px rgba(0, 0, 0, 0.35)" }}
    >
      {children}
    </span>
  );
}
