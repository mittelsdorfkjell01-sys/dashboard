import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import maplibregl, { LngLatBounds, type GeoJSONSource, type Map as MapLibreMap, type Marker } from "maplibre-gl";
import Header from "../components/Header";
import SpotCard from "../components/SpotCard";
import MapResultsList from "../components/MapResultsList";
import { ListIcon, MinusIcon, PlusIcon } from "../lib/icons";
import { useSpots, useSpotsLive } from "../lib/hooks";
import { getSpotCatalogVersion } from "../lib/api";
import type { Spot } from "../lib/types";
import { fetchPublicMapStyle, parsePublicMapUrl, PUBLIC_SPOT_LAYER_IDS, PUBLIC_SPOT_SOURCE_ID, publicMapSearch, setPublicClusterHover, setPublicSpotData, setPublicSpotSelection, sortViewportSpots, spotCountLabel, type PublicMapTheme } from "../lib/publicMap";
import "maplibre-gl/dist/maplibre-gl.css";

// Background catalogue check, not a live feed: 60s is plenty to notice a
// published/unpublished spot, with immediate checks on visibility/reconnect
// covering the "I just made a change" case without polling every 3s.
const CATALOG_POLL_MS = 60_000;
const MAX_RAIL_CARDS = 12;
// Coalesce a burst of moveends (e.g. several quick pan-and-release gestures)
// into one live-wind fetch instead of one per settle.
const VIEWPORT_DEBOUNCE_MS = 300;
const currentTheme = (): PublicMapTheme => document.documentElement.dataset.theme === "dark" ? "dark" : "light";
const reducedMotion = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;

function isVisible(map: MapLibreMap, spot: Spot): boolean {
  return Boolean(spot.coords && map.getBounds().contains([spot.coords[1], spot.coords[0]]));
}

