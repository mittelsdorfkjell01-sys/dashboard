import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import * as maplibregl from "maplibre-gl";
import "../lib/maplibreWorker";
import type { Map as MapLibreMap } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import "../map.css";
import { directionsUrl, haversineKm, mapLinkProps, placeUrl } from "../lib/mapLinks";
import { CloseIcon } from "../lib/icons";
import LeafletAttributionDisclosure from "./LeafletAttributionDisclosure";
import { SPOT_DOT_SIZE, spotDotHtml, spotDotVariant } from "../lib/spotPin";
import { useSpotOriginsMixed } from "../context/SpotOriginContext";
import { useOptionalUnits } from "../context/PrefsContext";
import { getMapPois, type MapPoi, type SpotOrigin } from "../lib/api";
import { formatDistance } from "../lib/units";
import { useMapLocation } from "../lib/useMapLocation";
import { POI_LOAD_ZOOM, POI_META, poiTitle } from "./locator/poiMeta";
import { layoutPois, type Box } from "./locator/poiLayout";
import { LocationSheet, PickSheet, PoiSheet, SpotSheet, type LocateStatus } from "./locator/LocatorSheets";
import { standardStyle } from "./locator/standardStyle";
import { useSiteTheme } from "../lib/theme";

const INITIAL_ZOOM = 12;
const MAX_ZOOM = 18.5;
const ZOOM_STEP = 0.75;

const reducedMotion = () =>
  typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

type Sheet =
  | { kind: "poi"; id: string }
  | { kind: "spot" }
  | { kind: "location" }
  | null;

/** Handlers switched by the click-to-activate flow. Rotation and pitch stay
 *  off: a north-up map needs no compass. */
function setInteractive(map: MapLibreMap, on: boolean) {
  for (const handler of [map.dragPan, map.scrollZoom, map.boxZoom, map.doubleClickZoom, map.keyboard, map.touchZoomRotate]) {
    if (on) handler.enable();
    else handler.disable();
  }
  map.touchZoomRotate.disableRotation();
}

function poiElement(poi: MapPoi): HTMLButtonElement {
  const meta = POI_META[poi.category];
  const button = document.createElement("button");
  button.type = "button";
  button.className = `swd-poi swd-poi-${poi.category}`;
  button.hidden = true;
  button.setAttribute("aria-label", `${meta.label}: ${poiTitle(poi)}`);
  button.title = `${meta.label}: ${poiTitle(poi)}`;
  const disc = document.createElement("span");
  disc.className = "swd-poi-disc";
  disc.setAttribute("aria-hidden", "true");
  disc.innerHTML = `<svg viewBox="0 0 20 20" focusable="false"><path d="${meta.path}"/></svg>`;
  button.append(disc);
  if (poi.name) {
    const name = document.createElement("span");
    name.className = "swd-poi-name";
    name.setAttribute("aria-hidden", "true");
    name.textContent = poi.name;
    button.append(name);
  }
  return button;
}

/**
 * "Lage" — the spot's map, modelled on Apple Maps' standard map: a soft
 * vector ground, small round category icons that appear as you zoom in and
 * never crowd each other, a card for whatever you tap, your own position, and
 * a route hand-off to the rider's maps app. The controls are bare white glyphs.
 *
 * Interaction is click-to-activate on desktop (page scroll is never
 * hijacked) and a tap-to-fullscreen on phones.
 */
