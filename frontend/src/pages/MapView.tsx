import { lazy, Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Link, useLocation, useNavigate } from "react-router-dom";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import "../map.css";
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
import { useSpotOriginsMixed } from "../context/SpotOriginContext";
import {
  parsePublicMapUrl,
  publicMapSearch,
  PUBLIC_SPOT_CLUSTER_MAX_ZOOM,
  PUBLIC_SPOT_CLUSTER_RADIUS,
  SPOT_DOT_COLOR,
  spotFeatures,
  sortViewportSpots,
  spotCountLabel,
  type PublicSpotProperties,
} from "../lib/publicMap";
import { cartoTileUrl, prefersRetinaTiles, CARTO_ATTRIBUTION, CARTO_VOYAGER_LABELS, CARTO_VOYAGER_NOLABELS } from "../lib/basemaps";
import LeafletAttributionDisclosure from "../components/LeafletAttributionDisclosure";
import ExplorerModeToggle from "../weather-map/ExplorerModeToggle";
import { parseFieldUrlState, updateFieldUrl, type ExplorerMode } from "../weather-map/fieldUrlState";
import { EUROPE_COUNTRY_LABELS, PLACE_LABEL_MIN_ZOOM } from "../weather-map/countryLabels";

const MapForecastChart = lazy(() => import("../components/data/MapForecastChart"));
const WindExplorer = lazy(() => import("../weather-map/WindExplorer"));

// The spot map is LIGHT again (2026-10-12): the dark ground was tried for a
// day and read as soot even once it was tinted blue. Back to Voyager's native
// travel palette — pale blue water, warm land, restrained detail — with its
// own dark haloed labels on top and no colour filter at all. @2x where the
// screen can show it, so the coast stays sharp.
const TILE_URL = cartoTileUrl(CARTO_VOYAGER_NOLABELS, { retina: prefersRetinaTiles() });
const LABEL_TILE_URL = cartoTileUrl(CARTO_VOYAGER_LABELS, { retina: prefersRetinaTiles() });
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
// The map is deliberately always light — it never follows the site's dark
// mode. See the `--sw-*`/`--map-*` token overrides scoped to `.swd-public-map`.
const reducedMotion = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;

type ClusterOrPoint = Supercluster.ClusterFeature<Supercluster.AnyProps> | Supercluster.PointFeature<PublicSpotProperties>;

