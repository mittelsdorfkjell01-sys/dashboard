import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import * as maplibregl from "maplibre-gl";
import type { Map as MapLibreMap } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import Header from "../components/Header";
import { useRegions, useSpotForecast, useSpots } from "../lib/hooks";
import { useMapBack } from "../lib/mapBack";
import { spotPath } from "../lib/spotRoutes";
import { sortViewportSpots } from "../lib/publicMap";
import { countryName } from "../lib/flags";
import { ChevronLeftIcon, ListIcon } from "../lib/icons";
import type { Spot } from "../lib/types";
import type { WhereSelection } from "../lib/searchSubmit";
import { usePrefs } from "../context/PrefsContext";
import { useSpotOriginsMixed } from "../context/SpotOriginContext";
import { windValue, WIND_UNIT_SUFFIX, waveValue, WAVE_UNIT_SUFFIX } from "../lib/units";
import { FieldSource } from "../weather-map/FieldSource";
import type { DecodedFieldTile } from "../weather-map/fieldTile";
import type { FieldViewportBounds } from "../weather-map/contracts";
import { REGION_FOCUS_ZOOM, SPOT_FOCUS_ZOOM } from "../weather-map/camera";
import { parseFieldUrlState, updateFieldUrl, type ExplorerMode } from "../weather-map/fieldUrlState";
import { useFieldManifest } from "../weather-map/useFieldManifest";
import { ArrowLayer, type ArrowTransition } from "./ArrowLayer";
import { FieldLayer } from "./FieldLayer";
import { ParticleLayer } from "./ParticleLayer";
import ForecastTile, { type TileHour } from "./ForecastTile";
import { headlineWaveM } from "../lib/waveReading";
import { usePointForecast } from "./pointForecast";
import { applyGround, applyNames, groundStyle, namesStyle, showCoastline, waterMaskStyle } from "./mapStyle";
import { useSiteTheme } from "../lib/theme";
import ModeSwitch from "./ModeSwitch";
import SpotBar from "./SpotBar";
import SpotMarks, { spotValue } from "./SpotMarks";
import { tilesForComponent, tilesForWind, type WaveComponent } from "./fieldSample";
import "./public-map.css";

/** Shared URL zoom is Leaflet's 256px convention; MapLibre's world is 512px. */
const toCanvasZoom = (shared: number) => shared - 1;
const toSharedZoom = (canvas: number) => canvas + 1;
const MAX_ZOOM = 13;
const HOUR_MS = 3_600_000;
const reducedMotion = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;
const hourKey = (at: number) => Math.floor(at / HOUR_MS) * HOUR_MS;
/** A spot, or (wind/waves, 2026-11-21) any tapped point on the map. */
type Selection = { kind: "spot"; id: string } | { kind: "point"; lng: number; lat: number };

/** Ebenen (2026-11-20): the wind is drawn as particles OR arrows, never both. */
interface Layers {
  wind: { field: boolean; display: "particles" | "arrows" };
  waves: { field: boolean; arrows: boolean };
}

/** How far back the clock reaches (2026-11-21: "Jetzt in der Mitte, nach
 *  links in die Vergangenheit"). It can only show what the publication still
 *  carries — in practice the hours since the model run started. */
const PAST_MS = 24 * HOUR_MS;
const FUTURE_MS = 7 * 24 * HOUR_MS;
function clockTimes(times: string[], now = Date.now()): string[] {
  const ordered = [...times].sort((a, b) => Date.parse(a) - Date.parse(b));
  const inWindow = ordered.filter((time) => { const at = Date.parse(time); return at >= now - PAST_MS && at <= now + FUTURE_MS; });
  return inWindow.length ? inWindow : ordered;
}

/** The spot forecast is the product's own (consensus, calibrated) — say so
 *  with its timestamp instead of an internal model key. */
function spotSourceLabel(generatedAt?: string): string {
  const at = generatedAt ? new Date(generatedAt) : null;
  const stamp = at && !Number.isNaN(at.getTime()) ? ` · Stand ${new Intl.DateTimeFormat("de-DE", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" }).format(at)}` : "";
  return `Spot-Vorhersage surfwind data${stamp}`;
}

/** "54,32° N · 10,51° O" — a tapped point has no name, only its place. */
function pointLabel(point: { lng: number; lat: number }): string {
  const format = (value: number) => Math.abs(value).toFixed(2).replace(".", ",");
  return `${format(point.lat)}° ${point.lat >= 0 ? "N" : "S"} · ${format(point.lng)}° ${point.lng >= 0 ? "O" : "W"}`;
}

