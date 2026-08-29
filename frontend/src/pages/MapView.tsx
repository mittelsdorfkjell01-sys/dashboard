import { lazy, Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Link, useLocation, useNavigate } from "react-router-dom";
import L from "leaflet";
import Supercluster from "supercluster";
import Header from "../components/Header";
import SpotCard from "../components/SpotCard";
import { ChevronLeftIcon, CloseIcon, ListIcon, MinusIcon, PlusIcon } from "../lib/icons";
import { useSpotForecast, useSpots, useSpotsLive } from "../lib/hooks";
import { getSpotCatalogVersion } from "../lib/api";
import type { Spot } from "../lib/types";
import { countryName } from "../lib/flags";
import { spotPath } from "../lib/spotRoutes";
import { SpotDataScopeProvider } from "../state/SpotDataScope";
import {
  parsePublicMapUrl,
  publicMapSearch,
  PUBLIC_SPOT_CLUSTER_MAX_ZOOM,
  PUBLIC_SPOT_CLUSTER_RADIUS,
  spotDotColor,
  spotFeatures,
  sortViewportSpots,
  spotCountLabel,
  type PublicSpotLiveValue,
  type PublicSpotProperties,
} from "../lib/publicMap";
import { cartoTileUrl, CARTO_ATTRIBUTION, CARTO_POSITRON } from "../lib/basemaps";

const MapForecastChart = lazy(() => import("../components/data/MapForecastChart"));

// Positron (CARTO light) raster basemap — clean, desaturated, Airbnb-style.
const TILE_URL = cartoTileUrl(CARTO_POSITRON);
const TILE_ATTRIBUTION = CARTO_ATTRIBUTION;

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
const SINGLE_SPOT_ZOOM = 13.5;
// Cap for cluster fitBounds/fallback zoom.
const CLUSTER_MAX_ZOOM = 15.5;
// Coalesce a burst of moveends into one live-wind fetch instead of one per settle.
const VIEWPORT_DEBOUNCE_MS = 300;
// Clustered world/continent views do not benefit from hundreds of individual
// live readings. Start once markers are meaningfully separated and cap the
// request fan-out to three batches (useSpotsLive batches 20 ids/request).
const LIVE_VALUES_MIN_ZOOM = 6;
const LIVE_VALUES_MAX_SPOTS = 60;
// The map is deliberately always light — it never follows the site's dark
// mode. See the `--sw-*`/`--map-*` token overrides scoped to `.swd-public-map`.
const reducedMotion = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;

type ClusterOrPoint = Supercluster.ClusterFeature<Supercluster.AnyProps> | Supercluster.PointFeature<PublicSpotProperties>;

