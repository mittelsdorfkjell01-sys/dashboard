import { useEffect, useRef } from "react";
import * as maplibregl from "maplibre-gl";
import type { ExpressionSpecification, GeoJSONSource, Map as MapLibreMap, MapMouseEvent, StyleSpecification } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { CARTO_ATTRIBUTION, CARTO_POSITRON_NOLABELS, CARTO_VOYAGER_LABELS, cartoTileUrl, prefersRetinaTiles } from "../lib/basemaps";
import type { Spot } from "../lib/types";
import type { FieldDisplayMode, FieldLayer, FieldManifest, FieldObservation, FieldViewportBounds } from "./contracts";
import { FieldSource } from "./FieldSource";
import type { DecodedFieldTile } from "./fieldTile";
import { PressureContourLayer } from "./PressureContourLayer";
import { WindAnimationLayer } from "./WindAnimationLayer";
import { WindFieldLayer } from "./WindFieldLayer";
import { EUROPE_COUNTRY_LABELS, PLACE_LABEL_MIN_ZOOM } from "./countryLabels";

interface Props {
  manifest: FieldManifest;
  active?: boolean;
  /** Any instant inside the published horizon — not necessarily a published
   *  one. Times in between are interpolated from the two around them. */
  validAt: string;
  prefetchValidAt?: string;
  display: FieldDisplayMode;
  layer?: FieldLayer;
  center: [number, number];
  zoom: number;
  spots?: Spot[];
  showSpots: boolean;
  /** Dot fill for every spot — one colour, the same mark the spot map draws. */
  spotColor: string;
  observations?: FieldObservation[];
  showObservations?: boolean;
  describedBy: string;
  focusPoint?: { longitude: number; latitude: number; label: string };
  focusRequest?: { id: number; center: [number, number]; zoom: number };
  onViewChange: (center: [number, number], zoom: number, bounds: FieldViewportBounds) => void;
  /** Handed the camera controls once the map exists, for the overlay's own
   *  zoom glyphs. */
  onReady?: (api: { zoomIn: () => void; zoomOut: () => void }) => void;
  /** Tap on open water — the caller opens the forecast for that coordinate. */
  onPick?: (longitude: number, latitude: number) => void;
  /** Tap landed on a spot dot — that spot's own forecast instead of the field. */
  onPickSpot?: (spotId: string) => void;
  onLoadingChange: (loading: boolean) => void;
  onError: (message: string | null) => void;
}

// The published pyramid ends at a tile zoom whose cells are a few kilometres
// across (ICON-D2 ≈ 3 km, ICON-EU ≈ 7 km). Past this zoom the whole screen
// sits inside a couple of cells: the colour goes flat and every streak points
// the same way, which reads as "the wind is not resolved any more"
// (2026-10-11). The map stops where the data stops saying something.
const WEATHER_MAP_MAX_ZOOM = 13;

/**
 * Leaflet counts zoom in 256px tiles, MapLibre's world is 512px wide at the
 * same number — so the same `z` shows exactly one level closer here. The URL
 * camera that all three products share is written in Leaflet's convention (it
 * is the one every other map and share link on the site uses), so this canvas
 * takes it one level down and reports it one level back up. Without it,
 * switching Spots → Wind halved the view and back again doubled it
 * (2026-10-12: "es soll immer der gleiche Ausschnitt da sein").
 */
const SHARED_ZOOM_OFFSET = 1;
const toCanvasZoom = (shared: number) => shared - SHARED_ZOOM_OFFSET;
const toSharedZoom = (canvas: number) => canvas + SHARED_ZOOM_OFFSET;

/** Hit radius around a tap when testing it against the spot dots, in screen
 *  pixels: a finger is far wider than a 6px circle, so a near miss must still
 *  count as "that spot" instead of falling through to the bare coordinate.
 *  Two pixels wider since the dots lost their ring, which used to be part of
 *  the hit geometry (2026-10-12). */
const SPOT_TAP_SLOP = 16;

/**
 * ONE ground for both products (2026-10-12): Positron, almost colourless, so
 * the field's own colours are the only ones on the map and the land keeps
 * just enough drawing to be recognisable under them. The waves sat on Voyager
 * for an afternoon, to give the sea a blue tone where the model has no data;
 * the land then read differently from the wind map, which mattered more.
 */
