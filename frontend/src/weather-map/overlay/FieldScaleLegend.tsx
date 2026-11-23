import { useOptionalUnits } from "../../context/PrefsContext";
import { WIND_BINS } from "../../lib/windScale";
import { waveValue, windValue, WAVE_UNIT_SUFFIX, WIND_UNIT_SUFFIX } from "../../lib/units";
import { FIELD_LAYER_STYLES } from "../fieldColor";

/** The wave ramp's stops, as the field paints them. */
const WAVE_STOPS = FIELD_LAYER_STYLES.waves.stops as readonly (readonly [number, readonly [number, number, number]])[];

/** Label every other step, so a 320px strip stays readable. */
const labelled = (index: number, count: number) => index % 2 === 0 && index < count;

/**
 * What the colours on the field mean. The map draws one quantity as colour
 * across the whole viewport, which until now had nothing anywhere that named
 * it — the 2026-10-11 brief took the old floating legend off the map because
 * it was a second control surface competing with the markers, and the map was
 * left unreadable instead (2026-11-16 review).
 *
 * It is the quietest panel on the map: a 6px strip of the bins, four
 * boundaries, and the publication it belongs to. For wind it shows the HOUSE
 * wind scale (lib/windScale.ts) — the same bins the field is painted with and
 * the same ones the forecast bars use, so the legend cannot disagree with
 * either. Boundaries are converted into the visitor's own unit.
 */
export default function FieldScaleLegend({
  product,
  source,
}: {
  product: "wind" | "waves";
  /** Model and publication time — the field's provenance, never invented. */
  source?: string;
}) {
  const units = useOptionalUnits();
  const wind = product === "wind";
  const steps = wind
    ? WIND_BINS.map((bin) => ({ from: bin.min, hex: bin.hex }))
    : WAVE_STOPS.map(([from, [r, g, b]]) => ({ from, hex: `rgb(${r} ${g} ${b})` }));
  const unit = wind ? WIND_UNIT_SUFFIX[units.wind] : WAVE_UNIT_SUFFIX[units.wave];
  const tick = (value: number) => (wind ? windValue(value, units.wind) : waveValue(value, units.wave));

  return (
    <section className="swd-wx-legend" aria-label={`Farbskala ${wind ? "Wind" : "Wellenhöhe"}`}>
      <p className="text-micro font-semibold uppercase tracking-caps text-muted">
        {wind ? "Wind" : "Wellenhöhe"} · {unit}
      </p>
      <div className="swd-wx-legend-scale" aria-hidden="true">
        {steps.map((step) => <span key={step.from} style={{ backgroundColor: step.hex }} />)}
      </div>
      <div className="swd-wx-legend-ticks text-micro tabular-nums text-muted" aria-hidden="true">
        {steps.map((step, index) => (
          <span key={step.from} className="flex-1 text-left">
            {labelled(index, steps.length)
              ? `${tick(step.from)}${index === steps.length - 1 ? "+" : ""}`
              : ""}
          </span>
        ))}
      </div>
      {source && <p className="truncate text-micro text-muted">{source}</p>}
    </section>
  );
}
