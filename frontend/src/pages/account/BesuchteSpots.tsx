import { Link } from "react-router-dom";
import { PinIcon, SearchIcon } from "../../lib/icons";
import { AccountPage } from "./AccountLayout";

/**
 * "Spots besucht" — the spots a visitor has actually been to. The backend that
 * records visits is not built yet, so this shows an editorial empty state that
 * mirrors the Favoriten placeholder. Once the API lands, list the visited spots
 * here the same way Favoriten renders its collection.
 */
export default function BesuchteSpots() {
  return (
    <AccountPage title="Spots besucht">
      <div className="rounded-[14px] border border-dashed border-line bg-surface px-6 py-14 text-center">
        <span className="mx-auto grid h-14 w-14 place-items-center rounded-[14px] bg-band text-ink">
          <PinIcon className="text-sz-24" />
        </span>
        <h2 className="mt-4 text-sz-17 font-semibold text-ink">Noch keine besuchten Spots</h2>
        <p className="mx-auto mt-1 max-w-[38ch] text-ui text-muted">
          Hier sammeln sich die Spots, an denen du wirklich warst. Diese Funktion kommt bald.
        </p>
        <Link
          to="/search"
          className="mt-5 inline-flex items-center gap-2 px-4 py-2 text-ui font-semibold text-ink transition-opacity hover:underline hover:underline-offset-4 hover:opacity-70"
        >
          <SearchIcon className="text-sz-16" />
          Spots entdecken
        </Link>
      </div>
    </AccountPage>
  );
}
