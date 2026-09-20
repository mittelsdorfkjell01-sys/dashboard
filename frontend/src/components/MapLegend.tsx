import { WIND_BINS } from "../lib/windScale";
import { WAVE_BINS } from "../lib/waveScale";
import type { PublicMapMode } from "../lib/publicMap";
import { useOptionalUnits } from "../context/PrefsContext";
import { windValue, WIND_UNIT_SUFFIX, waveValue, WAVE_UNIT_SUFFIX } from "./../lib/units";

// "waves" colors by primary swell height (`current.swell`) — the only wave
// field the public API exposes today; total-wave/wind-sea decomposition
// exists in the backend schema but isn't wired to the frontend contract yet
// (see docs/map-redesign-backend-gaps.md), so the label says exactly what's
// shown rather than implying a fuller breakdown.
const MODE_TITLE: Record<PublicMapMode, string> = {
  wind: "Wind",
  waves: "Swell (Primärwelle)",
};

/** Compact floating legend for the active marker-color mode — the same
 *  bins `spotColorExpression` paints markers with (lib/publicMap.ts), so the
 *  legend can never drift out of sync with what's actually on the map. The tick
 *  values + unit follow the viewer's chosen display units (PrefsContext). */
export default function MapLegend({ mode }: { mode: PublicMapMode }) {
  const units = useOptionalUnits();
  const bins = mode === "wind" ? WIND_BINS : WAVE_BINS;
  const title = MODE_TITLE[mode];
  const unit = mode === "wind" ? WIND_UNIT_SUFFIX[units.wind] : WAVE_UNIT_SUFFIX[units.wave];
  // Bin bounds are canonical (wind in kn, wave in m); render them in the chosen
  // unit so the legend matches the values shown elsewhere on the page.
  const tick = (value: number) => (mode === "wind" ? windValue(value, units.wind) : waveValue(value, units.wave));
  return (
    <div className="swd-map-legend" role="group" aria-label={`Legende: ${title}`}>
      <span className="swd-map-legend-title">{title} ({unit})</span>
      <div className="swd-map-legend-scale" aria-hidden="true">
        {bins.map((bin) => <span key={bin.min} style={{ backgroundColor: bin.hex }} />)}
      </div>
      <div className="swd-map-legend-ticks">
        <span>{tick(0)}</span>
        <span>{tick(bins[Math.floor(bins.length / 2)].min)}</span>
        <span>{tick(bins[bins.length - 1].min)}+</span>
      </div>
      <span className="swd-map-legend-note">Graue Marker: keine Live-Daten für diesen Modus</span>
    </div>
  );
}
