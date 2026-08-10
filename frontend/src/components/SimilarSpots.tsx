import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { API_BASE } from "../lib/api";
import { sportLabel } from "../lib/labels";

interface SimilarSpot {
  id: string;
  name: string;
  sports?: string[];
}

export default function SimilarSpots({ spotId, sport }: { spotId: string; sport?: string }) {
  const [spots, setSpots] = useState<SimilarSpot[]>([]);

  useEffect(() => {
    const controller = new AbortController();
    const query = new URLSearchParams({ mode: "charakter", limit: "3" });
    if (sport) query.set("sport", sport);
    fetch(`${API_BASE}/spots/${encodeURIComponent(spotId)}/similar?${query}`, { signal: controller.signal })
      .then((response) => (response.ok ? response.json() : Promise.reject(new Error("similar spots unavailable"))))
      .then((body: { results?: SimilarSpot[] }) => setSpots(body.results ?? []))
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
      <div className="no-scrollbar mt-5 flex snap-x-mandatory gap-4 overflow-x-auto pb-2 sm:grid sm:grid-cols-3 sm:overflow-visible sm:pb-0">
        {spots.map((item, index) => (
          <Link key={item.id} to={`/spot/${item.id}`} className="group min-w-[220px] snap-start sm:min-w-0">
            <div className="aspect-[16/10] overflow-hidden rounded-2xl bg-band">
              <div className="grid h-full place-items-center bg-[radial-gradient(circle_at_top_left,var(--sw-teal),transparent_70%)] text-caption font-medium text-ink-soft">
                {String(index + 1).padStart(2, "0")}
              </div>
            </div>
            <h3 className="mt-3 truncate text-ui font-semibold text-ink transition-colors group-hover:text-teal">{item.name}</h3>
            {item.sports?.length ? (
              <p className="mt-1 truncate text-caption text-muted">{item.sports.slice(0, 2).map(sportLabel).join(" · ")}</p>
            ) : null}
          </Link>
        ))}
      </div>
    </section>
  );
}
