import type { Map as MapLibreMap } from "maplibre-gl";
import type { FieldSource } from "../weather-map/FieldSource";
import type { DecodedFieldTile } from "../weather-map/fieldTile";
import { advectionPxPerSecond, mercatorStretch, metresPerPixel } from "../weather-map/WindAnimationLayer";

/* ------------------------------------------------------------------------
 * Wind particles (2026-11-20, after the reference image): thin white streaks
 * with fading tails, so the field reads as moving air. Speed and its zoom
 * compression are the shared, documented tuning
 * (weather-map/WindAnimationLayer.ts) — density and tails are this map's own.
 *
 * 2026-11-21 ("Halo-Effekt, besonders beim Rauszoomen"): the tails used to
 * fade by painting a translucent `destination-out` over the canvas each
 * frame. With 8-bit alpha that never reaches zero — every streak left a
 * ~5 % residue that built up into a grey veil over the whole map. Now every
 * particle remembers its last positions and the canvas is CLEARED and redrawn
 * each frame: the tail is geometry, not leftover pixels, so nothing lingers.
 * Density came down at the same time so the base map stays readable.
 * ---------------------------------------------------------------------- */

const AREA_PER_PARTICLE = 520;
const MAX_PARTICLES = 1800;
const MIN_PARTICLES = 250;
const MAX_AGE_S = 5;
/** Positions kept per particle = tail length in frames. */
const TRAIL_POINTS = 22;
/** Tail opacity steps, head first (one stroke call per step). */
const TAIL_ALPHA = [0.85, 0.6, 0.4, 0.24, 0.12];

interface Particle {
  /** Flattened [x0, y0, x1, y1, …], oldest first, newest last. */
  trail: number[];
  age: number;
  /** Past its age: stops moving, its tail drains away, then it reseeds. */
  dying: boolean;
}

export class ParticleLayer {
  readonly canvas = document.createElement("canvas");
  private readonly context: CanvasRenderingContext2D;
  private particles: Particle[] = [];
  private tiles: DecodedFieldTile[] = [];
  private source: FieldSource | null = null;
  private running = false;
  private frame = 0;
  private last = 0;
  private dark = false;
  private readonly onMove = () => this.clear();

  constructor(private readonly map: MapLibreMap) {
    this.canvas.className = "swd-pm-particles";
    this.canvas.setAttribute("aria-hidden", "true");
    map.getContainer().appendChild(this.canvas);
    const context = this.canvas.getContext("2d");
    if (!context) throw new Error("Windanimation ist auf diesem Gerät nicht verfügbar.");
    this.context = context;
    map.on("move", this.onMove);
  }

  setDark(dark: boolean) { this.dark = dark; }

  setData(source: FieldSource | null, tiles: DecodedFieldTile[]) {
    this.source = source;
    this.tiles = tiles;
  }

  setRunning(running: boolean) {
    if (running === this.running) return;
    this.running = running;
    if (running) { this.last = 0; this.frame = requestAnimationFrame(this.step); }
    else { cancelAnimationFrame(this.frame); this.clear(); }
  }

  private size() {
    const ratio = Math.min(window.devicePixelRatio || 1, 2);
    const container = this.map.getContainer();
    const width = container.clientWidth, height = container.clientHeight;
    if (this.canvas.width !== Math.floor(width * ratio) || this.canvas.height !== Math.floor(height * ratio)) {
      this.canvas.width = Math.floor(width * ratio);
      this.canvas.height = Math.floor(height * ratio);
    }
    return { width, height, ratio };
  }

  /** Screen-space trails belong to the old camera: drop them on a move. */
  private clear() {
    this.context.setTransform(1, 0, 0, 1, 0, 0);
    this.context.clearRect(0, 0, this.canvas.width, this.canvas.height);
    const { width, height } = this.size();
    for (const particle of this.particles) this.seed(particle, width, height, true);
  }

  private seed(particle: Particle, width: number, height: number, spreadAge = false) {
    particle.trail = [Math.random() * width, Math.random() * height];
    particle.age = spreadAge ? Math.random() * MAX_AGE_S * 0.8 : 0;
    particle.dying = false;
  }

  private readonly step = (now: number) => {
    this.frame = requestAnimationFrame(this.step);
    const dt = this.last ? Math.min(0.05, (now - this.last) / 1000) : 1 / 60;
    this.last = now;
    const source = this.source;
    const { width, height, ratio } = this.size();
    const context = this.context;
    context.setTransform(1, 0, 0, 1, 0, 0);
    context.clearRect(0, 0, this.canvas.width, this.canvas.height);
    if (!source || !this.tiles.length) return;
    context.setTransform(ratio, 0, 0, ratio, 0, 0);

    const target = Math.max(MIN_PARTICLES, Math.min(MAX_PARTICLES, Math.floor((width * height) / AREA_PER_PARTICLE)));
    while (this.particles.length < target) {
      const particle: Particle = { trail: [], age: 0, dying: false };
      this.seed(particle, width, height, true);
      this.particles.push(particle);
    }
    if (this.particles.length > target) this.particles.length = target;

    const centreLatitude = this.map.getCenter().lat;
    const pxPerMs = advectionPxPerSecond(metresPerPixel(this.map.getZoom(), centreLatitude));
    const paths = TAIL_ALPHA.map(() => new Path2D());
    const span = TRAIL_POINTS - 1;

    for (const particle of this.particles) {
      const trail = particle.trail;
      if (particle.dying) {
        trail.splice(0, 2);
        if (trail.length < 4) { this.seed(particle, width, height); continue; }
      } else {
        particle.age += dt;
        const x = trail[trail.length - 2], y = trail[trail.length - 1];
        const at = this.map.unproject([x, y]);
        const wind = source.sample(this.tiles, at.lng, at.lat);
        if (!wind) { this.seed(particle, width, height); continue; }
        const step = pxPerMs * mercatorStretch(at.lat, centreLatitude) * dt;
        const nx = x + wind.u * step, ny = y - wind.v * step;
        trail.push(nx, ny);
        if (trail.length > TRAIL_POINTS * 2) trail.splice(0, 2);
        if (particle.age > MAX_AGE_S || nx < 0 || ny < 0 || nx > width || ny > height) particle.dying = true;
      }
      // Segment k joins point k and k+1; its distance from the head picks
      // the opacity step, so the tail fades towards its end.
      const points = trail.length / 2;
      for (let k = 0; k < points - 1; k += 1) {
        const fromHead = points - 2 - k;
        const bucket = Math.min(TAIL_ALPHA.length - 1, Math.floor((fromHead * TAIL_ALPHA.length) / span));
        const path = paths[bucket];
        path.moveTo(trail[k * 2], trail[k * 2 + 1]);
        path.lineTo(trail[k * 2 + 2], trail[k * 2 + 3]);
      }
    }

    context.lineCap = "round";
    context.lineWidth = this.dark ? 1.05 : 1.2;
    context.strokeStyle = "#ffffff";
    const base = this.dark ? 0.8 : 0.92;
    for (let index = TAIL_ALPHA.length - 1; index >= 0; index -= 1) {
      context.globalAlpha = TAIL_ALPHA[index] * base;
      context.stroke(paths[index]);
    }
    context.globalAlpha = 1;
  };

  destroy() {
    cancelAnimationFrame(this.frame);
    this.map.off("move", this.onMove);
    this.canvas.remove();
  }
}
