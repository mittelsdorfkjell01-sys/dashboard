import { WIND_BINS } from "../lib/windScale";
import { useOptionalUnits } from "../context/PrefsContext";
import { windValue, WIND_UNIT_SUFFIX } from "../lib/units";

/** One-line legend for the shared wind-speed color scale — nine swatches with
 *  their ranges. Sits under any chart that colors bars via `windColor()`.
 *
 *  The bins are defined in knots (the canonical unit); the boundaries are
 *  converted into the visitor's chosen display unit here, so the legend cannot
 *  disagree with the bars it explains. It also used to print "kt" while every
 *  other reading on the site says "kn". */
export default function WindScaleLegend() {
  const units = useOptionalUnits();
  const suffix = WIND_UNIT_SUFFIX[units.wind];
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-data-caption text-muted">
      {WIND_BINS.map((bin, i) => (
        <span key={bin.min} className="inline-flex items-center gap-1">
          <span aria-hidden="true" className="h-2.5 w-2.5 rounded-card" style={{ backgroundColor: bin.hex }} />
          {i === WIND_BINS.length - 1
            ? `${windValue(bin.min, units.wind)}+`
            : `${windValue(bin.min, units.wind)}–${windValue(bin.max, units.wind)}`}{" "}
          {suffix}
        </span>
      ))}
    </div>
  );
}
