import { lazy, Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Link, useLocation, useNavigate } from "react-router-dom";
import maplibregl, { LngLatBounds, type GeoJSONSource, type Map as MapLibreMap, type Marker, type Popup } from "maplibre-gl";
import Header from "../components/Header";
import SpotCard from "../components/SpotCard";
import { ChevronLeftIcon, CloseIcon, ListIcon, MinusIcon, PlusIcon } from "../lib/icons";
import { useSpotForecast, useSpots, useSpotsLive } from "../lib/hooks";
import { getSpotCatalogVersion } from "../lib/api";
import type { Spot } from "../lib/types";
import { countryName } from "../lib/flags";
import { spotPath } from "../lib/spotRoutes";
import { SpotDataScopeProvider } from "../state/SpotDataScope";
import { fetchPublicMapStyle, parsePublicMapUrl, PUBLIC_SPOT_LAYER_IDS, PUBLIC_SPOT_SOURCE_ID, publicMapSearch, setPublicClusterHover, setPublicSpotData, setPublicSpotSelection, sortViewportSpots, spotCountLabel } from "../lib/publicMap";
import "maplibre-gl/dist/maplibre-gl.css";

const Meteogram = lazy(() => import("../components/data/Meteogram"));

// Background catalogue check, not a live feed: 60s is plenty to notice a
// published/unpublished spot, with immediate checks on visibility/reconnect
// covering the "I just made a change" case without polling every 3s.
const CATALOG_POLL_MS = 60_000;
// The "list" trigger opens a scrollable right-side panel of Landing-style
// tiles (two columns) — capped so a world-view viewport with hundreds of
// spots doesn't render an unbounded list.
const LIST_PANEL_MAX = 30;
// Comfortable "you've reached one specific spot" zoom — clicking a
// non-cluster marker eases in to at least this level (never zooms out).
// Deliberately not maxed out (2026-08-23 feedback: leave a bit more of the
// surroundings visible than a tight close-up).
const SINGLE_SPOT_ZOOM = 13.5;
// Cap for cluster fitBounds/fallback zoom — same "leave it a bit more
// zoomed out" feedback applies to multi-spot clusters.
const CLUSTER_MAX_ZOOM = 15.5;
// Coalesce a burst of moveends (e.g. several quick pan-and-release gestures)
// into one live-wind fetch instead of one per settle.
const VIEWPORT_DEBOUNCE_MS = 300;
// The map is deliberately always light — it never follows the site's dark
// mode (2026-08-22 feedback). See the matching `--sw-*`/`--map-*` token
// overrides scoped to `.swd-public-map` in index.css.
const reducedMotion = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;

function isVisible(map: MapLibreMap, spot: Spot): boolean {
  return Boolean(spot.coords && map.getBounds().contains([spot.coords[1], spot.coords[0]]));
}

