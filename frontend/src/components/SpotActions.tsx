import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import FavoriteButton from "./FavoriteButton";
import ShareButton from "./ShareButton";
import SuggestEditButton from "./SuggestEditButton";
import VisitedButton from "./VisitedButton";
import { CalendarIcon } from "../lib/icons";
import type { Spot } from "../lib/types";

/**
 * The spot's own actions: save, share, visited, plan a trip, suggest an edit.
 *
 * One row, rendered in exactly one place at a time — on desktop under the
 * community gallery, on phones at the head of the profile column. The page
 * picks the place with `useDesktopViewport`; this component is deliberately
 * NOT duplicated behind `hidden lg:flex` / `lg:hidden`, because a CSS-hidden
 * copy keeps its listeners and has already cost this app a bug where an
 * invisible desktop control swallowed taps meant for the mobile one.
 */
export default function SpotActions({
  spot,
  spotId,
  className = "",
}: {
  spot: Spot;
  spotId?: string;
  className?: string;
}) {
  const { t } = useTranslation();
  return (
    <div className={`flex flex-wrap items-center justify-center gap-2 ${className}`}>
      <FavoriteButton spot={spot} />
      <ShareButton spot={spot} />
      {spotId && <VisitedButton spotId={spotId} />}
      {spotId && (
        <Link
          to={`/konto/reisen?spotId=${encodeURIComponent(spotId)}&spotName=${encodeURIComponent(spot.name)}`}
          aria-label={t("trips.planSpot")}
          title={t("trips.planSpot")}
          className="grid h-11 w-11 place-items-center rounded-full border border-line text-ink transition-colors hover:bg-band"
        >
          <CalendarIcon className="text-lead" />
        </Link>
      )}
      <SuggestEditButton spot={spot} />
    </div>
  );
}
