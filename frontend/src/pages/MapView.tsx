import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import maplibregl, { LngLatBounds, type GeoJSONSource, type Map as MapLibreMap, type Marker } from "maplibre-gl";
import Header from "../components/Header";
import SpotCard from "../components/SpotCard";
import { CloseIcon, MinusIcon, PlusIcon } from "../lib/icons";
import { useSpots, useSpotsLive } from "../lib/hooks";
import { getSpotCatalogVersion } from "../lib/api";
import type { Spot } from "../lib/types";
import { applyPublicMapStyle, applyPublicSpotTheme, ensurePublicSpotLayers, parsePublicMapUrl, PUBLIC_MAP_STYLE_URL, PUBLIC_SPOT_LAYER_IDS, PUBLIC_SPOT_SOURCE_ID, publicMapSearch, setPublicSpotData, setPublicSpotSelection, sortViewportSpots, spotCountLabel, type PublicMapTheme, updatePublicMapLayerVisibility } from "../lib/publicMap";
import "maplibre-gl/dist/maplibre-gl.css";

const CATALOG_POLL_MS = 3_000;
const MAX_RAIL_CARDS = 12;
const currentTheme = (): PublicMapTheme => document.documentElement.dataset.theme === "dark" ? "dark" : "light";
const reducedMotion = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;

function isVisible(map: MapLibreMap, spot: Spot): boolean {
  return Boolean(spot.coords && map.getBounds().contains([spot.coords[1], spot.coords[0]]));
}

