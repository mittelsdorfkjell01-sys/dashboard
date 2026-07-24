// Approximate sunrise/sunset for the forecast chart's daylight shading — the
// classic "Sunrise/Sunset Algorithm" (Almanac for Computers, 1990), accurate
// to a few minutes, no external dependency. Longitude stands in for the
// timezone offset (solar time): the frontend has no IANA timezone for a spot,
// only coordinates, and this is a chart accent, not a legal/scientific time.

const rad = (deg: number) => (deg * Math.PI) / 180;
const toDeg = (r: number) => (r * 180) / Math.PI;
const norm360 = (d: number) => ((d % 360) + 360) % 360;

function dayOfYear(date: Date): number {
  const start = Date.UTC(date.getUTCFullYear(), 0, 1);
  const today = Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), date.getUTCDate());
  return Math.floor((today - start) / 86400000) + 1;
}

function calc(lat: number, lng: number, dayOfYr: number, isRise: boolean): number | null {
  const lngHour = lng / 15;
  const t = dayOfYr + ((isRise ? 6 : 18) - lngHour) / 24;

  const M = 0.9856 * t - 3.289;
  let L = M + 1.916 * Math.sin(rad(M)) + 0.02 * Math.sin(rad(2 * M)) + 282.634;
  L = norm360(L);

  let RA = toDeg(Math.atan(0.91764 * Math.tan(rad(L))));
  RA = norm360(RA);
  // RA must be in the same quadrant as L.
  const Lq = Math.floor(L / 90) * 90;
  const RAq = Math.floor(RA / 90) * 90;
  RA = (RA + (Lq - RAq)) / 15;

  const sinDec = 0.39782 * Math.sin(rad(L));
  const cosDec = Math.cos(Math.asin(sinDec));
  const cosH =
    (Math.cos(rad(90.833)) - sinDec * Math.sin(rad(lat))) / (cosDec * Math.cos(rad(lat)));
  if (cosH > 1 || cosH < -1) return null; // sun never sets / never rises (polar)

  let H = isRise ? 360 - toDeg(Math.acos(cosH)) : toDeg(Math.acos(cosH));
  H = H / 15;

  const T = H + RA - 0.06571 * t - 6.622;
  // Local mean time; using longitude (lngHour) as the timezone stand-in makes
  // this ≈ local civil time instead of UTC (see file header).
  return ((T % 24) + 24) % 24;
}

/** Sunrise/sunset for `date` at `[lat, lng]`, in approximate local decimal
 *  hours (e.g. 6.4 ≈ 06:24). `null` when the sun doesn't rise/set that day
 *  (polar latitudes) — callers should just skip the daylight shading then. */
export function sunTimes(
  lat: number,
  lng: number,
  date: Date
): { sunrise: number; sunset: number } | null {
  const d = dayOfYear(date);
  const sunrise = calc(lat, lng, d, true);
  const sunset = calc(lat, lng, d, false);
  if (sunrise == null || sunset == null) return null;
  return { sunrise, sunset };
}

/** Whether it's currently daytime at [lat, lng] — i.e. the real local clock
 *  time (approximated the same longitude-as-timezone way as {@link sunTimes})
 *  falls between today's sunrise and sunset. Polar day/night (no sunrise or
 *  sunset that day) defaults to daytime rather than guessing which one. */
export function isDaytime(lat: number, lng: number, now: Date = new Date()): boolean {
  const sun = sunTimes(lat, lng, now);
  if (!sun) return true;
  const utcHour = now.getUTCHours() + now.getUTCMinutes() / 60 + now.getUTCSeconds() / 3600;
  const localHour = ((utcHour + lng / 15) % 24 + 24) % 24;
  return localHour >= sun.sunrise && localHour < sun.sunset;
}
