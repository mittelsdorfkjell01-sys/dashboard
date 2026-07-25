import { Link } from "react-router-dom";
import SpotImage from "./SpotImage";
import { usableMediaUrl } from "../lib/api";

// One-letter month ticks for the wind-months strip (Jan … Dez).
const MONTH_INITIALS = ["J", "F", "M", "A", "M", "J", "J", "A", "S", "O", "N", "D"];

/**
 * Region result tile in the landing/top-spots grammar: a hero
 * image (or the branded SpotImage fallback), a bottom opaque teal caption panel
 * with the region name + country, the season **coverage** as the tile's metric, and a
 * 12-month **wind-months** strip (region.season.best_months) so you can read the
 * best time at a glance — any pattern, including non-contiguous months.
 *
 * Mirrors SpotTile so the search board reads as "the same site". Unreachable
 * seed image hosts (the `*.local` sentinel) are treated as "no image" so the
 * branded SpotImage fallback field renders instead.
 */
export default function RegionTile({
  slug,
  name,
  country,
  image,
  coverage,
  rank,
  windMonths,
}: {
  slug: string;
  name: string;
  country?: string | null;
  image?: string | null;
  coverage?: number | null;
  rank?: number;
  /** Best wind months as 1..12 numbers (region.season.best_months). */
  windMonths?: number[] | null;
}) {
  const usable = usableMediaUrl(image);
  const pct = typeof coverage === "number" ? Math.round(coverage * 100) : null;
  const months = windMonths ?? [];
  const to = slug ? `/region/${slug}` : "#";

  return (
    <Link
      to={to}
      className="group relative block h-[252px] w-full overflow-hidden rounded-3xl"
    >
      <div className="absolute inset-0">
        <SpotImage
          src={usable}
          name={name}
          region={country ?? undefined}
          compact
          className="transition-transform duration-500 group-hover:scale-105"
        />
      </div>
      <div className="absolute inset-0 bg-gradient-to-t from-black/55 via-black/10 to-transparent" />

      {typeof rank === "number" && (
        <span className="absolute left-3 top-3 inline-flex h-7 min-w-[28px] items-center justify-center rounded-full border border-line bg-white px-2 text-[13px] font-bold text-ink">
          {rank}
        </span>
      )}

      {/* bottom glass panel */}
      <div className="glass absolute inset-x-0 bottom-0 p-3.5 text-white">
        {country && (
          <p className="truncate text-[10px] font-medium uppercase tracking-[0.08em] text-white/85">
            {country}
          </p>
        )}
        <div className="mt-0.5 flex items-end justify-between gap-2">
          <p className="min-w-0 truncate text-[15px] font-semibold">{name}</p>
          {pct != null && (
            <span className="shrink-0 text-right leading-tight">
              <span className="block text-[15px] font-semibold">{pct}%</span>
              <span className="block text-[10px] text-white/80">Abdeckung</span>
            </span>
          )}
        </div>

        {months.length > 0 && (
          <div className="mt-2.5">
            <div className="mb-1 text-[9px] font-medium uppercase tracking-[0.12em] text-white/70">
              Windmonate
            </div>
            <div className="grid grid-cols-12 gap-[2px]">
              {MONTH_INITIALS.map((mi, i) => {
                const on = months.includes(i + 1);
                return (
                  <div key={i} className="text-center">
                    <div
                      className={`h-[6px] rounded-[1px] ${on ? "bg-white" : "bg-white/25"}`}
                    />
                    <div
                      className={`mt-[2px] text-[7px] leading-none ${
                        on ? "font-bold text-white" : "text-white/45"
                      }`}
                    >
                      {mi}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </Link>
  );
}
