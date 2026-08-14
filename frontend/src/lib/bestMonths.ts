// Formats a spot tile's best_months (backend-persisted, see
// app.scoring.region.compute_spot_best_months) into a single "Apr - Okt"
// range for display. Mirrors seasonView.ts's bestSeasonWindow algorithm —
// longest run of consecutive months, wrapping the Dec→Jan boundary — but
// works directly off the already-decided month list instead of a
// threshold-against-weighted-means curve.

const MONTHS_SHORT = ["Jan", "Feb", "Mär", "Apr", "Mai", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"];

export function bestMonthsRange(months?: number[] | null): string | null {
  if (!months || months.length === 0) return null;
  const inSeason = Array.from({ length: 12 }, (_, i) => months.includes(i + 1));
  if (inSeason.every(Boolean)) return `${MONTHS_SHORT[0]} - ${MONTHS_SHORT[11]}`;

  // Walk the circle starting right after a month that's NOT in season, so a
  // run wrapping Dec→Jan counts as one contiguous stretch.
  const falseAt = inSeason.findIndex((v) => !v);
  let bestStart = -1;
  let bestLen = 0;
  let runStart = -1;
  let runLen = 0;
  for (let k = 0; k < 12; k++) {
    const i = (falseAt + 1 + k) % 12;
    if (inSeason[i]) {
      if (runLen === 0) runStart = i;
      runLen++;
      if (runLen > bestLen) {
        bestLen = runLen;
        bestStart = runStart;
      }
    } else {
      runLen = 0;
    }
  }
  if (bestStart === -1) return null;
  const endIndex = (bestStart + bestLen - 1) % 12;
  return bestStart === endIndex
    ? MONTHS_SHORT[bestStart]
    : `${MONTHS_SHORT[bestStart]} - ${MONTHS_SHORT[endIndex]}`;
}
