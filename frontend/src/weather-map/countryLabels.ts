/**
 * Deliberately sparse country labels for the Europe overview. CARTO's raster
 * label tiles contain cities, roads and regions together, so they cannot be
 * filtered by feature class in the browser. These centroids let both map
 * engines show only countries until the user has zoomed far enough for the
 * normal place-label tiles.
 *
 * The set favours readable countries over microstates at continental zoom.
 */
export const EUROPE_COUNTRY_LABELS = [
  ["Island", -18.6, 64.9], ["Irland", -8.0, 53.3], ["Vereinigtes Königreich", -2.7, 54.5],
  ["Portugal", -8.0, 39.6], ["Spanien", -3.5, 40.2], ["Frankreich", 2.2, 46.4],
  ["Belgien", 4.6, 50.7], ["Niederlande", 5.5, 52.3], ["Luxemburg", 6.1, 49.8],
  ["Deutschland", 10.4, 51.1], ["Dänemark", 9.3, 56.0], ["Norwegen", 8.6, 61.7],
  ["Schweden", 15.0, 62.1], ["Finnland", 26.0, 64.4], ["Estland", 25.5, 58.6],
  ["Lettland", 24.6, 57.0], ["Litauen", 23.9, 55.2], ["Polen", 19.1, 52.0],
  ["Tschechien", 15.4, 49.8], ["Slowakei", 19.5, 48.7], ["Österreich", 14.1, 47.6],
  ["Schweiz", 8.2, 46.8], ["Italien", 12.6, 42.8], ["Slowenien", 14.9, 46.1],
  ["Kroatien", 16.4, 45.2], ["Ungarn", 19.4, 47.2], ["Bosnien und Herzegowina", 17.8, 44.2],
  ["Serbien", 20.8, 44.0], ["Montenegro", 19.2, 42.8], ["Albanien", 20.0, 41.1],
  ["Nordmazedonien", 21.7, 41.6], ["Griechenland", 22.2, 39.1], ["Bulgarien", 25.2, 42.7],
  ["Rumänien", 24.9, 45.9], ["Moldau", 28.6, 47.2], ["Ukraine", 31.3, 49.0],
  ["Belarus", 28.0, 53.5], ["Türkei", 35.2, 39.0], ["Zypern", 33.2, 35.1],
] as const satisfies ReadonlyArray<readonly [name: string, longitude: number, latitude: number]>;

/** Cities and other detailed raster labels do not enter before this zoom. */
export const PLACE_LABEL_MIN_ZOOM = 8;
