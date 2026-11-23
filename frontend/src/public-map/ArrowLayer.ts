import type { Map as MapLibreMap } from "maplibre-gl";
import type { DecodedFieldTile } from "../weather-map/fieldTile";
import { bearingOf, sampleTiles, waveReading, windReading, type WaveComponent } from "./fieldSample";

/* ------------------------------------------------------------------------
 * Field arrows for wind AND waves (2026-11-19 spec, density reworked
 * 2026-11-20).
 *
 * Form: a continuous shaft and a filled head of ~35 % of the length, pointing
 * where the wind or the waves GO. Size is a second channel only: the length
 * grows with √value inside 14–24 px. Wind below 2 kn is an open circle; a sea
 * below 0.1 m draws nothing. Missing data draws nothing at all.
 *
 * Density (2026-11-20: "dichter, und der Abstand soll beim Rauszoomen
 * bleiben — kein Neu-Rendern, ein smoother Übergang"): the lattice is a
 * power-of-two hierarchy anchored to the WORLD. The points of the coarse
 * level sit fixed on the map and travel with every pan and pinch; the points
 * of the next finer level, half-way between them, fade in continuously as you
 * zoom in and fade out as you zoom out. Nothing is ever re-laid out, so there
 * is no jump — the on-screen spacing stays between ~32 and ~64 px at every
 * zoom.
 *
 * Time: one step turns and scales each arrow in 200 ms along the shorter way
 * round; scrubbing sets them directly; playback couples the transition to
 * its tempo. While the next step loads the old arrows stay at 50 %.
 * Reduced motion sets everything directly.
 * ---------------------------------------------------------------------- */

export const ARROW_MIN_PX = 14;
export const ARROW_MAX_PX = 24;
export const ARROW_SCALE_TOP_KN = 40;
export const WAVE_SCALE_TOP_M = 4;
export const CALM_KN = 2;
export const FLAT_SEA_M = 0.1;
/** Screen spacing of the coarse level right at its own zoom (2026-11-21:
 *  64 → 84, the lattice covered too much of the map; spacing now ~42–84 px). */
export const LATTICE_PX = 84;
/** Waves get a denser lattice (2026-11-21, "beim Rauszoomen mehr Pfeile"):
 *  32–64 px, so a zoomed-out ocean carries as many arrows as a zoomed-in bay. */
export const WAVE_LATTICE_PX = 64;
/** Mask read-back resolution: one sample per 4 CSS px is plenty for a 1.5px arrow. */
const MASK_STEP = 4;
const STROKE_PX = 1.5;
const FADE_IN_MS = 140;
const KEY_LEVEL = 22;

export function arrowLengthPx(knots: number): number {
  const share = Math.min(1, Math.sqrt(Math.max(0, knots) / ARROW_SCALE_TOP_KN));
  return ARROW_MIN_PX + (ARROW_MAX_PX - ARROW_MIN_PX) * share;
}
export function waveArrowLengthPx(metres: number): number {
  const share = Math.min(1, Math.sqrt(Math.max(0, metres) / WAVE_SCALE_TOP_M));
  return ARROW_MIN_PX + (ARROW_MAX_PX - ARROW_MIN_PX) * share;
}

/** Signed shortest turn from `from` to `to`, in degrees (−180, 180]. */
export function shortestTurn(from: number, to: number): number {
  const delta = ((((to - from) % 360) + 540) % 360) - 180;
  return delta === -180 ? 180 : delta;
}

/** Opacity of a lattice point at a continuous zoom: points of the coarse
 *  level are always there, the in-between points of the next level fade in
 *  with the fractional part of the zoom (smoothstep, so it never pops). */
export function latticeAlpha(onCoarse: boolean, zoom: number): number {
  if (onCoarse) return 1;
  const f = zoom - Math.floor(zoom);
  return f * f * (3 - 2 * f);
}

export type ArrowTransition = "smooth" | "instant" | { playMs: number };
export type ArrowKind = "wind" | "waves";

