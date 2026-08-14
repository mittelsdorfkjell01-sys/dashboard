import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { isFavorite, toggleFavorite, FAVORITES_EVENT } from "../lib/account";
import type { Spot } from "../lib/types";

/** Primary "zu Favoriten hinzufügen" toggle. Logged out → sign-in prompt;
 *  logged in → the real favorites endpoint (`/account/favorites/:id`),
 *  which already exists. */
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
      className="min-h-11 px-5 py-2.5 text-label font-semibold text-ink transition-opacity hover:underline hover:underline-offset-4 hover:opacity-70"
    >
      {fav ? "in Favoriten" : "zu Favoriten hinzufügen"}
    </button>
  );
}
