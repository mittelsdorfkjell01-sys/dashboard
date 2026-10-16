import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import Header from "../components/Header";
import LeafletAttributionDisclosure from "../components/LeafletAttributionDisclosure";
import { buildMeteogramModel } from "../components/data/meteogramModel";
import { useRegions, useSpotForecast, useSpots } from "../lib/hooks";
import { SPOT_DOT_COLOR } from "../lib/publicMap";
import { spotPath } from "../lib/spotRoutes";
import { ChevronLeftIcon, MinusIcon, PlusIcon } from "../lib/icons";
import { isSpotForecastDisplayHour } from "../lib/spotForecastWindow";
import type { WhereSelection } from "../lib/searchSubmit";
import { usePrefs } from "../context/PrefsContext";
import type { ActiveFieldResponse, FieldDisplayMode, FieldViewportBounds } from "./contracts";
import { REGION_FOCUS_ZOOM, SPOT_FOCUS_ZOOM } from "./camera";
import { parseFieldUrlState, updateFieldUrl, type ExplorerMode, type FieldUrlState } from "./fieldUrlState";
import ExplorerModeToggle from "./ExplorerModeToggle";
import { useFieldManifest } from "./useFieldManifest";
import WeatherMapCanvas from "./WeatherMapCanvas";
import MapForecastSheet from "./overlay/MapForecastSheet";
import FieldTimeNav, { fieldWindow } from "./overlay/FieldTimeNav";
import { type MapForecastSlot } from "./overlay/slots";
import { useFieldPointForecast } from "./overlay/useFieldPointForecast";
import "./weather-map.css";

/** What the map is currently being asked about. */
type Pick_ =
  | { kind: "point"; lon: number; lat: number }
  | { kind: "spot"; id: string };

/** "54,41° N · 10,19° O" — a coordinate said the way a chart label would. */
function coordLabel(lon: number, lat: number): string {
  const fix = (value: number) => value.toFixed(2).replace(".", ",");
  return `${fix(Math.abs(lat))}° ${lat >= 0 ? "N" : "S"} · ${fix(Math.abs(lon))}° ${lon >= 0 ? "O" : "W"}`;
}

/**
 * The public wind map and its overlay. The overlay is deliberately two things
 * and no more (2026-10-11 brief):
 *
 *   • a search glyph in the top corner — the site's one search, in place-only
 *     mode: it resolves a spot/region/place and MOVES the camera instead of
 *     leaving for the results page;
 *   • a forecast sheet docked at the bottom, opened by tapping the map. Open
 *     water answers with the wind field at that coordinate, a spot dot with
 *     that spot's own forecast — one sheet, drawn with the Spot-Daten
 *     forecast's bars.
 *
 * Everything else on top of the field is transient status (loading, error,
 * offline) and the basemap attribution the Carto licence requires. There is no
 * control bar: the layer is always `wind`, the field is drawn at the published
 * instant nearest to now, and the display follows `prefers-reduced-motion`.
 * The camera is still shared through the URL — except from an embedded map,
 * which is a passenger on someone else's route.
 */
