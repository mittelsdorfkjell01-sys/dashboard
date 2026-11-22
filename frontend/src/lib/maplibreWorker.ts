import { setWorkerUrl } from "maplibre-gl";
import workerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url";

/**
 * MapLibre 6 looks for its worker as a sibling file of its own module
 * (`./maplibre-gl-worker.mjs` next to `maplibre-gl.mjs`). Once the library is
 * bundled into `/assets/maplibre-*.js` that sibling does not exist: the
 * production build answered 404, "Worker failed to load", and every map stayed
 * empty (found 2026-11-22 when the e2e suite moved from the dev server to the
 * production preview). Vite builds the worker — with the shared chunk it
 * imports — as its own asset, and MapLibre gets that URL before any map is
 * created. Import this module once, before `new maplibregl.Map`.
 */
setWorkerUrl(workerUrl);
