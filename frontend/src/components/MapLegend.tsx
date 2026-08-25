import { WIND_BINS } from "../lib/windScale";
import { WAVE_BINS } from "../lib/waveScale";
import type { PublicMapMode } from "../lib/publicMap";

// "waves" colors by primary swell height (`current.swell`) — the only wave
// field the public API exposes today; total-wave/wind-sea decomposition
// exists in the backend schema but isn't wired to the frontend contract yet
// (see docs/map-redesign-backend-gaps.md), so the label says exactly what's
// shown rather than implying a fuller breakdown.
const MODE_COPY: Record<PublicMapMode, { title: string; unit: string }> = {
  wind: { title: "Wind", unit: "kt" },
  waves: { title: "Swell (Primärwelle)", unit: "m" },
};

/** Compact floating legend for the active marker-color mode — the same
 *  bins `spotColorExpression` paints markers with (lib/publicMap.ts), so the
 *  legend can never drift out of sync with what's actually on the map. */
export default function MapLegend({ mode }: { mode: PublicMapMode }) {
  const bins = mode === "wind" ? WIND_BINS : WAVE_BINS;
  const { title, unit } = MODE_COPY[mode];
  const format = (value: number) => (Number.isInteger(value) ? String(value) : value.toFixed(1));
  return (
    <div className="swd-map-legend" role="group" aria-label={`Legende: ${title}`}>
      <span className="swd-map-legend-title">{title} ({unit})</span>
      <div className="swd-map-legend-scale" aria-hidden="true">
        {bins.map((bin) => <span key={bin.min} style={{ backgroundColor: bin.hex }} />)}
      </div>
      <div className="swd-map-legend-ticks">
        <span>0</span>
        <span>{format(bins[Math.floor(bins.length / 2)].min)}</span>
        <span>{format(bins[bins.length - 1].min)}+</span>
      </div>
      <span className="swd-map-legend-note">Graue Marker: keine Live-Daten für diesen Modus</span>
    </div>
  );
}
