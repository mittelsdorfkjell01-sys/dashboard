import { useEffect, useRef, useState } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import "../map.css";
import type { LiveConditionsRead } from "../lib/api";
import type { NormalizedForecastSeries } from "../lib/forecastNormalization";
import { useOptionalSpotDataScope } from "../state/SpotDataScope";
import { spotDotColor, type PublicMapMode } from "../lib/publicMap";
import { windColor } from "../lib/windScale";
import { waveColor } from "../lib/waveScale";
import { currentReading, OBSERVATION_BADGE } from "../lib/spotMapReading";
import MapModeSwitch from "./MapModeSwitch";
import MapLegend from "./MapLegend";
import { cartoTileUrl, CARTO_ATTRIBUTION, CARTO_VOYAGER } from "../lib/basemaps";
import type { Spot } from "../lib/types";
import LeafletAttributionDisclosure from "./LeafletAttributionDisclosure";

// Match the public map's softly coloured travel-map basemap.
const TILE_URL = cartoTileUrl(CARTO_VOYAGER);
const TILE_ATTRIBUTION = CARTO_ATTRIBUTION;
const SPOT_MAP_ZOOM = 14.5; // matches SpotMapEditor's DEFAULT_ZOOM, so an un-framed spot lines up with what an admin sees while framing it

function dotIcon(color: string): L.DivIcon {
  return L.divIcon({
    html: `<span class="swd-map-dot" style="background:${color}"></span>`,
    className: "swd-map-dot-icon",
    iconSize: [22, 22],
    iconAnchor: [11, 11],
  });
}

/** Directional marker: the same magnitude-coloured disc as `dotIcon`, plus a
 *  beak pointing the way the wind/swell travels TO. `rotation` is a screen-space
 *  bearing (0 = north), pre-derived from the real comes-from reading — never
 *  drawn when direction is null, so the disc never implies a direction it
 *  doesn't have. */
function vaneIcon(color: string, rotation: number): L.DivIcon {
  return L.divIcon({
    className: "swd-map-vane",
    html: `<svg width="28" height="28" viewBox="0 0 28 28" aria-hidden="true">
      <g transform="rotate(${rotation.toFixed(1)} 14 14)">
        <path d="M14 1.6 L17.5 8.4 L10.5 8.4 Z" fill="#FFFDF8" stroke="rgba(18,28,28,0.4)" stroke-width="0.75" stroke-linejoin="round" />
      </g>
      <circle cx="14" cy="14" r="7" fill="${color}" stroke="#FFFDF8" stroke-width="2" />
    </svg>`,
    iconSize: [28, 28],
    iconAnchor: [14, 14],
  });
}

const clamp = (value: number, lo: number, hi: number) => Math.max(lo, Math.min(hi, value));

/** Qualitative point-flow overlay: thin streaks drifting the way the active
 *  mode's reading travels, paced by its strength. This is NOT a spatial field —
 *  it visualises the spot's single point value (same direction everywhere), so
 *  it renders only when both magnitude and a real comes-from direction exist,
 *  never a fabricated flow. Drift only (no in-place sea-state marks): without a
 *  water mask those would fall on land, which the map brief forbids. The
 *  `swd-wind-streak` keyframe + reduced-motion handling live in map.css. */
function FlowLayer({ mode, reading }: { mode: PublicMapMode; reading: ReturnType<typeof currentReading> }) {
  if (!reading) return null;
  const isWind = mode === "wind";
  const mag = isWind ? reading.windKt : reading.waveM;
  const dir = isWind ? reading.windDir : reading.waveDir;
  if (mag == null || !Number.isFinite(mag) || dir == null || !Number.isFinite(dir)) return null;

  const bearing = (dir + 180) % 360; // comes-from → travel direction
  const count = isWind
    ? clamp(8 + Math.round(mag / 3), 8, 16)
    : clamp(5 + Math.round(mag * 2), 5, 11);
  const duration = isWind
    ? clamp(2.8 - mag * 0.06, 1.1, 2.8)          // stronger wind → quicker streaks
    : clamp(reading.period ? 6 - reading.period * 0.12 : 4.5, 3.2, 6);
  const color = isWind ? "#285F7C" : "#1C4E63";
  const length = isWind ? 54 : 80;

  return (
    <div aria-hidden className="pointer-events-none absolute inset-0 z-[1] overflow-hidden">
      <div
        className="absolute left-1/2 top-1/2 h-[150%] w-[150%]"
        style={{ transform: `translate(-50%, -50%) rotate(${bearing.toFixed(1)}deg)` }}
      >
        {Array.from({ length: count }, (_, i) => (
          <span
            key={i}
            className="swd-wind-streak absolute block rounded-full"
            style={{
              left: `${(i * 61.8) % 100}%`,
              top: `${((i * 37.5 + 12) % 76) + 12}%`,
              width: isWind ? 2 : 2.4,
              height: length,
              background: color,
              opacity: 0.6,
              boxShadow: "0 0 4px rgba(74,166,216,0.18)",
              animationDuration: `${duration}s`,
              animationDelay: `-${((i / count) * duration).toFixed(2)}s`,
            }}
          />
        ))}
      </div>
    </div>
  );
}

