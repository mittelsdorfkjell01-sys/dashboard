import { useCallback, useEffect, useRef, useState } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import "../map.css";
import { mapLinkProps } from "../lib/mapLinks";
import { CloseIcon, LinkIcon } from "../lib/icons";
import LeafletAttributionDisclosure from "./LeafletAttributionDisclosure";
import { SPOT_PIN_ANCHOR, SPOT_PIN_SIZE, spotPinSvg } from "../lib/spotPin";
import { useSpotOriginsMixed } from "../context/SpotOriginContext";
import type { SpotOrigin } from "../lib/api";

// Aerial imagery mirrors the reference: daylight coastline and naturally blue
// water. Esri World Imagery is keyless, so production never drops back to a
// street map. Note the {z}/{y}/{x} order (y before x) — Esri's ArcGIS tile
// scheme, not Leaflet's default {z}/{x}/{y}.
const AERIAL_TILE_URL =
  "https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}";
const AERIAL_FALLBACK_TILE_URL =
  "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}";
const REFERENCE_TILE_URL =
  "https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}";
const AERIAL_ATTRIBUTION =
  'Tiles © <a href="https://www.esri.com/">Esri</a> — Source: Esri, Maxar, Earthstar Geographics, and the GIS User Community';


/** Interaction handlers toggled by the click-to-activate flow. */
function interactionHandlers(map: L.Map) {
  return [map.dragging, map.scrollWheelZoom, map.doubleClickZoom, map.touchZoom, map.keyboard, map.boxZoom];
}

type BufferedTileLayer = L.TileLayer & {
  _getTiledPixelBounds(center: L.LatLng): L.Bounds;
};

/**
 * "Lage" — Leaflet locator map on keyless Esri aerial imagery (Figma Frame_9),
 * flat top-down view with the orange spot pin. Interaction is click-to-activate
 * (starts locked → first click enables pan/zoom → a plain click locks it
 * again), so page scroll is never hijacked and hovering the map changes nothing.
 */