export default function MapView() {
  const navigate = useNavigate();
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const markersRef = useRef<Marker[]>([]);
  const mapThemeRef = useRef<PublicMapTheme>(currentTheme());
  const initialFitDone = useRef(Boolean(parsePublicMapUrl(window.location.search)));
  const railRef = useRef<HTMLDivElement>(null);
  const dragStartRef = useRef<{ x: number; y: number }>();
  const [mapReady, setMapReady] = useState(false);
  const [mapZoom, setMapZoom] = useState(() => parsePublicMapUrl(window.location.search)?.zoom ?? 3);
  const [viewportIds, setViewportIds] = useState<string[]>([]);
  const [selectedId, setSelectedId] = useState<string | undefined>(() => parsePublicMapUrl(window.location.search)?.spot);
  const [hoveredId, setHoveredId] = useState<string>();
  const [catalogVersion, setCatalogVersion] = useState<string>();
  const [mapError, setMapError] = useState(false);
  const knownVersion = useRef<string>();
  const versionRequest = useRef<Promise<void> | null>(null);
  const { data: spots } = useSpots({ limit: 500, catalog_version: catalogVersion });

  useEffect(() => {
    let cancelled = false;
    let timer: number | undefined;
    const checkVersion = async () => {
      if (document.visibilityState === "hidden") return;
      if (versionRequest.current) return versionRequest.current;
      versionRequest.current = (async () => {
      try {
        const { version } = await getSpotCatalogVersion();
        if (!cancelled && version !== knownVersion.current) { knownVersion.current = version; setCatalogVersion(version); }
      } catch { /* Retain the current catalogue after transient failures. */ }
      finally { versionRequest.current = null; }
      })();
      return versionRequest.current;
    };
    const schedule = () => {
      if (cancelled) return;
      timer = window.setTimeout(async () => { await checkVersion(); schedule(); }, CATALOG_POLL_MS);
    };
    const refreshNow = () => { if (document.visibilityState !== "hidden") void checkVersion(); };
    void checkVersion(); schedule();
    document.addEventListener("visibilitychange", refreshNow);
    window.addEventListener("online", refreshNow);
    return () => {
      cancelled = true;
      if (timer !== undefined) window.clearTimeout(timer);
      document.removeEventListener("visibilitychange", refreshNow);
      window.removeEventListener("online", refreshNow);
    };
  }, []);

  const withCoords = useMemo(() => (spots ?? []).filter((spot): spot is Spot & { coords: [number, number] } => Boolean(spot.coords)), [spots]);
  const spotById = useMemo(() => new Map(withCoords.map((spot) => [spot.id, spot])), [withCoords]);
  useEffect(() => { if (selectedId && spots && !spotById.has(selectedId)) setSelectedId(undefined); }, [selectedId, spotById, spots]);

  const updateViewport = useCallback(() => {
    const map = mapRef.current;
    if (!map) return;
    const center = map.getCenter();
    const zoom = map.getZoom();
    setMapZoom(zoom);
    setViewportIds(withCoords.filter((spot) => isVisible(map, spot)).map((spot) => spot.id));
    const search = publicMapSearch([center.lng, center.lat], zoom, selectedId, window.location.search);
    window.history.replaceState(null, "", `${window.location.pathname}${search}${window.location.hash}`);
  }, [selectedId, withCoords]);

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    const saved = parsePublicMapUrl(window.location.search);
    let map: MapLibreMap;
    try {
      map = new maplibregl.Map({
      container: containerRef.current,
      style: PUBLIC_MAP_STYLE_URL[currentTheme()],
      center: saved?.center ?? [9.3, 40.3], zoom: saved?.zoom ?? 3,
      minZoom: 1.5, maxZoom: 17, bearing: 0, pitch: 0,
      pitchWithRotate: false, dragRotate: false, renderWorldCopies: false,
      crossSourceCollisions: true, fadeDuration: 200, refreshExpiredTiles: true,
      attributionControl: false,
      });
    } catch {
      setMapError(true);
      return;
    }
    mapRef.current = map;
    map.touchPitch.disable();
    map.scrollZoom.setWheelZoomRate(1 / 600);
    map.scrollZoom.setZoomRate(1 / 130);
    map.addControl(new maplibregl.AttributionControl({ compact: true }), "bottom-right");
    const applyStyle = () => {
      applyPublicMapStyle(map, currentTheme());
      ensurePublicSpotLayers(map);
      applyPublicSpotTheme(map, currentTheme());
    };
    map.on("style.load", applyStyle);
    map.on("zoomend", () => updatePublicMapLayerVisibility(map));
    map.on("load", () => {
      // Cached styles can finish before React attaches `style.load`; applying
      // again on the map's definitive load event keeps the hierarchy reliable.
      applyStyle();
      setMapError(false);
      setMapReady(true);
    });
    map.on("error", () => { if (!map.isStyleLoaded()) setMapError(true); });
    const observer = new MutationObserver(() => {
      const next = currentTheme();
      if (next !== mapThemeRef.current) {
        mapThemeRef.current = next;
        applyPublicMapStyle(map, next);
        applyPublicSpotTheme(map, next);
      }
    });
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
    return () => { observer.disconnect(); markersRef.current.forEach((marker) => marker.remove()); markersRef.current = []; map.remove(); mapRef.current = null; };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReady) return;
    map.on("moveend", updateViewport); updateViewport();
    return () => { map.off("moveend", updateViewport); };
  }, [mapReady, updateViewport]);

  useEffect(() => {
    const map = mapRef.current;
    if (!mapReady || !map || initialFitDone.current || withCoords.length === 0) return;
    const bounds = new LngLatBounds();
    withCoords.forEach((spot) => bounds.extend([spot.coords[1], spot.coords[0]]));
    initialFitDone.current = true;
    map.fitBounds(bounds, { padding: { top: 100, right: 52, bottom: window.innerWidth < 640 ? 270 : 240, left: 52 }, maxZoom: 7, duration: reducedMotion() ? 0 : 480 });
  }, [mapReady, withCoords]);

  useEffect(() => {
    const map = mapRef.current;
    if (!mapReady || !map) return;
    setPublicSpotData(map, withCoords);
  }, [mapReady, withCoords]);

  useEffect(() => {
    const map = mapRef.current;
    if (!mapReady || !map) return;
    setPublicSpotSelection(map, hoveredId, selectedId);
  }, [hoveredId, mapReady, selectedId]);

  useEffect(() => {
    const map = mapRef.current;
    if (!mapReady || !map) return;
    const renderMarkers = () => {
      markersRef.current.forEach((marker) => marker.remove()); markersRef.current = [];
      const features = map.queryRenderedFeatures({ layers: [PUBLIC_SPOT_LAYER_IDS.clusters, PUBLIC_SPOT_LAYER_IDS.points] });
      const seen = new Set<string>();
      for (const feature of features) {
        if (feature.geometry.type !== "Point") continue;
        const [lng, lat] = feature.geometry.coordinates;
        const cluster = Boolean(feature.properties?.cluster);
        const key = cluster ? `cluster:${feature.properties.cluster_id}` : `spot:${feature.properties?.spotId}`;
        if (seen.has(key)) continue;
        seen.add(key);
        const el = document.createElement("button");
        el.type = "button";
        el.className = "swd-map-a11y-marker";
        let ariaLabel: string;
        if (cluster) {
          const count = Number(feature.properties.point_count);
          ariaLabel = `Cluster mit ${count} Surfspots. Aktivieren zum Vergrößern.`;
          el.addEventListener("click", async () => {
            map.stop();
            const source = map.getSource(PUBLIC_SPOT_SOURCE_ID) as GeoJSONSource;
            const zoom = await source.getClusterExpansionZoom(Number(feature.properties.cluster_id));
            map.easeTo({ center: [lng, lat], zoom: Math.min(17, zoom), duration: reducedMotion() ? 0 : 480 });
          });
        } else {
          const id = String(feature.properties?.spotId || "");
          const spot = spotById.get(id);
          if (!spot) continue;
          ariaLabel = `Surfspot ${spot.name}`;
          el.setAttribute("aria-pressed", String(id === selectedId));
          el.dataset.tooltip = spot.name;
          el.addEventListener("mouseenter", () => setHoveredId(id));
          el.addEventListener("mouseleave", () => setHoveredId((value) => value === id ? undefined : value));
          el.addEventListener("focus", () => setHoveredId(id));
          el.addEventListener("blur", () => setHoveredId((value) => value === id ? undefined : value));
          el.addEventListener("click", () => setSelectedId(id));
        }
        const marker = new maplibregl.Marker({ element: el, anchor: "center" }).setLngLat([lng, lat]).addTo(map);
        // MapLibre assigns the generic label "Map marker" while constructing
        // a marker, so restore the useful localized label afterwards.
        el.setAttribute("aria-label", ariaLabel);
        markersRef.current.push(marker);
      }
    };
    requestAnimationFrame(renderMarkers);
    map.on("moveend", renderMarkers);
    map.on("zoomend", renderMarkers);
    map.on("idle", renderMarkers);
    return () => {
      map.off("moveend", renderMarkers); map.off("zoomend", renderMarkers); map.off("idle", renderMarkers);
      markersRef.current.forEach((marker) => marker.remove()); markersRef.current = [];
    };
  }, [mapReady, selectedId, spotById, withCoords]);

  const viewportSpots = useMemo(() => viewportIds.flatMap((id) => { const spot = spotById.get(id); return spot ? [spot] : []; }), [spotById, viewportIds]);
  const orderedSpots = useMemo(() => {
    const map = mapRef.current;
    const center: [number, number] = map ? [map.getCenter().lat, map.getCenter().lng] : [40.3, 9.3];
    const selected = selectedId ? spotById.get(selectedId) : undefined;
    const source = selected && !viewportSpots.some((spot) => spot.id === selected.id) ? [selected, ...viewportSpots] : viewportSpots;
    return sortViewportSpots(source, center, selectedId);
  }, [selectedId, spotById, viewportSpots]);
  const railSpots = orderedSpots.slice(0, MAX_RAIL_CARDS);
  const showCards = mapZoom >= 5 || Boolean(selectedId);
  const { data: live } = useSpotsLive(railSpots.map((spot) => spot.id));

  useEffect(() => {
    if (!selectedId) return;
    railRef.current?.querySelector<HTMLElement>(`[data-spot-id="${CSS.escape(selectedId)}"]`)?.scrollIntoView({ behavior: reducedMotion() ? "auto" : "smooth", inline: "center", block: "nearest" });
  }, [selectedId]);

  return (
    <main data-lenis-prevent className={`swd-public-map relative w-full overflow-hidden ${showCards && railSpots.length ? "has-map-cards" : ""}`} aria-labelledby="public-map-title">
      <Header showAccount={false} />
      <h1 id="public-map-title" className="sr-only">Spot-Karte</h1>
      <div role="region" aria-label="Interaktive Karte der veröffentlichten Surfspots" className="absolute inset-0">
        <div ref={containerRef} className="h-full w-full" />
      </div>
      {mapError && (
        <div role="status" className="swd-map-error absolute left-1/2 top-24 z-20 -translate-x-1/2">
          <span>Karte momentan nicht vollständig verfügbar.</span>
          <button type="button" onClick={() => { const map = mapRef.current; if (map) map.setStyle(PUBLIC_MAP_STYLE_URL[currentTheme()]); else window.location.reload(); }}>Erneut versuchen</button>
        </div>
      )}
      <div className="swd-map-controls pointer-events-none absolute z-20 flex flex-col items-end gap-3">
        <button type="button" aria-label="Zur Startseite" onClick={() => navigate("/")} className="swd-map-control pointer-events-auto"><CloseIcon className="text-[18px]" /></button>
        <div className="pointer-events-auto flex flex-col overflow-hidden rounded-lg border border-line bg-surface/95">
          <button type="button" aria-label="Vergrößern" onClick={() => mapRef.current?.zoomIn({ duration: reducedMotion() ? 0 : 210 })} className="swd-map-control"><PlusIcon className="text-[18px]" /></button>
          <span className="mx-2 h-px bg-line" />
          <button type="button" aria-label="Verkleinern" onClick={() => mapRef.current?.zoomOut({ duration: reducedMotion() ? 0 : 210 })} className="swd-map-control"><MinusIcon className="text-[18px]" /></button>
        </div>
      </div>
      <section aria-label="Surfspots im Kartenausschnitt" className="swd-map-rail-shell pointer-events-none absolute inset-x-0 bottom-0 z-10">
        {!showCards || railSpots.length === 0 ? (
          <p role="status" className="swd-map-status pointer-events-auto">{viewportSpots.length === 0 ? "Keine Spots in diesem Kartenausschnitt" : `${spotCountLabel(viewportSpots.length)} · Zum Entdecken heranzoomen`}</p>
        ) : (
          <>
            <div ref={railRef} data-lenis-prevent className="swd-map-rail pointer-events-auto no-scrollbar" onWheel={(event) => { if (Math.abs(event.deltaY) > Math.abs(event.deltaX)) event.currentTarget.scrollLeft += event.deltaY; }}>
              {railSpots.map((spot) => (
                <div key={spot.id} data-spot-id={spot.id} aria-current={spot.id === selectedId ? "true" : undefined}
                  className={`swd-map-card ${spot.id === selectedId ? "is-selected" : ""} ${spot.id === hoveredId ? "is-highlighted" : ""}`}
                  onMouseEnter={() => setHoveredId(spot.id)} onMouseLeave={() => setHoveredId((value) => value === spot.id ? undefined : value)}
                  onFocusCapture={() => setHoveredId(spot.id)} onBlurCapture={() => setHoveredId((value) => value === spot.id ? undefined : value)}
                  onPointerDown={(event) => { dragStartRef.current = { x: event.clientX, y: event.clientY }; }}
                  onClickCapture={(event) => { const start = dragStartRef.current; dragStartRef.current = undefined; if (start && Math.hypot(event.clientX - start.x, event.clientY - start.y) > 8) { event.preventDefault(); event.stopPropagation(); return; } setSelectedId(spot.id); }}>
                  <SpotCard spot={spot} compact mapRail live={live?.get(spot.id)} />
                </div>
              ))}
            </div>
            {orderedSpots.length > MAX_RAIL_CARDS && <p className="swd-map-more">Weitere Spots durch Heranzoomen entdecken</p>}
          </>
        )}
      </section>
    </main>
  );
}
