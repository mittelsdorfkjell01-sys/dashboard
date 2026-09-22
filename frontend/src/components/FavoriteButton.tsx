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
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const sync = () => setFav(isFavorite(id));
    window.addEventListener(FAVORITES_EVENT, sync);
    return () => window.removeEventListener(FAVORITES_EVENT, sync);
  }, [id]);

  const onClick = async () => {
    if (!user) {
      navigate("/anmelden");
      return;
    }
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      setFav(await toggleFavorite({ id, name: spot.name, region: spot.region, sports: spot.sports }));
    } catch {
      setError("Speichern fehlgeschlagen. Erneut versuchen.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <span className="relative inline-flex">
    <button
      type="button"
      onClick={() => void onClick()}
      disabled={busy}
      aria-pressed={fav}
      aria-label={fav ? "Aus Favoriten entfernen" : "Zu Favoriten hinzufügen"}
      title={fav ? "In Favoriten gespeichert" : "Zu Favoriten hinzufügen"}
      className="grid h-11 w-11 place-items-center rounded-full border border-line text-ink transition-colors hover:bg-band active:scale-[0.97] disabled:opacity-60 focus:outline-none focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink"
    >
      {fav ? <BookmarkFilledIcon className="text-sz-18" /> : <BookmarkIcon className="text-sz-18" />}
    </button>
    {error && <span role="alert" className="absolute left-0 top-full z-10 mt-1 w-44 rounded-lg bg-danger-bg p-2 text-caption text-danger">{error}</span>}
    </span>
  );
}
