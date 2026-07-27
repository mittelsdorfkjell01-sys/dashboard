import type { RegionMonth } from "../lib/types";

/**
 * The region's core answer: each month is a bar whose height is the share of the
 * region's spots that work that month (the backend's `spots_working`), so you
 * read the travel window at a glance. Peak months are filled ink and called out
 * as badges below. Mirrors the Windmonate look.
 *
 * Headless by design — the enclosing editorial SectionBand supplies the section
 * heading, so this renders only the reading + its caption.
 */
export default function RegionSeason({
  season,
  bestMonths,
}: {
  season: RegionMonth[];
  bestMonths: string[];
}) {
  const peak = Math.max(1, ...season.map((m) => m.working));
  const total = season[0]?.total ?? 0;

  return (
    <div>
      <div className="mb-1 flex justify-end">
        <span className="text-[12px] text-muted">Spots, die gleichzeitig laufen · von {total}</span>
      </div>

      {/* Each column is h-full so it has a definite height for the bars'
          percentage heights to resolve against — the row's items-end alone
          would leave the column auto-sized and every bar 0px tall. */}
      <div className="mt-5 flex h-44 gap-2 sm:gap-3">
        {season.map((m) => {
          const strong = m.working >= peak * 0.85;
          const share = m.working / Math.max(1, m.total);
          return (
            <div
              key={m.month}
              className="flex h-full flex-1 flex-col items-center justify-end gap-2"
            >
              <div
                className={`w-full max-w-[26px] rounded-t-[4px] transition-colors ${
                  strong ? "bg-ink" : "bg-ink/35"
                }`}
                style={{ height: `${Math.max(5, share * 100)}%` }}
                title={`${m.month}: ${m.working} von ${m.total} Spots · Ø ${m.wind} kts`}
              />
              <span className="text-[10.5px] font-medium tracking-wide text-muted">{m.month}</span>
            </div>
          );
        })}
      </div>

      {bestMonths.length > 0 && (
        <div className="mt-6 flex flex-wrap items-center gap-2">
          <span className="text-[12px] text-muted">Beste Reisezeit:</span>
          {bestMonths.map((mo) => (
            <span
              key={mo}
              className="inline-flex items-center rounded-2xl bg-orange/15 px-3 py-1 text-[12px] font-medium text-ink"
            >
              {mo}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
