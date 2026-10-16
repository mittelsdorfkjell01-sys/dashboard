import { useMemo } from "react";
import type { NormalizedForecastSeries } from "../../../lib/forecastNormalization";
import { isSpotForecastDisplayHour } from "../../../lib/spotForecastWindow";
import { buildMeteogramModel } from "../meteogramModel";
import { useSpotDataScope } from "../../../state/SpotDataScope";
import WindForecastBars from "../../forecast/WindForecastBars";

/**
 * Wind-only forecast strip for the map overlay (Figma Frame 80, bottom). It
 * reuses the top meteogram's wind data (same `buildMeteogramModel` slots and
 * wind scale) but only the wind bars, drawn at half the meteogram's size so
 * twice as many hours fit — the bars themselves come from the shared
 * `WindForecastBars`, which the wind map's spot forecast draws too. It scrolls
 * only by finger-swipe and never auto-follows the scrubber; tapping a bar
 * drives the shared selection. Renders nothing without an hourly forecast.
 */
export default function OverlayForecastStrip({ forecast }: { forecast: NormalizedForecastSeries | null }) {
  const { selectedAtUtc, setSelectedAtUtc, windUnit } = useSpotDataScope();
  const model = useMemo(() => (forecast ? buildMeteogramModel(forecast, isSpotForecastDisplayHour) : null), [forecast]);
  const slots = useMemo(() => model?.slots ?? [], [model]);

  if (!slots.length) return null;

  return (
    <div
      className="overflow-x-auto px-3 pt-2 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
      role="group"
      aria-label="Windforecast — Zeitpunkt wählen"
    >
      <WindForecastBars
        slots={slots}
        selectedUtcKey={selectedAtUtc}
        onSelect={setSelectedAtUtc}
        windUnit={windUnit}
      />
    </div>
  );
}
