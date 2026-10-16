import type { Map as MapLibreMap } from "maplibre-gl";
import type { FieldDisplayMode } from "./contracts";
import type { FieldSource } from "./FieldSource";
import type { DecodedFieldTile } from "./fieldTile";

interface Particle { longitude: number; latitude: number; age: number }

const ARROW_SPACING = 62;
const WEB_MERCATOR_NORTH = 85.05112878;
const ARROW_MIN_LENGTH = 14;
const ARROW_MAX_LENGTH = 56;
/** The field colours speak in knots, so the arrows have to as well. */
const MS_TO_KT = 1.943844;

/* ------------------------------------------------------------------------
 * Zoom, speed and density (2026-10-12, checked against the references)
 *
 * Both the SPEED and the DENSITY used to be fixed in screen pixels, so a
 * 20 kt wind drifted at the same rate on a continental view as at street
 * level. Literal realism is no better: a particle at the wind's real ground
 * speed moves `speed / metresPerPixel` px per second, which at z4 is a
 * thousandth of a pixel per second and at z13 crosses the screen in under a
 * second. Every published implementation therefore compresses it, and the
 * two that document their maths agree closely:
 *
 *   • earth / leaflet-velocity (the original `windy.js` lineage): the step is
 *     `wind × VELOCITY_SCALE × mapArea^0.4 × pixelJacobian`. The Jacobian is
 *     px per radian, i.e. ∝ 1/mpp, and mapArea ∝ mpp², so the whole thing is
 *     ∝ (1/mpp)^0.2 — zooming in speeds the field up, very gently.
 *   • Mapbox's raster-particle layer: a `raster-particle-speed-factor`
 *     (default 0.2) over data-space velocities, particles counted per tile
 *     (512), tails as a per-frame fade (0.98), and a colour map parameterised
 *     by particle speed.
 *   • Windy keeps white particles over the coloured field and only recolours
 *     them when the ground underneath gets busy.
 *
 * So: `ADVECTION_ZOOM_EXPONENT = 0.2`, the earth/leaflet-velocity figure,
 * anchored to the tuning that looked right at z≈8 (4.8 px/s per m/s). Four
 * times closer to the ground is then 1.32× faster, not 4×.
 *
 * The streak is the path the particle actually covered in the last
 * `TRAIL_SECONDS`, so length follows speed and zoom by construction instead
 * of through a second, unrelated curve.
 *
 * Density stays the screen density that was tuned against the "white haze"
 * complaint, with one cap: no more than ~`PARTICLE_PER_CELL` streaks per
 * published cell. Zoomed out that is far above the base density and nothing
 * changes; only in the last zoom levels, where one ICON cell can fill half
 * the screen, does the carpet thin out instead of drawing dozens of identical
 * parallel streaks. (Mapbox's per-tile count does the same thing in a coarser
 * way.) The arrow lattice follows the same rule.
 * ---------------------------------------------------------------------- */

/** Metres of ground per screen pixel — MapLibre's world is 512·2^zoom px. */
export function metresPerPixel(zoom: number, latitude: number): number {
  const circumference = 40075016.686 * Math.cos((latitude * Math.PI) / 180);
  return Math.abs(circumference) / (512 * 2 ** zoom);
}

/** Screen pixels per second, per m/s of wind. */
export const ADVECTION_REF_MPP = 197; // = z8 at 50°N, where the old tuning sat
export const ADVECTION_REF_PX_PER_MS = 3.4; // was 4.8 — asked to slow down
export const ADVECTION_ZOOM_EXPONENT = 0.2;
export const ADVECTION_MIN_PX_PER_MS = 1.6;
export const ADVECTION_MAX_PX_PER_MS = 14;

export function advectionPxPerSecond(metresPerPixelValue: number): number {
  if (!(metresPerPixelValue > 0)) return ADVECTION_REF_PX_PER_MS;
  const ratio = ADVECTION_REF_MPP / metresPerPixelValue;
  const scaled = ADVECTION_REF_PX_PER_MS * ratio ** ADVECTION_ZOOM_EXPONENT;
  return Math.min(ADVECTION_MAX_PX_PER_MS, Math.max(ADVECTION_MIN_PX_PER_MS, scaled));
}