interface ArrowState {
  a0: number; a1: number; l0: number; l1: number;
  t0: number; dur: number; born: number; version: number;
  value: number; gust?: number; calm: boolean; period?: number;
}

export interface ArrowPick { kind: ArrowKind; x: number; y: number; value: number; gust?: number; period?: number; fromDeg: number; calm: boolean }

const reducedMotion = () => typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

export class ArrowLayer {
  readonly canvas = document.createElement("canvas");
  private readonly context: CanvasRenderingContext2D;
  private tiles: DecodedFieldTile[] = [];
  private kind: ArrowKind = "wind";
  private component: WaveComponent = "total";
  private version = 0;
  private transition: ArrowTransition = "smooth";
  private loading = false;
  private visible = false;
  private hoverKey: string | null = null;
  private readonly arrows = new Map<string, ArrowState>();
  private frame = 0;
  private waterMask: HTMLCanvasElement | null = null;
  private readonly maskScratch = document.createElement("canvas");
  private readonly onMove = () => this.schedule();

  constructor(private readonly map: MapLibreMap) {
    this.canvas.className = "swd-pm-arrows";
    this.canvas.setAttribute("aria-hidden", "true");
    map.getContainer().appendChild(this.canvas);
    const context = this.canvas.getContext("2d");
    if (!context) throw new Error("Pfeile sind auf diesem Gerät nicht verfügbar.");
    this.context = context;
    map.on("move", this.onMove);
  }

  setVisible(visible: boolean) { this.visible = visible; this.schedule(); }

  /** The real coastline (white = water). With it, wave arrows reach the coast
   *  and never sit on land; without it (wind) arrows go everywhere. */
  setWaterMask(mask: HTMLCanvasElement | null) {
    if (this.waterMask === mask) return;
    this.waterMask = mask;
    this.arrows.clear();
    this.schedule();
  }

  /** Redraw on the next frame (the mask has caught up with the camera). */
  refresh() { this.schedule(); }

  private readWater(width: number, height: number): ((x: number, y: number) => boolean) | null {
    const mask = this.waterMask;
    if (!mask || mask.width === 0) return null;
    const w = Math.max(1, Math.ceil(width / MASK_STEP)), h = Math.max(1, Math.ceil(height / MASK_STEP));
    if (this.maskScratch.width !== w || this.maskScratch.height !== h) { this.maskScratch.width = w; this.maskScratch.height = h; }
    const context = this.maskScratch.getContext("2d", { willReadFrequently: true });
    if (!context) return null;
    context.clearRect(0, 0, w, h);
    context.drawImage(mask, 0, 0, w, h);
    const data = context.getImageData(0, 0, w, h).data;
    return (x, y) => {
      const i = Math.floor(y / MASK_STEP), j = Math.floor(x / MASK_STEP);
      if (i < 0 || j < 0 || i >= h || j >= w) return false;
      return data[(i * w + j) * 4] > 127;
    };
  }

  setLoading(loading: boolean) {
    if (this.loading === loading) return;
    this.loading = loading;
    this.schedule();
  }

  setData(tiles: DecodedFieldTile[], kind: ArrowKind, component: WaveComponent, transition: ArrowTransition) {
    if (kind !== this.kind || component !== this.component) this.arrows.clear();
    this.tiles = tiles;
    this.kind = kind;
    this.component = component;
    this.transition = transition;
    this.version += 1;
    this.loading = false;
    this.schedule();
  }

  setHover(key: string | null) {
    if (this.hoverKey === key) return;
    this.hoverKey = key;
    this.schedule();
  }

