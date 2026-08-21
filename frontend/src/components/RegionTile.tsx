import { Link } from "react-router-dom";
import SpotImage from "./SpotImage";
import { usableMediaUrl } from "../lib/api";
import { countryName } from "../lib/flags";
import { sportLabel } from "../lib/labels";

/**
 * Region result tile — the region counterpart of SpotCard, built to the same
 * grammar: one framed `aspect-video` image with nothing laid over it, then
 * three quiet lines below (name + spot count, geography, sports). No
 * background, border or shadow on the card itself; no hover motion. Mirrors
 * SpotCard's focus ring and full-tile click target so a region and a spot
 * read as the same product.
 *
 * Unreachable seed image hosts (the `*.local` sentinel) are treated as "no
 * image" so the branded SpotImage fallback field renders instead.
 */
export default function RegionTile({
  slug,
  name,
  country,
  image,
  spotCount,
  sports,
}: {
  slug: string;
  name: string;
  country?: string | null;
  image?: string | null;
  /** Published spots in the region (region.spot_count). */
  spotCount?: number | null;
  /** Unique sports across the region's published spots (region.sports). */
  sports?: string[] | null;
}) {
  const usable = usableMediaUrl(image);
  const to = slug ? `/region/${slug}` : "#";
  const geography = countryName(country ?? undefined) || country || "";
  const sportsLine = (sports ?? []).map(sportLabel).join(" · ");

  return (
    <Link
      to={to}
      className="swd-mobile-deferred-card group flex h-full flex-col rounded-2xl focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal"
    >
      <div className="relative aspect-video overflow-hidden rounded-2xl">
        <SpotImage src={usable} name={name} region={geography || undefined} compact />
      </div>

      <div className="flex flex-1 flex-col gap-0 pt-1.5 sm:pt-2">
        <div className="flex items-baseline justify-between gap-3">
          <p className="min-w-0 truncate text-body font-semibold text-ink">{name}</p>
          {typeof spotCount === "number" && (
            <span className="shrink-0 whitespace-nowrap text-label font-semibold text-ink">
              {spotCount} {spotCount === 1 ? "Spot" : "Spots"}
            </span>
          )}
        </div>

        {geography && <p className="truncate text-[11px] text-muted sm:text-caption">{geography}</p>}

        {sportsLine && (
          <p className="mt-auto truncate pt-1 text-[11px] text-muted sm:text-caption">{sportsLine}</p>
        )}
      </div>
    </Link>
  );
}
