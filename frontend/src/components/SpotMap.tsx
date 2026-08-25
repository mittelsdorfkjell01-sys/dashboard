import { useEffect, useRef, useState } from "react";
import maplibregl, { type Map as MapLibreMap } from "maplibre-gl";
import type { LiveConditionsRead } from "../lib/api";
import type { NormalizedForecastSeries } from "../lib/forecastNormalization";
import { useOptionalSpotDataScope } from "../state/SpotDataScope";
import { fetchPublicMapStyle, setPublicSpotData, setPublicSpotMode, type PublicMapMode, type PublicSpotLiveValue } from "../lib/publicMap";
import { windColor } from "../lib/windScale";
import { waveColor } from "../lib/waveScale";
import { currentReading, OBSERVATION_BADGE } from "../lib/spotMapReading";
import MapModeSwitch from "./MapModeSwitch";
import MapLegend from "./MapLegend";
import type { Spot } from "../lib/types";
import "maplibre-gl/dist/maplibre-gl.css";

const reducedMotion = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;
const SPOT_MAP_ZOOM = 14.5; // matches SpotMapEditor's DEFAULT_ZOOM, so an un-framed spot lines up with what an admin sees while framing it

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
  const mapRef = useRef<MapLibreMap | null>(null);
  const [mapReady, setMapReady] = useState(false);
  const [mapError, setMapError] = useState(false);
  const reading = currentReading(live, dataScope?.selectedForecast ?? null);
  const [northUp, setNorthUp] = useState(reading?.coastalNormalDeg == null);

  useEffect(() => {
    if (!containerRef.current || mapRef.current || !spot.coords) return;
    const container = containerRef.current;
    let cancelled = false;
    void (async () => {
      let style;
      try {
        style = await fetchPublicMapStyle("light");
      } catch (err) {
        console.error("Spot map: failed to load base style", err);
        if (!cancelled) setMapError(true);
        return;
      }
      if (cancelled || !spot.coords) return;
      let map: MapLibreMap;
      try {
        const center = mapCenter ?? spot.coords;
        map = new maplibregl.Map({
          container,
          style,
          center: [center[1], center[0]],
          zoom: zoom ?? SPOT_MAP_ZOOM,
          // Coastal orientation by default when the spot has a real coast
          // bearing on file — never derived from wind/wave direction. Falls
          // back to north-up when no coast bearing is set.
          bearing: reading?.coastalNormalDeg ?? 0,
          minZoom: 6, maxZoom: 16, pitch: 0, pitchWithRotate: false,
          renderWorldCopies: false, attributionControl: false,
        });
      } catch (err) {
        console.error("Spot map: failed to construct MapLibre map", err);
        setMapError(true);
        return;
      }
      mapRef.current = map;
      map.touchPitch.disable();
      map.scrollZoom.disable();
      map.dragPan.disable();
      map.dragRotate.disable();
      map.doubleClickZoom.disable();
      map.touchZoomRotate.disable();
      map.keyboard.disable();
      map.addControl(new maplibregl.AttributionControl({ compact: true }), "bottom-right");
      map.on("load", () => { setMapError(false); setMapReady(true); });
      map.on("error", (event) => { console.error("Spot map: MapLibre runtime error", event.error); if (!map.isStyleLoaded()) setMapError(true); });
    })();
    return () => {
      cancelled = true;
      const map = mapRef.current;
      if (map) { map.remove(); mapRef.current = null; }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- spot identity change remounts the page, not this effect
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!mapReady || !map || !spot.coords) return;
    const live: Map<string, PublicSpotLiveValue> = new Map([[spot.id, { windKt: reading?.windKt ?? null, waveM: reading?.waveM ?? null }]]);
    setPublicSpotData(map, [spot], live);
  }, [mapReady, spot, reading?.windKt, reading?.waveM]);

  useEffect(() => {
    const map = mapRef.current;
    if (!mapReady || !map) return;
    setPublicSpotMode(map, mode, "light");
  }, [mapReady, mode]);

  const toggleOrientation = () => {
    const map = mapRef.current;
    if (!map || reading?.coastalNormalDeg == null) return;
    const next = !northUp;
    setNorthUp(next);
    map.easeTo({ bearing: next ? 0 : reading.coastalNormalDeg, duration: reducedMotion() ? 0 : 400 });
  };

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
      <div ref={containerRef} className={`h-full w-full transition-opacity duration-300 ${mapReady ? "opacity-100" : "opacity-0"}`} />

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

      {reading?.coastalNormalDeg != null && (
        <button
          type="button"
          onClick={toggleOrientation}
          aria-pressed={!northUp}
          aria-label={northUp ? "Zur Küstenausrichtung wechseln" : "Zur Nordausrichtung wechseln"}
          className="swd-map-control pointer-events-auto absolute right-3 top-3 z-20 flex-col gap-0.5 text-[10px] font-semibold"
        >
          <svg width="14" height="14" viewBox="0 0 18 18" style={{ transform: `rotate(${northUp ? 0 : reading.coastalNormalDeg}deg)` }}>
            <path d="M9 1 L11.5 9 L9 17 L6.5 9 Z" fill="none" stroke="currentColor" strokeWidth="1.3" />
            <path d="M9 1 L11.5 9 L9 9 Z" fill="currentColor" />
          </svg>
          {northUp ? "N" : "Küste"}
        </button>
      )}

      <div className="pointer-events-none absolute bottom-3 left-3 z-20">
        <div className="pointer-events-auto"><MapLegend mode={mode} /></div>
      </div>

      {reading && (
        <div className="swd-spot-map-header pointer-events-none absolute right-3 top-14 z-20 flex flex-col items-end gap-1">
          <div className="pointer-events-auto flex items-center gap-2 rounded-full border border-line bg-surface/95 px-3 py-1.5 text-label text-ink shadow-sm">
            <span aria-hidden className="h-2 w-2 rounded-full" style={{ backgroundColor: swatch }} />
            <span className="font-semibold">{OBSERVATION_BADGE[reading.type]}</span>
            <span className="text-muted">{reading.label.split(" · ")[1]}</span>
          </div>
        </div>
      )}
    </div>
  );
}