  /** Nearest drawn arrow within 22 px of a screen point, for the tooltip. */
  pick(x: number, y: number): (ArrowPick & { key: string }) | null {
    if (!this.visible) return null;
    let best: (ArrowPick & { key: string }) | null = null;
    let bestDistance = 22;
    for (const point of this.lattice()) {
      if (point.alpha < 0.5) continue;
      const distance = Math.hypot(point.x - x, point.y - y);
      if (distance >= bestDistance) continue;
      const state = this.arrows.get(point.key);
      if (!state) continue;
      bestDistance = distance;
      best = { key: point.key, kind: this.kind, x: point.x, y: point.y, value: state.value, gust: state.gust, period: state.period, fromDeg: (state.a1 + 180) % 360, calm: state.calm };
    }
    return best;
  }

  private schedule() {
    if (this.frame) return;
    this.frame = requestAnimationFrame((now) => { this.frame = 0; this.draw(now); });
  }

  private resize() {
    const ratio = Math.min(window.devicePixelRatio || 1, 2);
    const container = this.map.getContainer();
    const width = container.clientWidth, height = container.clientHeight;
    if (this.canvas.width !== Math.floor(width * ratio) || this.canvas.height !== Math.floor(height * ratio)) {
      this.canvas.width = Math.floor(width * ratio);
      this.canvas.height = Math.floor(height * ratio);
    }
    this.context.setTransform(ratio, 0, 0, ratio, 0, 0);
    return { width, height };
  }

  /** The finer level's lattice on screen; `alpha` says how present a point is
   *  at this zoom. Keys are world-absolute, so a point keeps its identity (and
   *  its transition) across every zoom level it is visible at. */
  private lattice(): Array<{ key: string; x: number; y: number; longitude: number; latitude: number; alpha: number }> {
    const container = this.map.getContainer();
    const width = container.clientWidth, height = container.clientHeight;
    const zoom = this.map.getZoom();
    const fine = Math.floor(zoom) + 1;
    const step = (this.kind === "waves" ? WAVE_LATTICE_PX : LATTICE_PX) / (512 * 2 ** fine); // normalised mercator, finer level
    const nw = this.map.unproject([-30, -30]), se = this.map.unproject([width + 30, height + 30]);
    const mx = (lon: number) => (lon + 180) / 360;
    const my = (lat: number) => (1 - Math.asinh(Math.tan((Math.max(-85, Math.min(85, lat)) * Math.PI) / 180)) / Math.PI) / 2;
    const x0 = Math.floor(mx(nw.lng) / step), x1 = Math.ceil(mx(se.lng) / step);
    const y0 = Math.floor(my(nw.lat) / step), y1 = Math.ceil(my(se.lat) / step);
    const points: Array<{ key: string; x: number; y: number; longitude: number; latitude: number; alpha: number }> = [];
    if ((x1 - x0) * (y1 - y0) > 6000) return points;
    const fade = latticeAlpha(false, zoom);
    const shift = 2 ** (KEY_LEVEL - fine);
    for (let j = y0; j <= y1; j += 1) {
      for (let i = x0; i <= x1; i += 1) {
        const onCoarse = (i & 1) === 0 && (j & 1) === 0;
        const alpha = onCoarse ? 1 : fade;
        if (alpha <= 0.01) continue;
        const nx = i * step, ny = j * step;
        const longitude = nx * 360 - 180;
        const latitude = (Math.atan(Math.sinh(Math.PI * (1 - 2 * ny))) * 180) / Math.PI;
        const p = this.map.project([longitude, latitude]);
        points.push({ key: `${i * shift}:${j * shift}`, x: p.x, y: p.y, longitude, latitude, alpha });
      }
    }
    return points;
  }

  private read(longitude: number, latitude: number) {
    const values = sampleTiles(this.tiles, longitude, latitude);
    if (this.kind === "wind") {
      const wind = windReading(values);
      if (!wind) return null;
      return { bearing: bearingOf(wind.u, wind.v), length: arrowLengthPx(wind.knots), value: wind.knots, gust: wind.gustKnots, calm: wind.knots < CALM_KN, hidden: false, period: undefined };
    }
    const wave = waveReading(this.waterMask ? sampleTiles(this.tiles, longitude, latitude, true) : values, this.component);
    if (!wave) return null;
    return { bearing: bearingOf(wave.dx, wave.dy), length: waveArrowLengthPx(wave.height), value: wave.height, gust: undefined, calm: false, hidden: wave.height < FLAT_SEA_M, period: wave.period };
  }

