import { useEffect, useRef, useState } from "react";
import maplibregl, { type Map as MlMap } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { mapLinkProps } from "../lib/mapLinks";
import { MinusIcon, PlusIcon } from "../lib/icons";

const KEY = import.meta.env.VITE_MAPTILER_KEY as string | undefined;

// Orange teardrop pin (same look as the old Leaflet marker).
const PIN_SVG = `<svg width="30" height="38" viewBox="0 0 24 30" xmlns="http://www.w3.org/2000/svg">
  <path d="M12 0C5.7 0 1 4.7 1 10.7 1 18.4 12 30 12 30s11-11.6 11-19.3C23 4.7 18.3 0 12 0Z" fill="#E0823C" stroke="#ffffff" stroke-width="1.4"/>
  <circle cx="12" cy="10.5" r="3.4" fill="#ffffff"/>
</svg>`;

/** Interaction handlers toggled by the click-to-activate flow. Rotation stays
 *  off so the slight-3D tilt/bearing never gets knocked askew. */
function interactionHandlers(map: MlMap) {
  return [map.dragPan, map.scrollZoom, map.doubleClickZoom, map.touchZoomRotate, map.keyboard, map.boxZoom];
}

/**
 * "Lage" — MapLibre GL locator map on MapTiler vector tiles (Figma Frame_9).
 * Terrain relief + a slight 3D tilt; labels are filtered to just place names
 * and the Gastro / Camping / Parkplatz POI classes plus the orange spot pin.
 * Interaction is click-to-activate (starts locked → first click enables
 * pan/zoom → a plain click locks it again), so page scroll is never hijacked
 * and hovering the map changes nothing.
 */
export default function LocatorMap({ coords }: { coords: [number, number] }) {
  const [lat, lng] = coords;
  const link = mapLinkProps(lat, lng);
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MlMap | null>(null);
  const [active, setActive] = useState(false);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (!KEY || !containerRef.current || mapRef.current) return;
    const map = new maplibregl.Map({
      container: containerRef.current,
      style: `https://api.maptiler.com/maps/outdoor-v2/style.json?key=${KEY}`,
      center: [lng, lat],
      zoom: 12.5,
      pitch: 0, // flat top-down view
      attributionControl: { compact: true },
    });
    mapRef.current = map;
    map.dragRotate.disable();
    map.touchPitch.disable();
    for (const h of interactionHandlers(map)) h.disable(); // start locked

    map.on("load", () => {
      // Keep the built-in 2D relief (Hillshade) for the "Gelände" look, but no
      // 3D terrain tilt — the map reads normally from above.

      // Filtering: keep place names (source-layer "place") + the three wanted
      // POI symbol layers; hide every other symbol (road/water/contour labels,
      // shops, sport, culture, …) AND the long-distance trail lines (the bright
      // orange lines that read like coloured motorways). Then narrow
      // Transport→parking, Tourism→campsite.
      for (const layer of map.getStyle().layers ?? []) {
        const src = (layer as { "source-layer"?: string })["source-layer"];
        if (layer.type === "symbol") {
          const keep = src === "place" || ["Food", "Transport", "Tourism"].includes(layer.id);
          map.setLayoutProperty(layer.id, "visibility", keep ? "visible" : "none");
        } else if (src === "trail") {
          map.setLayoutProperty(layer.id, "visibility", "none");
        }
      }
      if (map.getLayer("Transport")) {
        map.setFilter("Transport", ["all", ["==", "$type", "Point"], ["in", "class", "parking", "parking_garage", "parking_paid"]]);
      }
      if (map.getLayer("Tourism")) {
        map.setFilter("Tourism", ["all", ["==", "$type", "Point"], ["==", "class", "campsite"]]);
      }

      const el = document.createElement("div");
      el.innerHTML = PIN_SVG;
      new maplibregl.Marker({ element: el, anchor: "bottom" }).setLngLat([lng, lat]).addTo(map);
      setReady(true);
    });

    return () => {
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

  if (!KEY) {
    return (
      <div className="grid h-[440px] w-full place-items-center rounded-3xl border border-line bg-band px-6 text-center text-caption text-muted sm:h-[540px]">
        Karte nicht konfiguriert — <code>VITE_MAPTILER_KEY</code> fehlt.
      </div>
    );
  }

  return (
    <div className="relative overflow-hidden rounded-3xl">
      <div ref={containerRef} className="h-[440px] w-full sm:h-[540px]" />

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
        <div className="pointer-events-auto flex flex-col overflow-hidden rounded-2xl border border-line bg-white">
          <button
            type="button"
            aria-label="Vergrößern"
            onClick={() => mapRef.current?.zoomIn()}
            className="grid h-11 w-11 place-items-center text-teal transition-colors hover:bg-line/40"
          >
            <PlusIcon className="text-[20px]" />
          </button>
          <span className="mx-2 h-px bg-line" />
          <button
            type="button"
            aria-label="Verkleinern"
            onClick={() => mapRef.current?.zoomOut()}
            className="grid h-11 w-11 place-items-center text-teal transition-colors hover:bg-line/40"
          >
            <MinusIcon className="text-[20px]" />
          </button>
        </div>

        <a
          href={link.href}
          target={link.target}
          rel={link.rel}
          className="pointer-events-auto rounded-2xl border border-line bg-white px-4 py-2 text-label font-medium text-ink transition-colors hover:bg-line/40"
        >
          Maps
        </a>
      </div>
    </div>
  );
}
