import type { Map as MapLibreMap } from "maplibre-gl";
import type { DecodedFieldTile } from "./fieldTile";

const PRESSURE_INTERVAL_HPA = 4;
const MIN_PRESSURE_HPA = 850;
const MAX_PRESSURE_HPA = 1100;

type Point = readonly [number, number];

export interface PressureContourSegment {
  level: number;
  start: Point;
  end: Point;
}

function interpolate(level: number, first: number, second: number): number {
  if (first === second) return 0.5;
  return Math.max(0, Math.min(1, (level - first) / (second - first)));
}

function cellSegments(
  level: number,
  topLeft: number,
  topRight: number,
  bottomRight: number,
  bottomLeft: number,
): Array<readonly [Point, Point]> {
  const crossings: Array<{ edge: number; point: Point }> = [];
  const add = (edge: number, first: number, second: number, point: (ratio: number) => Point) => {
    if ((first >= level) === (second >= level)) return;
    crossings.push({ edge, point: point(interpolate(level, first, second)) });
  };
  add(0, topLeft, topRight, (ratio) => [ratio, 0]);
  add(1, topRight, bottomRight, (ratio) => [1, ratio]);
  add(2, bottomRight, bottomLeft, (ratio) => [1 - ratio, 1]);
  add(3, bottomLeft, topLeft, (ratio) => [0, 1 - ratio]);
  if (crossings.length === 2) return [[crossings[0].point, crossings[1].point]];
  if (crossings.length !== 4) return [];

  const byEdge = new Map(crossings.map((crossing) => [crossing.edge, crossing.point]));
  const centerHigh = (topLeft + topRight + bottomRight + bottomLeft) / 4 >= level;
  const mask = (topLeft >= level ? 8 : 0)
    | (topRight >= level ? 4 : 0)
    | (bottomRight >= level ? 2 : 0)
    | (bottomLeft >= level ? 1 : 0);
  const pairs = mask === 10
    ? centerHigh ? [[0, 3], [1, 2]] : [[0, 1], [2, 3]]
    : centerHigh ? [[0, 1], [2, 3]] : [[0, 3], [1, 2]];
  return pairs.map(([first, second]) => [byEdge.get(first)!, byEdge.get(second)!]);
}

function smoothPressure(values: Float32Array, width: number, height: number): Float32Array {
  if (width < 5 || height < 5) return values;
  const smoothed = new Float32Array(values.length);
  const kernel = [1, 2, 1];
  for (let y = 0; y < height; y += 1) {
    for (let x = 0; x < width; x += 1) {
      let weighted = 0;
      let weightSum = 0;
      for (let offsetY = -1; offsetY <= 1; offsetY += 1) {
        const sourceY = y + offsetY;
        if (sourceY < 0 || sourceY >= height) continue;
        for (let offsetX = -1; offsetX <= 1; offsetX += 1) {
          const sourceX = x + offsetX;
          if (sourceX < 0 || sourceX >= width) continue;
          const value = values[sourceY * width + sourceX];
          if (!Number.isFinite(value)) continue;
          const weight = kernel[offsetY + 1] * kernel[offsetX + 1];
          weighted += value * weight;
          weightSum += weight;
        }
      }
      smoothed[y * width + x] = weightSum ? weighted / weightSum : Number.NaN;
    }
  }
  return smoothed;
}

export function pressureContourSegments(tile: DecodedFieldTile): PressureContourSegment[] {
  const rawPressure = tile.arrays.pressure_msl;
  if (!rawPressure) return [];
  const { width, height } = tile.header;
  const pressure = smoothPressure(rawPressure, width, height);
  const overlap = tile.header.overlap ?? 0;
  const innerWidth = width - overlap * 2;
  const innerHeight = height - overlap * 2;
  if (innerWidth < 2 || innerHeight < 2) return [];
  const segments: PressureContourSegment[] = [];
  const firstX = Math.max(0, overlap - 1);
  const firstY = Math.max(0, overlap - 1);
  const lastX = Math.min(width - 2, overlap + innerWidth - 1);
  const lastY = Math.min(height - 2, overlap + innerHeight - 1);

  for (let y = firstY; y <= lastY; y += 1) {
    for (let x = firstX; x <= lastX; x += 1) {
      const topLeft = pressure[y * width + x];
      const topRight = pressure[y * width + x + 1];
      const bottomRight = pressure[(y + 1) * width + x + 1];
      const bottomLeft = pressure[(y + 1) * width + x];
      const values = [topLeft, topRight, bottomRight, bottomLeft];
      if (!values.every(Number.isFinite)) continue;
      const minimum = Math.max(MIN_PRESSURE_HPA, Math.min(...values));
      const maximum = Math.min(MAX_PRESSURE_HPA, Math.max(...values));
      for (
        let level = Math.ceil(minimum / PRESSURE_INTERVAL_HPA) * PRESSURE_INTERVAL_HPA;
        level <= maximum;
        level += PRESSURE_INTERVAL_HPA
      ) {
        for (const [start, end] of cellSegments(level, topLeft, topRight, bottomRight, bottomLeft)) {
          if (Math.hypot(start[0] - end[0], start[1] - end[1]) < 0.001) continue;
          const normalize = ([localX, localY]: Point): Point => [
            (x + localX - overlap + 0.5) / innerWidth,
            (y + localY - overlap + 0.5) / innerHeight,
          ];
          segments.push({ level, start: normalize(start), end: normalize(end) });
        }
      }
    }
  }
  return segments;
}