function visibleBounds(map: MapLibreMap): FieldViewportBounds {
  const bounds = map.getBounds();
  return { west: bounds.getWest(), south: bounds.getSouth(), east: bounds.getEast(), north: bounds.getNorth() };
}

function allowsPrefetch(): boolean {
  const connection = (navigator as Navigator & { connection?: { saveData?: boolean; effectiveType?: string } }).connection;
  return !connection?.saveData && !["slow-2g", "2g"].includes(connection?.effectiveType ?? "");
}

/** Does a set of decoded tiles belong to the product on screen? */
function tilesAre(tiles: DecodedFieldTile[], product: "wind" | "waves"): boolean {
  const arrays = tiles[0]?.arrays;
  if (!arrays) return false;
  return product === "waves" ? Boolean(arrays.wave_u) : Boolean(arrays.wind_u);
}

/**
 * The public map (2026-11-19 redesign, reworked 2026-11-20): ONE MapLibre
 * surface for Spots, Wind and Wellen. The mode only changes what lies on the
 * ground — camera, spots and clock are shared.
 *
 * Stack, bottom to top: ground · colour field · particles · arrows · place
 * names · spot marks · chrome (back, mode switch, glyph stack, legend, the
 * slim spot bar and the forecast tile).
 */
export default function PublicMap() {
  const goBack = useMapBack();
  const { units } = usePrefs();
  const originsMixed = useSpotOriginsMixed();
  const theme = useSiteTheme();
  const themeRef = useRef(theme);
  themeRef.current = theme;
  const initialUrl = useRef(parseFieldUrlState(window.location.search));
  const hasUrlCamera = useRef(new URLSearchParams(window.location.search).has("lat"));
  const initialSpot = useRef(new URLSearchParams(window.location.search).get("spot") ?? undefined);

  const [mode, setModeState] = useState<ExplorerMode>(initialUrl.current.mode);
  const product: "wind" | "waves" = mode === "waves" ? "waves" : "wind";
  const [component, setComponent] = useState<WaveComponent>("total");
  const [layers, setLayers] = useState<Layers>(() => ({
    wind: { field: true, display: reducedMotion() ? "arrows" : "particles" },
    waves: { field: true, arrows: true },
  }));

  // --- map ------------------------------------------------------------------
  const groundRef = useRef<HTMLDivElement>(null);
  const namesRef = useRef<HTMLDivElement>(null);
  const maskRef = useRef<HTMLDivElement>(null);
  const [map, setMap] = useState<MapLibreMap | null>(null);
  const [mapError, setMapError] = useState<string | null>(null);
  const [viewTick, setViewTick] = useState(0);
  const [viewport, setViewport] = useState<{ center: [number, number]; bounds: FieldViewportBounds }>();
  const layersRef = useRef<{ field?: FieldLayer; particles?: ParticleLayer; arrows?: ArrowLayer; names?: MapLibreMap; mask?: MapLibreMap }>({});

  useEffect(() => {
    if (!groundRef.current || !namesRef.current || !maskRef.current) return;
    let ground: MapLibreMap;
    let names: MapLibreMap;
    let mask: MapLibreMap;
    const camera = { center: initialUrl.current.center, zoom: toCanvasZoom(initialUrl.current.zoom) };
    try {
      ground = new maplibregl.Map({
        container: groundRef.current, style: groundStyle(initialUrl.current.mode, themeRef.current), ...camera,
        minZoom: 1.5, maxZoom: MAX_ZOOM, attributionControl: false, dragRotate: false, pitchWithRotate: false,
        touchPitch: false, renderWorldCopies: false, fadeDuration: 0,
      });
      ground.touchZoomRotate.disableRotation();
      names = new maplibregl.Map({
        container: namesRef.current, style: namesStyle(themeRef.current), ...camera,
        minZoom: 1.5, maxZoom: MAX_ZOOM, attributionControl: false, interactive: false, renderWorldCopies: false, fadeDuration: 0,
      });
      // Hidden water mask (white = sea) that cuts the wave colour at the real
      // coastline; its pixels are read by the field layer, hence preserved.
      mask = new maplibregl.Map({
        container: maskRef.current, style: waterMaskStyle(), ...camera,
        minZoom: 1.5, maxZoom: MAX_ZOOM, attributionControl: false, interactive: false, renderWorldCopies: false, fadeDuration: 0,
        canvasContextAttributes: { preserveDrawingBuffer: true, antialias: true },
      });
    } catch (error) {
      setMapError(error instanceof Error ? error.message : "Die Karte konnte nicht gestartet werden.");
      return;
    }
    layersRef.current.names = names;
    layersRef.current.mask = mask;
    let frame = 0;
    const tick = () => {
      if (frame) return;
      frame = requestAnimationFrame(() => { frame = 0; setViewTick((value) => value + 1); });
    };
    ground.on("load", () => {
      try {
        ground.getCanvas().setAttribute("aria-label", "Interaktive Karte mit Spots, Wind und Wellen");
        layersRef.current.field = new FieldLayer(ground);
        layersRef.current.particles = new ParticleLayer(ground);
        layersRef.current.arrows = new ArrowLayer(ground);
        setMap(ground);
        const center = ground.getCenter();
        setViewport({ center: [center.lng, center.lat], bounds: visibleBounds(ground) });
      } catch (error) {
        setMapError(error instanceof Error ? error.message : "WebGL ist auf diesem Gerät nicht verfügbar.");
      }
    });
    ground.on("move", () => {
      // The padding travels too (2026-11-21): `easeTo({ padding })` on a spot
      // tap keeps it on the ground map, and without it the names/coastline
      // and the water mask sat offset from the ground ("der Umriss verschiebt sich").
      const view = { center: ground.getCenter(), zoom: ground.getZoom(), padding: ground.getPadding() };
      names.jumpTo(view);
      mask.jumpTo(view);
      tick();
    });
    const resize = new ResizeObserver(() => requestAnimationFrame(() => { ground.resize(); names.resize(); mask.resize(); tick(); }));
    resize.observe(groundRef.current);
    return () => {
      cancelAnimationFrame(frame);
      resize.disconnect();
      layersRef.current.particles?.destroy();
      layersRef.current.arrows?.destroy();
      layersRef.current.field?.destroy();
      layersRef.current = {};
      names.remove();
      mask.remove();
      ground.remove();
      setMap(null);
    };
  }, []);

  // --- data -----------------------------------------------------------------
  const { data: spotsData, error: spotsError, reload: reloadSpots } = useSpots({ limit: 500 });
  const spots = useMemo(() => (spotsData ?? []).filter((spot) => spot.coords), [spotsData]);
  const { data: regions } = useRegions();

  const [fieldAt, setFieldAt] = useState<number>();
  const requestedDay = useMemo(() => {
    // Past hours come from the current publication; only a later day may
    // need a model that reaches further.
    if (fieldAt === undefined || fieldAt <= Date.now() || new Date(fieldAt).toDateString() === new Date().toDateString()) return undefined;
    return new Date(hourKey(fieldAt)).toISOString().slice(0, 10) + "T12:00:00.000Z";
  }, [fieldAt]);
  const { state: manifestState, reload: reloadManifest } = useFieldManifest(undefined, viewport?.center, viewport?.bounds, product, requestedDay);
  const manifestResponse = manifestState.data;
  const manifest = useMemo(() => {
    const candidate = manifestResponse?.manifest;
    if (!candidate) return undefined;
    const names = new Set(candidate.variables.map((variable) => variable.name));
    return (product === "waves" ? names.has("wave_u") : names.has("wind_u")) ? candidate : undefined;
  }, [manifestResponse, product]);
  const source = useMemo(() => (manifest ? new FieldSource(manifest) : null), [manifest]);
  // Only offer the wave parts the publication actually carries.
  const components = useMemo<WaveComponent[]>(() => {
    if (product !== "waves" || !manifest) return ["total"];
    const names = new Set<string>(manifest.variables.map((variable) => variable.name));
    return (["total", "swell", "sea"] as const).filter((key) => key === "total" || names.has(key === "swell" ? "primary_swell_height" : "wind_sea_height"));
  }, [manifest, product]);
  useEffect(() => { if (!components.includes(component)) setComponent("total"); }, [components, component]);

  // --- clock ----------------------------------------------------------------
  const horizon = useMemo(() => {
    const times = clockTimes(manifest?.valid_times ?? []);
    if (!times.length) return null;
    const publishedFrom = Date.parse(times[0]);
    const activeTo = Date.parse(times[times.length - 1]);
    const reach = (manifestResponse?.available_models ?? [])
      .filter((model) => model.covers_viewport !== false && model.covers_point !== false && model.valid_to)
      .map((model) => Date.parse(model.valid_to!))
      .filter(Number.isFinite);
    const publishedTo = Math.max(activeTo, ...reach);
    const nowAt = Math.min(Math.max(Date.now(), publishedFrom), activeTo);
    return { publishedFrom, publishedTo, nowAt };
  }, [manifest, manifestResponse?.available_models]);
  const hours = useMemo(() => {
    if (!horizon) return [];
    const list: number[] = [];
    // From the oldest published hour (past) through now to the horizon, so
    // "Jetzt" sits mid-strip with history to its left.
    for (let at = Math.ceil(horizon.publishedFrom / HOUR_MS) * HOUR_MS; at <= horizon.publishedTo && list.length < 24 * 8; at += HOUR_MS) list.push(at);
    return list;
  }, [horizon]);
  useEffect(() => {
    if (!horizon || !hours.length) return;
    setFieldAt((current) => (current === undefined || current < hours[0] || current > hours[hours.length - 1]
      ? hours.reduce((best, hour) => (Math.abs(hour - horizon.nowAt) < Math.abs(best - horizon.nowAt) ? hour : best), hours[0])
      : current));
  }, [horizon, hours]);

  const transitionRef = useRef<ArrowTransition>("smooth");
  const changeTime = useCallback((at: number, how: { scrub: boolean } = { scrub: false }) => {
    transitionRef.current = how.scrub ? "instant" : "smooth";
    setFieldAt(at);
  }, []);

  // --- field tiles ------------------------------------------------------------
  const [tiles, setTiles] = useState<DecodedFieldTile[]>([]);
  const tilesRef = useRef<DecodedFieldTile[]>([]);
  const requestRef = useRef<AbortController | null>(null);
  const paintRef = useRef<() => void>(() => undefined);
  const loadRef = useRef<() => void>(() => undefined);

  const drawField = useCallback(() => {
    const { field } = layersRef.current;
    const current = tilesRef.current;
    const matches = mode !== "spots" && tilesAre(current, product);
    const on = matches && (mode === "wind" ? layers.wind.field : layers.waves.field);
    const mask = mode === "waves" ? layersRef.current.mask?.getCanvas() : null;
    field?.draw(on ? (mode === "waves" ? tilesForComponent(current, component) : tilesForWind(current)) : [], mode === "waves" ? "waves" : "wind", mask);
  }, [mode, product, layers, component]);

  paintRef.current = () => {
    const { particles, arrows, field } = layersRef.current;
    const current = tilesRef.current;
    const matches = mode !== "spots" && tilesAre(current, product);
    const dark = theme === "dark";
    field?.setDark(dark);
    particles?.setDark(dark);
    drawField();
    const particlesOn = matches && mode === "wind" && layers.wind.display === "particles" && !reducedMotion();
    particles?.setData(source, particlesOn ? current : []);
    particles?.setRunning(particlesOn);
    const arrowsOn = matches && (mode === "wind" ? layers.wind.display === "arrows" || reducedMotion() : layers.waves.arrows);
    arrows?.setVisible(arrowsOn);
    arrows?.setWaterMask(mode === "waves" ? layersRef.current.mask?.getCanvas() ?? null : null);
    if (matches) arrows?.setData(current, product, component, transitionRef.current);
  };

  loadRef.current = () => {
    if (!map || !source || mode === "spots" || fieldAt === undefined) return;
    requestRef.current?.abort();
    const controller = new AbortController();
    requestRef.current = controller;
    const validAt = new Date(fieldAt).toISOString();
    const buffer = allowsPrefetch() ? 1 : 0;
    const cached = source.hasViewportAt(map.getBounds(), map.getZoom(), validAt, buffer);
    if (!cached) layersRef.current.arrows?.setLoading(true);
    source.loadViewportAt(map.getBounds(), map.getZoom(), validAt, controller.signal, buffer)
      .then((loaded) => {
        if (controller.signal.aborted) return;
        tilesRef.current = loaded;
        setTiles(loaded);
        paintRef.current();
        transitionRef.current = "smooth";
        setMapError(null);
        const next = hours.find((hour) => hour > fieldAt);
        if (next && allowsPrefetch()) void source.prefetchViewport(map.getBounds(), map.getZoom(), new Date(next).toISOString(), buffer);
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) return;
        layersRef.current.arrows?.setLoading(false);
        setMapError(error instanceof Error ? error.message : "Kartendaten konnten nicht geladen werden.");
      });
  };

  useEffect(() => { loadRef.current(); }, [map, source, fieldAt, mode]);
  useEffect(() => { paintRef.current(); }, [layers, component, mode, product, map, theme, source]);
  useEffect(() => () => requestRef.current?.abort(), []);

  useEffect(() => {
    if (!map) return;
    const onMoveEnd = () => {
      const center = map.getCenter();
      setViewport({ center: [center.lng, center.lat], bounds: visibleBounds(map) });
      updateFieldUrl({ mode, center: [center.lng, center.lat], zoom: toSharedZoom(map.getZoom()), validAt: undefined, model: undefined });
      loadRef.current();
    };
    // The mask paints a frame after the camera moved; redraw the waves when it
    // has, so the coast cut never trails behind a pan.
    const mask = layersRef.current.mask;
    const onMaskRender = () => { if (mode === "waves") { drawField(); layersRef.current.arrows?.refresh(); } };
    map.on("move", drawField);
    map.on("moveend", onMoveEnd);
    mask?.on("render", onMaskRender);
    return () => { map.off("move", drawField); map.off("moveend", onMoveEnd); mask?.off("render", onMaskRender); };
  }, [map, mode, drawField]);

  // The overview without a shared camera frames the catalogue once.
  const framed = useRef(false);
  useEffect(() => {
    if (!map || framed.current || hasUrlCamera.current || !spots.length) return;
    framed.current = true;
    const bounds = new maplibregl.LngLatBounds();
    for (const spot of spots) bounds.extend([spot.coords![1], spot.coords![0]]);
    map.fitBounds(bounds, { padding: { top: 80, bottom: 160, left: 40, right: 60 }, maxZoom: 6, duration: 0 });
  }, [map, spots]);

  // --- selection --------------------------------------------------------------
  const [selection, setSelection] = useState<Selection | null>(() => (initialSpot.current ? { kind: "spot", id: initialSpot.current } : null));
  const [listOpen, setListOpen] = useState(false);
  const [layersOpen, setLayersOpen] = useState(false);
  const selectedSpot = selection?.kind === "spot" ? spots.find((spot) => spot.id === selection.id) ?? null : null;
  // --- mode -------------------------------------------------------------------
  const setMode = (next: ExplorerMode) => {
    if (next === mode) return;
    setModeState(next);
    // Replace, not push (2026-11-21): a mode is a view of the same page, so
    // "Zurück" leaves the map instead of stepping through Wellen → Wind → Spots.
    updateFieldUrl({ mode: next });
    if (map) applyGround(map, next, theme);
    // A tapped point only exists on the weather maps.
    if (next === "spots" && selection?.kind === "point") setSelection(null);
    setLayersOpen(false);
  };
  useEffect(() => {
    const onPop = () => {
      const next = parseFieldUrlState(window.location.search).mode;
      setModeState(next);
      if (map) applyGround(map, next, themeRef.current);
    };
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, [map]);

  // The theme can flip while the map is open (the account menu's switch).
  useEffect(() => {
    if (!map) return;
    applyGround(map, mode, theme);
    const names = layersRef.current.names;
    if (names?.isStyleLoaded()) applyNames(names, theme);
    else names?.once("load", () => applyNames(names, themeRef.current));
    // `mode` is applied by setMode itself; this effect is for the theme.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [map, theme]);

  useEffect(() => {
    const names = layersRef.current.names;
    if (!map || !names) return;
    if (names.isStyleLoaded()) showCoastline(names, mode !== "spots");
    else names.once("load", () => showCoastline(names, mode !== "spots"));
  }, [map, mode]);

  const selectSpot = useCallback((spot: Spot) => {
    setSelection({ kind: "spot", id: spot.id });
    setListOpen(false);
    if (map && spot.coords) {
      const zoom = Math.max(map.getZoom(), toCanvasZoom(SPOT_FOCUS_ZOOM) - 1);
      // Wind/Wellen open the forecast strip, so the spot sits a little higher.
      map.easeTo({ center: [spot.coords[1], spot.coords[0]], zoom, duration: reducedMotion() ? 0 : 600, padding: { bottom: mode === "spots" ? 200 : 260, top: 0, left: 0, right: 0 } });
    }
  }, [map, mode]);

  // --- tap on the map ------------------------------------------------------------
  useEffect(() => {
    if (!map) return;
    const onClick = (event: maplibregl.MapMouseEvent) => {
      setListOpen(false); setLayersOpen(false);
      // Wind/Wellen (2026-11-21): a tap — finger or mouse — anywhere opens that
      // point's forecast in the time tile. On the Spots map it clears.
      if (mode !== "spots") setSelection({ kind: "point", lng: event.lngLat.lng, lat: event.lngLat.lat });
      else if (selection) setSelection(null);
    };
    map.on("click", onClick);
    return () => { map.off("click", onClick); };
  }, [map, selection, mode]);

  // --- the selected place's forecast (wind/waves) ----------------------------------
  const weatherMode = mode !== "spots";
  const selectedPoint = selection?.kind === "point" ? selection : null;
  const { data: spotForecast, loading: spotForecastLoading } = useSpotForecast(weatherMode && selectedSpot ? selectedSpot.id : undefined);
  const pointForecast = usePointForecast(weatherMode && selectedPoint ? selectedPoint : null);
  const tileForecast = selectedSpot ? spotForecast : selectedPoint ? pointForecast.forecast : null;
  const tileLoading = selectedSpot ? spotForecastLoading : pointForecast.loading;
  const tileSource = selectedSpot ? spotSourceLabel(spotForecast?.generated_at) : pointForecast.source;
  // The forecast as the strip draws it: one entry per hour (map clock ms).
  const tileHours = useMemo(() => {
    if (!tileForecast) return undefined;
    const byHour = new Map<number, TileHour>();
    for (const day of tileForecast.days) for (const hour of day.hours) {
      const at = Date.parse(hour.utcKey);
      if (at % HOUR_MS !== 0) continue;
      const waveFrom = hour.waves?.primary_swell?.mean_direction_from_deg ?? hour.waves?.total_wave?.mean_direction_from_deg ?? hour.swell_dir;
      byHour.set(at, { wind: hour.wind, gust: hour.gust, windFrom: hour.dir, wave: headlineWaveM(hour), period: hour.period, waveFrom });
    }
    return byHour.size ? byHour : undefined;
  }, [tileForecast]);

  // --- search, locate, list ----------------------------------------------------
  const resolvePlace = (picked: WhereSelection | null, text: string) => {
    if (!map) return;
    const needle = text.trim().toLowerCase();
    const spot = picked?.kind === "spot" && picked.id
      ? spots.find((candidate) => candidate.id === picked.id)
      : !picked && needle ? spots.find((candidate) => candidate.name.toLowerCase() === needle) : undefined;
    if (spot?.coords) { selectSpot(spot); map.easeTo({ center: [spot.coords[1], spot.coords[0]], zoom: toCanvasZoom(SPOT_FOCUS_ZOOM), duration: reducedMotion() ? 0 : 650 }); return; }
    const region = picked?.kind === "region" && picked.id
      ? regions?.find((candidate) => candidate.id === picked.id)
      : !picked && needle ? regions?.find((candidate) => candidate.name.toLowerCase() === needle) : undefined;
    if (region?.center) map.easeTo({ center: [region.center.lon, region.center.lat], zoom: toCanvasZoom(REGION_FOCUS_ZOOM), duration: reducedMotion() ? 0 : 650 });
  };

  const [user, setUser] = useState<[number, number] | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  useEffect(() => { if (!notice) return; const timer = window.setTimeout(() => setNotice(null), 3200); return () => window.clearTimeout(timer); }, [notice]);
  const locate = () => {
    if (!navigator.geolocation) { setNotice("Dein Browser gibt keinen Standort frei."); return; }
    navigator.geolocation.getCurrentPosition(
      (position) => {
        const at: [number, number] = [position.coords.longitude, position.coords.latitude];
        setUser(at);
        map?.easeTo({ center: at, zoom: Math.max(map.getZoom(), toCanvasZoom(9)), duration: reducedMotion() ? 0 : 650 });
      },
      () => setNotice("Standort nicht verfügbar. Erlaube den Zugriff in den Browser-Einstellungen."),
      { enableHighAccuracy: false, timeout: 8000, maximumAge: 300_000 },
    );
  };

  const listSpots = useMemo(() => {
    if (!listOpen || !map) return [];
    const bounds = map.getBounds();
    const center = map.getCenter();
    const inView = spots.filter((spot) => bounds.contains([spot.coords![1], spot.coords![0]]));
    return sortViewportSpots(inView, [center.lat, center.lng]).slice(0, 40);
  }, [listOpen, map, spots]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => { if (event.key === "Escape") { setListOpen(false); setLayersOpen(false); } };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  // --- render ---------------------------------------------------------------------------
  const fieldOn = mode === "wind" ? layers.wind.field : mode === "waves" ? layers.waves.field : false;
  const unavailable = mode !== "spots" && !manifest && manifestState.status !== "loading";
  const weather = mode !== "spots";
  const barOpen = mode === "spots" && Boolean(selectedSpot);
  const userPoint = user && map ? map.project(user) : null;
  const wavesTiles = tilesAre(tiles, product) ? tiles : [];
  void viewTick;

  return (
    <main data-lenis-prevent className={`swd-pm ${theme === "dark" ? "is-dark" : "sw-theme-light"} is-${mode}${weather ? " has-tile" : ""}${barOpen ? " has-bar" : ""}`} aria-labelledby="swd-pm-title">
      <h1 id="swd-pm-title" className="sr-only">Karte: Spots, Wind und Wellen</h1>
      <div ref={groundRef} className="swd-pm-ground" />
      <div ref={namesRef} className="swd-pm-names" aria-hidden="true" />
      <div ref={maskRef} className="swd-pm-mask" aria-hidden="true" />

      {map && (
        <SpotMarks map={map} viewTick={viewTick} spots={spots} mode={mode} selectedId={selectedSpot?.id} originsMixed={originsMixed} onSelect={selectSpot} />
      )}
      {userPoint && <span className="swd-pm-user" style={{ transform: `translate(${userPoint.x}px, ${userPoint.y}px)` }} aria-hidden="true" />}

      {selectedPoint && map && (() => {
        const at = map.project([selectedPoint.lng, selectedPoint.lat]);
        return <span className="swd-pm-tapmark" style={{ transform: `translate(${Math.round(at.x)}px, ${Math.round(at.y)}px)` }} aria-hidden="true" />;
      })()}

      <button type="button" className="swd-pm-glyph swd-pm-back" aria-label="Zurück" onClick={goBack}><ChevronLeftIcon className="text-title" /></button>
      <ModeSwitch mode={mode} onMode={setMode} />

      <div className="swd-pm-glyphs">
        <div className="swd-pm-search"><Header whereOnly onResolve={resolvePlace} /></div>
        <button type="button" className="swd-pm-glyph" aria-label="Mein Standort" aria-pressed={Boolean(user)} onClick={locate}>
          <svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" strokeWidth="2.1" strokeLinecap="round" aria-hidden="true"><circle cx="12" cy="12" r="5" /><path d="M12 2v3M12 19v3M2 12h3M19 12h3" /></svg>
        </button>
        <button type="button" className="swd-pm-glyph" aria-label="Spots im Ausschnitt" aria-pressed={listOpen} aria-expanded={listOpen} onClick={() => { setListOpen(!listOpen); setLayersOpen(false); }}>
          <ListIcon className="text-title" />
        </button>
        {weather && (
          <button type="button" className="swd-pm-glyph" aria-label="Ebenen" aria-pressed={layersOpen} aria-expanded={layersOpen} onClick={() => { setLayersOpen(!layersOpen); setListOpen(false); }}>
            <svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" strokeWidth="2.1" strokeLinejoin="round" aria-hidden="true"><path d="M12 3l9 5-9 5-9-5 9-5z" /><path d="M3 13l9 5 9-5" /></svg>
          </button>
        )}
      </div>

      {layersOpen && weather && (
        <section className="swd-pm-pop" aria-label="Ebenen">
          <h2 className="text-ui font-semibold text-ink">Ebenen</h2>
          <label className="swd-pm-switch text-ui text-ink" htmlFor="swd-pm-layer-field">
            <span>Farbfläche</span>
            <input id="swd-pm-layer-field" type="checkbox" checked={fieldOn} onChange={(event) => setLayers((current) => mode === "wind" ? { ...current, wind: { ...current.wind, field: event.target.checked } } : { ...current, waves: { ...current.waves, field: event.target.checked } })} />
          </label>
          {mode === "wind" ? (
            <div className="swd-pm-segment" role="radiogroup" aria-label="Wind zeichnen als">
              {(["particles", "arrows"] as const).map((key) => {
                const disabled = key === "particles" && reducedMotion();
                const checked = (reducedMotion() ? "arrows" : layers.wind.display) === key;
                return (
                  <button key={key} type="button" role="radio" aria-checked={checked} disabled={disabled} className="text-caption" onClick={() => setLayers((current) => ({ ...current, wind: { ...current.wind, display: key } }))}>
                    {key === "particles" ? "Partikel" : "Pfeile"}
                  </button>
                );
              })}
            </div>
          ) : (
            <>
              <label className="swd-pm-switch text-ui text-ink" htmlFor="swd-pm-layer-arrows">
                <span>Pfeile (Laufrichtung)</span>
                <input id="swd-pm-layer-arrows" type="checkbox" checked={layers.waves.arrows} onChange={(event) => setLayers((current) => ({ ...current, waves: { ...current.waves, arrows: event.target.checked } }))} />
              </label>
              {components.length > 1 && (
                <div className="swd-pm-segment" role="radiogroup" aria-label="Wellenanteil">
                  {components.map((key) => (
                    <button key={key} type="button" role="radio" aria-checked={component === key} className="text-caption" onClick={() => setComponent(key)}>
                      {{ total: "Gesamt", swell: "Dünung", sea: "Windsee" }[key]}
                    </button>
                  ))}
                </div>
              )}
            </>
          )}
          {mode === "wind" && reducedMotion() && <p className="text-caption text-muted">Reduzierte Bewegung ist an: Der Wind wird als Pfeile gezeichnet.</p>}
        </section>
      )}

      {listOpen && (
        <section className="swd-pm-pop is-list" aria-label="Spots im Ausschnitt">
          <h2 className="text-ui font-semibold text-ink">Spots im Ausschnitt</h2>
          {listSpots.length === 0 ? (
            <p className="text-caption text-muted">Hier liegt kein Spot. Zoome heraus oder verschiebe die Karte.</p>
          ) : (
            <ul>
              {listSpots.map((spot) => {
                const value = spotValue(spot, wavesTiles, mode, component);
                return (
                  <li key={spot.id}>
                    <button type="button" onClick={() => selectSpot(spot)}>
                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-ui text-ink">{spot.name}</span>
                        <span className="block truncate text-caption text-muted">{[spot.regionName ?? spot.region, countryName(spot.regionCountry ?? undefined)].filter(Boolean).join(" · ")}</span>
                      </span>
                      {value?.kind === "wind" && <span className="font-num text-ui font-semibold tabular-nums text-ink">{windValue(value.knots, units.wind)} {WIND_UNIT_SUFFIX[units.wind]}</span>}
                      {value?.kind === "waves" && <span className="font-num text-ui font-semibold tabular-nums text-ink">{waveValue(value.height, units.wave)} {WAVE_UNIT_SUFFIX[units.wave]}</span>}
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </section>
      )}

      {(mapError || unavailable || (spotsError && !spots.length)) && (
        <div className="swd-pm-message" role="alert">
          <strong className="text-ui font-semibold text-ink">
            {spotsError && !spots.length ? "Spots konnten nicht geladen werden." : mapError ? "Kartendaten fehlen gerade." : manifestState.status === "offline" ? "Offline" : `${mode === "waves" ? "Wellenkarte" : "Windkarte"} noch nicht verfügbar`}
          </strong>
          <p className="text-caption text-muted">{spotsError && !spots.length ? spotsError : mapError ?? ("message" in manifestState ? manifestState.message : "Die Karte wird vorbereitet.")}</p>
          <button type="button" className="text-caption font-semibold text-accent" onClick={() => { setMapError(null); if (spotsError) reloadSpots(); reloadManifest(); }}>Erneut versuchen</button>
        </div>
      )}
      {notice && <p className="swd-pm-notice text-caption" role="status">{notice}</p>}

      <div className="swd-pm-dock">
        {barOpen && selectedSpot && (
          <SpotBar
            title={selectedSpot.name}
            editorial={originsMixed && selectedSpot.origin !== "community"}
            meta={[selectedSpot.regionName ?? selectedSpot.region, countryName(selectedSpot.regionCountry ?? undefined)].filter(Boolean).join(" · ")}
            href={spotPath(selectedSpot)}
          />
        )}
        {weather && (
          <ForecastTile
            hours={hours}
            value={fieldAt}
            nowAt={horizon?.nowAt}
            onChange={changeTime}
            spotHref={selectedSpot ? spotPath(selectedSpot, "daten") : undefined}
            spotName={selectedSpot?.name}
            place={selectedPoint ? pointLabel(selectedPoint) : undefined}
            loading={tileLoading && !tileHours}
            forecast={tileHours}
            source={tileSource}
            onClose={selection ? () => setSelection(null) : undefined}
            windUnit={units.wind}
            waveUnit={units.wave}
          />
        )}
      </div>
    </main>
  );
}
