import { useMemo } from "react";
import type { Map as MapLibreMap } from "maplibre-gl";
import Supercluster from "supercluster";
import type { Spot } from "../lib/types";
import { spotFeatures, type PublicSpotProperties } from "../lib/publicMap";
import { EditorialMarkIcon } from "../lib/icons";
import type { DecodedFieldTile } from "../weather-map/fieldTile";
import type { ExplorerMode } from "../weather-map/fieldUrlState";
import { bearingOf, sampleTiles, waveReading, windReading, type WaveComponent } from "./fieldSample";
import { CALM_KN } from "./ArrowLayer";

/** Groups dissolve into single spots from this shared (Leaflet) zoom on. */
const SINGLES_FROM_ZOOM = 8;
/** In Spots mode, names appear from here. */
const NAME_MIN_ZOOM = 10;

/** A spot sits on the beach; the wave model's nearest sea cell may be a few
 *  kilometres out. Look outward in a small ring before giving up — and if
 *  nothing answers, there is no value (missing data is never a zero). */
function waveNear(tiles: DecodedFieldTile[], lon: number, lat: number, component: WaveComponent) {
  const direct = waveReading(sampleTiles(tiles, lon, lat), component);
  if (direct) return direct;
  for (const radius of [0.03, 0.06]) {
    for (let index = 0; index < 8; index += 1) {
      const angle = (index / 8) * Math.PI * 2;
      const found = waveReading(sampleTiles(tiles, lon + Math.cos(angle) * radius * 1.6, lat + Math.sin(angle) * radius), component);
      if (found) return found;
    }
  }
  return null;
}

export type SpotValue =
  | { kind: "wind"; knots: number; bearing: number; calm: boolean }
  | { kind: "waves"; height: number; period?: number; bearing: number };

/** The field's value at a spot — used by the spot list, never drawn on the
 *  map (2026-11-20: the values moved off the map into the card). */
export function spotValue(spot: Spot, tiles: DecodedFieldTile[], mode: ExplorerMode, component: WaveComponent): SpotValue | null {
  if (!spot.coords || !tiles.length || mode === "spots") return null;
  const [lat, lon] = spot.coords;
  if (mode === "wind") {
    const wind = windReading(sampleTiles(tiles, lon, lat));
    return wind ? { kind: "wind", knots: wind.knots, bearing: bearingOf(wind.u, wind.v), calm: wind.knots < CALM_KN } : null;
  }
  const wave = waveNear(tiles, lon, lat, component);
  return wave ? { kind: "waves", height: wave.height, period: wave.period, bearing: bearingOf(wave.dx, wave.dy) } : null;
}

/**
 * Spot dots and groups over the map. Only the mark itself: since 2026-11-20
 * no values hang over the spots — a tap opens the card above the forecast
 * tile, which carries them.
 */
export default function SpotMarks({
  map,
  viewTick,
  spots,
  mode,
  selectedId,
  originsMixed,
  onSelect,
}: {
  map: MapLibreMap;
  /** Bumped on every camera frame; the marks re-project from it. */
  viewTick: number;
  spots: Spot[];
  mode: ExplorerMode;
  selectedId?: string;
  originsMixed: boolean;
  onSelect: (spot: Spot) => void;
}) {
  const byId = useMemo(() => new Map(spots.map((spot) => [spot.id, spot])), [spots]);
  const index = useMemo(() => {
    const cluster = new Supercluster<PublicSpotProperties>({ radius: 44, maxZoom: SINGLES_FROM_ZOOM - 1 });
    cluster.load(spotFeatures(spots) as Supercluster.PointFeature<PublicSpotProperties>[]);
    return cluster;
  }, [spots]);

  void viewTick;
  const zoom = map.getZoom() + 1; // shared (Leaflet) convention
  const bounds = map.getBounds();
  const container = map.getContainer();
  const features = index.getClusters([bounds.getWest() - 0.5, bounds.getSouth() - 0.5, bounds.getEast() + 0.5, bounds.getNorth() + 0.5], Math.floor(zoom));
  const width = container.clientWidth, height = container.clientHeight;

  return (
    <div className="swd-pm-marks" aria-label="Spots auf der Karte">
      {features.map((feature) => {
        const [lon, lat] = feature.geometry.coordinates;
        const point = map.project([lon, lat]);
        if (point.x < -60 || point.y < -60 || point.x > width + 60 || point.y > height + 60) return null;
        const props = feature.properties as Supercluster.ClusterProperties & PublicSpotProperties;
        if (props.cluster) {
          const count = props.point_count;
          const size = count < 10 ? 30 : count < 50 ? 36 : 42;
          return (
            <button
              key={`c${props.cluster_id}`}
              type="button"
              className="swd-pm-cluster font-num"
              style={{ width: size, height: size, transform: `translate(${Math.round(point.x - size / 2)}px, ${Math.round(point.y - size / 2)}px)` }}
              aria-label={`${count} Spots. Heranzoomen`}
              onClick={(event) => {
                event.stopPropagation();
                const next = Math.min(index.getClusterExpansionZoom(props.cluster_id), SINGLES_FROM_ZOOM);
                map.easeTo({ center: [lon, lat], zoom: next - 1, duration: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? 0 : 500 });
              }}
            >
              {count}
            </button>
          );
        }
        const spot = byId.get(props.spotId);
        if (!spot) return null;
        const selected = spot.id === selectedId;
        const community = originsMixed && spot.origin === "community";
        const editorial = originsMixed && spot.origin !== "community";
        const showName = selected || (mode === "spots" && zoom >= NAME_MIN_ZOOM);
        return (
          <button
            key={spot.id}
            type="button"
            className={`swd-pm-spot${selected ? " is-selected" : ""}${community ? " is-community" : ""}${editorial ? " is-editorial" : ""}`}
            style={{ transform: `translate(${Math.round(point.x)}px, ${Math.round(point.y)}px)` }}
            aria-label={community ? `${spot.name}, von der Community eingetragen` : spot.name}
            aria-pressed={selected}
            onClick={(event) => { event.stopPropagation(); onSelect(spot); }}
          >
            <span className="swd-pm-dot">{editorial && <EditorialMarkIcon width={10} height={10} />}</span>
            {showName && <span className="swd-pm-name text-caption font-medium">{spot.name}</span>}
          </button>
        );
      })}
    </div>
  );
}