export default function SpotMap({
  spot,
  live = null,
  forecast: _forecast = null,
  rounded = true,
  aspect = "sm:aspect-[21/9]",
  showModeSwitch = false,
  zoom,
  mapCenter,
}: {
  spot: Spot;
  live?: LiveConditionsRead | null;
  forecast?: NormalizedForecastSeries | null;
  rounded?: boolean;
  aspect?: string;
  showModeSwitch?: boolean;
  /** Admin-curated preview framing (editorial.map_view) — real, editor-set
   *  data, not a guessed default. Falls back to the spot's own coordinates
   *  at a fixed zoom when unset. */
  zoom?: number;
  mapCenter?: [number, number];
}) {
  const dataScope = useOptionalSpotDataScope();
  const mode: PublicMapMode = dataScope?.mapLayer ?? "wind";
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<L.Map | null>(null);
  const markerRef = useRef<L.Marker | null>(null);
  const [mapError, setMapError] = useState(false);
  const reading = currentReading(live, dataScope?.selectedForecast ?? null);

  useEffect(() => {
    if (!containerRef.current || mapRef.current || !spot.coords) return;
    const container = containerRef.current;
    const center = mapCenter ?? spot.coords;
    let map: L.Map;
    try {
      map = L.map(container, {
        center: [center[0], center[1]],
        zoom: zoom ?? SPOT_MAP_ZOOM,
        minZoom: 6,
        maxZoom: 16,
        zoomControl: false,
        attributionControl: false,
        fadeAnimation: false,
        // Static preview: no interaction at all.
        dragging: false,
        scrollWheelZoom: false,
        doubleClickZoom: false,
        touchZoom: false,
        keyboard: false,
        boxZoom: false,
      });
      L.tileLayer(TILE_URL, {
        subdomains: "a",
        attribution: TILE_ATTRIBUTION,
        maxZoom: 20,
        detectRetina: false,
        updateWhenIdle: false,
        updateWhenZooming: true,
        updateInterval: 120,
        keepBuffer: 4,
      }).addTo(map);
    } catch (err) {
      console.error("Spot map: failed to construct Leaflet map", err);
      setMapError(true);
      return;
    }
    mapRef.current = map;
    requestAnimationFrame(() => map.invalidateSize());
    return () => {
      map.remove();
      mapRef.current = null;
      markerRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- spot identity change remounts the page, not this effect
  }, []);

  // Marker + its colour follow the active mode and the current reading.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !spot.coords) return;
    const color = spotDotColor(mode, { windKt: reading?.windKt ?? null, waveM: reading?.waveM ?? null });
    // Direction is real point data (comes-from bearing); rotate to the travel
    // direction like WindArrow. A plain disc when it's null — no fabricated vane.
    const dirFrom = mode === "wind" ? reading?.windDir : reading?.waveDir;
    const icon = dirFrom != null && Number.isFinite(dirFrom) ? vaneIcon(color, (dirFrom + 180) % 360) : dotIcon(color);
    if (markerRef.current) {
      markerRef.current.setIcon(icon);
    } else {
      markerRef.current = L.marker([spot.coords[0], spot.coords[1]], { icon, keyboard: false, interactive: false }).addTo(map);
    }
  }, [spot, mode, reading?.windKt, reading?.waveM, reading?.windDir, reading?.waveDir]);

  if (!spot.coords) {
    return (
      <div className="flex aspect-[4/5] w-full items-center justify-center rounded-3xl border border-line bg-band text-center text-label text-muted sm:aspect-video">
        Für diesen Spot sind keine Koordinaten hinterlegt — die Karte kann nicht gerendert werden.
      </div>
    );
  }

  const swatch = reading?.type && mode === "wind" ? windColor(reading.windKt) : mode === "waves" ? waveColor(reading?.waveM) : windColor(null);

  return (
    <div data-forecast-utc={reading?.type === "forecast" ? dataScope?.selectedForecast?.utcKey ?? "" : ""} data-observation-type={reading?.type ?? "unavailable"} className={`swd-spot-map relative w-full overflow-hidden ${aspect} aspect-[4/5] ${rounded ? "rounded-3xl" : ""}`}>
      <div ref={containerRef} className="h-full w-full isolate" />

      <FlowLayer mode={mode} reading={reading} />

      {mapError && (
        <div role="status" className="swd-map-error absolute left-1/2 top-1/2 z-20 -translate-x-1/2 -translate-y-1/2">
          <span>Karte momentan nicht verfügbar.</span>
        </div>
      )}

      {showModeSwitch && (
        <div className="pointer-events-none absolute left-3 top-3 z-20 flex flex-col items-start gap-2">
          <div className="pointer-events-auto"><MapModeSwitch mode={mode} onChange={(next) => dataScope?.setMapLayer(next)} /></div>
        </div>
      )}

      <div className="pointer-events-none absolute bottom-3 left-3 z-20">
        <div className="pointer-events-auto"><MapLegend mode={mode} /></div>
      </div>

      {reading && (
        <div className="swd-spot-map-header pointer-events-none absolute right-3 top-3 z-20 flex flex-col items-end gap-1">
          <div className="pointer-events-auto flex items-center gap-2 rounded-full border border-line bg-surface/95 px-3 py-1.5 text-label text-ink shadow-card">
            <span aria-hidden className="h-2 w-2 rounded-full" style={{ backgroundColor: swatch }} />
            <span className="font-semibold">{OBSERVATION_BADGE[reading.type]}</span>
            <span className="text-muted">{reading.label.split(" · ")[1]}</span>
          </div>
        </div>
      )}

      <LeafletAttributionDisclosure source="carto" />
    </div>
  );
}