function latitudeAt(worldY: number, zoom: number): number {
  return (Math.atan(Math.sinh(Math.PI * (1 - (2 * worldY) / 2 ** zoom))) * 180) / Math.PI;
}

export class PressureContourLayer {
  readonly canvas = document.createElement("canvas");
  private readonly context: CanvasRenderingContext2D;
  private readonly cache = new Map<string, PressureContourSegment[]>();

  constructor(private readonly map: MapLibreMap) {
    this.canvas.className = "swd-field-contours";
    this.canvas.setAttribute("aria-hidden", "true");
    map.getContainer().appendChild(this.canvas);
    const context = this.canvas.getContext("2d");
    if (!context) throw new Error("Isobaren sind auf diesem Gerät nicht verfügbar.");
    this.context = context;
  }

  private resize() {
    const ratio = Math.min(window.devicePixelRatio || 1, 2);
    const width = this.map.getContainer().clientWidth;
    const height = this.map.getContainer().clientHeight;
    if (this.canvas.width !== Math.floor(width * ratio) || this.canvas.height !== Math.floor(height * ratio)) {
      this.canvas.width = Math.floor(width * ratio);
      this.canvas.height = Math.floor(height * ratio);
      this.context.setTransform(ratio, 0, 0, ratio, 0, 0);
    }
    return { width, height };
  }

  private tileSegments(tile: DecodedFieldTile): PressureContourSegment[] {
    const existing = this.cache.get(tile.key);
    if (existing) return existing;
    const segments = pressureContourSegments(tile);
    this.cache.set(tile.key, segments);
    while (this.cache.size > 320) {
      const oldest = this.cache.keys().next().value as string | undefined;
      if (!oldest) break;
      this.cache.delete(oldest);
    }
    return segments;
  }

  draw(tiles: DecodedFieldTile[], visible: boolean) {
    const { width, height } = this.resize();
    const context = this.context;
    context.clearRect(0, 0, width, height);
    if (!visible) return;

    const projected = new Map<number, Array<readonly [Point, Point]>>();
    for (const tile of tiles) {
      const zoom = tile.header.z;
      const scale = 2 ** zoom;
      const project = ([x, y]: Point): Point => {
        const worldX = tile.header.x + x;
        const worldY = tile.header.y + y;
        const screen = this.map.project([
          (worldX / scale) * 360 - 180,
          latitudeAt(worldY, zoom),
        ]);
        return [screen.x, screen.y];
      };
      for (const segment of this.tileSegments(tile)) {
        const start = project(segment.start);
        const end = project(segment.end);
        if ((start[0] < -10 && end[0] < -10) || (start[1] < -10 && end[1] < -10)
          || (start[0] > width + 10 && end[0] > width + 10) || (start[1] > height + 10 && end[1] > height + 10)) continue;
        const levelSegments = projected.get(segment.level) ?? [];
        levelSegments.push([start, end]);
        projected.set(segment.level, levelSegments);
      }
    }

    context.lineCap = "round";
    context.lineJoin = "round";
    for (const [level, segments] of projected) {
      context.beginPath();
      for (const [start, end] of segments) {
        context.moveTo(start[0], start[1]);
        context.lineTo(end[0], end[1]);
      }
      context.strokeStyle = "rgba(12, 35, 41, .56)";
      context.lineWidth = level % 8 === 0 ? 3.5 : 3;
      context.stroke();
      context.strokeStyle = level % 8 === 0 ? "rgba(255, 255, 255, .88)" : "rgba(255, 255, 255, .68)";
      context.lineWidth = level % 8 === 0 ? 1.35 : 1;
      context.stroke();
    }

    context.font = "700 11px system-ui, sans-serif";
    context.textAlign = "center";
    context.textBaseline = "middle";
    const labels: Point[] = [];
    for (const [level, segments] of [...projected].sort(([first], [second]) => first - second)) {
      if (level % 8 !== 0) continue;
      const candidate = segments.find(([start, end]) => {
        const x = (start[0] + end[0]) / 2;
        const y = (start[1] + end[1]) / 2;
        return x > 90 && x < width - 90 && y > 96 && y < height - 170
          && labels.every(([labelX, labelY]) => Math.hypot(x - labelX, y - labelY) > 76);
      });
      if (!candidate) continue;
      const x = (candidate[0][0] + candidate[1][0]) / 2;
      const y = (candidate[0][1] + candidate[1][1]) / 2;
      labels.push([x, y]);
      context.lineWidth = 3.5;
      context.strokeStyle = "rgba(12, 35, 41, .9)";
      context.strokeText(String(level), x, y);
      context.fillStyle = "rgba(255, 255, 255, .96)";
      context.fillText(String(level), x, y);
    }
  }

  destroy() {
    this.canvas.remove();
    this.cache.clear();
  }
}
