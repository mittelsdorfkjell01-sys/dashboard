import { Link } from "react-router-dom";
import { ChevronRightIcon, EditorialMarkIcon } from "../lib/icons";

/**
 * The bar for a tapped spot on the Spots map (2026-11-20): name and region,
 * and on the right the way to the spot — nothing else. The wind and wave
 * maps carry no bar; their time tile links to the spot's Daten tab instead.
 */
export default function SpotBar({
  title,
  editorial,
  meta,
  href,
}: {
  title: string;
  editorial: boolean;
  meta: string;
  href: string;
}) {
  return (
    <section className="swd-pm-bar" aria-label={title}>
      <div className="swd-pm-bar-row">
        <div className="min-w-0 flex-1">
          <h2 className="flex items-center gap-1.5 text-ui font-semibold text-ink">
            <span className="truncate">{title}</span>
            {editorial && <EditorialMarkIcon className="shrink-0 text-caption text-ink-soft" aria-label="Redaktioneller Spot" role="img" />}
          </h2>
          {meta && <p className="truncate text-caption text-muted">{meta}</p>}
        </div>
        <Link to={href} className="swd-pm-bar-link text-caption font-semibold text-accent">
          <span>Zum Spot</span>
          <ChevronRightIcon className="text-ui" />
        </Link>
      </div>
    </section>
  );
}
