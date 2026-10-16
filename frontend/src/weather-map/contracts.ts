export type FieldFreshness = "fresh" | "delayed" | "stale" | "expired";
/** How the field's direction is drawn on top of the colours. `none` draws
 *  nothing: the waves are read from the colour alone (2026-10-12). */
export type FieldDisplayMode = "particles" | "arrows" | "none";
export type FieldLayer = "wind" | "waves" | "gust" | "temperature" | "precipitation" | "pressure" | "clouds";

export interface FieldViewportBounds {
  west: number;
  south: number;
  east: number;
  north: number;
}

export interface FieldVariableDefinition {
  name: "wind_u" | "wind_v" | "wind_gust" | "temperature_2m" | "precipitation" | "pressure_msl" | "cloud_cover" | "wave_u" | "wave_v" | "total_wave_height" | "total_wave_direction" | "total_wave_period" | "wind_sea_height" | "wind_sea_direction" | "wind_sea_period" | "primary_swell_height" | "primary_swell_direction" | "primary_swell_period";
  unit: "m/s" | "°C" | "mm" | "hPa" | "%" | "m" | "°" | "s";
  semantic: "eastward" | "northward" | "magnitude" | "air_temperature" | "accumulation" | "mean_sea_level_pressure" | "fraction" | "wave_eastward" | "wave_northward" | "wave_height" | "direction_from" | "wave_period";
  height_m: number | null;
}

export interface FieldManifest {
  contract_version: "weather-field-v2";
  publication_id: string;
  provider: string;
  model: string;
  model_run: string;
  published_at: string;
  valid_times: string[];
  coverage: { west: number; south: number; east: number; north: number };
  variables: FieldVariableDefinition[];
  compression: "gzip";
  quality_status: "experimental" | "candidate" | "validated" | "rejected";
  freshness: {
    status: FieldFreshness;
    age_seconds: number;
    expected_next_run_at: string;
  };
  attribution: Array<{ provider: string; text: string; url: string; licence: string }>;
  field_template: string;
  series_template?: string | null;
  tile_scheme: {
    tile_size: number;
    overlap: number;
    lod: Array<{
      source_zoom: number;
      consumer_zoom_min: number;
      consumer_zoom_max: number;
      source_decimation: number;
    }>;
  };
}

export interface ActiveFieldResponse {
  enabled: true;
  public: true;
  status: FieldFreshness;
  publication_id: string;
  generation: number;
  manifest_url: string;
  manifest: FieldManifest;
  series_manifests?: FieldManifest[];
  available_models: Array<{
    key: string;
    name: string;
    provider: string;
    coverage: FieldManifest["coverage"];
    model_run: string;
    primary: boolean;
    priority: number;
    freshness: FieldFreshness;
    covers_point: boolean;
    covers_viewport?: boolean;
    /** First and last published instant of this model's active run. */
    valid_from?: string | null;
    valid_to?: string | null;
  }>;
  selection: {
    mode: "auto" | "manual" | "fallback";
    requested_model: string | null;
    selected_model: string;
    reason: "coverage_priority" | "manual_override" | "requested_model_unavailable" | "degraded_coverage_fallback";
    latitude: number | null;
    longitude: number | null;
  };
}

export interface FieldSample {
  product: "model_wind";
  publication_id: string;
  generation: number;
  run_id: string;
  provider: string;
  model: string;
  model_run: string;
  valid_at: string;
  latitude: number;
  longitude: number;
  u_ms: number;
  v_ms: number;
  speed_ms: number;
  direction_from_deg: number;
  gust_ms: number | null;
  temperature_c: number | null;
  precipitation_mm: number | null;
  pressure_hpa: number | null;
  cloud_cover_percent: number | null;
  interpolation: string;
  freshness: FieldFreshness;
}

export interface FieldSampleSeries {
  samples: Array<FieldSample | WaveFieldSample>;
}

export interface WaveFieldSample {
  product: "model_wave";
  publication_id: string;
  generation: number;
  run_id: string;
  provider: string;
  model: string;
  model_run: string;
  valid_at: string;
  latitude: number;
  longitude: number;
  wave_u: number;
  wave_v: number;
  total_wave_height_m: number | null;
  total_wave_direction_from_deg: number | null;
  total_wave_period_s: number | null;
  wind_sea_height_m: number | null;
  wind_sea_direction_from_deg: number | null;
  wind_sea_period_s: number | null;
  primary_swell_height_m: number | null;
  primary_swell_direction_from_deg: number | null;
  primary_swell_period_s: number | null;
  interpolation: string;
  freshness: FieldFreshness;
}

export interface FieldComparison {
  product: "model_wind_comparison";
  valid_at: string;
  latitude: number;
  longitude: number;
  samples: FieldSample[];
  spread: {
    model_count: number;
    speed_min_ms: number | null;
    speed_max_ms: number | null;
    speed_spread_ms: number | null;
    gust_min_ms: number | null;
    gust_max_ms: number | null;
    gust_spread_ms: number | null;
  };
}

export interface FieldObservation {
  station_id: string;
  name: string | null;
  provider: string;
  latitude: number;
  longitude: number;
  observed_at: string;
  wind_speed_ms: number;
  wind_gust_ms: number | null;
  wind_direction_from_deg: number | null;
  quality: number | null;
}
