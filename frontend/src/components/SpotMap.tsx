import { useEffect, useRef, useState } from "react";
import L from "leaflet";
import type { LiveConditionsRead } from "../lib/api";
import type { NormalizedForecastSeries } from "../lib/forecastNormalization";
import { useOptionalSpotDataScope } from "../state/SpotDataScope";
import { spotDotColor, type PublicMapMode } from "../lib/publicMap";
import { windColor } from "../lib/windScale";
import { waveColor } from "../lib/waveScale";
import { currentReading, OBSERVATION_BADGE } from "../lib/spotMapReading";
import MapModeSwitch from "./MapModeSwitch";
import MapLegend from "./MapLegend";
import { cartoTileUrl, CARTO_ATTRIBUTION, CARTO_POSITRON } from "../lib/basemaps";
import type { Spot } from "../lib/types";

// Positron (CARTO light) raster basemap — clean, desaturated, Airbnb-style.
const TILE_URL = cartoTileUrl(CARTO_POSITRON);
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
        attributionControl: true,
        // Static preview: no interaction at all.
        dragging: false,
        scrollWheelZoom: false,
        doubleClickZoom: false,
        touchZoom: false,
        keyboard: false,
        boxZoom: false,
      });
      L.tileLayer(TILE_URL, { subdomains: "abcd", attribution: TILE_ATTRIBUTION, maxZoom: 20, detectRetina: true }).addTo(map);
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
    if (markerRef.current) {
      markerRef.current.setIcon(dotIcon(color));
    } else {
      markerRef.current = L.marker([spot.coords[0], spot.coords[1]], { icon: dotIcon(color), keyboard: false, interactive: false }).addTo(map);
    }
  }, [spot, mode, reading?.windKt, reading?.waveM]);

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
      <div ref={containerRef} className="h-full w-full" />

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
    </div>
  );
}
