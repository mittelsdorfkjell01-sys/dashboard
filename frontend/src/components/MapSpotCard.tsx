import { Link } from "react-router-dom";
import type { Spot } from "../lib/types";
import { WindBadge } from "./SpotBits";
import SpotImage from "./SpotImage";

/** Compact card used in the map's recommended strip and as the pin popup. */
export default function MapSpotCard({
  spot,
  className = "",
}: {
  spot: Spot;
  className?: string;
}) {
  return (
    <Link
      to={`/spot/${spot.id}`}
      className={`block overflow-hidden rounded-2xl border border-line bg-white ${className}`}
    >
      <div className="aspect-[16/7] w-full bg-line">
        <SpotImage src={spot.image} name={spot.name} region={spot.region} compact />
      </div>
      <div className="px-3 py-2.5">
        <p className="truncate text-[12px] italic text-muted">{spot.region}</p>
        <div className="mt-0.5 flex items-center justify-between gap-2">
          <h4 className="truncate text-[15px] font-semibold text-ink">{spot.name}</h4>
          <WindBadge value={spot.wind} />
        </div>
      </div>
    </Link>
  );
}
