import { Link } from "react-router-dom";
import { GridIcon, MapIcon } from "../lib/icons";

/**
 * Grid | Karte switch above the top-spots list. Per the mock it is an
 * outlined white pill — both items in ink with a hairline divider between,
 * no filled/selected background.
 */
export default function ViewToggle({ active }: { active: "grid" | "map" }) {
  const item =
    "flex items-center gap-2 px-5 py-2.5 text-[16px] font-medium text-ink transition-colors hover:text-teal";
  return (
    <div className="inline-flex items-center rounded-full border border-line bg-white px-1">
      <Link to="/" className={item} aria-current={active === "grid" ? "page" : undefined}>
        <GridIcon className="text-[18px]" />
        Grid
      </Link>
      <span className="my-2 h-6 w-px bg-line" />
      <Link to="/map" className={item} aria-current={active === "map" ? "page" : undefined}>
        <MapIcon className="text-[18px]" />
        Karte
      </Link>
    </div>
  );
}
