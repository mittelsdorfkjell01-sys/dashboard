/**
 * Deliberately sparse country labels for the Europe overview. CARTO's raster
 * label tiles contain cities, roads and regions together, so they cannot be
 * filtered by feature class in the browser. These centroids let both map
 * engines show only countries until the user has zoomed far enough for the
 * normal place-label tiles.
 *
 * The set favours readable countries over microstates at continental zoom,
 * and since 2026-11-16 it carries only countries with a COASTLINE on the seas
 * this map covers. The ten landlocked ones (Luxemburg, Tschechien, Slowakei,
 * Österreich, Schweiz, Ungarn, Serbien, Nordmazedonien, Belarus, Moldau) were
 * names a surf map never needs, and they were the crowded middle of the
 * continent — which is why the labels had been shrunk to 8px, two steps below
 * the type scale's floor, to fit. Fewer names, each at the scale's `micro`
 * size (see `.swd-country-label` in map.css).
 */
export const EUROPE_COUNTRY_LABELS = [
  ["Island", -18.6, 64.9], ["Irland", -8.0, 53.3], ["Vereinigtes Königreich", -2.7, 54.5],
  ["Portugal", -8.0, 39.6], ["Spanien", -3.5, 40.2], ["Frankreich", 2.2, 46.4],
  ["Belgien", 4.6, 50.7], ["Niederlande", 5.5, 52.3],
  ["Deutschland", 10.4, 51.1], ["Dänemark", 9.3, 56.0], ["Norwegen", 8.6, 61.7],
  ["Schweden", 15.0, 62.1], ["Finnland", 26.0, 64.4], ["Estland", 25.5, 58.6],
  ["Lettland", 24.6, 57.0], ["Litauen", 23.9, 55.2], ["Polen", 19.1, 52.0],
  ["Italien", 12.6, 42.8], ["Slowenien", 14.9, 46.1],
  ["Kroatien", 16.4, 45.2], ["Bosnien und Herzegowina", 17.8, 44.2],
  ["Montenegro", 19.2, 42.8], ["Albanien", 20.0, 41.1],
  ["Griechenland", 22.2, 39.1], ["Bulgarien", 25.2, 42.7],
  ["Rumänien", 24.9, 45.9], ["Ukraine", 31.3, 49.0],
  ["Türkei", 35.2, 39.0], ["Zypern", 33.2, 35.1],
] as const satisfies ReadonlyArray<readonly [name: string, longitude: number, latitude: number]>;

/** Cities and other detailed raster labels do not enter before this zoom. */
export const PLACE_LABEL_MIN_ZOOM = 8;
