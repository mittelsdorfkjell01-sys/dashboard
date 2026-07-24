import { Link } from "react-router-dom";
import type { Spot } from "../lib/types";
import { WindBadge } from "./SpotBits";
import SpotImage from "./SpotImage";

/** Landing-grid card: image, region + name, wind reading.
 *  Category axes (level/water/style) are intentionally NOT shown here — they are
 *  filter/sort data (see SortDropdown), not visible pills.
 *
 *  `default` is the landing/search treatment. `editorial` is the larger,
 *  image-led variant for the region page grid: taller image, display-weight name
 *  first, meta demoted below it. */
export default function SpotCard({
  spot,
  variant = "default",
}: {
  spot: Spot;
  variant?: "default" | "editorial";
}) {
  const editorial = variant === "editorial";

  return (
    <Link to={`/spot/${spot.id}`} className="group block">
      <div
        className={`relative overflow-hidden rounded-2xl bg-line ${
          editorial ? "aspect-[4/3]" : "aspect-[16/11]"
        }`}
      >
        <SpotImage
          src={spot.image}
          name={spot.name}
          region={spot.region}
          className="transition-transform duration-500 group-hover:scale-[1.03] motion-reduce:transition-none motion-reduce:group-hover:scale-100"
        />
      </div>

      {editorial ? (
        <div className="mt-4">
          <h3 className="text-[22px] font-semibold leading-tight text-ink text-balance">
            {spot.name}
          </h3>
          <div className="mt-2 flex items-baseline justify-between gap-3">
            <p className="truncate text-[13px] text-muted">{spot.region}</p>
            <WindBadge value={spot.wind} />
          </div>
        </div>
      ) : (
        <div className="mt-3">
          <div className="flex items-baseline justify-between gap-3">
            <p className="truncate text-[12px] text-muted">{spot.region}</p>
            <WindBadge value={spot.wind} />
          </div>
          <h3 className="mt-1 text-lg font-semibold leading-tight text-ink">{spot.name}</h3>
        </div>
      )}
    </Link>
  );
}