/**
 * Mercator stretches north–south: at 60°N a metre of ground is twice as many
 * screen pixels as at the equator. The step is derived once per frame from the
 * map's centre latitude, so every particle away from that centre is corrected
 * by this ratio — otherwise the same wind would visibly crawl at the top of a
 * continental view and race at the bottom. (earth/leaflet-velocity do the same
 * thing by sampling the projection's local Jacobian per particle.) Clamped,
 * because the ratio runs away near the poles.
 */
export function mercatorStretch(latitude: number, centreLatitude: number): number {
  const cosParticle = Math.cos((latitude * Math.PI) / 180);
  const cosCentre = Math.cos((centreLatitude * Math.PI) / 180);
  if (!(cosParticle > 0.01) || !(cosCentre > 0.01)) return 1;
  return Math.min(4, Math.max(0.25, cosCentre / cosParticle));
}

/** Screen area per streak, given the on-screen size of one published cell. */
export const PARTICLE_PER_CELL = 40;
export function particleAreaPx(cellPx: number): number {
  if (!(cellPx > 0)) return PARTICLE_AREA_PER;
  return Math.max(PARTICLE_AREA_PER, (cellPx * cellPx) / PARTICLE_PER_CELL);
}

/** Arrow lattice spacing: never finer than ~2 arrows per cell edge. */
export function arrowSpacingPx(cellPx: number): number {
  if (!(cellPx > 0)) return ARROW_SPACING;
  return Math.min(190, Math.max(ARROW_SPACING, cellPx / 2.2));
}

// Streak geometry (2026-10-11 feedback: "länger, schmaler, wie ein länglich
// gezogener Tropfen"). Fewer, longer streaks than before, so a drawn-out tail
// does not pile up into the white haze that read as cloud cover.
const TRAIL_SEGMENTS = 6;
const TRAIL_POINTS = TRAIL_SEGMENTS + 2;
const STRIDE = TRAIL_POINTS * 2;
const TRAIL_MIN_PX = 9;
const TRAIL_MAX_PX = 96;
// Sparse on purpose: long streaks at high density turn a light basemap into
// a bank of white cloud (2026-10-11, twice). Roughly half the old count.
const PARTICLE_MAX = 1200;
const PARTICLE_AREA_PER = 1050;
/** Even when one cell fills the screen, the flow has to read as motion. */
const PARTICLE_MIN = 260;
/** Seconds a streak lives before it is reseeded somewhere else. Long enough
 *  to follow one across a bend instead of seeing it blink out (2026-10-12). */
const PARTICLE_MAX_AGE_S = 5.5;
/** Head first: the tip carries the weight, the tail thins out to nothing. */
const TRAIL_WIDTH = [1.6, 1.25, 0.95, 0.72, 0.52, 0.36, 0.24];
const TRAIL_ALPHA = [0.82, 0.55, 0.36, 0.23, 0.14, 0.08, 0.04];

/** How much of the recent past a streak shows. */
export const TRAIL_SECONDS = 1.6;

/** Streak length in px: the distance this particle covered in the last
 *  `TRAIL_SECONDS` at `pxPerSecondPerMs` — the streak IS the path, so it
 *  follows speed and zoom without a second curve of its own. Clamped so calm
 *  air still leaves a mark and a gale does not smear across the viewport. */
export function trailLengthPx(speedMs: number, pxPerSecondPerMs: number): number {
  const speed = Number.isFinite(speedMs) ? Math.max(0, speedMs) : 0;
  const travelled = speed * pxPerSecondPerMs * TRAIL_SECONDS;
  return Math.min(TRAIL_MAX_PX, Math.max(TRAIL_MIN_PX, travelled));
}

/** Arrow length over the SAME domain the colour scale spans, 0–40 kt
 *  ([fieldColor.ts](frontend/src/weather-map/fieldColor.ts) `STOPS`). It used
 *  to grow by 3.2 px per m/s and hit its cap at ~13 m/s (25 kt), so the top
 *  third of the colour range drew identical arrows — colour and geometry said
 *  different things about the same wind (2026-10-12). */
