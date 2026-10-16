// Formatting for the V3 wind-climatology "best season" window — shared by the
// detailed Windmonate module (dark Daten page) and the lightweight summary
// lines on the Daten header and Info tab, so the label reads identically
// everywhere without pulling the heavy lazy module into those bundles.

const MONTHS = [
  "Januar", "Februar", "März", "April", "Mai", "Juni",
  "Juli", "August", "September", "Oktober", "November", "Dezember",
];

/** Format a V3 best_season month-day range (both "MM-DD" strings) as a German
 *  label, e.g. "15. Juni – 20. September" (or "15.–20. Juni" within one month). */
export function formatMonthDayRange(startDate: string, endDate: string): string {
  const [startMonth, startDay] = startDate.split("-").map(Number);
  const [endMonth, endDay] = endDate.split("-").map(Number);
  if (startMonth === endMonth) return `${startDay}.–${endDay}. ${MONTHS[startMonth - 1]}`;
  return `${startDay}. ${MONTHS[startMonth - 1]} – ${endDay}. ${MONTHS[endMonth - 1]}`;
}
