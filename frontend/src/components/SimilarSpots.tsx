import { useEffect, useState } from "react";
import { API_BASE, resolveMediaUrl } from "../lib/api";
import { useSpotsLive } from "../lib/hooks";
import { countryName } from "../lib/flags";
import SpotCard from "./SpotCard";
import type { Spot } from "../lib/types";

interface SimilarSpotApi {
  id: string;
  name: string;
  sports?: string[];
  region?: string | null;
  region_country?: string | null;
  image?: { url?: string | null } | null;
  wind?: number | null;
  wave_height?: number | null;
  description?: string | null;
}

function toCardSpot(item: SimilarSpotApi): Spot {
  return {
    id: item.id,
    name: item.name,
    region: [item.region, countryName(item.region_country ?? undefined)].filter(Boolean).join(", "),
    regionName: item.region ?? undefined,
    regionCountry: item.region_country ?? null,
    wind: item.wind ?? 0,
    typicalWindKt: item.wind ?? null,
    typicalWaveHeightM: item.wave_height ?? null,
    tags: [],
    image: resolveMediaUrl(item.image?.url) ?? "",
    sports: item.sports,
    description: item.description ?? undefined,
  };
}

export default function SimilarSpots({ spotId, sport }: { spotId: string; sport?: string }) {
  const [spots, setSpots] = useState<SimilarSpotApi[]>([]);
  const { data: live } = useSpotsLive(spots.map((s) => s.id));

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
          <div key={item.id} className="min-w-[clamp(196px,78vw,232px)] snap-start sm:min-w-0">
            <SpotCard spot={toCardSpot(item)} live={live?.get(item.id)} />
          </div>
        ))}
      </div>
    </section>
  );
}