export default function MapView() {
  const navigate = useNavigate();
  const location = useLocation();
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<L.Map | null>(null);
  const markersLayer = useRef<L.LayerGroup | null>(null);
  const indexRef = useRef<Supercluster<PublicSpotProperties> | null>(null);
  const popupRef = useRef<L.Popup | null>(null);
  const initialFitDone = useRef(Boolean(parsePublicMapUrl(window.location.search)));
  const [mapReady, setMapReady] = useState(false);
  const [viewportIds, setViewportIds] = useState<string[]>([]);
  const [viewportZoom, setViewportZoom] = useState(3);
  const [selectedId, setSelectedId] = useState<string | undefined>(() => parsePublicMapUrl(window.location.search)?.spot);
  const [tilesOpen, setTilesOpen] = useState(false);
  const [popupContainer, setPopupContainer] = useState<HTMLDivElement | null>(null);
  const [catalogVersion, setCatalogVersion] = useState<string>();
  const [catalogReady, setCatalogReady] = useState(false);
  const [mapError, setMapError] = useState(false);
  const knownVersion = useRef<string>();
  const { data: spots } = useSpots(
    { limit: 500, catalog_version: catalogVersion },
    catalogReady,
  );

  // `location.key === "default"` means this tab has no entry to go back to
  // (deep link, reload, new tab) — fall back to the homepage.
  const goBack = () => { if (location.key !== "default") navigate(-1); else navigate("/"); };

  useEffect(() => {
    let cancelled = false;
    let timer: number | undefined;
    let versionRequest: Promise<void> | null = null;
    const checkVersion = async () => {
      if (document.visibilityState === "hidden") return;
      if (versionRequest) return versionRequest;
      versionRequest = (async () => {
        try {
          const { version } = await getSpotCatalogVersion();
          if (!cancelled && version !== knownVersion.current) {
            knownVersion.current = version;
            setCatalogVersion(version);
          }
        } catch {
          /* Retain the current catalogue after transient failures. */
        } finally {
          if (!cancelled) setCatalogReady(true);
          versionRequest = null;
        }
      })();
      return versionRequest;
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
  const commitViewport = useCallback(() => {
    const map = mapRef.current;
    if (!map) return;
    const center = map.getCenter();
    const zoom = map.getZoom();
    // URL sync stays immediate; only the live-data-triggering viewport commit
    // is debounced.
    const search = publicMapSearch([center.lng, center.lat], zoom, selectedId, window.location.search);
    window.history.replaceState(null, "", `${window.location.pathname}${search}${window.location.hash}`);
    window.clearTimeout(viewportTimer.current);
    viewportTimer.current = window.setTimeout(() => {
      const bounds = map.getBounds();
      setViewportZoom(zoom);
      setViewportIds(withCoords.filter((spot) => bounds.contains([spot.coords[0], spot.coords[1]])).map((spot) => spot.id));
    }, VIEWPORT_DEBOUNCE_MS);
  }, [selectedId, withCoords]);

  // --- map construction -----------------------------------------------------
  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    const container = containerRef.current;
    const saved = parsePublicMapUrl(window.location.search);
    let map: L.Map;
    try {
      map = L.map(container, {
        center: saved ? [saved.center[1], saved.center[0]] : [40.3, 9.3],
        zoom: saved?.zoom ?? 3,
        minZoom: 2,
        maxZoom: 17,
        zoomControl: false,
        attributionControl: true,
        zoomSnap: 0.25,
        worldCopyJump: false,
      });
      L.tileLayer(TILE_URL, { subdomains: "abcd", attribution: TILE_ATTRIBUTION, maxZoom: 20, detectRetina: true }).addTo(map);
    } catch (err) {
      console.error("Public map: failed to construct Leaflet map", err);
      setMapError(true);
      return;
    }
    mapRef.current = map;
    markersLayer.current = L.layerGroup().addTo(map);
    // Background click closes whichever bottom panel is open (marker clicks call
    // stopPropagation via Leaflet's own layer events, so they don't bubble here).
    map.on("click", () => { setSelectedId(undefined); setTilesOpen(false); });
    const readyFrame = requestAnimationFrame(() => {
      map.invalidateSize();
      setMapReady(true);
    });
    return () => {
      cancelAnimationFrame(readyFrame);
      window.clearTimeout(viewportTimer.current);
      map.remove();
      mapRef.current = null;
      markersLayer.current = null;
      popupRef.current = null;
    };
  }, []);

  // Viewport tracking (URL + debounced live/list commit).
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReady) return;
    map.on("moveend", commitViewport); commitViewport();
    return () => { map.off("moveend", commitViewport); };
  }, [mapReady, commitViewport]);

  // Initial fit to all spots (only when the URL carried no saved view).
  useEffect(() => {
    const map = mapRef.current;
    if (!mapReady || !map || initialFitDone.current || withCoords.length === 0) return;
    initialFitDone.current = true;
    const bounds = L.latLngBounds(withCoords.map((spot) => [spot.coords[0], spot.coords[1]] as [number, number]));
    map.fitBounds(bounds, { paddingTopLeft: [52, 100], paddingBottomRight: [52, window.innerWidth < 640 ? 270 : 240], maxZoom: 7, animate: !reducedMotion() });
  }, [mapReady, withCoords]);

  // Live wind readings for currently-visible spots → marker colours.
  const markerLiveIds = useMemo(
    () => viewportZoom >= LIVE_VALUES_MIN_ZOOM ? viewportIds.slice(0, LIVE_VALUES_MAX_SPOTS) : [],
    [viewportIds, viewportZoom],
  );
  const { data: viewportLive } = useSpotsLive(markerLiveIds);
  const liveValues = useMemo(() => {
    const map = new Map<string, PublicSpotLiveValue>();
    viewportLive?.forEach((reading, id) => map.set(id, { windKt: reading.current?.wind ?? null, waveM: reading.current?.swell ?? null }));
    return map;
  }, [viewportLive]);

  // (Re)build the cluster index whenever the spot set changes.
  useEffect(() => {
    if (!mapReady) return;
    const index = new Supercluster<PublicSpotProperties>({ radius: PUBLIC_SPOT_CLUSTER_RADIUS, maxZoom: PUBLIC_SPOT_CLUSTER_MAX_ZOOM });
    index.load(spotFeatures(withCoords) as Supercluster.PointFeature<PublicSpotProperties>[]);
    indexRef.current = index;
  }, [mapReady, withCoords]);

  const selectedSpot = selectedId ? spotById.get(selectedId) : undefined;
  const { data: selectedForecast, loading: selectedForecastLoading } = useSpotForecast(selectedSpot?.id);

  const clusterZoomToken = useRef(0);
  // Render the visible clusters/points as Leaflet markers. Re-runs on every map
  // move and whenever selection or live colours change.
  const renderMarkers = useCallback(() => {
    const map = mapRef.current;
    const layer = markersLayer.current;
    const index = indexRef.current;
    if (!map || !layer || !index) return;
    layer.clearLayers();
    const b = map.getBounds();
    const clusters = index.getClusters([b.getWest(), b.getSouth(), b.getEast(), b.getNorth()], Math.round(map.getZoom())) as ClusterOrPoint[];
    for (const feature of clusters) {
      const [lng, lat] = feature.geometry.coordinates;
      const props = feature.properties as Supercluster.ClusterProperties & PublicSpotProperties;
      if (props.cluster) {
        const count = props.point_count;
        const size = count < 10 ? 30 : count < 50 ? 34 : 38;
        const icon = L.divIcon({ className: "swd-map-cluster-icon", html: `<span class="swd-map-cluster" style="width:${size}px;height:${size}px">${count}</span>`, iconSize: [size, size], iconAnchor: [size / 2, size / 2] });
        const marker = L.marker([lat, lng], { icon, keyboard: true });
        marker.on("add", () => marker.getElement()?.setAttribute("aria-label", `Cluster mit ${count} Surfspots. Aktivieren zum Vergrößern.`));
        marker.on("click", async () => {
          map.stop?.();
          const token = ++clusterZoomToken.current;
          const leaves = index.getLeaves(props.cluster_id, Infinity) as Supercluster.PointFeature<PublicSpotProperties>[];
          if (clusterZoomToken.current !== token) return;
          const bounds = L.latLngBounds(leaves.map((leaf) => [leaf.geometry.coordinates[1], leaf.geometry.coordinates[0]] as [number, number]));
          if (!bounds.isValid()) { map.setView([lat, lng], Math.min(CLUSTER_MAX_ZOOM, map.getZoom() + 2), { animate: !reducedMotion() }); return; }
          map.fitBounds(bounds, { padding: [110, 110], maxZoom: CLUSTER_MAX_ZOOM, animate: !reducedMotion() });
        });
        layer.addLayer(marker);
      } else {
        const spot = spotById.get(props.spotId);
        if (!spot) continue;
        const selected = props.spotId === selectedId;
        const color = spotDotColor("wind", liveValues.get(props.spotId));
        const icon = L.divIcon({ className: `swd-map-a11y-marker${selected ? " is-selected" : ""}`, html: `<span class="swd-map-dot" style="background:${color}"></span>`, iconSize: [30, 30], iconAnchor: [15, 15] });
        const marker = L.marker([lat, lng], { icon, keyboard: true });
        marker.on("add", () => {
          const el = marker.getElement();
          if (!el) return;
          el.setAttribute("aria-label", `Surfspot ${spot.name}`);
          el.setAttribute("data-tooltip", spot.name);
          el.setAttribute("aria-pressed", String(selected));
        });
        marker.on("click", () => {
          setSelectedId(props.spotId);
          setTilesOpen(false);
          map.setView([lat, lng], Math.max(map.getZoom(), SINGLE_SPOT_ZOOM), { animate: !reducedMotion() });
        });
        layer.addLayer(marker);
      }
    }
  }, [selectedId, spotById, liveValues]);

  useEffect(() => {
    const map = mapRef.current;
    if (!mapReady || !map) return;
    renderMarkers();
    map.on("moveend", renderMarkers);
    map.on("zoomend", renderMarkers);
    return () => { map.off("moveend", renderMarkers); map.off("zoomend", renderMarkers); };
  }, [mapReady, renderMarkers]);

  // Desktop popup: the selected spot's Landing-style tile, anchored to its
  // marker (hidden on narrow screens via `.swd-map-popup` CSS). A plain Leaflet
  // popup just hosts a React portal so this is the same SpotCard used elsewhere.
  useEffect(() => {
    const map = mapRef.current;
    popupRef.current?.remove();
    popupRef.current = null;
    setPopupContainer(null);
    if (!mapReady || !map || !selectedSpot?.coords) return;
    const el = document.createElement("div");
    const popup = L.popup({ closeButton: false, autoClose: false, closeOnClick: false, autoPan: false, offset: [0, -14], className: "swd-map-popup", maxWidth: 200 })
      .setLatLng([selectedSpot.coords[0], selectedSpot.coords[1]])
      .setContent(el)
      .openOn(map);
    popupRef.current = popup;
    setPopupContainer(el);
    return () => { popup.remove(); if (popupRef.current === popup) popupRef.current = null; };
  }, [mapReady, selectedSpot]);

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

  const listEmptyLabel = viewportSpots.length === 0 ? "Keine Spots in diesem Kartenausschnitt" : `${spotCountLabel(viewportSpots.length)} · Zum Entdecken heranzoomen`;
  const regionLine = (spot: Spot) => [spot.regionName, countryName(spot.regionCountry ?? undefined)].filter(Boolean).join(" · ");

  return (
    <main data-lenis-prevent className={`swd-public-map relative w-full overflow-hidden ${selectedSpot ? "has-bottom-panel" : ""}`} aria-labelledby="public-map-title">
      <Header />
      <h1 id="public-map-title" className="sr-only">Spot-Karte</h1>
      <div role="region" aria-label="Interaktive Karte der veröffentlichten Surfspots" className="absolute inset-0">
        <div className={`swd-map-canvas h-full w-full transition-opacity duration-300 ${mapReady ? "opacity-100" : "opacity-0"}`}>
          <div ref={containerRef} className="h-full w-full" />
        </div>
      </div>
      {popupContainer && selectedSpot && createPortal(
        <div className="w-[176px]"><SpotCard spot={selectedSpot} live={live?.get(selectedSpot.id)} /></div>,
        popupContainer,
      )}
      {mapError && (
        <div role="status" className="swd-map-error absolute left-1/2 top-24 z-20 -translate-x-1/2">
          <span>Karte momentan nicht verfügbar.</span>
          <button type="button" onClick={() => window.location.reload()}>Erneut versuchen</button>
        </div>
      )}
      <div className="swd-map-controls-left pointer-events-none absolute z-20 flex flex-col items-start gap-3">
        <button type="button" aria-label="Zurück" onClick={goBack} className="swd-map-back pointer-events-auto">
          <ChevronLeftIcon className="text-sz-19" />
        </button>
        <div className="swd-map-control-group pointer-events-auto flex flex-col overflow-hidden">
          <button type="button" aria-label="Vergrößern" onClick={() => mapRef.current?.zoomIn()} className="swd-map-control swd-map-control-stacked"><PlusIcon className="text-sz-17" /></button>
          <span className="mx-2 h-px bg-line" />
          <button type="button" aria-label="Verkleinern" onClick={() => mapRef.current?.zoomOut()} className="swd-map-control swd-map-control-stacked"><MinusIcon className="text-sz-17" /></button>
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
            <ListIcon className="text-sz-17" />
          </button>
        </div>
      )}
      {tilesOpen && (
        <div id="swd-map-list-panel" className="swd-map-side-panel pointer-events-auto absolute z-20">
            <div className="swd-map-panel-head">
              <p className="swd-map-list-title">Spots im Ausschnitt</p>
              <button type="button" aria-label="Schließen" aria-expanded={true} onClick={() => setTilesOpen(false)} className="swd-map-plain-close">
                <CloseIcon className="text-body" />
              </button>
            </div>
            {listPanelSpots.length === 0 ? (
              <p role="status" className="swd-map-list-empty">{listEmptyLabel}</p>
            ) : (
              <div className="swd-map-tile-grid">
                {listPanelSpots.map((spot) => <SpotCard key={spot.id} spot={spot} live={live?.get(spot.id)} />)}
              </div>
            )}
          </div>
        )}
      {selectedSpot && (
        <section aria-label="Kartendetails" className="swd-map-bottom-shell pointer-events-none absolute inset-x-0 bottom-0 z-10">
          <div className="swd-map-panel pointer-events-auto">
            <div className="swd-map-panel-head">
              <div className="min-w-0">
                <p className="truncate font-semibold text-ink">{selectedSpot.name}</p>
                {regionLine(selectedSpot) && <p className="truncate text-caption text-muted">{regionLine(selectedSpot)}</p>}
              </div>
              <div className="flex shrink-0 items-center gap-2">
                <Link to={spotPath(selectedSpot)} className="swd-map-chart-cta">Zum Spot</Link>
                <button type="button" aria-label="Schließen" onClick={() => setSelectedId(undefined)} className="swd-map-plain-close">
                  <CloseIcon className="text-body" />
                </button>
              </div>
            </div>
            <div className="swd-map-chart-scroll">
              {selectedForecastLoading && <div className="h-[258px] animate-pulse bg-band" />}
              {!selectedForecastLoading && (
                <Suspense fallback={<div className="h-[258px]" />}>
                  {selectedForecast && selectedForecast.days.some((day) => day.hours.length > 0) ? (
                    <SpotDataScopeProvider forecast={selectedForecast}>
                      <MapForecastChart forecast={selectedForecast} />
                    </SpotDataScopeProvider>
                  ) : (
                    <p className="flex h-[80px] items-center justify-center px-4 text-center text-caption text-muted">Vorhersage momentan nicht verfügbar.</p>
                  )}
                </Suspense>
              )}
            </div>
          </div>
        </section>
      )}
    </main>
  );
}
