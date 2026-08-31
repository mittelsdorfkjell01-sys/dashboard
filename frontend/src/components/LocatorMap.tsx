import { useEffect, useRef, useState } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import "../map.css";
import { mapLinkProps } from "../lib/mapLinks";
import { LinkIcon } from "../lib/icons";

// Aerial imagery mirrors the reference: daylight coastline and naturally blue
// water. Esri World Imagery is keyless, so production never drops back to a
// street map. Note the {z}/{y}/{x} order (y before x) — Esri's ArcGIS tile
// scheme, not Leaflet's default {z}/{x}/{y}.
const AERIAL_TILE_URL =
  "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}";
const AERIAL_ATTRIBUTION =
  'Tiles © <a href="https://www.esri.com/">Esri</a> — Source: Esri, Maxar, Earthstar Geographics, and the GIS User Community';

// Orange teardrop pin (unchanged look from the previous marker).
const PIN_SVG = `<svg width="30" height="38" viewBox="0 0 24 30" xmlns="http://www.w3.org/2000/svg">
  <path d="M12 0C5.7 0 1 4.7 1 10.7 1 18.4 12 30 12 30s11-11.6 11-19.3C23 4.7 18.3 0 12 0Z" fill="#E0823C" stroke="#ffffff" stroke-width="1.4"/>
  <circle cx="12" cy="10.5" r="3.4" fill="#ffffff"/>
</svg>`;

/** Interaction handlers toggled by the click-to-activate flow. */
function interactionHandlers(map: L.Map) {
  return [map.dragging, map.scrollWheelZoom, map.doubleClickZoom, map.touchZoom, map.keyboard, map.boxZoom];
}

/**
 * "Lage" — Leaflet locator map on keyless Esri aerial imagery (Figma Frame_9),
 * flat top-down view with the orange spot pin. Interaction is click-to-activate
 * (starts locked → first click enables pan/zoom → a plain click locks it
 * again), so page scroll is never hijacked and hovering the map changes nothing.
 */
export default function LocatorMap({ coords }: { coords: [number, number] }) {
  const [lat, lng] = coords;
  const link = mapLinkProps(lat, lng);
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<L.Map | null>(null);
  const [active, setActive] = useState(false);
  const [ready, setReady] = useState(false);
  const [unavailable, setUnavailable] = useState(false);

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    const container = containerRef.current;
    let map: L.Map;
    try {
      map = L.map(container, {
        center: [lat, lng],
        zoom: 13,
        minZoom: 3,
        maxZoom: 18,
        zoomControl: false,
        attributionControl: true,
        zoomSnap: 0.5,
      });
      L.tileLayer(AERIAL_TILE_URL, { attribution: AERIAL_ATTRIBUTION, maxZoom: 19, detectRetina: false }).addTo(map);
    } catch (error) {
      console.error("Unable to initialise locator map:", error);
      setUnavailable(true);
      return;
    }
    mapRef.current = map;
    for (const h of interactionHandlers(map)) h.disable(); // start locked

    const icon = L.divIcon({ html: PIN_SVG, className: "swd-locator-pin", iconSize: [30, 38], iconAnchor: [15, 38] });
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
      map.remove();
      mapRef.current = null;
    };
  }, [lat, lng]);

  // Enable/disable interaction to match the active state.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    for (const h of interactionHandlers(map)) {
      if (active) h.enable();
      else h.disable();
    }
  }, [active, ready]);

  // While active, a plain click (not a drag) locks the map again.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !active) return;
    const lock = () => setActive(false);
    map.on("click", lock);
    return () => {
      map.off("click", lock);
    };
  }, [active]);

  if (unavailable) {
    return (
      <div className="grid h-[360px] place-items-center bg-band px-6 text-center sm:h-[440px] lg:h-full lg:min-h-[360px]">
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
    // data-lenis-prevent stops the wheel from also scrolling the surrounding
    // page while Leaflet is consuming it to zoom the map.
    <div
      data-lenis-prevent
      className="swd-locator-map relative h-[360px] overflow-hidden bg-band sm:h-[440px] lg:h-full"
    >
      <div ref={containerRef} className="h-full w-full" />

      {/* Locked: transparent click-catcher (no text, no hover styling). */}
      {!active && (
        <button
          type="button"
          aria-label="Karte aktivieren"
          onClick={() => setActive(true)}
          className="absolute inset-0 z-[450] bg-transparent"
        />
      )}

      <div className="pointer-events-none absolute left-4 top-4 z-[500] flex flex-col items-start gap-3">
        <div className="pointer-events-auto flex flex-col">
          <button
            type="button"
            aria-label="Vergrößern"
            onClick={() => mapRef.current?.zoomIn()}
            className="grid h-11 w-11 place-items-center text-white transition-opacity hover:opacity-65"
          >
            <ControlGlyph plus />
          </button>
          <button
            type="button"
            aria-label="Verkleinern"
            onClick={() => mapRef.current?.zoomOut()}
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
          <LinkIcon width={18} height={18} />
        </a>
      </div>
    </div>
  );
}

function ControlGlyph({ plus = false }: { plus?: boolean }) {
  return (
    <span aria-hidden className="relative block h-4 w-4">
      <span className="absolute left-0 top-[7px] h-0.5 w-4 rounded-full bg-white" />
      {plus && <span className="absolute left-[7px] top-0 h-4 w-0.5 rounded-full bg-white" />}
    </span>
  );
}
