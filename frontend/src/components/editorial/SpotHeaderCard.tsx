/**
 * The glass namebox — floats over the hero's bottom edge. Breadcrumb
 * (region › country) and the spot name on the left, the community score on
 * the right. Per the Figma spec this is deliberately translucent + blurred
 * (unlike the rest of the app's "opaque surfaces only" rule) — the hero stays
 * faintly visible through it.
 *
 * The score is never a fabricated placeholder: it's the real Bayesian rating
 * aggregate the backend already computes from published star ratings
 * (`app/community/aggregate.py`, 0–5 scale), shown ×2 to match this design's
 * 0–10 scale. A spot with no ratings yet shows the prior mean (currently
 * 3.5 → "7.0") — a real statistical default, not an invented number, but it
 * will look the same across every unrated spot until real ratings come in.
 */
export default function SpotHeaderCard({
  name,
  regionName,
  country,
  score,
}: {
  name: string;
  regionName?: string;
  country?: string;
  /** 0–5 scale (`RatingAggregate.score`); rendered ×2. Omitted entirely
   *  (not "—") when there's truly no reading yet. */
  score?: number | null;
}) {
  const breadcrumb = [regionName, country].filter(Boolean).join(" › ");

  return (
    <div className="relative z-20 -mt-16 max-w-[1180px] rounded-[28px] bg-white/50 px-6 py-7 backdrop-blur-md sm:-mt-20 sm:px-10 sm:py-8">
      <div className="flex flex-wrap items-end justify-between gap-6">
        <div className="min-w-0">
          {breadcrumb && <p className="text-label text-ink-soft/80">{breadcrumb}</p>}
          <h1 className="mt-1 text-editorial-2 font-semibold text-balance text-ink">{name}</h1>
        </div>

        {typeof score === "number" && (
          <span className="shrink-0 text-stat font-semibold leading-none tabular-nums text-ink-soft">
            {(score * 2).toFixed(1)}
          </span>
        )}
      </div>
    </div>
  );
}