  private draw(now: number) {
    const { width, height } = this.resize();
    const context = this.context;
    context.clearRect(0, 0, width, height);
    if (!this.visible || !this.tiles.length) return;
    const still = reducedMotion();
    const duration = still || this.transition === "instant" ? 0 : this.transition === "smooth" ? 200 : Math.max(0, this.transition.playMs * 0.85);
    let animating = false;
    context.lineCap = "round";
    context.lineJoin = "round";
    context.shadowBlur = 0; // plain white, no halo (2026-11-20)
    context.strokeStyle = "#ffffff";
    context.fillStyle = "#ffffff";
    context.lineWidth = STROKE_PX;
    const seen = new Set<string>();
    const water = this.kind === "waves" ? this.readWater(width, height) : null;
    for (const point of this.lattice()) {
      seen.add(point.key);
      if (water && !water(point.x, point.y)) continue;
      let state = this.arrows.get(point.key);
      if (!state || state.version !== this.version) {
        const reading = this.read(point.longitude, point.latitude);
        if (!reading || reading.hidden) { this.arrows.delete(point.key); continue; }
        if (!state) {
          state = { a0: reading.bearing, a1: reading.bearing, l0: reading.length, l1: reading.length, t0: now, dur: 0, born: now, version: this.version, value: reading.value, gust: reading.gust, calm: reading.calm, period: reading.period };
        } else {
          const current = this.current(state, now);
          Object.assign(state, { a0: current.angle, a1: reading.bearing, l0: current.length, l1: reading.length, t0: now, dur: duration, version: this.version, value: reading.value, gust: reading.gust, calm: reading.calm, period: reading.period });
        }
        this.arrows.set(point.key, state);
      }
      const { angle, length, done } = this.current(state, now);
      const fade = still ? 1 : Math.min(1, (now - state.born) / FADE_IN_MS);
      if (!done || fade < 1) animating = true;
      const hovered = this.hoverKey === point.key;
      context.globalAlpha = (this.loading ? 0.5 : hovered ? 1 : 0.92) * fade * point.alpha;
      context.save();
      context.translate(point.x, point.y);
      if (state.calm) {
        context.beginPath();
        context.arc(0, 0, hovered ? 4 : 3.5, 0, Math.PI * 2);
        context.stroke();
      } else {
        const full = length * (hovered ? 1.15 : 1);
        const head = full * 0.35;
        context.rotate((angle * Math.PI) / 180);
        context.beginPath();
        context.moveTo(0, full / 2);
        context.lineTo(0, -full / 2 + head * 0.6);
        context.stroke();
        context.beginPath();
        context.moveTo(0, -full / 2);
        context.lineTo(head * 0.42, -full / 2 + head);
        context.lineTo(-head * 0.42, -full / 2 + head);
        context.closePath();
        context.fill();
      }
      context.restore();
    }
    context.globalAlpha = 1;
    context.shadowBlur = 0;
    if (this.arrows.size > 8000) for (const key of this.arrows.keys()) if (!seen.has(key)) this.arrows.delete(key);
    if (animating) this.schedule();
  }

  private current(state: ArrowState, now: number) {
    const progress = state.dur > 0 ? Math.min(1, (now - state.t0) / state.dur) : 1;
    const eased = 1 - (1 - progress) ** 3;
    return { angle: state.a0 + shortestTurn(state.a0, state.a1) * eased, length: state.l0 + (state.l1 - state.l0) * eased, done: progress >= 1 };
  }

  destroy() {
    cancelAnimationFrame(this.frame);
    this.map.off("move", this.onMove);
    this.canvas.remove();
  }
}
