import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { isFavorite, toggleFavorite, FAVORITES_EVENT } from "../lib/account";
import { BookmarkIcon, BookmarkFilledIcon } from "../lib/icons";
import type { Spot } from "../lib/types";

/** Compact save/bookmark toggle (no label). Logged out → sign-in prompt;
 *  logged in → the real favorites endpoint (`/account/favorites/:id`). */
export default function FavoriteButton({ spot }: { spot: Spot }) {
  const id = spot.uuid ?? spot.id;
  const { user } = useAuth();
  const navigate = useNavigate();
  const [fav, setFav] = useState(() => isFavorite(id));

  useEffect(() => {
    const sync = () => setFav(isFavorite(id));
    window.addEventListener(FAVORITES_EVENT, sync);
    return () => window.removeEventListener(FAVORITES_EVENT, sync);
  }, [id]);

  const onClick = () => {
    if (!user) {
      navigate("/anmelden");
      return;
    }
    setFav(toggleFavorite({ id, name: spot.name, region: spot.region, sports: spot.sports }));
  };

  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={fav}
      aria-label={fav ? "Aus Favoriten entfernen" : "Zu Favoriten hinzufügen"}
      title={fav ? "In Favoriten gespeichert" : "Zu Favoriten hinzufügen"}
      className="grid h-10 w-10 place-items-center rounded-full border border-line text-ink transition-colors hover:bg-band active:scale-[0.97] focus:outline-none focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink"
    >
      {fav ? <BookmarkFilledIcon className="text-sz-18" /> : <BookmarkIcon className="text-sz-18" />}
    </button>
  );
}