export default function LocatorMap({
  coords,
  origin,
}: {
  coords: [number, number];
  /** Herkunft des Spots — variiert nur die Füllung des Pins (offen für einen
   *  Community-Spot). Ohne Angabe bleibt es der gefüllte Pin. */
  origin?: SpotOrigin;
}) {
  const [lat, lng] = coords;
  const link = mapLinkProps(lat, lng);
  // No origin treatment while the catalogue is all ours.
  const originsMixed = useSpotOriginsMixed();
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<L.Map | null>(null);
  const retryTilesRef = useRef<() => void>(() => undefined);
  const [active, setActive] = useState(false);
  const [fullscreen, setFullscreen] = useState(false);
  // Below lg the inline map is small, so a tap opens it fullscreen; from lg up
  // (the wide desktop layout) it keeps the click-to-activate inline pan/zoom and
  // its wheel-zoom tile handling unchanged.
  const [small, setSmall] = useState(
    () => typeof window !== "undefined" && window.matchMedia("(max-width: 1023.98px)").matches,
  );
  useEffect(() => {
    const mq = window.matchMedia("(max-width: 1023.98px)");
    const update = () => setSmall(mq.matches);
    update();
    mq.addEventListener("change", update);
    return () => mq.removeEventListener("change", update);
  }, []);
  const [ready, setReady] = useState(false);
  const [unavailable, setUnavailable] = useState(false);
  const [tilesIncomplete, setTilesIncomplete] = useState(false);

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    const container = containerRef.current;
    const startedAt = performance.now();
    let visibleTileRequests = 0;
    let fallbackFailures = 0;
    let labelsAdded = false;
    let zoomFadeTimer = 0;
    let map: L.Map;
    try {
      map = L.map(container, {
        center: [lat, lng],
        zoom: 13,
        minZoom: 3,
        maxZoom: 18,
        zoomControl: false,
        attributionControl: false,
        fadeAnimation: false,
        // Native half-step transitions keep controls precise while quarter
        // snapping prevents layout or fitted views from jumping to integers.
        zoomAnimation: true,
        zoomSnap: 0.25,
        zoomDelta: 0.5,
        // Accumulate the small deltas emitted by precision trackpads, then let
        // Leaflet zoom around the pointer. This stays responsive without the
        // abrupt multi-level jumps caused by Leaflet's much faster defaults.
        wheelDebounceTime: 24,
        wheelPxPerZoomLevel: 240,
        scrollWheelZoom: false,
      });
      const tileLayer = L.tileLayer(AERIAL_TILE_URL, {
        attribution: AERIAL_ATTRIBUTION,
        maxZoom: 19,
        detectRetina: false,
        updateWhenIdle: false,
        // Keep the already loaded level scaled beneath the interaction and
        // request the replacement level once the zoom settles. Rebuilding the
        // grid at every intermediate wheel step exposes empty tiles on slower
        // connections.
        updateWhenZooming: false,
        updateInterval: 120,
        // Retain an extra off-screen ring so short pans do not reveal the map
        // background before the next network response arrives.
        keepBuffer: 4,
      }) as BufferedTileLayer;
      // Leaflet normally requests exactly the visible rectangle. A zoom-out
      // (especially a pinch) makes that old rectangle much smaller than the
      // frame before the next level is ready, exposing the map background at
      // the edges. Preload a 40% ring around the viewport so the current
      // imagery still covers the full frame throughout that transition.
      const visiblePixelBounds = tileLayer._getTiledPixelBounds.bind(tileLayer);
      tileLayer._getTiledPixelBounds = (center) => visiblePixelBounds(center).pad(0.5);
      tileLayer.on("tileloadstart", () => {
        visibleTileRequests += 1;
      });
      tileLayer.on("tileerror", (event) => {
        const source = (event.tile as HTMLImageElement).src;
        if (source.includes("services.arcgisonline.com")) {
          tileLayer.setUrl(AERIAL_FALLBACK_TILE_URL, false);
          tileLayer.redraw();
          return;
        }
        fallbackFailures += 1;
        setTilesIncomplete(true);
      });
      tileLayer.on("load", () => {
        const complete = fallbackFailures === 0;
        setTilesIncomplete(!complete);
        if (!complete) return;
        container.dataset.visibleReadyMs = String(
          Math.max(0.1, Math.round((performance.now() - startedAt) * 10) / 10),
        );
        container.dataset.visibleTileRequests = String(visibleTileRequests);
        if (!labelsAdded) {
          labelsAdded = true;
          const labelsPane = map.createPane("locatorLabels");
          labelsPane.classList.add("swd-locator-labels");
          labelsPane.style.zIndex = "450";
          labelsPane.style.pointerEvents = "none";
          L.tileLayer(REFERENCE_TILE_URL, {
            maxZoom: 19,
            pane: "locatorLabels",
          }).addTo(map);
        }
      });
      retryTilesRef.current = () => {
        fallbackFailures = 0;
        visibleTileRequests = 0;
        setTilesIncomplete(false);
        tileLayer.setUrl(AERIAL_TILE_URL, false);
        tileLayer.redraw();
      };
      tileLayer.addTo(map);
    } catch (error) {
      console.error("Unable to initialise locator map:", error);
      setUnavailable(true);
      return;
    }
    mapRef.current = map;
    const updateZoom = () => {
      container.dataset.currentZoom = map.getZoom().toFixed(3);
    };
    const startZoomFade = () => {
      if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
      window.clearTimeout(zoomFadeTimer);
      container.classList.add("swd-locator-zoom-fading");
    };
    const finishZoomFade = () => {
      window.clearTimeout(zoomFadeTimer);
      zoomFadeTimer = window.setTimeout(
        () => container.classList.remove("swd-locator-zoom-fading"),
        240,
      );
      updateZoom();
    };
    map.on("zoom", updateZoom);
    map.on("zoomstart", startZoomFade);
    map.on("zoomend", finishZoomFade);
    updateZoom();
    for (const h of interactionHandlers(map)) h.disable(); // start locked

    const icon = L.divIcon({
      html: spotPinSvg(originsMixed ? origin : "editorial"),
      className: "swd-locator-pin",
      iconSize: SPOT_PIN_SIZE,
      iconAnchor: SPOT_PIN_ANCHOR,
    });
    L.marker([lat, lng], { icon, keyboard: false, interactive: false }).addTo(map);

    // The page matches this map's height to the responsive gallery after the
    // first render; Leaflet must be told to re-measure its container.
    let resizeFrame = 0;
    const resizeObserver = new ResizeObserver(() => {
      cancelAnimationFrame(resizeFrame);
      resizeFrame = requestAnimationFrame(() => map.invalidateSize());
    });
    resizeObserver.observe(container);

    requestAnimationFrame(() => { map.invalidateSize(); setReady(true); });

    return () => {
      resizeObserver.disconnect();
      cancelAnimationFrame(resizeFrame);
      window.clearTimeout(zoomFadeTimer);
      retryTilesRef.current = () => undefined;
      map.remove();
      mapRef.current = null;
    };
  }, [lat, lng, origin, originsMixed]);

  const requestZoom = useCallback((delta: number) => {
    const map = mapRef.current;
    if (!map) return;
    const target = Math.max(map.getMinZoom(), Math.min(map.getMaxZoom(), map.getZoom() + delta));
    if (target === map.getZoom()) return;
    map.setZoom(target, { animate: true });
  }, []);

  // Enable/disable interaction to match the active state.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    for (const h of interactionHandlers(map)) {
      if (active) h.enable();
      else h.disable();
    }
  }, [active, ready]);

  // Desktop only: while activated inline, a plain click (not a drag) locks the
  // map again. Never runs on the touch/fullscreen path.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !active || fullscreen) return;
    const lock = () => setActive(false);
    map.on("click", lock);
    return () => {
      map.off("click", lock);
    };
  }, [active, fullscreen]);

  // Fullscreen: lock the page behind it and re-measure the map for its new size
  // (on open and again on close, so the inline view redraws correctly). Esc
  // closes it too.
  useEffect(() => {
    if (!fullscreen) return;
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const frame = requestAnimationFrame(() => mapRef.current?.invalidateSize());
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setFullscreen(false);
        setActive(false);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => {
      document.body.style.overflow = prevOverflow;
      cancelAnimationFrame(frame);
      window.removeEventListener("keydown", onKey);
      requestAnimationFrame(() => mapRef.current?.invalidateSize());
    };
  }, [fullscreen]);

  if (unavailable) {
    return (
      <div className="grid h-[360px] place-items-center rounded-card bg-band px-6 text-center sm:h-[440px] lg:h-full lg:min-h-[360px]">
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

  return (
    <>
      {/* Hold the inline slot's height while the map is lifted into fullscreen,
          so the page behind (and the scroll position) doesn't shift. */}
      {fullscreen && <div aria-hidden className="h-[360px] sm:h-[440px] lg:h-full" />}
      <div
        data-lenis-prevent={active ? "" : undefined}
        className={
          fullscreen
            ? "swd-locator-map fixed inset-0 z-fullscreen h-[100dvh] w-screen max-w-none overflow-hidden bg-band"
            : "swd-locator-map relative h-[360px] overflow-hidden rounded-card bg-band sm:h-[440px] lg:h-full"
        }
      >
        <div ref={containerRef} className="h-full w-full" />

        {/* Inline click-catcher: phones open fullscreen; desktop activates the
            inline pan/zoom (unchanged). Hidden once active. */}
        {!active && (
          <button
            type="button"
            aria-label={small ? "Karte im Vollbild öffnen" : "Karte aktivieren"}
            onClick={() => {
              if (small) {
                setFullscreen(true);
                setActive(true);
              } else {
                setActive(true);
              }
            }}
            className="absolute inset-0 z-map-overlay bg-transparent"
          />
        )}

        {/* Fullscreen: a small ✕ top-right closes back to the inline map (same
            scroll position). */}
        {fullscreen && (
          <button
            type="button"
            aria-label="Vollbild schließen"
            onClick={() => {
              setFullscreen(false);
              setActive(false);
            }}
            className="absolute right-4 z-map-control grid h-11 w-11 place-items-center rounded-full bg-ink/55 text-white transition-colors hover:bg-ink/70"
            style={{ top: "calc(1rem + env(safe-area-inset-top, 0px))" }}
          >
            <CloseIcon width={16} height={16} />
          </button>
        )}

        <div
          className="pointer-events-none absolute left-4 top-4 z-map-control flex flex-col items-start gap-2"
          style={fullscreen ? { top: "calc(1rem + env(safe-area-inset-top, 0px))" } : undefined}
        >
          <div className="pointer-events-auto flex flex-col">
            <button
              type="button"
              aria-label="Vergrößern"
              onClick={() => requestZoom(0.5)}
              className="grid h-11 w-11 place-items-center text-white transition-opacity hover:opacity-65"
            >
              <ControlGlyph plus />
            </button>
            <button
              type="button"
              aria-label="Verkleinern"
              onClick={() => requestZoom(-0.5)}
              className="grid h-11 w-11 place-items-center text-white transition-opacity hover:opacity-65"
            >
              <ControlGlyph />
            </button>
          </div>

          <a
            href={link.href}
            target={link.target}
            rel={link.rel}
            aria-label="In externer Karte öffnen"
            title="In externer Karte öffnen"
            className="pointer-events-auto grid h-11 w-11 place-items-center text-white transition-opacity hover:opacity-65"
          >
            <LinkIcon width={15} height={15} />
          </a>
        </div>

        <LeafletAttributionDisclosure source="esri" tone="overlay" />

        {tilesIncomplete && (
          <div
            role="alert"
            className="absolute bottom-14 left-1/2 z-map-control flex -translate-x-1/2 items-center gap-3 rounded-card bg-black/80 px-4 py-3 text-caption text-white shadow-card"
          >
            <span>Satellitenbild unvollständig</span>
            <button
              type="button"
              onClick={() => retryTilesRef.current()}
              className="min-h-11 whitespace-nowrap font-semibold underline underline-offset-2"
            >
              Erneut laden
            </button>
          </div>
        )}
      </div>
    </>
  );
}

function ControlGlyph({ plus = false }: { plus?: boolean }) {
  return (
    <span aria-hidden className="relative block h-3 w-3">
      <span className="absolute left-0 top-[5px] h-0.5 w-3 rounded-full bg-white" />
      {plus && <span className="absolute left-[5px] top-0 h-3 w-0.5 rounded-full bg-white" />}
    </span>
  );
}