function rasterStyle(style: string, saturation: number): StyleSpecification {
  return {
    version: 8,
    sources: {
      // @2x on a high-DPR screen: the ground is the only thing under the wind
      // field, and an upscaled 256px raster made the land read as blurred
      // (2026-10-12). `tileSize` stays 256 — the logical tile is unchanged,
      // the image inside it simply carries twice the pixels.
      carto: { type: "raster", tiles: [cartoTileUrl(style, { retina: prefersRetinaTiles() })], tileSize: 256, attribution: CARTO_ATTRIBUTION },
    },
    layers: [{ id: "carto", type: "raster", source: "carto", paint: { "raster-opacity": 1, "raster-saturation": saturation } }],
  };
}

function labelRasterStyle(style: string): StyleSpecification {
  return {
    version: 8,
    sources: {
      labels: { type: "raster", tiles: [cartoTileUrl(style, { retina: prefersRetinaTiles() })], tileSize: 256, attribution: CARTO_ATTRIBUTION },
    },
    layers: [{ id: "labels", type: "raster", source: "labels", minzoom: PLACE_LABEL_MIN_ZOOM }],
  };
}

function createCountryMarkers(map: MapLibreMap): maplibregl.Marker[] {
  return EUROPE_COUNTRY_LABELS.map(([name, longitude, latitude]) => {
    const element = document.createElement("span");
    element.className = "swd-country-label";
    element.textContent = name;
    return new maplibregl.Marker({ element, anchor: "center" }).setLngLat([longitude, latitude]).addTo(map);
  });
}

function showCountryMarkers(markers: maplibregl.Marker[], zoom: number): void {
  const visible = zoom < PLACE_LABEL_MIN_ZOOM;
  for (const marker of markers) marker.getElement().hidden = !visible;
}

// No extra desaturation: Positron is pale already, and taking more out left
// nothing of the land to read under the field (2026-10-12).
const BASE_STYLE = rasterStyle(CARTO_POSITRON_NOLABELS, 0);
const LABEL_STYLE = labelRasterStyle(CARTO_VOYAGER_LABELS);

function allowsFieldPrefetch(): boolean {
  const connection = (navigator as Navigator & {
    connection?: { saveData?: boolean; effectiveType?: string };
  }).connection;
  return !connection?.saveData && !["slow-2g", "2g"].includes(connection?.effectiveType ?? "");
}

function visibleBounds(map: MapLibreMap): FieldViewportBounds {
  const bounds = map.getBounds();
  return {
    west: bounds.getWest(),
    south: bounds.getSouth(),
    east: bounds.getEast(),
    north: bounds.getNorth(),
  };
}

// Spot dots match the public spot map's `.swd-map-dot`: an 18px disc in the
// one spot colour with a soft drop shadow (a separate blurred circle below).
// No ring — no mark on this map carries a white stroke (2026-10-12).
function syncSpots(map: MapLibreMap, spots: Spot[] | undefined, showSpots: boolean, spotColor: string) {
  const id = "weather-spots";
  const data: GeoJSON.FeatureCollection = {
    type: "FeatureCollection",
    features: showSpots ? (spots ?? []).flatMap((spot) => spot.coords ? [{ type: "Feature" as const, geometry: { type: "Point" as const, coordinates: [spot.coords[1], spot.coords[0]] }, properties: { id: spot.id, name: spot.name, origin: spot.origin ?? "editorial" } }] : []) : [],
  };
  const source = map.getSource(id) as GeoJSONSource | undefined;
  if (source) source.setData(data);
  else {
    map.addSource(id, { type: "geojson", data });
    map.addLayer({ id: `${id}-shadow`, type: "circle", source: id, paint: { "circle-radius": 10, "circle-color": "rgba(15, 25, 25, 0.35)", "circle-blur": 0.6, "circle-translate": [0, 1] } });
    // Radius 9 = the spot map's 18px disc. It was 8 inside a 2px ring; with
    // the ring gone the disc itself carries that width (2026-10-12).
    //
    // A community spot carries the same disc in the same colour, open instead
    // of filled — the same treatment the spot map's `.swd-map-dot.is-community`
    // uses, and the stroke is the spot colour, never white. No gate needed: as
    // long as the catalogue is all ours, no feature matches and every dot
    // stays filled.
    const isCommunity: ExpressionSpecification = ["==", ["get", "origin"], "community"];
    map.addLayer({
      id,
      type: "circle",
      source: id,
      paint: {
        "circle-radius": 9,
        "circle-color": ["case", isCommunity, "#ffffff", spotColor],
        "circle-stroke-color": spotColor,
        "circle-stroke-width": ["case", isCommunity, 3, 0],
      },
    });
  }
}