export const ARROW_SCALE_MAX_KT = 40;
export function windArrowLength(speedMs: number): number {
  if (!Number.isFinite(speedMs)) return ARROW_MIN_LENGTH;
  const knots = Math.max(0, speedMs) * MS_TO_KT;
  const share = Math.min(1, knots / ARROW_SCALE_MAX_KT);
  return Math.round(ARROW_MIN_LENGTH + share * (ARROW_MAX_LENGTH - ARROW_MIN_LENGTH));
}

/** Keep the arrow lattice tied to the projected world instead of the viewport. */
export function alignedGridStart(projectedOrigin: number, spacing: number): number {
  return ((projectedOrigin % spacing) + spacing) % spacing;
}

export function fadeParticleTrails(
  context: CanvasRenderingContext2D,
  width: number,
  height: number,
) {
  context.save();
  context.globalCompositeOperation = "destination-out";
  // Firm enough that the drawn-out streaks cannot pile up into a white haze
  // over the map (2026-10-11: "es sieht aus, als wären Wolken eingefügt"),
  // gentle enough that each streak still fades out instead of blinking off.
  context.fillStyle = "rgba(0, 0, 0, .2)";
  context.fillRect(0, 0, width, height);
  context.restore();
}

export class WindAnimationLayer {
  readonly canvas = document.createElement("canvas");
  private readonly context: CanvasRenderingContext2D;
  private particles: Particle[] = [];
  private frame = 0;
  private lastFrameAt = 0;
  private active = true;
  private mode: FieldDisplayMode = "particles";
  private tiles: DecodedFieldTile[] = [];
  /** Scratch buffer for this frame's streak polylines (head → tail). */
  private trail = new Float32Array(PARTICLE_MAX * STRIDE);

  constructor(private readonly map: MapLibreMap, private source: FieldSource) {
    this.canvas.className = "swd-field-motion";
    this.canvas.setAttribute("aria-hidden", "true");
    map.getContainer().appendChild(this.canvas);
    const context = this.canvas.getContext("2d");
    if (!context) throw new Error("Windanimation ist auf diesem Gerät nicht verfügbar.");
    this.context = context;
  }

  setSource(source: FieldSource) {
    this.source = source;
  }

  setActive(active: boolean) {
    this.active = active;
    if (active) this.redraw();
  }

  setData(tiles: DecodedFieldTile[], mode: FieldDisplayMode) {
    this.tiles = tiles;
    this.mode = mode;
    this.particles = [];
    const { width, height } = this.resize();
    this.context.clearRect(0, 0, width, height);
    if (mode === "arrows") this.drawArrows();
  }

  private resize() {
    const ratio = Math.min(window.devicePixelRatio || 1, 2);
    const width = this.map.getContainer().clientWidth, height = this.map.getContainer().clientHeight;
    if (this.canvas.width !== Math.floor(width * ratio) || this.canvas.height !== Math.floor(height * ratio)) {
      this.canvas.width = Math.floor(width * ratio); this.canvas.height = Math.floor(height * ratio);
      this.context.setTransform(ratio, 0, 0, ratio, 0, 0);
    }
    return { width, height };
  }

  /** On-screen size of one published cell, straight from the loaded tile —
   *  no assumption about the model's resolution. 0 when nothing is loaded. */
  private cellPx(): number {
    const tile = this.tiles[0];
    if (!tile) return 0;
    const n = 2 ** tile.header.z;
    const west = (tile.header.x / n) * 360 - 180;
    const east = ((tile.header.x + 1) / n) * 360 - 180;
    const latitude = this.map.getCenter().lat;
    const inner = tile.header.width - 2 * (tile.header.overlap ?? 0);
    if (inner <= 0) return 0;
    const left = this.map.project([west, latitude]);
    const right = this.map.project([east, latitude]);
    return Math.abs(right.x - left.x) / inner;
  }

