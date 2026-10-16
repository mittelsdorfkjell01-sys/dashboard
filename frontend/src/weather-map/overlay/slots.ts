import { MS_TO_KT } from "../../lib/liveWindPresentation";
import type { WindBarSlot } from "../../components/forecast/WindForecastBars";
import type { FieldSample, WaveFieldSample } from "../contracts";

/**
 * One hour in the map's bottom forecast sheet. It is the shared wind-bar slot
 * plus the two values the Daten forecast prints above its bars, and the local
 * date the sheet groups its day captions by. A `NormalizedForecastHour`
 * satisfies it as it is, so a tapped SPOT feeds the sheet straight from the
 * same model the Spot-Daten forecast uses; a tapped COORDINATE is mapped onto
 * it from the field samples below.
 */
export type MapForecastSlot = WindBarSlot & {
  localDate: string;
  air?: number | null;
  swell?: number | null;
  period?: number | null;
  swellDirection?: number | null;
};

const HOUR = new Intl.DateTimeFormat("de-DE", { hour: "2-digit", minute: "2-digit" });
const DATE = new Intl.DateTimeFormat("sv-SE", { year: "numeric", month: "2-digit", day: "2-digit" });

/**
 * Field samples → sheet slots, in the VIEWER's time zone. A coordinate on open
 * water has no place to borrow a time zone from (unlike a spot, which carries
 * its own), so the honest reading is the one on the viewer's clock.
 * Wind and gust are converted to knots, the unit every chart on the site
 * scales and colours by; the viewer's unit preference is applied on display.
 */
export function fieldSampleSlots(samples: Array<FieldSample | WaveFieldSample>): MapForecastSlot[] {
  return samples
    .map((sample) => {
      const at = new Date(sample.valid_at);
      if (sample.product === "model_wave") {
        return {
          utcKey: sample.valid_at,
          localDate: DATE.format(at),
          localTime: HOUR.format(at),
          localHour: at.getHours(),
          wind: null,
          gust: null,
          swell: sample.total_wave_height_m,
          period: sample.total_wave_period_s,
          swellDirection: sample.total_wave_direction_from_deg,
        };
      }
      return {
        utcKey: sample.valid_at,
        localDate: DATE.format(at),
        localTime: HOUR.format(at),
        localHour: at.getHours(),
        wind: sample.speed_ms * MS_TO_KT,
        gust: sample.gust_ms == null ? null : sample.gust_ms * MS_TO_KT,
        air: sample.temperature_c,
      };
    })
    .sort((a, b) => Date.parse(a.utcKey) - Date.parse(b.utcKey));
}

export function fieldTileSeriesSlots(
  samples: Array<{ validAt: string; values: Record<string, number | undefined> }>,
  product: "wind" | "waves",
): MapForecastSlot[] {
  return samples.map(({ validAt, values }) => {
    const at = new Date(validAt);
    const common = {
      utcKey: validAt,
      localDate: DATE.format(at),
      localTime: HOUR.format(at),
      localHour: at.getHours(),
    };
    if (product === "waves") {
      const u = values.wave_u, v = values.wave_v;
      return {
        ...common,
        wind: null,
        gust: null,
        swell: values.total_wave_height ?? (u !== undefined && v !== undefined ? Math.hypot(u, v) : null),
        period: values.total_wave_period,
        swellDirection: values.total_wave_direction,
      };
    }
    const u = values.wind_u, v = values.wind_v;
    return {
      ...common,
      wind: u !== undefined && v !== undefined ? Math.hypot(u, v) * MS_TO_KT : null,
      gust: values.wind_gust === undefined ? null : values.wind_gust * MS_TO_KT,
      air: values.temperature_2m,
    };
  }).sort((a, b) => Date.parse(a.utcKey) - Date.parse(b.utcKey));
}

/** Contiguous runs of one local date, for the sheet's day captions. */
export function dayRuns(slots: MapForecastSlot[]): Array<{ date: string; count: number }> {
  const runs: Array<{ date: string; count: number }> = [];
  for (const slot of slots) {
    const last = runs[runs.length - 1];
    if (last && last.date === slot.localDate) last.count += 1;
    else runs.push({ date: slot.localDate, count: 1 });
  }
  return runs;
}