function syncFocusPoint(map: MapLibreMap, point: Props["focusPoint"]) {
  const id = "weather-focus-point";
  const data: GeoJSON.FeatureCollection = {
    type: "FeatureCollection",
    features: point ? [{
      type: "Feature",
      geometry: { type: "Point", coordinates: [point.longitude, point.latitude] },
      properties: { label: point.label },
    }] : [],
  };
  const source = map.getSource(id) as GeoJSONSource | undefined;
  if (source) source.setData(data);
  else {
    map.addSource(id, { type: "geojson", data });
    map.addLayer({
      id,
      type: "circle",
      source: id,
      paint: {
        "circle-radius": 8,
        "circle-color": "#f06f4f",
      },
    });
  }
}

function syncObservations(
  map: MapLibreMap,
  observations: FieldObservation[] | undefined,
  showObservations: boolean,
) {
  const id = "weather-observations";
  const data: GeoJSON.FeatureCollection = {
    type: "FeatureCollection",
    features: showObservations ? (observations ?? []).map((observation) => ({
      type: "Feature" as const,
      geometry: { type: "Point" as const, coordinates: [observation.longitude, observation.latitude] },
      properties: {
        name: observation.name ?? observation.station_id,
        provider: observation.provider,
        speed: observation.wind_speed_ms,
        observedAt: observation.observed_at,
      },
    })) : [],
  };
  const source = map.getSource(id) as GeoJSONSource | undefined;
  if (source) source.setData(data);
  else {
    map.addSource(id, { type: "geojson", data });
    map.addLayer({
      id,
      type: "circle",
      source: id,
      paint: {
        "circle-radius": ["interpolate", ["linear"], ["zoom"], 2, 4, 8, 7],
        "circle-color": "#f06f4f",
      },
    });
  }
}