export default function WindExplorer({
  active = true,
  onModeChange,
  focus,
  embedded = false,
  product = "wind",
}: {
  /** A hidden public-map pane remains mounted and warm, but must not write the
   *  shared camera URL or receive map input until selected. */
  active?: boolean;
  /** Switches to the spot map. Omitted on the embedded map, which has no
   *  overlay furniture of its own. */
  onModeChange?: (mode: ExplorerMode) => void;
  /** Opening camera; falls back to the URL state. */
  focus?: { center: [number, number]; zoom: number };
  /** Render inside a page column instead of owning the viewport. */
  embedded?: boolean;
  product?: "wind" | "waves";
}) {
  const navigate = useNavigate();
  const [camera, setCamera] = useState<{ zoomIn: () => void; zoomOut: () => void }>();
  const mode: ExplorerMode = product;
  const requestedLayer = product === "waves" ? "waves" as const : "wind" as const;
  const urlState = useRef(parseFieldUrlState(window.location.search));
  const initial = useRef(focus ? { ...urlState.current, ...focus } : urlState.current);
  // An embedded map is a passenger on someone else's route — it reads the URL
  // once (for a shared link) and never writes back to it. Stable identity: the
  // effects below take it as a dependency.
  const syncUrl = useCallback(
    (patch: Partial<FieldUrlState>) => { if (!embedded && active) updateFieldUrl(patch); },
    [active, embedded],
  );
  const { units } = usePrefs();
  const [mapViewport, setMapViewport] = useState<{ center: [number, number]; bounds: FieldViewportBounds }>();
  // The instant the field is drawn at, in milliseconds — continuous, not one
  // of the published steps. Everything between two published hours is
  // interpolated in `FieldSource.loadViewportAt`.
  const [fieldAt, setFieldAt] = useState<number>();
  // Which model can answer depends on HOW FAR AHEAD the clock stands: the
  // short-range model (ICON-D2 over Germany) publishes two days, so a later
  // day has to be asked for explicitly or the map runs out of days. Rounded
  // to the day, so dragging inside a day never re-selects the model.
  const requestedDay = useMemo(() => {
    if (fieldAt === undefined) return undefined;
    const day = new Date(fieldAt);
    if (day.toDateString() === new Date().toDateString()) return undefined;
    return new Date(fieldAt).toISOString();
  }, [fieldAt]);
  const { state, reload } = useFieldManifest(undefined, mapViewport?.center, mapViewport?.bounds, product, requestedDay);
  const visualRef = useRef<{ data: ActiveFieldResponse; product: "wind" | "waves" }>();
  const responseVariables = new Set(state.data?.manifest?.variables?.map((variable) => variable.name) ?? []);
  const responseMatchesProduct = Boolean(
    state.data?.manifest
      && (product === "waves"
        ? responseVariables.has("wave_u") && responseVariables.has("wave_v")
        : responseVariables.has("wind_u") && responseVariables.has("wind_v")),
  );
  if (state.data && responseMatchesProduct) visualRef.current = { data: state.data, product };
  // During a product request the last fully usable field stays painted. The
  // toggle changes immediately; the canvas swaps atomically when the new
  // manifest and its first tiles are ready.
  const visual = responseMatchesProduct && state.data
    ? { data: state.data, product }
    : visualRef.current;
  const visualProduct = visual?.product ?? product;
  const visualLayer = visualProduct === "waves" ? "waves" as const : "wind" as const;
  const manifest = visual?.data.manifest;
  const pointManifests = useMemo(
    () => visual?.data.series_manifests?.length ? visual.data.series_manifests : manifest ? [manifest] : [],
    [visual?.data.series_manifests, manifest],
  );
  // Without a display switch the field draws as particles, except where motion
  // is unwelcome. The WAVES carry no streaks at all (2026-10-12): a swell is
  // not a flow you watch moving, and the drifting marks only broke up the
  // colour. The wave direction stays readable in the forecast sheet.
  const display: FieldDisplayMode = useMemo(
    () => {
      if (visualProduct === "waves") return "none";
      return window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "arrows" : "particles";
    },
    [visualProduct],
  );
  // Spot dots always overlay the wind map — they are what makes a spot tappable.
  const showSpots = true;
  const [, setLoadingTiles] = useState(false);
  const [fieldError, setFieldError] = useState<string | null>(null);
  // Camera jump: a new id re-triggers easeTo. Used by the search and by a
  // caller re-framing the map after mount (the results map following a search).
  const [focusRequest, setFocusRequest] = useState<{ id: number; center: [number, number]; zoom: number }>();
  // Compared on the primitives, since `focus` is a fresh object every render.
  const focusLon = focus?.center[0];
  const focusLat = focus?.center[1];
  const focusZoom = focus?.zoom;
  const framed = useRef(true);
  useEffect(() => {
    if (focusLon === undefined || focusLat === undefined || focusZoom === undefined) return;
    // The opening frame is already applied through `initial` on the canvas.
    if (framed.current) { framed.current = false; return; }
    setFocusRequest({ id: Date.now(), center: [focusLon, focusLat], zoom: focusZoom });
  }, [focusLon, focusLat, focusZoom]);
  const { data: spots } = useSpots({ limit: 500 }, showSpots);
  const { data: regions } = useRegions();

  // --- the tapped place and its forecast -----------------------------------
  const [picked, setPicked] = useState<Pick_ | null>(null);
  const pickedSpot = useMemo(
    () => (picked?.kind === "spot" ? spots?.find((candidate) => candidate.id === picked.id) ?? null : null),
    [picked, spots],
  );
  const { data: spotForecast, loading: spotForecastLoading } = useSpotForecast(
    picked?.kind === "spot" ? picked.id : undefined,
  );
  const { slots: pointSlots, loading: pointLoading } = useFieldPointForecast(
    picked?.kind === "point" ? [picked.lon, picked.lat] : null,
    pointManifests,
    visualProduct,
  );
  // A spot's hours come from the very model the Spot-Daten forecast draws, so
  // the same hour reads the same on both surfaces (06:00–22:00 local).
  const spotSlots = useMemo<MapForecastSlot[]>(
    () => (spotForecast ? buildMeteogramModel(spotForecast, isSpotForecastDisplayHour).slots : []),
    [spotForecast],
  );
  const slots = picked?.kind === "spot" ? spotSlots : pointSlots;
  const sheetLoading = picked?.kind === "spot" ? spotForecastLoading : pointLoading;

  const closeSheet = useCallback(() => setPicked(null), []);
  // Escape closes the sheet, like every other dismissible surface on the site.
  useEffect(() => {
    if (!picked) return;
    const onKey = (event: KeyboardEvent) => { if (event.key === "Escape") closeSheet(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [picked, closeSheet]);

  // The hours the map offers: every published instant from now through the
  // next five days, and nothing outside it (a deep-future step would show a
  // field nobody asked to see).
  const times = useMemo(() => fieldWindow(manifest?.valid_times ?? []), [manifest]);
  // What the clock may offer. The END comes from every model that covers this
  // view, not just the one currently drawn: ICON-D2 stops after two days, but
  // ICON-EU reaches five, and picking that day re-selects the model. The
  // START stays with the active publication, which is what is on screen.
  const reach = useMemo(() => {
    const ends = (visual?.data.available_models ?? [])
      .filter((model) => model.covers_viewport !== false && model.covers_point !== false)
      .map((model) => (model.valid_to ? Date.parse(model.valid_to) : Number.NaN))
      .filter((end) => Number.isFinite(end));
    return ends.length ? Math.max(...ends) : undefined;
  }, [visual?.data.available_models]);
  const horizon = useMemo(() => {
    if (!times.length) return null;
    const publishedFrom = Date.parse(times[0]);
    const activeTo = Date.parse(times[times.length - 1]);
    const publishedTo = Math.max(activeTo, reach ?? activeTo);
    return { publishedFrom, publishedTo, nowAt: Math.min(Math.max(Date.now(), publishedFrom), activeTo) };
  }, [times, reach]);
  const selectedAt = fieldAt ?? horizon?.nowAt;
  const selectedTime = selectedAt === undefined ? undefined : new Date(selectedAt).toISOString();
  // Keep the next published step warm, so dragging forward rarely waits.
  const nextTime = useMemo(() => {
    if (selectedAt === undefined) return undefined;
    return times.find((time) => Date.parse(time) > selectedAt);
  }, [times, selectedAt]);

  // Opens on now, and returns there if the publication moves past the instant
  // the viewer had chosen.
  useEffect(() => {
    if (!horizon) return;
    setFieldAt((current) => (
      current === undefined || current < horizon.publishedFrom || current > horizon.publishedTo
        ? horizon.nowAt
        : current
    ));
  }, [horizon]);

  useEffect(() => {
    syncUrl({ model: undefined, validAt: undefined, layer: requestedLayer, display });
  }, [syncUrl, display, requestedLayer]);

  useEffect(() => {
    if (!active || embedded) return;
    const shared = parseFieldUrlState(window.location.search);
    setFocusRequest({ id: Date.now(), center: shared.center, zoom: shared.zoom });
  }, [active, embedded]);

  /** The search answers by moving the camera, never by leaving the map. A spot
   *  additionally opens its forecast, which is what one was looking for. */
  const resolvePlace = (selection: WhereSelection | null, text: string) => {
    const moveTo = (center: [number, number], zoom: number) =>
      setFocusRequest({ id: Date.now(), center, zoom });
    const needle = text.trim().toLowerCase();

    const spot = selection?.kind === "spot" && selection.id
      ? spots?.find((candidate) => candidate.id === selection.id)
      : !selection && needle
        ? spots?.find((candidate) => candidate.name.toLowerCase() === needle)
        : undefined;
    if (spot?.coords) {
      const [latitude, longitude] = spot.coords;
      moveTo([longitude, latitude], SPOT_FOCUS_ZOOM);
      setPicked({ kind: "spot", id: spot.id });
      return;
    }

    const region = selection?.kind === "region" && selection.id
      ? regions?.find((candidate) => candidate.id === selection.id)
      : !selection && needle
        ? regions?.find((candidate) => candidate.name.toLowerCase() === needle)
        : undefined;
    if (region?.center) moveTo([region.center.lon, region.center.lat], REGION_FOCUS_ZOOM);
  };

  // One clock for the whole map: the sheet highlights the hour the field is
  // drawn at, and picking an hour in the sheet moves the field to it — exactly
  // to it, since the field no longer has to land on a published step.
  const sheetSelection = useMemo(() => {
    if (selectedAt === undefined || !slots.length) return null;
    return slots.reduce((best, slot) => (
      Math.abs(Date.parse(slot.utcKey) - selectedAt) < Math.abs(Date.parse(best.utcKey) - selectedAt) ? slot : best
    )).utcKey;
  }, [slots, selectedAt]);
  const pickSheetHour = (utcKey: string) => {
    if (!horizon) return;
    setFieldAt(Math.min(horizon.publishedTo, Math.max(horizon.publishedFrom, Date.parse(utcKey))));
  };

  const unavailable = !manifest;

  const Root = embedded ? "section" : "main";

  return (
    <Root data-lenis-prevent className={`swd-wind-explorer${embedded ? " is-embedded" : ""}`} aria-labelledby="wind-explorer-title">
      {embedded
        ? <h2 id="wind-explorer-title" className="sr-only">Wetterkarte</h2>
        : <h1 id="wind-explorer-title" className="sr-only">Wetterkarten Explorer</h1>}
      <p id="wind-map-help" className="sr-only">Karte mit den Pfeiltasten bewegen. Eingabetaste oder Leertaste öffnet die Vorhersage für den Punkt in der Kartenmitte.</p>
      <div className={`swd-field-map-wrap${picked ? " has-sheet" : ""}`}>
        {manifest && selectedTime ? (
          <WeatherMapCanvas
            manifest={manifest}
            validAt={selectedTime}
            prefetchValidAt={nextTime}
            display={display}
            layer={visualLayer}
            active={active}
            center={initial.current.center}
            zoom={initial.current.zoom}
            spots={spots ?? undefined}
            showSpots={showSpots}
            spotColor={SPOT_DOT_COLOR}
            showObservations={false}
            focusRequest={focusRequest}
            describedBy="wind-map-help"
            onReady={setCamera}
            onViewChange={(center, zoom, bounds) => {
              setMapViewport({ center, bounds });
              syncUrl({ mode, center, zoom, validAt: undefined, model: undefined, display, layer: requestedLayer, showSpots });
            }}
            onPick={(lon, lat) => setPicked({ kind: "point", lon, lat })}
            onPickSpot={(id) => setPicked({ kind: "spot", id })}
            onLoadingChange={setLoadingTiles}
            onError={setFieldError}
          />
        ) : <div className="swd-field-map-placeholder" />}

        {/* The same furniture as the spot map, in the same places and sizes:
            back + zoom as bare glyphs on the left, the mode switch centred at
            the top, and one glyph on the right — the list on the spot map, the
            search here. White, because the wind field is the darker surface.
            The embedded map (results page) carries none of it. */}
        {!embedded && (
          <>
            <div className="swd-map-controls-left pointer-events-none absolute z-scrim flex flex-col items-start gap-2">
              <button type="button" aria-label="Zurück" onClick={() => navigate("/")} className="swd-map-bare-control pointer-events-auto">
                <ChevronLeftIcon className="text-title" />
              </button>
              <div className="pointer-events-auto flex flex-col">
                <button type="button" aria-label="Vergrößern" onClick={() => camera?.zoomIn()} className="swd-map-bare-control"><PlusIcon className="text-title" /></button>
                <button type="button" aria-label="Verkleinern" onClick={() => camera?.zoomOut()} className="swd-map-bare-control"><MinusIcon className="text-title" /></button>
              </div>
            </div>
            {onModeChange && <ExplorerModeToggle mode={mode} onChange={onModeChange} />}
            {/* The search is the glyph alone — no pill, no label, no second
                implementation: `Header variant="inline"` opens the site's own
                sheet in place-only mode. */}
            <div className="swd-map-controls swd-wx-search pointer-events-none absolute z-scrim flex flex-col items-end gap-3">
              <Header variant="inline" whereOnly onResolve={resolvePlace} />
            </div>
          </>
        )}

        {(unavailable || fieldError) && (
          <section className="swd-field-message" role="alert">
            <strong>{state.status === "offline" ? "Offline" : fieldError ? "Kartendaten fehlen" : `${product === "waves" ? "Wellenkarte" : "Windkarte"} noch nicht verfügbar`}</strong>
            <p>{fieldError ?? ("message" in state ? state.message : "Die Karte wird vorbereitet.")}</p>
            <div><button type="button" onClick={reload}>Erneut versuchen</button></div>
          </section>
        )}

        {state.status === "offline" && manifest && <div className="swd-field-expired is-offline" role="status">Offline · bereits geladene Felddaten</div>}

        <LeafletAttributionDisclosure source="carto" tone="overlay" className="swd-wx-attribution" />

        {!embedded && manifest && horizon && selectedAt !== undefined && (
          <FieldTimeNav
            value={selectedAt}
            nowAt={horizon.nowAt}
            publishedFrom={horizon.publishedFrom}
            publishedTo={horizon.publishedTo}
            onChange={setFieldAt}
          />
        )}

        {picked && (
          <MapForecastSheet
            title={picked.kind === "spot" ? pickedSpot?.name ?? "Spot" : coordLabel(picked.lon, picked.lat)}
            titleHref={picked.kind === "spot" && pickedSpot ? spotPath(pickedSpot, "daten") : undefined}
            meta={picked.kind === "spot" ? pickedSpot?.region : manifest?.model?.toUpperCase()}
            slots={slots}
            selectedUtcKey={sheetSelection}
            onSelect={pickSheetHour}
            onClose={closeSheet}
            loading={sheetLoading}
            windUnit={units.wind}
            tempUnit={units.temp}
            waveUnit={units.wave}
            product={visualProduct}
          />
        )}
      </div>
    </Root>
  );
}