function SpotExplorer({
  active,
  onModeChange,
}: {
  active: boolean;
  onModeChange: (mode: ExplorerMode) => void;
}) {
  const navigate = useNavigate();
  const location = useLocation();
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<L.Map | null>(null);
  const markersLayer = useRef<L.LayerGroup | null>(null);
  // Keyed cache of live markers (`c:<clusterId>` / `p:<spotId>` → marker + a
  // signature of its visual state) so a pan/zoom reuses unchanged markers
  // instead of clearing and rebuilding the whole layer each move.
  const markerCache = useRef<Map<string, { marker: L.Marker; sig: string }>>(new Map());
  const indexRef = useRef<Supercluster<PublicSpotProperties> | null>(null);
  const popupRef = useRef<L.Popup | null>(null);
  const initialView = useRef(parsePublicMapUrl(window.location.search));
  const initialCoordinates = useRef<[number, number][]>([]);
  const [mapReady, setMapReady] = useState(false);
  const [viewportIds, setViewportIds] = useState<string[]>([]);
  const [selectedId, setSelectedId] = useState<string | undefined>(() => parsePublicMapUrl(window.location.search)?.spot);
  const [tilesOpen, setTilesOpen] = useState(false);
  const [popupContainer, setPopupContainer] = useState<HTMLDivElement | null>(null);
  const [catalogVersion, setCatalogVersion] = useState<string>();
  const [catalogReady, setCatalogReady] = useState(false);
  const [mapError, setMapError] = useState(false);
  const knownVersion = useRef<string>();
  const { data: spots, loading: spotsLoading, error: spotsError, reload: reloadSpots } = useSpots(
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
  initialCoordinates.current = withCoords.map((spot) => spot.coords);
  // A shared/deep-linked view can start immediately. The default overview
  // waits for the catalogue, so Leaflet requests only the final fitted zoom
  // instead of loading a temporary world view and replacing every tile.
  const mapCanInitialize = initialView.current !== null || (catalogReady && !spotsLoading);
  const spotById = useMemo(() => new Map(withCoords.map((spot) => [spot.id, spot])), [withCoords]);
  // Gate for the origin treatment: no mark while every spot is ours.
  const originsMixed = useSpotOriginsMixed();
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
      setViewportIds(withCoords.filter((spot) => bounds.contains([spot.coords[0], spot.coords[1]])).map((spot) => spot.id));
    }, VIEWPORT_DEBOUNCE_MS);
  }, [selectedId, withCoords]);

  // --- map construction -----------------------------------------------------
  useEffect(() => {
    if (!mapCanInitialize || !containerRef.current || mapRef.current) return;
    const container = containerRef.current;
    const saved = initialView.current;
    let map: L.Map;
    let tileLayer: L.TileLayer;
    let labelLayer: L.TileLayer;
    let countryLabels: L.LayerGroup;
    let revealTimer = 0;
    let readyFrame = 0;
    try {
      map = L.map(container, {
        minZoom: 2,
        maxZoom: 17,
        zoomControl: false,
        attributionControl: false,
        // Tiles appear as soon as their bytes arrive. Keeping the old level
        // underneath provides the transition; a second opacity fade only
        // prolongs pale gaps on slower connections.
        fadeAnimation: false,
        // Fine zoom snapping keeps fitBounds/cluster easing from clamping to
        // whole levels; a gentler wheel ratio + debounce turns scroll-zoom from
        // steppy jumps into a smooth glide.
        zoomSnap: 0.25,
        wheelPxPerZoomLevel: 120,
        wheelDebounceTime: 30,
        worldCopyJump: false,
      });
      if (saved) {
        map.setView([saved.center[1], saved.center[0]], saved.zoom, { animate: false });
      } else if (initialCoordinates.current.length > 0) {
        map.fitBounds(L.latLngBounds(initialCoordinates.current), {
          paddingTopLeft: [52, 100],
          paddingBottomRight: [52, window.innerWidth < 640 ? 270 : 240],
          maxZoom: 7,
          animate: false,
        });
      } else {
        map.setView([40.3, 9.3], 3, { animate: false });
      }
      tileLayer = L.tileLayer(TILE_URL, {
        subdomains: "a",
        attribution: TILE_ATTRIBUTION,
        maxZoom: 20,
        detectRetina: false,
        // Request the next integer tile level during a smooth zoom, including
        // on touch devices, and keep a generous off-screen ring. Leaflet then
        // retains loaded parent/child tiles until their replacements are ready.
        updateWhenIdle: false,
        updateWhenZooming: true,
        updateInterval: 120,
        keepBuffer: 4,
      }).addTo(map);
      // CARTO's raster labels cannot distinguish countries from cities. Keep
      // them out until street-level context is useful; the sparse country
      // markers below carry the continental overview on their own.
      labelLayer = L.tileLayer(LABEL_TILE_URL, {
        subdomains: "a",
        attribution: TILE_ATTRIBUTION,
        minZoom: PLACE_LABEL_MIN_ZOOM,
        maxZoom: 20,
        detectRetina: false,
        updateWhenIdle: false,
        updateWhenZooming: true,
        keepBuffer: 3,
        pane: "overlayPane",
      }).addTo(map);
      countryLabels = L.layerGroup(EUROPE_COUNTRY_LABELS.map(([name, longitude, latitude]) => L.marker(
        [latitude, longitude],
        {
          interactive: false,
          keyboard: false,
          icon: L.divIcon({ className: "swd-country-label-marker", html: `<span>${name}</span>` }),
        },
      ))).addTo(map);
    } catch (err) {
      console.error("Public map: failed to construct Leaflet map", err);
      setMapError(true);
      return;
    }
    mapRef.current = map;
    markersLayer.current = L.layerGroup().addTo(map);
    const markersForCleanup = markerCache.current;
    const syncCountryLabels = () => {
      if (map.getZoom() < PLACE_LABEL_MIN_ZOOM) {
        if (!map.hasLayer(countryLabels)) countryLabels.addTo(map);
      } else if (map.hasLayer(countryLabels)) map.removeLayer(countryLabels);
    };
    map.on("zoomend", syncCountryLabels);
    syncCountryLabels();
    // Keep Leaflet's cached pixel size in step with the container. On mobile the
    // visual viewport changes height when the address bar collapses and width on
    // rotation; without this the map keeps its first-measured size and leaves a
    // bare strip (showing through to whatever is behind the app) along the edge
    // that grew. A ResizeObserver catches both, where a one-shot invalidateSize
    // at init cannot. The resize runs in the next frame — never synchronously
    // inside the observer callback — so Leaflet's own relayout can't re-enter the
    // observer and trip the "ResizeObserver loop" error.
    let resizeFrame = 0;
    const resizeObserver = new ResizeObserver(() => {
      cancelAnimationFrame(resizeFrame);
      resizeFrame = requestAnimationFrame(() => { if (mapRef.current === map) map.invalidateSize({ animate: false }); });
    });
    resizeObserver.observe(container);
    // Background click closes whichever bottom panel is open (marker clicks call
    // stopPropagation via Leaflet's own layer events, so they don't bubble here).
    map.on("click", () => { setSelectedId(undefined); setTilesOpen(false); });
    const revealMap = () => {
      window.clearTimeout(revealTimer);
      tileLayer.off("load", revealMap);
      map.off("zoomend", syncCountryLabels);
      labelLayer.remove();
      setMapReady(true);
    };
    // Reveal the map as one composed surface after its first visible tile set
    // has loaded. The timeout preserves a usable partial map during provider
    // errors instead of leaving the canvas hidden indefinitely.
    revealTimer = window.setTimeout(revealMap, 1800);
    readyFrame = requestAnimationFrame(() => {
      map.invalidateSize();
      if (tileLayer.isLoading()) tileLayer.once("load", revealMap);
      else revealMap();
    });
    return () => {
      cancelAnimationFrame(readyFrame);
      window.clearTimeout(revealTimer);
      tileLayer.off("load", revealMap);
      window.clearTimeout(viewportTimer.current);
      resizeObserver.disconnect();
      cancelAnimationFrame(resizeFrame);
      map.remove();
      mapRef.current = null;
      markersLayer.current = null;
      markersForCleanup.clear();
      popupRef.current = null;
    };
  }, [mapCanInitialize]);

  // Viewport tracking (URL + debounced live/list commit).
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReady) return;
    map.on("moveend", commitViewport); commitViewport();
    return () => { map.off("moveend", commitViewport); };
  }, [mapReady, commitViewport]);

  // The map stays mounted behind the wind/wave canvas. On return, resize the
  // retained Leaflet surface and adopt the shared URL camera instead of
  // rebuilding every tile, cluster and marker from scratch.
  useEffect(() => {
    const map = mapRef.current;
    if (!active || !map) return;
    const shared = parsePublicMapUrl(window.location.search);
    const frame = window.requestAnimationFrame(() => {
      map.invalidateSize({ pan: false });
      if (shared) map.setView([shared.center[1], shared.center[0]], shared.zoom, { animate: false });
    });
    return () => window.cancelAnimationFrame(frame);
  }, [active]);

  // No live query for the markers any more: every dot is `SPOT_DOT_COLOR`,
  // so there is nothing to tint. Live readings are still fetched for the
  // spots shown in the bottom row and the selected spot's card.

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
    const cache = markerCache.current;
    const b = map.getBounds();
    const clusters = index.getClusters([b.getWest(), b.getSouth(), b.getEast(), b.getNorth()], Math.round(map.getZoom())) as ClusterOrPoint[];
    // Diff the desired feature set against the live markers: keep any whose
    // visual signature is unchanged, (re)build only what actually differs, and
    // drop what's no longer in view. Avoids the full clear→rebuild flicker.
    const alive = new Set<string>();
    for (const feature of clusters) {
      const [lng, lat] = feature.geometry.coordinates;
      const props = feature.properties as Supercluster.ClusterProperties & PublicSpotProperties;
      const key = props.cluster ? `c:${props.cluster_id}` : `p:${props.spotId}`;
      let sig: string;
      let build: () => L.Marker;
      if (props.cluster) {
        const count = props.point_count;
        // Cluster ids/centroids are per-zoom, so a moved centroid at the same id
        // must still rebuild — fold rounded position into the signature.
        sig = `${count}@${lat.toFixed(4)},${lng.toFixed(4)}`;
        build = () => {
          const size = count < 10 ? 30 : count < 50 ? 34 : 38;
          const icon = L.divIcon({ className: "swd-map-cluster-icon", html: `<span class="swd-map-cluster" style="width:${size}px;height:${size}px">${count}</span>`, iconSize: [44, 44], iconAnchor: [22, 22] });
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
          return marker;
        };
      } else {
        const spot = spotById.get(props.spotId);
        if (!spot) continue;
        const selected = props.spotId === selectedId;
        // Same disc, open instead of filled — the mark says who entered the
        // spot, not how good it is. Hidden while the catalogue is all ours.
        const community = originsMixed && spot.origin === "community";
        sig = `${selected ? "s" : ""}${community ? "c" : ""}`;
        build = () => {
          const icon = L.divIcon({ className: `swd-map-a11y-marker${selected ? " is-selected" : ""}`, html: `<span class="swd-map-dot${community ? " is-community" : ""}" style="--swd-map-dot-color:${SPOT_DOT_COLOR}"></span>`, iconSize: [44, 44], iconAnchor: [22, 22] });
          const marker = L.marker([lat, lng], { icon, keyboard: true });
          marker.on("add", () => {
            const el = marker.getElement();
            if (!el) return;
            el.setAttribute("aria-label", community ? `Surfspot ${spot.name}, von der Community eingetragen` : `Surfspot ${spot.name}`);
            el.setAttribute("data-tooltip", spot.name);
            el.setAttribute("aria-pressed", String(selected));
          });
          marker.on("click", () => {
            setSelectedId(props.spotId);
            setTilesOpen(false);
            map.setView([lat, lng], Math.max(map.getZoom(), SINGLE_SPOT_ZOOM), { animate: !reducedMotion() });
          });
          return marker;
        };
      }
      alive.add(key);
      const existing = cache.get(key);
      if (existing && existing.sig === sig) continue; // unchanged → leave in place
      if (existing) layer.removeLayer(existing.marker);
      const marker = build();
      layer.addLayer(marker);
      cache.set(key, { marker, sig });
    }
    // Remove markers that dropped out of view / the feature set.
    for (const [key, entry] of cache) {
      if (alive.has(key)) continue;
      layer.removeLayer(entry.marker);
      cache.delete(key);
    }
  }, [selectedId, spotById, originsMixed]);

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
  const catalogueUnavailable = Boolean(spotsError && !spots?.length);
  const retryMapProblem = () => {
    setMapError(false);
    if (catalogueUnavailable) reloadSpots();
    else window.location.reload();
  };

  return (
    <main data-lenis-prevent className={`swd-public-map relative w-full overflow-hidden ${selectedSpot ? "has-bottom-panel" : ""} ${tilesOpen ? "has-bottom-row" : ""}`} aria-labelledby="public-map-title">
      {/* The search is docked at the bottom centre; while the selected-spot
          chart or the spot row holds the bottom, drop the search so the two
          don't stack on top of each other. */}
      {!selectedSpot && !tilesOpen && <Header />}
      <ExplorerModeToggle mode="spots" onChange={onModeChange} />
      <h1 id="public-map-title" className="sr-only">Spot-Karte</h1>
      <p id="public-map-help" className="sr-only">
        Nutze die Zoomtasten oder die Kartensteuerung. Spotmarker sind per Tastatur erreichbar und öffnen eine Vorschau.
      </p>
      <div role="region" aria-label="Interaktive Karte der veröffentlichten Surfspots" aria-busy={spotsLoading} className="absolute inset-0">
        <div className={`swd-map-canvas h-full w-full transition-opacity duration-slow ${mapReady ? "opacity-100" : "opacity-0"}`}>
          <div ref={containerRef} aria-label="Surfspot-Karte" aria-describedby="public-map-help" className="h-full w-full" />
        </div>
      </div>
      {popupContainer && selectedSpot && createPortal(
        <div className="w-[176px]"><SpotCard spot={selectedSpot} live={live?.get(selectedSpot.id)} preferLiveWind /></div>,
        popupContainer,
      )}
      {(mapError || catalogueUnavailable) && (
        <div role="alert" className="swd-map-error absolute left-1/2 top-24 z-scrim -translate-x-1/2">
          <div>
            <strong>{catalogueUnavailable ? "Spots konnten nicht geladen werden." : "Karte momentan nicht verfügbar."}</strong>
            <p>{catalogueUnavailable ? spotsError : "Prüfe deine Verbindung und lade die Karte erneut."}</p>
          </div>
          <button type="button" onClick={retryMapProblem}>Erneut versuchen</button>
        </div>
      )}
      <LeafletAttributionDisclosure source="carto" />
      <div className="swd-map-controls-left pointer-events-none absolute z-scrim flex flex-col items-start gap-2">
        <button type="button" aria-label="Zurück" onClick={goBack} className="swd-map-bare-control pointer-events-auto">
          <ChevronLeftIcon className="text-title" />
        </button>
        <div className="pointer-events-auto flex flex-col">
          <button type="button" aria-label="Vergrößern" onClick={() => mapRef.current?.zoomIn()} className="swd-map-bare-control"><PlusIcon className="text-title" /></button>
          <button type="button" aria-label="Verkleinern" onClick={() => mapRef.current?.zoomOut()} className="swd-map-bare-control"><MinusIcon className="text-title" /></button>
        </div>
      </div>
      {/* The list glyph stays put whether the row is open or not — it is the
          switch for it, not a one-way door (2026-10-11 feedback: it used to
          vanish on the first tap). Bare mark, same size as back/zoom. */}
      <div className="swd-map-controls pointer-events-none absolute z-scrim flex flex-col items-end gap-3">
        <button
          type="button"
          aria-label="Spots im Ausschnitt anzeigen"
          aria-pressed={tilesOpen}
          aria-expanded={tilesOpen}
          aria-controls="swd-map-list-panel"
          onClick={() => { setTilesOpen((open) => !open); setSelectedId(undefined); }}
          className="swd-map-bare-control pointer-events-auto"
        >
          <ListIcon className="text-title" />
        </button>
      </div>
      {tilesOpen && (
        <section id="swd-map-list-panel" aria-label="Spots im Ausschnitt" className="swd-map-bottom-shell is-row pointer-events-none absolute inset-x-0 bottom-0 z-scrim">
          <div className="swd-map-panel pointer-events-auto">
            <div className="swd-map-panel-head">
              <p className="swd-map-list-title">Spots im Ausschnitt</p>
              <button type="button" aria-label="Schließen" aria-expanded={true} onClick={() => setTilesOpen(false)} className="swd-map-plain-close">
                <CloseIcon className="text-body" />
              </button>
            </div>
            {listPanelSpots.length === 0 ? (
              <p role="status" className="swd-map-list-empty">{listEmptyLabel}</p>
            ) : (
              <div className="swd-map-row-scroll">
                {listPanelSpots.map((spot) => (
                  <div key={spot.id} className="swd-map-row-item">
                    <SpotCard spot={spot} live={live?.get(spot.id)} mapRail preferLiveWind />
                  </div>
                ))}
              </div>
            )}
          </div>
        </section>
      )}
      {selectedSpot && (
        <section aria-label="Kartendetails" className="swd-map-bottom-shell pointer-events-none absolute inset-x-0 bottom-0 z-scrim">
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

export default function MapView() {
  const [mode, setMode] = useState<ExplorerMode>(() => parseFieldUrlState(window.location.search).mode);
  const [weatherMode, setWeatherMode] = useState<"wind" | "waves">(() => {
    const initial = parseFieldUrlState(window.location.search).mode;
    return initial === "waves" ? "waves" : "wind";
  });
  useEffect(() => {
    const sync = () => {
      setMode(parseFieldUrlState(window.location.search).mode);
    };
    window.addEventListener("popstate", sync);
    return () => window.removeEventListener("popstate", sync);
  }, []);
  const changeMode = (next: ExplorerMode) => {
    updateFieldUrl({ mode: next }, false);
    if (next !== "spots") setWeatherMode(next);
    setMode(next);
  };
  return (
    <div className="swd-explorer-stack">
      <div className={`swd-explorer-pane${mode === "spots" ? " is-active" : ""}`} aria-hidden={mode !== "spots"}>
        <SpotExplorer active={mode === "spots"} onModeChange={changeMode} />
      </div>
      <div className={`swd-explorer-pane${mode !== "spots" ? " is-active" : ""}`} aria-hidden={mode === "spots"}>
        <Suspense fallback={null}>
          <WindExplorer active={mode !== "spots"} product={weatherMode} onModeChange={changeMode} />
        </Suspense>
      </div>
    </div>
  );
}