export default function WeatherMapCanvas(props: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const labelContainerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const labelMapRef = useRef<MapLibreMap | null>(null);
  const countryMarkersRef = useRef<maplibregl.Marker[]>([]);
  const sourceRef = useRef<FieldSource | null>(null);
  const fieldRef = useRef<WindFieldLayer | null>(null);
  const motionRef = useRef<WindAnimationLayer | null>(null);
  const contourRef = useRef<PressureContourLayer | null>(null);
  const tilesRef = useRef<DecodedFieldTile[]>([]);
  const requestRef = useRef<AbortController | null>(null);
  const loadCurrentRef = useRef<() => void>(() => undefined);
  const manifestRef = useRef(props.manifest);
  const tilesManifestRef = useRef<FieldManifest | null>(null);
  const renderedLayerRef = useRef<FieldLayer>(props.layer ?? "wind");
  const validAtRef = useRef(props.validAt);
  const displayRef = useRef(props.display);
  const layerRef = useRef(props.layer ?? "wind");
  const cameraRef = useRef({ center: props.center, zoom: props.zoom });
  const callbacksRef = useRef(props);
  callbacksRef.current = props;
  validAtRef.current = props.validAt;
  displayRef.current = props.display;
  layerRef.current = props.layer ?? "wind";

  loadCurrentRef.current = () => {
    const map = mapRef.current;
    const source = sourceRef.current;
    // The only precondition is the field layer itself, which is created on the
    // map's `load` event (and calls this straight after). Never gate on
    // `map.loaded()`: that is false while ANY basemap raster tile is still in
    // flight, which is exactly the state `moveend` fires in after a zoom — the
    // field request was then dropped without a retry and the wind stopped
    // loading as you zoomed in (2026-10-12). The field canvas is independent
    // of the basemap tiles, so it can load and draw right away.
    if (!map || !source || !fieldRef.current) return;
    requestRef.current?.abort();
    const controller = new AbortController();
    requestRef.current = controller;
    const bufferTiles = allowsFieldPrefetch() ? 1 : 0;
    const cached = source.hasViewportAt(map.getBounds(), map.getZoom(), validAtRef.current, bufferTiles);
    if (!cached) callbacksRef.current.onLoadingChange(true);
    source.loadViewportAt(map.getBounds(), map.getZoom(), validAtRef.current, controller.signal, bufferTiles)
      .then((tiles) => {
        if (controller.signal.aborted) return;
        tilesRef.current = tiles;
        tilesManifestRef.current = source.manifest;
        renderedLayerRef.current = layerRef.current;
        fieldRef.current?.draw(tiles, renderedLayerRef.current);
        motionRef.current?.setData(tiles, displayRef.current);
        contourRef.current?.draw(tiles, renderedLayerRef.current === "pressure");
        callbacksRef.current.onError(null);
        const nextValidAt = callbacksRef.current.prefetchValidAt;
        if (nextValidAt && nextValidAt !== validAtRef.current && allowsFieldPrefetch()) {
          void source.prefetchViewport(map.getBounds(), map.getZoom(), nextValidAt, bufferTiles);
        }
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted) callbacksRef.current.onError(
          error instanceof Error ? error.message : "Windfeld konnte nicht geladen werden.",
        );
      })
      .finally(() => {
        if (!controller.signal.aborted && !cached) callbacksRef.current.onLoadingChange(false);
      });
  };

  useEffect(() => {
    if (!containerRef.current || !labelContainerRef.current || mapRef.current) return;
    const source = new FieldSource(manifestRef.current);
    sourceRef.current = source;
    const map = new maplibregl.Map({
      container: containerRef.current,
      style: BASE_STYLE,
      center: cameraRef.current.center,
      zoom: toCanvasZoom(cameraRef.current.zoom),
      minZoom: 2,
      maxZoom: WEATHER_MAP_MAX_ZOOM,
      attributionControl: false,
      dragRotate: false,
      pitchWithRotate: false,
      renderWorldCopies: false,
      fadeDuration: 0,
    });
    const labelMap = new maplibregl.Map({
      container: labelContainerRef.current,
      style: LABEL_STYLE,
      center: cameraRef.current.center,
      zoom: toCanvasZoom(cameraRef.current.zoom),
      minZoom: 2,
      maxZoom: WEATHER_MAP_MAX_ZOOM,
      attributionControl: false,
      interactive: false,
      renderWorldCopies: false,
      fadeDuration: 0,
    });
    // No MapLibre controls: the overlay draws its own back/zoom glyphs, the
    // same ones the spot map uses, instead of a second control language.
    mapRef.current = map;
    callbacksRef.current.onReady?.({
      zoomIn: () => map.zoomTo(Math.min(map.getZoom() + 1, WEATHER_MAP_MAX_ZOOM), { duration: 220 }),
      zoomOut: () => map.zoomTo(Math.max(map.getZoom() - 1, 2), { duration: 220 }),
    });
    labelMapRef.current = labelMap;
    map.on("load", () => {
      try {
        const canvas = map.getCanvas();
        canvas.setAttribute("aria-label", "Interaktive Wetterkarte");
        canvas.setAttribute("aria-describedby", callbacksRef.current.describedBy);
        fieldRef.current = new WindFieldLayer(map);
        motionRef.current = new WindAnimationLayer(map, source);
        motionRef.current.setActive(callbacksRef.current.active !== false);
        contourRef.current = new PressureContourLayer(map);
        motionRef.current.start();
        const center = map.getCenter();
        callbacksRef.current.onViewChange(
          [center.lng, center.lat],
          toSharedZoom(map.getZoom()),
          visibleBounds(map),
        );
        loadCurrentRef.current();
      } catch (error) {
        callbacksRef.current.onError(error instanceof Error ? error.message : "WebGL ist nicht verfügbar.");
      }
    });
    labelMap.on("load", () => {
      countryMarkersRef.current = createCountryMarkers(labelMap);
      showCountryMarkers(countryMarkersRef.current, labelMap.getZoom());
      syncSpots(labelMap, callbacksRef.current.spots, callbacksRef.current.showSpots, callbacksRef.current.spotColor);
      syncFocusPoint(labelMap, callbacksRef.current.focusPoint);
      syncObservations(labelMap, callbacksRef.current.observations, Boolean(callbacksRef.current.showObservations));
    });
    map.on("move", () => {
      const center = map.getCenter();
      labelMap.jumpTo({ center, zoom: map.getZoom(), bearing: map.getBearing(), pitch: map.getPitch() });
      showCountryMarkers(countryMarkersRef.current, map.getZoom());
      fieldRef.current?.draw(tilesRef.current, renderedLayerRef.current);
      motionRef.current?.redraw();
      contourRef.current?.draw(tilesRef.current, renderedLayerRef.current === "pressure");
    });
    map.on("moveend", () => {
      const center = map.getCenter();
      const camera = { center: [center.lng, center.lat] as [number, number], zoom: toSharedZoom(map.getZoom()) };
      cameraRef.current = camera;
      callbacksRef.current.onViewChange(camera.center, camera.zoom, visibleBounds(map));
      loadCurrentRef.current();
    });
    map.on("click", (event: MapMouseEvent) => {
      // Spot dots live on the label overlay, which mirrors this map's camera,
      // so the tap's screen point queries cleanly against it. A dot wins over
      // the coordinate: tapping a spot asks about that spot.
      const { onPick, onPickSpot } = callbacksRef.current;
      if (onPickSpot && labelMap.getLayer("weather-spots")) {
        const { x, y } = event.point;
        const hit = labelMap.queryRenderedFeatures([
          [x - SPOT_TAP_SLOP, y - SPOT_TAP_SLOP],
          [x + SPOT_TAP_SLOP, y + SPOT_TAP_SLOP],
        ], { layers: ["weather-spots"] })[0];
        const spotId = hit?.properties?.id;
        if (spotId) { onPickSpot(String(spotId)); return; }
      }
      onPick?.(event.lngLat.lng, event.lngLat.lat);
    });
    return () => {
      requestRef.current?.abort();
      motionRef.current?.destroy();
      contourRef.current?.destroy();
      fieldRef.current?.destroy();
      countryMarkersRef.current.forEach((marker) => marker.remove());
      countryMarkersRef.current = [];
      labelMap.remove();
      map.remove();
      mapRef.current = null;
      labelMapRef.current = null;
    };
  }, []);

  useEffect(() => {
    loadCurrentRef.current();
    return () => requestRef.current?.abort();
  }, [props.validAt, props.display, props.prefetchValidAt]);

  useEffect(() => {
    if (manifestRef.current === props.manifest) return;
    manifestRef.current = props.manifest;
    const source = new FieldSource(props.manifest);
    sourceRef.current = source;
    motionRef.current?.setSource(source);
    // Keep the previous field pixels on screen until this resolves. The draw
    // and motion buffers swap together, so changing Wind/Wellen never exposes
    // the bare basemap or a partially decoded product.
    loadCurrentRef.current();
  }, [props.manifest]);

  useEffect(() => {
    motionRef.current?.setActive(props.active !== false);
    if (props.active === false) return;
    const frame = window.requestAnimationFrame(() => {
      mapRef.current?.resize();
      labelMapRef.current?.resize();
      fieldRef.current?.draw(tilesRef.current, renderedLayerRef.current);
      motionRef.current?.redraw();
      loadCurrentRef.current();
    });
    return () => window.cancelAnimationFrame(frame);
  }, [props.active]);

  useEffect(() => {
    if (tilesManifestRef.current !== props.manifest) return;
    renderedLayerRef.current = props.layer ?? "wind";
    fieldRef.current?.draw(tilesRef.current, props.layer ?? "wind");
    contourRef.current?.draw(tilesRef.current, props.layer === "pressure");
  }, [props.layer, props.manifest]);

  // `isStyleLoaded()`, not `loaded()`: adding or updating a GeoJSON source
  // only needs the style, while `loaded()` is also false whenever a tile is
  // still in flight — gating on it dropped marker updates that arrived during
  // a pan or zoom, with nothing to retry them (2026-10-12).
  useEffect(() => {
    const map = labelMapRef.current;
    if (!map || !map.isStyleLoaded()) return;
    syncSpots(map, props.spots, props.showSpots, props.spotColor);
  }, [props.showSpots, props.spots, props.spotColor]);

  useEffect(() => {
    const map = labelMapRef.current;
    if (!map || !map.isStyleLoaded()) return;
    syncFocusPoint(map, props.focusPoint);
  }, [props.focusPoint]);

  useEffect(() => {
    // A camera move needs no loaded sources, only a map.
    if (!props.focusRequest || !mapRef.current) return;
    mapRef.current.easeTo({
      center: props.focusRequest.center,
      zoom: toCanvasZoom(props.focusRequest.zoom),
      duration: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? 0 : 650,
    });
  }, [props.focusRequest]);

  useEffect(() => {
    const map = labelMapRef.current;
    if (!map || !map.isStyleLoaded()) return;
    syncObservations(map, props.observations, Boolean(props.showObservations));
  }, [props.observations, props.showObservations]);

  // Keyboard equivalent of a tap: the point at the map centre.
  const pickCentre = () => {
    const centre = mapRef.current?.getCenter();
    if (centre) callbacksRef.current.onPick?.(centre.lng, centre.lat);
  };

  return (
    <div
      className="swd-weather-map-canvas"
      aria-label="Interaktive Wetterkarte"
      aria-describedby={props.describedBy}
      onKeyDown={(event) => {
        if (event.key !== "Enter" && event.key !== " ") return;
        event.preventDefault();
        pickCentre();
      }}
    >
      <div ref={containerRef} className="swd-weather-map-base" />
      <div ref={labelContainerRef} className="swd-weather-map-labels" aria-hidden="true" />
    </div>
  );
}