  private reset(particle?: Particle): Particle {
    const { width, height } = this.resize();
    const value = particle ?? { longitude: 0, latitude: 0, age: 0 };
    // Prefer a location backed by a loaded tile. This avoids long, apparently
    // empty particle phases around partial coverage and viewport edges.
    for (let attempt = 0; attempt < 12; attempt += 1) {
      const lngLat = this.map.unproject([Math.random() * width, Math.random() * height]);
      value.longitude = lngLat.lng;
      value.latitude = lngLat.lat;
      if (this.tiles.length === 0 || this.source.sample(this.tiles, lngLat.lng, lngLat.lat)) break;
    }
    value.age = Math.random() * PARTICLE_MAX_AGE_S * 0.7;
    return value;
  }

  private drawArrows() {
    const { width, height } = this.resize();
    const context = this.context;
    context.clearRect(0, 0, width, height);
    context.strokeStyle = "rgba(255,255,255,.96)";
    context.lineWidth = 1.35;
    context.lineCap = "round";
    context.lineJoin = "round";
    context.shadowColor = "rgba(3,18,22,.82)";
    context.shadowBlur = 1.5;
    const spacing = arrowSpacingPx(this.cellPx());
    const worldOrigin = this.map.project([-180, WEB_MERCATOR_NORTH]);
    const startX = alignedGridStart(worldOrigin.x, spacing);
    const startY = alignedGridStart(worldOrigin.y, spacing);
    for (let y = startY; y < height; y += spacing) for (let x = startX; x < width; x += spacing) {
      const lngLat = this.map.unproject([x, y]);
      const wind = this.source.sample(this.tiles, lngLat.lng, lngLat.lat);
      if (!wind) continue;
      const angle = Math.atan2(-wind.v, wind.u);
      const length = windArrowLength(Math.hypot(wind.u, wind.v));
      const headLength = Math.min(7, Math.max(4, length * 0.16));
      const headWidth = Math.min(4.5, Math.max(2.5, length * 0.1));
      context.save(); context.translate(x, y); context.rotate(angle);
      context.beginPath(); context.moveTo(-length / 2, 0); context.lineTo(length / 2, 0); context.lineTo(length / 2 - headLength, -headWidth); context.moveTo(length / 2, 0); context.lineTo(length / 2 - headLength, headWidth);
      context.stroke(); context.restore();
    }
  }