export default function MapView() {
  const navigate = useNavigate();
  const location = useLocation();
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const markersRef = useRef<Marker[]>([]);
  const popupRef = useRef<Popup | null>(null);
  const initialFitDone = useRef(Boolean(parsePublicMapUrl(window.location.search)));
  const [mapReady, setMapReady] = useState(false);
  // Bumped after the error-retry button's `setStyle` call. `setStyle` gives
  // the GeoJSON source a fresh (empty) copy of its style spec — the live
  // data + selection/hover filters applied imperatively after the *first*
  // load do not carry over on their own, so the effects that (re-)apply
  // them re-run whenever this changes.
  const [styleGeneration, setStyleGeneration] = useState(0);
  const [viewportIds, setViewportIds] = useState<string[]>([]);
  const [selectedId, setSelectedId] = useState<string | undefined>(() => parsePublicMapUrl(window.location.search)?.spot);
  const [hoveredId, setHoveredId] = useState<string>();
  const [hoveredClusterId, setHoveredClusterId] = useState<number>();
  const [tilesOpen, setTilesOpen] = useState(false);
  const [popupContainer, setPopupContainer] = useState<HTMLDivElement | null>(null);
  const [catalogVersion, setCatalogVersion] = useState<string>();
  const [mapError, setMapError] = useState(false);
  const knownVersion = useRef<string>();
  const versionRequest = useRef<Promise<void> | null>(null);
  const { data: spots } = useSpots({ limit: 500, catalog_version: catalogVersion });

  // `location.key === "default"` means this tab has no entry to go back to
  // (deep link, reload, new tab) — fall back to the homepage instead of
  // leaving the visitor stuck or navigating outside the app.
  const goBack = () => { if (location.key !== "default") navigate(-1); else navigate("/"); };

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
    void (async () => {
      let style;
      try {
        style = await fetchPublicMapStyle("light");
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
    })();
    return () => {
      cancelled = true;
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

  // Clicking empty map background closes whichever bottom panel is open,
  // same as the explicit close button. Marker click handlers below call
  // `stopPropagation()` — MapLibre's own "click" listener sits on the map
  // container itself, so without that a marker click bubbles up into it
  // too, and this handler would fire right after selecting a spot and
  // immediately clear it again (2026-08-23 bugfix: that's why the
  // tile/forecast never seemed to open).
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReady) return;
    const onBackgroundClick = () => { setSelectedId(undefined); setTilesOpen(false); };
    map.on("click", onBackgroundClick);
    return () => { map.off("click", onBackgroundClick); };
  }, [mapReady]);

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

  const selectedSpot = selectedId ? spotById.get(selectedId) : undefined;
  const { data: selectedForecast, loading: selectedForecastLoading } = useSpotForecast(selectedSpot?.id);

  // The selected spot's Landing-style tile, anchored to its marker
  // (desktop only — hidden entirely on narrow screens via CSS, see
  // `.swd-map-popup` in index.css). A plain MapLibre Popup just hosts a
  // React portal so this is the *same* SpotCard everywhere else, not a
  // second hand-built card.
  useEffect(() => {
    const map = mapRef.current;
    popupRef.current?.remove();
    popupRef.current = null;
    setPopupContainer(null);
    if (!mapReady || !map || !selectedSpot?.coords) return;
    const el = document.createElement("div");
    // MapLibre's own anchor auto-flip only avoids the map *container's*
    // edges — it has no idea our header floats over the top ~84px or that
    // selecting a spot also raises the chart panel over the bottom ~360px,
    // so the default above-marker placement can poke into either. Pick the
    // anchor ourselves: whichever side actually has room for the popup's
    // own height, preferring above (the default) when both do.
    const lngLat: [number, number] = [selectedSpot.coords[1], selectedSpot.coords[0]];
    const screenY = map.project(lngLat).y;
    const containerHeight = map.getContainer().clientHeight;
    const POPUP_HEIGHT = 190;
    const HEADER_ZONE = 84;
    const BOTTOM_PANEL_ZONE = 360;
    const roomAbove = screenY - HEADER_ZONE;
    const roomBelow = containerHeight - BOTTOM_PANEL_ZONE - screenY;
    const anchor = roomAbove >= POPUP_HEIGHT ? "bottom" : roomBelow >= POPUP_HEIGHT ? "top" : roomAbove >= roomBelow ? "bottom" : "top";
    const popup = new maplibregl.Popup({ closeButton: false, closeOnClick: false, offset: 18, anchor, className: "swd-map-popup", maxWidth: "none" })
      .setLngLat(lngLat)
      .setDOMContent(el)
      .addTo(map);
    popupRef.current = popup;
    setPopupContainer(el);
    return () => { popup.remove(); if (popupRef.current === popup) popupRef.current = null; };
  }, [mapReady, selectedSpot, styleGeneration]);

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
          el.addEventListener("click", async (event) => {
            event.stopPropagation();
            map.stop();
            // A second cluster click before this promise resolves must win —
            // without this token, a slow first lookup could still land and
            // ease the map toward the *first* cluster after the user already
            // moved on to a second one.
            const token = ++clusterZoomToken.current;
            const source = map.getSource(PUBLIC_SPOT_SOURCE_ID) as GeoJSONSource;
            // Frame the cluster's actual member spots as tightly as possible
            // (not just supercluster's generic "expansion zoom", which only
            // guarantees the cluster *splits* — not that the resulting
            // points are nicely centred/visible together).
            const leaves = await source.getClusterLeaves(clusterId, count, 0);
            if (clusterZoomToken.current !== token) return;
            const bounds = new LngLatBounds();
            for (const leaf of leaves) {
              if (leaf.geometry.type === "Point") bounds.extend(leaf.geometry.coordinates as [number, number]);
            }
            // A little slower and a little less tight than a plain expansion
            // zoom (2026-08-23 feedback) — the member spots should land
            // comfortably inside the frame, not crammed against the edges.
            if (bounds.isEmpty()) { map.easeTo({ center: [lng, lat], zoom: Math.min(CLUSTER_MAX_ZOOM, map.getZoom() + 2), duration: reducedMotion() ? 0 : 650 }); return; }
            map.fitBounds(bounds, { padding: 110, maxZoom: CLUSTER_MAX_ZOOM, duration: reducedMotion() ? 0 : 650 });
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
          // Selecting a spot switches the bottom panel to its chart — close
          // the tile browser so the panel isn't showing two things at once.
          // A resolved single spot (no more clustering left) also zooms in,
          // same as a cluster click, instead of only clusters ever moving
          // the camera (2026-08-23 feedback).
          el.addEventListener("click", (event) => {
            event.stopPropagation();
            setSelectedId(id);
            setTilesOpen(false);
            map.easeTo({ center: [lng, lat], zoom: Math.max(map.getZoom(), SINGLE_SPOT_ZOOM), duration: reducedMotion() ? 0 : 650 });
          });
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
    return sortViewportSpots(viewportSpots, center);
  }, [viewportSpots]);
  const listPanelSpots = orderedSpots.slice(0, LIST_PANEL_MAX);
  const liveIds = useMemo(() => {
    const ids = new Set((tilesOpen ? listPanelSpots : []).map((spot) => spot.id));
    if (selectedId) ids.add(selectedId);
    return [...ids];
  }, [selectedId, listPanelSpots, tilesOpen]);
  const { data: live } = useSpotsLive(liveIds);

  const emptyLabel = viewportSpots.length === 0 ? "Keine Spots in diesem Kartenausschnitt" : `${spotCountLabel(viewportSpots.length)} · Zum Entdecken heranzoomen`;
  const hasBottomPanel = Boolean(selectedSpot);
  const regionLine = (spot: Spot) => [spot.regionName, countryName(spot.regionCountry ?? undefined)].filter(Boolean).join(" · ");

  return (
    <main data-lenis-prevent className={`swd-public-map relative w-full overflow-hidden ${hasBottomPanel ? "has-bottom-panel" : ""}`} aria-labelledby="public-map-title">
      <Header />
      <h1 id="public-map-title" className="sr-only">Spot-Karte</h1>
      <div role="region" aria-label="Interaktive Karte der veröffentlichten Surfspots" className="absolute inset-0">
        {/* Opacity-gated until the patched style has actually painted, so the
            unstyled Voyager default never flashes before the theme applies. */}
        <div ref={containerRef} className={`h-full w-full transition-opacity duration-300 ${mapReady ? "opacity-100" : "opacity-0"}`} />
      </div>
      {popupContainer && selectedSpot && createPortal(
        <div className="w-[176px]"><SpotCard spot={selectedSpot} live={live?.get(selectedSpot.id)} /></div>,
        popupContainer,
      )}
      {mapError && (
        <div role="status" className="swd-map-error absolute left-1/2 top-24 z-20 -translate-x-1/2">
          <span>Karte momentan nicht vollständig verfügbar.</span>
          <button
            type="button"
            onClick={() => {
              const map = mapRef.current;
              if (!map) { window.location.reload(); return; }
              fetchPublicMapStyle("light")
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
      <div className="swd-map-controls-left pointer-events-none absolute z-20 flex flex-col items-start gap-3">
        <button type="button" aria-label="Zurück" onClick={goBack} className="swd-map-back pointer-events-auto">
          <ChevronLeftIcon className="text-[19px]" />
        </button>
        <div className="swd-map-control-group pointer-events-auto flex flex-col overflow-hidden">
          <button type="button" aria-label="Vergrößern" onClick={() => mapRef.current?.zoomIn({ duration: reducedMotion() ? 0 : 210 })} className="swd-map-control swd-map-control-stacked"><PlusIcon className="text-[17px]" /></button>
          <span className="mx-2 h-px bg-line" />
          <button type="button" aria-label="Verkleinern" onClick={() => mapRef.current?.zoomOut({ duration: reducedMotion() ? 0 : 210 })} className="swd-map-control swd-map-control-stacked"><MinusIcon className="text-[17px]" /></button>
        </div>
      </div>
      {!tilesOpen && (
        <div className="swd-map-controls pointer-events-none absolute z-20 flex flex-col items-end gap-3">
          <button
            type="button"
            aria-label="Spots im Ausschnitt anzeigen"
            aria-expanded={false}
            aria-controls="swd-map-list-panel"
            onClick={() => { setTilesOpen(true); setSelectedId(undefined); }}
            className="swd-map-control pointer-events-auto h-10 w-10"
          >
            <ListIcon className="text-[17px]" />
          </button>
        </div>
      )}
      {tilesOpen && (
        <div id="swd-map-list-panel" className="swd-map-side-panel pointer-events-auto absolute z-20">
            <div className="swd-map-panel-head">
              <p className="swd-map-list-title">Spots im Ausschnitt</p>
              <button type="button" aria-label="Schließen" aria-expanded={true} onClick={() => setTilesOpen(false)} className="swd-map-plain-close">
                <CloseIcon className="text-[15px]" />
              </button>
            </div>
            {listPanelSpots.length === 0 ? (
              <p role="status" className="swd-map-list-empty">{emptyLabel}</p>
            ) : (
              <div className="swd-map-tile-grid">
                {listPanelSpots.map((spot) => <SpotCard key={spot.id} spot={spot} live={live?.get(spot.id)} />)}
              </div>
            )}
          </div>
        )}
      <section aria-label="Kartendetails" className="swd-map-bottom-shell pointer-events-none absolute inset-x-0 bottom-0 z-10">
        {selectedSpot ? (
          <div className="swd-map-panel pointer-events-auto">
            <div className="swd-map-panel-head">
              <div className="min-w-0">
                <p className="truncate font-semibold text-ink">{selectedSpot.name}</p>
                {regionLine(selectedSpot) && <p className="truncate text-caption text-muted">{regionLine(selectedSpot)}</p>}
              </div>
              <div className="flex shrink-0 items-center gap-2">
                <Link to={spotPath(selectedSpot)} className="swd-map-chart-cta">Zum Spot</Link>
                <button type="button" aria-label="Schließen" onClick={() => setSelectedId(undefined)} className="swd-map-plain-close">
                  <CloseIcon className="text-[15px]" />
                </button>
              </div>
            </div>
            <div className="swd-map-chart-scroll">
              {selectedForecastLoading && <div className="h-[258px] animate-pulse bg-band" />}
              {!selectedForecastLoading && (
                <Suspense fallback={<div className="h-[258px]" />}>
                  {selectedForecast && selectedForecast.days.some((day) => day.hours.length > 0) ? (
                    <SpotDataScopeProvider forecast={selectedForecast}>
                      <Meteogram forecast={selectedForecast} compact />
                    </SpotDataScopeProvider>
                  ) : (
                    <p className="flex h-[80px] items-center justify-center px-4 text-center text-caption text-muted">Vorhersage momentan nicht verfügbar.</p>
                  )}
                </Suspense>
              )}
            </div>
          </div>
        ) : (
          <p role="status" className="swd-map-status pointer-events-auto">{emptyLabel}</p>
        )}
      </section>
    </main>
  );
}
