import { useEffect, useState } from "react";
import { API_BASE } from "../lib/api";
import SpotCard from "./SpotCard";
import type { Spot } from "../lib/types";

// The `/similar` endpoint only returns id/slug/name/location/sports (see
// app/search/pins.py::spot_brief) — no image, region, wind or description.
// SpotCard renders those as its existing empty states (image fallback, no
// region line, "—" wind) rather than inventing values that aren't there.
interface SimilarSpotApi {
  id: string;
  name: string;
  sports?: string[];
}

function toCardSpot(item: SimilarSpotApi): Spot {
  return {
    id: item.id,
    name: item.name,
    region: "",
    wind: 0,
    tags: [],
    image: "",
    sports: item.sports,
  };
}

export default function SimilarSpots({ spotId, sport }: { spotId: string; sport?: string }) {
  const [spots, setSpots] = useState<SimilarSpotApi[]>([]);

  useEffect(() => {
    const controller = new AbortController();
    const query = new URLSearchParams({ mode: "charakter", limit: "5" });
    if (sport) query.set("sport", sport);
    fetch(`${API_BASE}/spots/${encodeURIComponent(spotId)}/similar?${query}`, { signal: controller.signal })
      .then((response) => (response.ok ? response.json() : Promise.reject(new Error("similar spots unavailable"))))
      .then((body: { results?: SimilarSpotApi[] }) => setSpots(body.results ?? []))
      .catch((error: unknown) => {
        if (!(error instanceof DOMException && error.name === "AbortError")) setSpots([]);
      });
    return () => controller.abort();
  }, [spotId, sport]);

  if (!spots.length) return null;

  return (
    <section aria-labelledby="similar-spots-heading">
      <div className="flex items-end justify-between gap-4 border-b border-line pb-3">
        <div>
          <h2 id="similar-spots-heading" className="text-title font-semibold text-ink">Ähnliche Spots</h2>
          <p className="mt-1 text-caption text-muted">Spots mit vergleichbarem Charakter</p>
        </div>
      </div>
      <div className="no-scrollbar mt-5 flex snap-x-mandatory gap-4 overflow-x-auto pb-2 sm:grid sm:grid-cols-3 sm:overflow-visible sm:pb-0 lg:grid-cols-5">
        {spots.map((item) => (
          <div key={item.id} className="min-w-[220px] snap-start sm:min-w-0">
            <SpotCard spot={toCardSpot(item)} />
          </div>
        ))}
      </div>
    </section>
  );
}