  start() {
    const animate = (frameAt: number) => {
      this.frame = requestAnimationFrame(animate);
      if (!this.active) {
        this.lastFrameAt = frameAt;
        return;
      }
      // Seconds, capped so a tab that was backgrounded does not teleport the
      // whole field on its first frame back.
      const dt = this.lastFrameAt ? Math.min(0.05, (frameAt - this.lastFrameAt) / 1000) : 1 / 60;
      this.lastFrameAt = frameAt;
      if (this.mode !== "particles") return;
      const { width, height } = this.resize();
      const context = this.context;
      fadeParticleTrails(context, width, height);
      const cellPx = this.cellPx();
      const centreLatitude = this.map.getCenter().lat;
      const stepPerMs = advectionPxPerSecond(metresPerPixel(this.map.getZoom(), centreLatitude));

      const area = particleAreaPx(cellPx);
      const target = Math.max(
        PARTICLE_MIN,
        Math.min(PARTICLE_MAX, Math.floor((width * height) / area)),
      );
      while (this.particles.length < target) this.particles.push(this.reset());
      if (this.particles.length > target) this.particles.length = target;
      // Each streak is collected as a polyline from its head backwards, then
      // the whole field is stroked once per segment: the head pass is the
      // widest and brightest, every pass behind it thinner and fainter. That
      // is what gives the drawn-out teardrop — thick at the tip, vanishing at
      // the tail — without a per-particle gradient (2026-10-11 feedback).
      // Each segment is drawn as a quadratic curve between the midpoints of
      // its neighbours, with the shared point as the control: consecutive
      // pieces meet at those midpoints with the same tangent, so a streak
      // following a bend is one smooth curve instead of a chain of straight
      // dashes with visible corners (2026-10-12).
      const points = this.trail;
      let count = 0;
      for (const particle of this.particles) {
        const point = this.map.project([particle.longitude, particle.latitude]);
        const wind = this.source.sample(this.tiles, particle.longitude, particle.latitude);
        particle.age += dt;
        if (!wind || particle.age > PARTICLE_MAX_AGE_S || point.x < 0 || point.y < 0 || point.x > width || point.y > height) { this.reset(particle); continue; }
        // Advect one step downwind, at the field's own ground speed, corrected
        // for how far this particle's latitude is stretched by Mercator.
        const stepHere = stepPerMs * mercatorStretch(particle.latitude, centreLatitude);
        const nextPoint: [number, number] = [
          point.x + wind.u * stepHere * dt,
          point.y - wind.v * stepHere * dt,
        ];
        const nextLngLat = this.map.unproject(nextPoint);
        particle.longitude = nextLngLat.lng;
        particle.latitude = nextLngLat.lat;
        // The trail curves *upwind* by integrating backwards along the flow
        // field — a flowing streak, not a straight fixed-length dash.
        const speed = Math.hypot(wind.u, wind.v);
        const segPx = trailLengthPx(speed, stepHere) / TRAIL_SEGMENTS;
        const base = count * STRIDE;
        points[base] = nextPoint[0]; points[base + 1] = nextPoint[1];
        points[base + 2] = point.x; points[base + 3] = point.y;
        let bx = point.x, by = point.y, bu = wind.u, bv = wind.v, written = 2;
        for (let step = 0; step < TRAIL_SEGMENTS; step += 1) {
          const sp = Math.hypot(bu, bv) || 1;
          bx -= (bu / sp) * segPx;
          by += (bv / sp) * segPx;
          points[base + written * 2] = bx; points[base + written * 2 + 1] = by;
          written += 1;
          const backLngLat = this.map.unproject([bx, by]);
          const back = this.source.sample(this.tiles, backLngLat.lng, backLngLat.lat);
          if (!back) break;
          bu = back.u; bv = back.v;
        }
        // A short trail repeats its last point, so every streak has the same
        // number of passes and the taper stays aligned.
        for (let index = written; index < TRAIL_POINTS; index += 1) {
          points[base + index * 2] = bx; points[base + index * 2 + 1] = by;
        }
        count += 1;
      }
      context.lineCap = "round";
      context.lineJoin = "round";
      context.shadowColor = "transparent";
      context.shadowBlur = 0;
      for (let segment = 0; segment < TRAIL_POINTS - 1; segment += 1) {
        context.strokeStyle = `rgba(255,255,255,${TRAIL_ALPHA[segment]})`;
        context.lineWidth = TRAIL_WIDTH[segment];
        context.beginPath();
        for (let index = 0; index < count; index += 1) {
          const here = index * STRIDE + segment * 2;
          const next = here + 2;
          // Start at the midpoint with the previous segment (the head starts
          // at the head itself), end at the midpoint with the next one.
          const startX = segment === 0 ? points[here] : (points[here - 2] + points[here]) / 2;
          const startY = segment === 0 ? points[here + 1] : (points[here - 1] + points[here + 1]) / 2;
          const last = segment === TRAIL_POINTS - 2;
          const endX = last ? points[next] : (points[next] + points[next + 2]) / 2;
          const endY = last ? points[next + 1] : (points[next + 1] + points[next + 3]) / 2;
          context.moveTo(startX, startY);
          context.quadraticCurveTo(points[here], points[here + 1], endX, endY);
        }
        context.stroke();
      }
    };
    this.frame = requestAnimationFrame(animate);
  }

  redraw() {
    if (this.mode === "arrows") {
      this.drawArrows();
      return;
    }
    const { width, height } = this.resize();
    // Trails contain screen-space pixels from the previous camera position.
    // Clearing them lets the geographically stored particles be reprojected
    // on the next frame without leaving a detached overlay behind.
    this.context.clearRect(0, 0, width, height);
  }

  destroy() { cancelAnimationFrame(this.frame); this.canvas.remove(); }
}
