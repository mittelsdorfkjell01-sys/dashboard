import { WIND_BINS } from "../lib/windScale";

/** One-line legend for the shared wind-speed color scale — nine swatches with
 *  their kt ranges. Sits under any chart that colors bars via `windColor()`. */
export default function WindScaleLegend() {
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-data-caption text-muted">
      {WIND_BINS.map((bin, i) => (
        <span key={bin.min} className="inline-flex items-center gap-1">
          <span aria-hidden="true" className="h-2.5 w-2.5 rounded-sm" style={{ backgroundColor: bin.hex }} />
          {i === WIND_BINS.length - 1 ? `${bin.min}+` : `${bin.min}–${bin.max}`} kt
        </span>
      ))}
    </div>
  );
}