export default function LocatorMap({
  coords,
  origin,
  name = "Spot",
  timeZone,
}: {
  coords: [number, number];
  /** Herkunft des Spots — variiert nur die Füllung des Pins. */
  origin?: SpotOrigin;
  name?: string;
  /** IANA-Zeitzone des Spots — für „Geöffnet/Geschlossen“ in der Ortskachel. */
  timeZone?: string | null;
}) {
  const [lat, lng] = coords;
  const originsMixed = useSpotOriginsMixed();
  const units = useOptionalUnits();
  const theme = useSiteTheme();
  const themeRef = useRef(theme);
  themeRef.current = theme;
  const { location, save: saveLocation, syncError } = useMapLocation();

  const rootRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const activationButtonRef = useRef<HTMLButtonElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const poiMarkersRef = useRef(new Map<string, { marker: maplibregl.Marker; element: HTMLButtonElement; poi: MapPoi }>());
  const userMarkerRef = useRef<maplibregl.Marker | null>(null);
  const poiAbortRef = useRef<AbortController | null>(null);
  const poiRequestedRef = useRef(false);
  const selectedIdRef = useRef<string | null>(null);
  const relayoutRef = useRef<() => void>(() => {});
  const tileErrorRef = useRef(false);

  const [active, setActive] = useState(false);
  const [fullscreen, setFullscreen] = useState(false);
  const [small, setSmall] = useState(
    () => typeof window !== "undefined" && window.matchMedia("(max-width: 1023.98px)").matches,
  );
  const [ready, setReady] = useState(false);
  const [unavailable, setUnavailable] = useState(false);
  const [tilesLoading, setTilesLoading] = useState(false);
  const [showLoadingNotice, setShowLoadingNotice] = useState(false);
  const [tilesIncomplete, setTilesIncomplete] = useState(false);
  const [poiItems, setPoiItems] = useState<MapPoi[]>([]);
  const [poiZoom, setPoiZoom] = useState(false);
  const [poiStatus, setPoiStatus] = useState<"idle" | "loading" | "ready" | "error">("idle");
  const [sheet, setSheet] = useState<Sheet>(null);
  const [picking, setPicking] = useState(false);
  const [locateStatus, setLocateStatus] = useState<LocateStatus>("idle");

  const canLocate = typeof navigator !== "undefined" && "geolocation" in navigator
    && (typeof window === "undefined" || window.isSecureContext !== false);
  const userCoords = useMemo<[number, number] | null>(
    () => (location ? [location.lat, location.lon] : null),
    [location],
  );
  const distanceToSpot = userCoords ? formatDistance(haversineKm(userCoords, coords), units.distance) : null;
  const spotRoute = directionsUrl(coords, userCoords);
  const selectedPoi = sheet?.kind === "poi" ? poiItems.find((poi) => poi.id === sheet.id) ?? null : null;
  selectedIdRef.current = selectedPoi?.id ?? null;

  useEffect(() => {
    const mq = window.matchMedia("(max-width: 1023.98px)");
    const update = () => setSmall(mq.matches);
    update();
    mq.addEventListener("change", update);
    return () => mq.removeEventListener("change", update);
  }, []);

  const loadPois = useCallback(async () => {
    if (poiRequestedRef.current) return;
    poiRequestedRef.current = true;
    poiAbortRef.current?.abort();
    const controller = new AbortController();
    poiAbortRef.current = controller;
    setPoiStatus("loading");
    try {
      const result = await getMapPois(lat, lng, 3_000, controller.signal);
      setPoiItems(result.items);
      setPoiStatus("ready");
    } catch (error) {
      if (controller.signal.aborted) return;
      console.warn("Unable to load nearby OpenStreetMap POIs:", error);
      setPoiStatus("error");
    }
  }, [lat, lng]);

  useEffect(() => {
    if (!tilesLoading) {
      setShowLoadingNotice(false);
      return;
    }
    const timer = window.setTimeout(() => setShowLoadingNotice(true), 250);
    return () => window.clearTimeout(timer);
  }, [tilesLoading]);

  useEffect(() => {
    poiAbortRef.current?.abort();
    poiRequestedRef.current = false;
    setPoiItems([]);
    setPoiStatus("idle");
    setSheet(null);
  }, [lat, lng]);

  // --- The map itself -------------------------------------------------------
  useEffect(() => {
    const container = containerRef.current;
    const root = rootRef.current;
    if (!container || !root || mapRef.current) return;
    let map: MapLibreMap;
    try {
      map = new maplibregl.Map({
        container,
        style: standardStyle(themeRef.current),
        center: [lng, lat],
        zoom: INITIAL_ZOOM,
        minZoom: 2,
        maxZoom: MAX_ZOOM,
        attributionControl: false,
        dragRotate: false,
        pitchWithRotate: false,
        touchPitch: false,
        renderWorldCopies: false,
        fadeDuration: 160,
        locale: { "Map.Title": "Karte" },
      });
    } catch (error) {
      console.error("Unable to initialise locator map:", error);
      setUnavailable(true);
      return;
    }
    mapRef.current = map;
    setInteractive(map, false);
    const startedAt = performance.now();
    tileErrorRef.current = false;
    let errorTimer = 0;
    let readyReported = false;
    let tileRequests = 0;

    const updateZoomDataset = () => {
      root.dataset.currentZoom = map.getZoom().toFixed(3);
      setPoiZoom(map.getZoom() >= POI_LOAD_ZOOM);
    };
    map.on("dataloading", (event) => {
      if ((event as { sourceId?: string }).sourceId !== "base") return;
      if (!readyReported) tileRequests += 1;
      setTilesLoading(true);
    });
    map.on("error", (event) => {
      if ((event as { sourceId?: string }).sourceId !== "base") {
        console.warn("Locator map error:", event.error);
        return;
      }
      tileErrorRef.current = true;
      // A failed vector tile can keep MapLibre from ever going idle, so the
      // gap is reported shortly after the last error instead.
      window.clearTimeout(errorTimer);
      errorTimer = window.setTimeout(() => {
        setTilesLoading(false);
        setTilesIncomplete(true);
      }, 600);
    });
    map.on("movestart", () => { tileErrorRef.current = false; });
    map.on("idle", () => {
      window.clearTimeout(errorTimer);
      setTilesLoading(false);
      setTilesIncomplete(tileErrorRef.current);
      if (!readyReported && !tileErrorRef.current) {
        readyReported = true;
        root.dataset.visibleReadyMs = String(Math.round((performance.now() - startedAt) * 10) / 10);
        root.dataset.visibleTileRequests = String(tileRequests);
        root.dispatchEvent(new CustomEvent("swd:locator-ready", { bubbles: true }));
      }
    });
    map.on("zoom", updateZoomDataset);
    let layoutFrame = 0;
    const scheduleLayout = () => {
      cancelAnimationFrame(layoutFrame);
      layoutFrame = requestAnimationFrame(() => relayoutRef.current());
    };
    map.on("move", scheduleLayout);
    map.on("resize", scheduleLayout);
    updateZoomDataset();

    const spotElement = document.createElement("button");
    spotElement.type = "button";
    spotElement.className = "swd-locator-spot";
    spotElement.setAttribute("aria-label", `Spot ${name}`);
    spotElement.innerHTML = spotDotHtml(spotDotVariant(origin, originsMixed));
    spotElement.addEventListener("click", (event) => {
      event.stopPropagation();
      setSheet({ kind: "spot" });
    });
    new maplibregl.Marker({ element: spotElement, anchor: "center" }).setLngLat([lng, lat]).addTo(map);

    const poiMarkers = poiMarkersRef.current;
    const resizeObserver = new ResizeObserver(() => map.resize());
    resizeObserver.observe(container);
    map.once("load", () => setReady(true));

    return () => {
      window.clearTimeout(errorTimer);
      cancelAnimationFrame(layoutFrame);
      resizeObserver.disconnect();
      poiMarkers.clear();
      userMarkerRef.current = null;
      map.remove();
      mapRef.current = null;
      setReady(false);
    };
  }, [lat, lng, name, origin, originsMixed]);

  // --- POI placement: Apple-size pins that never crowd ----------------------
  const relayout = useCallback(() => {
    const map = mapRef.current;
    if (!map) return;
    const canvas = map.getCanvas();
    const width = canvas.clientWidth;
    const height = canvas.clientHeight;
    const spot = map.project([lng, lat]);
    const reserved: Box[] = [{
      left: spot.x - SPOT_DOT_SIZE / 2, right: spot.x + SPOT_DOT_SIZE / 2,
      top: spot.y - SPOT_DOT_SIZE / 2, bottom: spot.y + SPOT_DOT_SIZE / 2,
    }];
    if (userCoords) {
      const me = map.project([userCoords[1], userCoords[0]]);
      reserved.push({ left: me.x - 12, right: me.x + 12, top: me.y - 12, bottom: me.y + 12 });
    }
    const entries = [...poiMarkersRef.current.values()];
    const placements = layoutPois(
      entries.map(({ poi }) => {
        const point = map.project([poi.lon, poi.lat]);
        return { id: poi.id, category: poi.category, name: poi.name, distance: poi.distance_m, x: point.x, y: point.y };
      }),
      { zoom: map.getZoom(), width, height, selectedId: selectedIdRef.current, reserved },
    );
    for (const { element, poi } of entries) {
      const placement = placements.get(poi.id);
      const visible = Boolean(placement?.visible);
      if (element.hidden === visible) {
        element.hidden = !visible;
        if (visible) element.classList.add("is-entering");
      }
      element.classList.toggle("has-label", Boolean(placement?.label));
      element.dataset.selected = poi.id === selectedIdRef.current ? "true" : "false";
    }
    if (rootRef.current) rootRef.current.dataset.visiblePois = String([...placements.values()].filter((p) => p.visible).length);
  }, [lat, lng, userCoords]);
  relayoutRef.current = relayout;

  useEffect(() => {
    if (ready && poiZoom) void loadPois();
  }, [loadPois, poiZoom, ready]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    const markers = poiMarkersRef.current;
    for (const { marker } of markers.values()) marker.remove();
    markers.clear();
    for (const poi of poiItems) {
      const element = poiElement(poi);
      element.addEventListener("click", (event) => {
        event.stopPropagation();
        setSheet({ kind: "poi", id: poi.id });
      });
      element.addEventListener("animationend", () => element.classList.remove("is-entering"));
      const marker = new maplibregl.Marker({ element, anchor: "center" }).setLngLat([poi.lon, poi.lat]).addTo(map);
      markers.set(poi.id, { marker, element, poi });
    }
    relayoutRef.current();
  }, [poiItems, ready]);

  useEffect(() => { relayoutRef.current(); }, [sheet, relayout]);

  // --- The rider's own position ---------------------------------------------
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    if (!userCoords) {
      userMarkerRef.current?.remove();
      userMarkerRef.current = null;
      return;
    }
    if (!userMarkerRef.current) {
      const element = document.createElement("span");
      element.className = "swd-locator-user";
      element.append(document.createElement("span"));
      element.setAttribute("role", "img");
      element.setAttribute("aria-label", "Dein Standort");
      userMarkerRef.current = new maplibregl.Marker({ element, anchor: "center" });
    }
    userMarkerRef.current.setLngLat([userCoords[1], userCoords[0]]).addTo(map);
    relayoutRef.current();
  }, [ready, userCoords]);

  const sheetPadding = useCallback(() => {
    const sheetHeight = rootRef.current?.querySelector<HTMLElement>(".swd-locator-sheet")?.offsetHeight ?? 0;
    // Right edge clears the control column, so neither pin lands under it.
    return { top: 72, bottom: Math.max(48, sheetHeight + 32), left: 48, right: 88 };
  }, []);

  const showBoth = useCallback((point: [number, number]) => {
    const map = mapRef.current;
    if (!map) return;
    const bounds = new maplibregl.LngLatBounds([lng, lat], [lng, lat]).extend([point[1], point[0]]);
    requestAnimationFrame(() => map.fitBounds(bounds, {
      padding: sheetPadding(), maxZoom: 15, duration: reducedMotion() ? 0 : 600,
    }));
  }, [lat, lng, sheetPadding]);

  const activate = useCallback(() => {
    if (small) setFullscreen(true);
    setActive(true);
  }, [small]);

  const locate = useCallback(() => {
    if (!canLocate) return;
    setLocateStatus("locating");
    navigator.geolocation.getCurrentPosition(
      (position) => {
        const point: [number, number] = [position.coords.latitude, position.coords.longitude];
        saveLocation({ lat: point[0], lon: point[1], source: "gps" });
        setLocateStatus("idle");
        showBoth(point);
      },
      (error) => setLocateStatus(error.code === error.PERMISSION_DENIED ? "denied" : "unavailable"),
      { enableHighAccuracy: true, timeout: 10_000, maximumAge: 60_000 },
    );
  }, [canLocate, saveLocation, showBoth]);

  const startPicking = useCallback(() => {
    activate();
    setSheet(null);
    setPicking(true);
    const map = mapRef.current;
    if (map && userCoords) map.jumpTo({ center: [userCoords[1], userCoords[0]] });
  }, [activate, userCoords]);

  const confirmPick = useCallback(() => {
    const map = mapRef.current;
    if (!map) return;
    const center = map.getCenter();
    saveLocation({ lat: center.lat, lon: center.lng, source: "manual" });
    setPicking(false);
    setSheet({ kind: "location" });
  }, [saveLocation]);

  const requestZoom = useCallback((delta: number) => {
    const map = mapRef.current;
    if (!map) return;
    map.easeTo({ zoom: map.getZoom() + delta, duration: reducedMotion() ? 0 : 220 });
  }, []);

  const reloadTiles = useCallback(() => {
    const map = mapRef.current;
    if (!map) return;
    setTilesIncomplete(false);
    tileErrorRef.current = false;
    // A fresh style re-requests every tile; markers are DOM and stay put.
    map.setStyle(standardStyle(themeRef.current), { diff: false });
  }, []);

  // The ground follows the site theme; a diffed style only repaints colours,
  // tiles and the DOM markers stay.
  const styledThemeRef = useRef(theme);
  useEffect(() => {
    const map = mapRef.current;
    if (!map || styledThemeRef.current === theme) return;
    styledThemeRef.current = theme;
    map.setStyle(standardStyle(theme));
  }, [theme]);

  const reloadPois = useCallback(() => {
    poiRequestedRef.current = false;
    void loadPois();
  }, [loadPois]);

  const closeFullscreen = useCallback(() => {
    setFullscreen(false);
    setActive(false);
    setPicking(false);
    setSheet(null);
    requestAnimationFrame(() => activationButtonRef.current?.focus({ preventScroll: true }));
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    setInteractive(map, active);
    if (active) map.getCanvas().focus({ preventScroll: true });
  }, [active, ready]);

  // Desktop only: while activated inline, a plain click on the map (not on a
  // pin, not a drag) locks it again, as before.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !active || fullscreen || picking) return;
    const lock = () => {
      if (sheet) setSheet(null);
      else setActive(false);
    };
    map.on("click", lock);
    return () => { map.off("click", lock); };
  }, [active, fullscreen, picking, sheet]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      if (picking) setPicking(false);
      else if (sheet) setSheet(null);
      else if (fullscreen) closeFullscreen();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [closeFullscreen, fullscreen, picking, sheet]);

  useEffect(() => {
    if (!fullscreen) return;
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const frame = requestAnimationFrame(() => {
      mapRef.current?.resize();
      closeButtonRef.current?.focus({ preventScroll: true });
    });
    return () => {
      document.body.style.overflow = previous;
      cancelAnimationFrame(frame);
      requestAnimationFrame(() => mapRef.current?.resize());
    };
  }, [fullscreen]);

  if (unavailable) {
    const link = mapLinkProps(lat, lng);
    return (
      <div className="grid h-[clamp(20rem,55svh,27.5rem)] place-items-center rounded-card bg-band px-6 text-center lg:h-full lg:min-h-[360px]">
        <div>
          <p className="text-ui font-semibold text-ink">Karte momentan nicht verfügbar</p>
          <a
            href={link.href}
            target={link.target}
            rel={link.rel}
            className="mt-4 inline-flex min-h-11 items-center px-4 py-2 text-ui font-semibold text-ink transition-opacity hover:underline hover:underline-offset-4 hover:opacity-70"
          >
            In externer Karte öffnen
          </a>
        </div>
      </div>
    );
  }

  const topOffset = fullscreen ? { top: "calc(0.75rem + env(safe-area-inset-top, 0px))" } : undefined;
  const notice = (() => {
    if (picking) return null;
    if (showLoadingNotice) return { role: "status" as const, text: "Karte wird geladen …" };
    if (tilesIncomplete && !tilesLoading) return { role: "alert" as const, text: "Karte unvollständig", action: reloadTiles };
    if (!poiZoom || tilesLoading) return null;
    if (poiStatus === "loading") return { role: "status" as const, text: "Orte werden geladen …" };
    if (poiStatus === "error") return { role: "alert" as const, text: "Orte momentan nicht verfügbar", action: reloadPois };
    if (poiStatus === "ready" && poiItems.length === 0) return { role: "status" as const, text: "Keine passenden OpenStreetMap-Einträge in der Nähe" };
    return null;
  })();

  return (
    <>
      {fullscreen && <div aria-hidden className="h-[clamp(20rem,55svh,27.5rem)] lg:h-full" />}
      <div
        ref={rootRef}
        data-lenis-prevent={active ? "" : undefined}
        data-map-active={active ? "true" : "false"}
        data-fullscreen={fullscreen ? "true" : "false"}
        className={`swd-locator-map ${
          fullscreen
            ? "fixed inset-0 z-fullscreen h-[100dvh] w-[100dvw] overflow-hidden"
            : "relative h-[clamp(20rem,55svh,27.5rem)] w-full min-w-0 max-w-full overflow-hidden rounded-card lg:h-full"
        }`}
      >
        <div ref={containerRef} className="swd-locator-canvas" />

        {picking && <span aria-hidden className="swd-locator-crosshair" />}

        {notice && (
          <div role={notice.role} aria-live="polite" className="swd-locator-notice">
            <span>{notice.text}</span>
            {notice.action && (
              <button type="button" onClick={notice.action} className="min-h-11 shrink-0 px-2 font-semibold underline underline-offset-2">
                Erneut laden
              </button>
            )}
          </div>
        )}

        {!active && (
          <button
            ref={activationButtonRef}
            type="button"
            aria-label={small ? "Karte im Vollbild öffnen" : "Karte aktivieren"}
            onClick={() => {
              activate();
              if (!small) requestAnimationFrame(() => mapRef.current?.getCanvas().focus({ preventScroll: true }));
            }}
            className="absolute inset-0 z-map-overlay bg-transparent"
          />
        )}

        {fullscreen && (
          <button
            ref={closeButtonRef}
            type="button"
            aria-label="Vollbild schließen"
            onClick={closeFullscreen}
            className="swd-locator-control absolute left-3 z-map-control"
            style={topOffset}
          >
            <CloseIcon width={18} height={18} />
          </button>
        )}

        <div className="absolute right-3 top-3 z-map-control flex flex-col items-end gap-2" style={topOffset}>
          <div className="flex flex-col">
            <button type="button" aria-label="Vergrößern" onClick={() => requestZoom(ZOOM_STEP)} className="swd-locator-control">
              <PlusGlyph />
            </button>
            <button type="button" aria-label="Verkleinern" onClick={() => requestZoom(-ZOOM_STEP)} className="swd-locator-control">
              <PlusGlyph minus />
            </button>
          </div>
          <div className="flex flex-col">
            <button
              type="button"
              aria-label="Dein Standort"
              aria-pressed={sheet?.kind === "location"}
              onClick={() => {
                activate();
                setPicking(false);
                setSheet({ kind: "location" });
                if (userCoords) showBoth(userCoords);
              }}
              className="swd-locator-control"
            >
              <LocateGlyph filled={Boolean(location)} />
            </button>
            <a
              href={spotRoute}
              target="_blank"
              rel="noopener noreferrer"
              aria-label="Route zum Spot in Karten-App öffnen"
              title="Route zum Spot"
              className="swd-locator-control"
            >
              <RouteGlyph />
            </a>
          </div>
        </div>

        {picking && <PickSheet onConfirm={confirmPick} onCancel={() => setPicking(false)} />}

        {!picking && selectedPoi && (
          <PoiSheet
            key={selectedPoi.id}
            poi={selectedPoi}
            openHref={placeUrl([selectedPoi.lat, selectedPoi.lon], { label: selectedPoi.name, address: selectedPoi.address })}
            unit={units.distance}
            timeZone={timeZone}
            onClose={() => setSheet(null)}
          />
        )}
        {!picking && sheet?.kind === "spot" && (
          <SpotSheet
            name={name}
            glyph={<span className="swd-sheet-spot" dangerouslySetInnerHTML={{ __html: spotDotHtml(spotDotVariant(origin, originsMixed)) }} />}
            openHref={placeUrl(coords, { label: name })}
            distanceFromYou={distanceToSpot}
            onClose={() => setSheet(null)}
          />
        )}
        {!picking && sheet?.kind === "location" && (
          <LocationSheet
            location={location}
            distanceToSpot={distanceToSpot}
            status={locateStatus}
            canLocate={canLocate}
            syncError={syncError}
            onLocate={locate}
            onPick={startPicking}
            onRemove={() => { saveLocation(null); setLocateStatus("idle"); }}
            onClose={() => setSheet(null)}
          />
        )}

        {!sheet && !picking && <LeafletAttributionDisclosure source="openfreemap" />}
      </div>
    </>
  );
}

function PlusGlyph({ minus = false }: { minus?: boolean }) {
  return (
    <svg aria-hidden width="18" height="18" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round">
      <path d="M2 7h10" />
      {!minus && <path d="M7 2v10" />}
    </svg>
  );
}

/** The navigation arrow every maps app uses for "my location". */
function LocateGlyph({ filled }: { filled: boolean }) {
  return (
    <svg aria-hidden width="17" height="17" viewBox="0 0 20 20" fill={filled ? "currentColor" : "none"} stroke="currentColor" strokeWidth="1.7" strokeLinejoin="round">
      <path d="M17.5 2.5 2.8 8.6l6.3 2.3 2.3 6.3 6.1-14.7Z" />
    </svg>
  );
}

function RouteGlyph() {
  return (
    <svg aria-hidden width="18" height="18" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
      <path d="M10 1.8 18.2 10 10 18.2 1.8 10 10 1.8Z" />
      <path d="M7.5 12.5V10a1.5 1.5 0 0 1 1.5-1.5h3.5" />
      <path d="m11 6.5 2 2-2 2" />
    </svg>
  );
}