export default function MapView() {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const markersRef = useRef<Marker[]>([]);
  const mapThemeRef = useRef<PublicMapTheme>(currentTheme());
  const initialFitDone = useRef(Boolean(parsePublicMapUrl(window.location.search)));
  const railRef = useRef<HTMLDivElement>(null);
  const dragStartRef = useRef<{ x: number; y: number }>();
  const [mapReady, setMapReady] = useState(false);
  // Bumped after every completed `setStyle` (theme flip, error retry).
  // `setStyle` gives the GeoJSON source a fresh (empty) copy of its style
  // spec — the live data + selection/hover filters applied imperatively
  // after the *first* load do not carry over on their own, so the effects
  // that (re-)apply them re-run whenever this changes.
  const [styleGeneration, setStyleGeneration] = useState(0);
  const [mapZoom, setMapZoom] = useState(() => parsePublicMapUrl(window.location.search)?.zoom ?? 3);
  const [viewportIds, setViewportIds] = useState<string[]>([]);
  const [selectedId, setSelectedId] = useState<string | undefined>(() => parsePublicMapUrl(window.location.search)?.spot);
  const [hoveredId, setHoveredId] = useState<string>();
  const [hoveredClusterId, setHoveredClusterId] = useState<number>();
  const [listOpen, setListOpen] = useState(false);
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

  const viewportTimer = useRef<number>();
  const updateViewport = useCallback(() => {
    const map = mapRef.current;
    if (!map) return;
    const center = map.getCenter();
    const zoom = map.getZoom();
    setMapZoom(zoom);
    // URL sync stays immediate (cheap, and a stale-by-300ms URL during a pan
    // is harmless); only the live-data-triggering viewport commit is debounced.
    const search = publicMapSearch([center.lng, center.lat], zoom, selectedId, window.location.search);
    window.history.replaceState(null, "", `${window.location.pathname}${search}${window.location.hash}`);
    window.clearTimeout(viewportTimer.current);
    viewportTimer.current = window.setTimeout(() => {
      setViewportIds(withCoords.filter((spot) => isVisible(map, spot)).map((spot) => spot.id));
    }, VIEWPORT_DEBOUNCE_MS);
  }, [selectedId, withCoords]);

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    const container = containerRef.current;
    const saved = parsePublicMapUrl(window.location.search);
    let cancelled = false;
    let observer: MutationObserver | undefined;
    void (async () => {
      let style;
      try {
        style = await fetchPublicMapStyle(currentTheme());
      } catch (err) {
        console.error("Public map: failed to load base style", err);
        if (!cancelled) setMapError(true);
        return;
      }
      if (cancelled) return;
      let map: MapLibreMap;
      try {
        map = new maplibregl.Map({
          container,
          style,
          center: saved?.center ?? [9.3, 40.3], zoom: saved?.zoom ?? 3,
          minZoom: 1.5, maxZoom: 17, bearing: 0, pitch: 0,
          pitchWithRotate: false, dragRotate: false, renderWorldCopies: false,
          crossSourceCollisions: true, fadeDuration: 200, refreshExpiredTiles: true,
          attributionControl: false,
        });
      } catch (err) {
        console.error("Public map: failed to construct MapLibre map", err);
        setMapError(true);
        return;
      }
      mapRef.current = map;
      map.touchPitch.disable();
      map.scrollZoom.setWheelZoomRate(1 / 600);
      map.scrollZoom.setZoomRate(1 / 130);
      map.addControl(new maplibregl.AttributionControl({ compact: true }), "bottom-right");
      map.on("load", () => { setMapError(false); setMapReady(true); });
      map.on("error", (event) => {
        console.error("Public map: MapLibre runtime error", event.error);
        if (!map.isStyleLoaded()) setMapError(true);
      });
      // Theme flips rebuild the whole (already-colored) style document and
      // hand it to `setStyle` — MapLibre diffs it against the current one
      // (same source/layer ids, only paint/zoom values differ) and patches
      // in place, so this is a single, complete repaint rather than ~40
      // hand-written `setPaintProperty` calls kept in sync by hand.
      observer = new MutationObserver(() => {
        const next = currentTheme();
        if (next === mapThemeRef.current) return;
        mapThemeRef.current = next;
        fetchPublicMapStyle(next)
          .then((nextStyle) => {
            if (mapRef.current !== map) return;
            // `setStyle`'s diff (default) applies source/layer changes
            // synchronously — including resetting the GeoJSON source back to
            // its spec's empty placeholder data — and does *not* emit
            // "style.load" for a diffed update (that event is reserved for a
            // full reload). Re-apply state right after the call returns
            // rather than waiting for an event that will never come.
            map.setStyle(nextStyle);
            setStyleGeneration((g) => g + 1);
          })
          .catch((err) => console.error("Public map: failed to load theme style", err));
      });
      observer.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
    })();
    return () => {
      cancelled = true;
      observer?.disconnect();
      window.clearTimeout(viewportTimer.current);
      const map = mapRef.current;
      if (map) { markersRef.current.forEach((marker) => marker.remove()); markersRef.current = []; map.remove(); mapRef.current = null; }
    };
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
  }, [mapReady, styleGeneration, withCoords]);

  useEffect(() => {
    const map = mapRef.current;
    if (!mapReady || !map) return;
    setPublicSpotSelection(map, hoveredId, selectedId);
  }, [hoveredId, mapReady, selectedId, styleGeneration]);

  useEffect(() => {
    const map = mapRef.current;
    if (!mapReady || !map) return;
    setPublicClusterHover(map, hoveredClusterId);
  }, [hoveredClusterId, mapReady, styleGeneration]);

  const clusterZoomToken = useRef(0);
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
          const clusterId = Number(feature.properties.cluster_id);
          ariaLabel = `Cluster mit ${count} Surfspots. Aktivieren zum Vergrößern.`;
          el.addEventListener("mouseenter", () => setHoveredClusterId(clusterId));
          el.addEventListener("mouseleave", () => setHoveredClusterId((value) => value === clusterId ? undefined : value));
          el.addEventListener("focus", () => setHoveredClusterId(clusterId));
          el.addEventListener("blur", () => setHoveredClusterId((value) => value === clusterId ? undefined : value));
          el.addEventListener("click", async () => {
            map.stop();
            // A second cluster click before this promise resolves must win —
            // without this token, a slow first lookup could still land and
            // ease the map toward the *first* cluster after the user already
            // moved on to a second one.
            const token = ++clusterZoomToken.current;
            const source = map.getSource(PUBLIC_SPOT_SOURCE_ID) as GeoJSONSource;
            const zoom = await source.getClusterExpansionZoom(clusterId);
            if (clusterZoomToken.current !== token) return;
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

  const emptyLabel = viewportSpots.length === 0 ? "Keine Spots in diesem Kartenausschnitt" : `${spotCountLabel(viewportSpots.length)} · Zum Entdecken heranzoomen`;

  return (
    <main data-lenis-prevent className={`swd-public-map relative w-full overflow-hidden ${showCards && railSpots.length ? "has-map-cards" : ""}`} aria-labelledby="public-map-title">
      <Header />
      <h1 id="public-map-title" className="sr-only">Spot-Karte</h1>
      <div role="region" aria-label="Interaktive Karte der veröffentlichten Surfspots" className="absolute inset-0">
        {/* Opacity-gated until the patched style has actually painted, so the
            unstyled Voyager default never flashes before the theme applies. */}
        <div ref={containerRef} className={`h-full w-full transition-opacity duration-300 ${mapReady ? "opacity-100" : "opacity-0"}`} />
      </div>
      {mapError && (
        <div role="status" className="swd-map-error absolute left-1/2 top-24 z-20 -translate-x-1/2">
          <span>Karte momentan nicht vollständig verfügbar.</span>
          <button
            type="button"
            onClick={() => {
              const map = mapRef.current;
              if (!map) { window.location.reload(); return; }
              fetchPublicMapStyle(currentTheme())
                .then((style) => {
                  map.setStyle(style);
                  setStyleGeneration((g) => g + 1);
                  setMapError(false);
                })
                .catch(() => window.location.reload());
            }}
          >
            Erneut versuchen
          </button>
        </div>
      )}
      <div className="swd-map-controls pointer-events-none absolute z-20 flex flex-col items-end gap-3">
        <button type="button" aria-label="Als Liste anzeigen" aria-expanded={listOpen} onClick={() => setListOpen(true)} className="swd-map-control pointer-events-auto h-10 w-10 sm:h-10 sm:w-10">
          <ListIcon className="text-[17px]" />
        </button>
        <div className="swd-map-control-group pointer-events-auto flex flex-col overflow-hidden">
          <button type="button" aria-label="Vergrößern" onClick={() => mapRef.current?.zoomIn({ duration: reducedMotion() ? 0 : 210 })} className="swd-map-control swd-map-control-stacked"><PlusIcon className="text-[17px]" /></button>
          <span className="mx-2 h-px bg-line" />
          <button type="button" aria-label="Verkleinern" onClick={() => mapRef.current?.zoomOut({ duration: reducedMotion() ? 0 : 210 })} className="swd-map-control swd-map-control-stacked"><MinusIcon className="text-[17px]" /></button>
        </div>
      </div>
      <section aria-label="Surfspots im Kartenausschnitt" className="swd-map-rail-shell pointer-events-none absolute inset-x-0 bottom-0 z-10">
        {!showCards || railSpots.length === 0 ? (
          <p role="status" className="swd-map-status pointer-events-auto">{emptyLabel}</p>
        ) : (
          <>
            <div ref={railRef} data-lenis-prevent className="swd-map-rail pointer-events-auto no-scrollbar" onWheel={(event) => { if (Math.abs(event.deltaY) > Math.abs(event.deltaX)) event.currentTarget.scrollLeft += event.deltaY; }}>
              {railSpots.map((spot) => {
                const outOfViewport = spot.id === selectedId && !viewportSpots.some((s) => s.id === spot.id);
                return (
                <div key={spot.id} data-spot-id={spot.id} aria-current={spot.id === selectedId ? "true" : undefined}
                  className={`swd-map-card ${spot.id === selectedId ? "is-selected" : ""} ${spot.id === hoveredId ? "is-highlighted" : ""}`}
                  onMouseEnter={() => setHoveredId(spot.id)} onMouseLeave={() => setHoveredId((value) => value === spot.id ? undefined : value)}
                  onFocusCapture={() => setHoveredId(spot.id)} onBlurCapture={() => setHoveredId((value) => value === spot.id ? undefined : value)}
                  onPointerDown={(event) => { dragStartRef.current = { x: event.clientX, y: event.clientY }; }}
                  onClickCapture={(event) => { const start = dragStartRef.current; dragStartRef.current = undefined; if (start && Math.hypot(event.clientX - start.x, event.clientY - start.y) > 8) { event.preventDefault(); event.stopPropagation(); return; } setSelectedId(spot.id); }}>
                  {outOfViewport && <span className="swd-map-card-badge">Außerhalb des Ausschnitts</span>}
                  <SpotCard spot={spot} compact mapRail live={live?.get(spot.id)} />
                </div>
                );
              })}
            </div>
            {orderedSpots.length > MAX_RAIL_CARDS && <p className="swd-map-more">Weitere Spots durch Heranzoomen entdecken</p>}
          </>
        )}
      </section>
      <MapResultsList
        open={listOpen}
        onClose={() => setListOpen(false)}
        spots={orderedSpots.slice(0, MAX_RAIL_CARDS)}
        live={live}
        selectedId={selectedId}
        onSelect={(id) => { setSelectedId(id); setListOpen(false); }}
        emptyLabel={emptyLabel}
      />
    </main>
  );
}
