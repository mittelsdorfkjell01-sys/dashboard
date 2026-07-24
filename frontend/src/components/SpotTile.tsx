import { useEffect, useState, type MouseEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import SpotImage from "./SpotImage";
import { sportLabel } from "../lib/labels";
import { useAuth } from "../context/AuthContext";
import { isFavorite, toggleFavorite, FAVORITES_EVENT } from "../lib/account";
import { HeartIcon, HeartFilledIcon } from "../lib/icons";
import type { Spot } from "../lib/types";
import type { LiveConditionsRead } from "../lib/api";

// Live wind (kt) above which we treat a spot as "running now" (orange dot).
const RUNNING_WIND_KT = 12;

/** German-comma wave height, or an honest em-dash when live is missing. */
const fmtWave = (m?: number | null) =>
  typeof m === "number" ? `${m.toFixed(1).replace(".", ",")} m` : "—";

/**
 * Glass-overlay top-spot tile (Frame_1/5). Wind comes from the list record
 * immediately; live wave + the "running" dot come from the batch live lookup
 * passed in by the parent row (one request for the whole row, best-effort).
 * Missing live values show "—" / a neutral dot — never an invented constant.
 */
export default function SpotTile({
  spot,
  live,
}: {
  spot: Spot;
  live?: LiveConditionsRead | null;
}) {
  const id = spot.uuid ?? spot.id;
  const { user } = useAuth();
  const navigate = useNavigate();
  const [fav, setFav] = useState(() => isFavorite(id));
  useEffect(() => {
    const sync = () => setFav(isFavorite(id));
    window.addEventListener(FAVORITES_EVENT, sync);
    return () => window.removeEventListener(FAVORITES_EVENT, sync);
  }, [id]);

  // Toggle without triggering the tile's navigation; prompt sign-in when needed.
  const onFav = (e: MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (!user) {
      navigate("/anmelden");
      return;
    }
    setFav(toggleFavorite({ id, name: spot.name, region: spot.region, sports: spot.sports }));
  };

  const liveWind = live?.current.wind ?? null;
  const wind = liveWind ?? (spot.wind || null);
  const wave = live?.current.swell ?? null;
  const running = liveWind != null && liveWind >= RUNNING_WIND_KT;
  const tags = (spot.sports ?? []).slice(0, 4).map(sportLabel);

  return (
    <Link
      to={`/spot/${id}`}
      className="group relative block h-[190px] w-full overflow-hidden rounded-3xl"
    >
      <div className="absolute inset-0">
        <SpotImage
          src={spot.image}
          name={spot.name}
          region={spot.region}
          compact
          className="transition-transform duration-500 group-hover:scale-105"
        />
      </div>
      <div className="absolute inset-0 bg-gradient-to-t from-black/50 via-black/10 to-transparent" />

      <button
        type="button"
        onClick={onFav}
        aria-pressed={fav}
        aria-label={
          fav ? `${spot.name} aus Favoriten entfernen` : `${spot.name} zu Favoriten hinzufügen`
        }
        className="absolute right-2.5 top-2.5 z-10 grid h-9 w-9 place-items-center rounded-full bg-black/25 text-white backdrop-blur transition-colors hover:bg-black/45"
      >
        {fav ? (
          <HeartFilledIcon className="text-[18px] text-orange" />
        ) : (
          <HeartIcon className="text-[18px]" />
        )}
      </button>

      {/* bottom glass panel */}
      <div className="glass absolute inset-x-0 bottom-0 p-3.5 text-white">
        <p className="truncate text-[10px] font-medium text-white/90">{spot.region}</p>
        <div className="mt-0.5 flex items-start justify-between gap-2">
          <p className="min-w-0 truncate text-[15px] font-semibold">{spot.name}</p>
          <div className="shrink-0 text-right leading-tight">
            <p className="flex items-center justify-end gap-1 text-[13px] font-semibold">
              <span
                aria-hidden="true"
                className={`inline-block h-2 w-2 rounded-full ${
                  running ? "bg-orange" : "border border-white/70 bg-transparent"
                }`}
              />
              {running && <span className="sr-only">läuft gerade</span>}
              {fmtWave(wave)}
            </p>
            <p className="text-[13px] font-semibold">
              {wind != null ? `${Math.round(wind)} kts` : "—"}
            </p>
          </div>
        </div>
        {tags.length > 0 && (
          <p className="mt-1.5 flex flex-nowrap gap-x-2 overflow-hidden text-[10px] text-white/90">
            {tags.map((t) => (
              <span key={t} className="whitespace-nowrap">{t}</span>
            ))}
          </p>
        )}
      </div>
    </Link>
  );
}
