import type { Map as MapLibreMap } from "maplibre-gl";
import type { DecodedFieldTile } from "../weather-map/fieldTile";
import { MS_TO_KN } from "./fieldSample";
import { waveAlpha, waveRgb, windAlpha, windRgb } from "./fieldColors";

/**
 * The public map's colour field (2026-11-20). Same WebGL approach as
 * weather-map/WindFieldLayer.ts — one premultiplied texture per tile, the
 * published overlap ring kept for the filter, one-cell holes repaired, a soft
 * fade at the edge of the model's domain — but painted with the map's own
 * continuous wind ramp and the intensity-weighted wave ramp, per theme.
 * The shared layer stays untouched for the embedded results map.
 *
 * Waves reach the coast exactly (2026-11-20, "die Färbung soll direkt an die
 * Küste dran gehen, jetzt ist das so gepixelt"): the model's sea cells are
 * grown a few cells inland, and the result is cut with a WATER MASK rendered
 * from the vector tiles — so the edge follows the real coastline instead of
 * the model's coarse land/sea staircase.
 */

export type FieldKind = "wind" | "waves";

function latitudeAt(y: number, zoom: number): number {
  return (Math.atan(Math.sinh(Math.PI * (1 - (2 * y) / 2 ** zoom))) * 180) / Math.PI;
}

const EDGE_FADE_RADIUS = 2;
const EDGE_FADE_MIN = 0.22;

function compile(gl: WebGLRenderingContext, kind: number, source: string) {
  const shader = gl.createShader(kind);
  if (!shader) throw new Error("WebGL shader could not be created.");
  gl.shaderSource(shader, source);
  gl.compileShader(shader);
  if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(shader) || "WebGL shader failed.");
  return shader;
}

function valueAt(kind: FieldKind, arrays: Record<string, Float32Array>, index: number): number | undefined {
  if (kind === "wind") {
    const u = arrays.wind_u?.[index], v = arrays.wind_v?.[index];
    return u === undefined || v === undefined ? undefined : Math.hypot(u, v) * MS_TO_KN;
  }
  return arrays.total_wave_height?.[index];
}

export class FieldLayer {
  readonly canvas = document.createElement("canvas");
  private readonly gl: WebGLRenderingContext;
  private readonly program: WebGLProgram;
  private readonly buffer: WebGLBuffer;
  private readonly textures = new Map<string, WebGLTexture>();
  private maskTexture: WebGLTexture | null = null;
  private dark = false;

  constructor(private readonly map: MapLibreMap) {
    this.canvas.className = "swd-pm-field";
    this.canvas.setAttribute("aria-hidden", "true");
    map.getContainer().appendChild(this.canvas);
    const gl = this.canvas.getContext("webgl", { alpha: true, antialias: false, premultipliedAlpha: true, preserveDrawingBuffer: true });
    if (!gl) throw new Error("WebGL ist auf diesem Gerät nicht verfügbar.");
    this.gl = gl;
    const program = gl.createProgram();
    const buffer = gl.createBuffer();
    if (!program || !buffer) throw new Error("WebGL-Ressourcen konnten nicht erstellt werden.");
    gl.attachShader(program, compile(gl, gl.VERTEX_SHADER, `
      attribute vec2 a_position; attribute vec2 a_texcoord; varying vec2 v_texcoord;
      void main(){ gl_Position=vec4(a_position,0.0,1.0); v_texcoord=a_texcoord; }
    `));
    gl.attachShader(program, compile(gl, gl.FRAGMENT_SHADER, `
      precision mediump float; varying vec2 v_texcoord;
      uniform sampler2D u_texture; uniform sampler2D u_mask; uniform float u_useMask; uniform vec2 u_viewport;
      void main(){
        vec4 colour = texture2D(u_texture, v_texcoord);
        float sea = u_useMask > 0.5 ? texture2D(u_mask, vec2(gl_FragCoord.x / u_viewport.x, 1.0 - gl_FragCoord.y / u_viewport.y)).r : 1.0;
        gl_FragColor = colour * sea;
      }
    `));
    gl.linkProgram(program);
    if (!gl.getProgramParameter(program, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(program) || "WebGL link failed.");
    this.program = program;
    this.buffer = buffer;
  }

  setDark(dark: boolean) { this.dark = dark; }

  private resize() {
    const ratio = Math.min(window.devicePixelRatio || 1, 2);
    const width = Math.max(1, Math.floor(this.map.getContainer().clientWidth * ratio));
    const height = Math.max(1, Math.floor(this.map.getContainer().clientHeight * ratio));
    if (this.canvas.width !== width || this.canvas.height !== height) { this.canvas.width = width; this.canvas.height = height; }
    this.gl.viewport(0, 0, width, height);
    return ratio;
  }

  private texture(tile: DecodedFieldTile, kind: FieldKind, masked: boolean): WebGLTexture {
    const key = `${tile.key}/${kind}/${this.dark ? "d" : "l"}${masked ? "/m" : ""}`;
    const existing = this.textures.get(key);
    if (existing) { this.textures.delete(key); this.textures.set(key, existing); return existing; }
    const gl = this.gl;
    const texture = gl.createTexture();
    if (!texture) throw new Error("Feld-Textur konnte nicht erstellt werden.");
    const { width, height } = tile.header;
    const published = (x: number, y: number) => {
      if (x < 0 || y < 0 || x >= width || y >= height) return undefined;
      const value = valueAt(kind, tile.arrays, y * width + x);
      return value !== undefined && Number.isFinite(value) ? value : undefined;
    };
    let values = new Float32Array(width * height);
    for (let y = 0; y < height; y += 1) for (let x = 0; x < width; x += 1) {
      const own = published(x, y);
      if (own !== undefined) { values[y * width + x] = own; continue; }
      const w = published(x - 1, y), e = published(x + 1, y), n = published(x, y - 1), s = published(x, y + 1);
      values[y * width + x] = w !== undefined && e !== undefined ? (w + e) / 2 : n !== undefined && s !== undefined ? (n + s) / 2 : Number.NaN;
    }
    // Masked (waves): grow the sea a few cells inland so there is colour right
    // up to the real coastline; the mask removes whatever lands on land.
    if (masked) {
      for (let pass = 0; pass < 4; pass += 1) {
        const next = values.slice();
        for (let y = 0; y < height; y += 1) for (let x = 0; x < width; x += 1) {
          if (Number.isFinite(values[y * width + x])) continue;
          let sum = 0, count = 0;
          for (const [dx, dy] of [[1, 0], [-1, 0], [0, 1], [0, -1], [1, 1], [-1, -1], [1, -1], [-1, 1]]) {
            const nx = x + dx, ny = y + dy;
            if (nx < 0 || ny < 0 || nx >= width || ny >= height) continue;
            const v = values[ny * width + nx];
            if (Number.isFinite(v)) { sum += v; count += 1; }
          }
          if (count) next[y * width + x] = sum / count;
        }
        values = next;
      }
    }
    const has = (x: number, y: number) => (x < 0 || y < 0 || x >= width || y >= height ? true : Number.isFinite(values[y * width + x]));
    const pixels = new Uint8Array(width * height * 4);
    for (let y = 0; y < height; y += 1) for (let x = 0; x < width; x += 1) {
      const value = values[y * width + x];
      if (!Number.isFinite(value)) continue;
      let covered = 0, weight = 0;
      if (masked) { covered = 1; weight = 1; } else for (let dy = -EDGE_FADE_RADIUS; dy <= EDGE_FADE_RADIUS; dy += 1) for (let dx = -EDGE_FADE_RADIUS; dx <= EDGE_FADE_RADIUS; dx += 1) {
        const wgt = 1 / (1 + Math.hypot(dx, dy));
        weight += wgt;
        if (has(x + dx, y + dy)) covered += wgt;
      }
      const color = kind === "wind" ? windRgb(value) : waveRgb(value);
      const alpha = Math.round((kind === "wind" ? windAlpha(value, this.dark) : waveAlpha(value, this.dark)) * Math.max(EDGE_FADE_MIN, covered / weight));
      const scale = alpha / 255, target = (y * width + x) * 4;
      pixels[target] = Math.round(color[0] * scale);
      pixels[target + 1] = Math.round(color[1] * scale);
      pixels[target + 2] = Math.round(color[2] * scale);
      pixels[target + 3] = alpha;
    }
    gl.bindTexture(gl.TEXTURE_2D, texture);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, width, height, 0, gl.RGBA, gl.UNSIGNED_BYTE, pixels);
    this.textures.set(key, texture);
    while (this.textures.size > 320) {
      const oldest = this.textures.keys().next().value as string | undefined;
      if (!oldest) break;
      const removed = this.textures.get(oldest);
      if (removed) gl.deleteTexture(removed);
      this.textures.delete(oldest);
    }
    return texture;
  }

  /** `mask`: a canvas, white where there is water — clips the field to it. */
  draw(tiles: DecodedFieldTile[], kind: FieldKind, mask?: HTMLCanvasElement | null) {
    const gl = this.gl;
    const ratio = this.resize();
    gl.clearColor(0, 0, 0, 0);
    gl.clear(gl.COLOR_BUFFER_BIT);
    if (!tiles.length) return;
    gl.enable(gl.BLEND);
    gl.blendFunc(gl.ONE, gl.ONE_MINUS_SRC_ALPHA);
    gl.useProgram(this.program);
    const masked = Boolean(mask && mask.width > 0);
    gl.uniform1f(gl.getUniformLocation(this.program, "u_useMask"), masked ? 1 : 0);
    gl.uniform2f(gl.getUniformLocation(this.program, "u_viewport"), this.canvas.width, this.canvas.height);
    gl.uniform1i(gl.getUniformLocation(this.program, "u_texture"), 0);
    gl.uniform1i(gl.getUniformLocation(this.program, "u_mask"), 1);
    if (masked && mask) {
      if (!this.maskTexture) this.maskTexture = gl.createTexture();
      gl.activeTexture(gl.TEXTURE1);
      gl.bindTexture(gl.TEXTURE_2D, this.maskTexture);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
      gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, mask);
      gl.activeTexture(gl.TEXTURE0);
    }
    gl.bindBuffer(gl.ARRAY_BUFFER, this.buffer);
    const position = gl.getAttribLocation(this.program, "a_position");
    const texcoord = gl.getAttribLocation(this.program, "a_texcoord");
    gl.enableVertexAttribArray(position);
    gl.enableVertexAttribArray(texcoord);
    for (const tile of tiles) {
      const n = 2 ** tile.header.z;
      const west = (tile.header.x / n) * 360 - 180, east = ((tile.header.x + 1) / n) * 360 - 180;
      const north = latitudeAt(tile.header.y, tile.header.z), south = latitudeAt(tile.header.y + 1, tile.header.z);
      const nw = this.map.project([west, north]), se = this.map.project([east, south]);
      const left = (nw.x * ratio / this.canvas.width) * 2 - 1, right = (se.x * ratio / this.canvas.width) * 2 - 1;
      const top = 1 - (nw.y * ratio / this.canvas.height) * 2, bottom = 1 - (se.y * ratio / this.canvas.height) * 2;
      const overlap = tile.header.overlap ?? 0;
      const u0 = overlap / tile.header.width, u1 = (tile.header.width - overlap) / tile.header.width;
      const v0 = overlap / tile.header.height, v1 = (tile.header.height - overlap) / tile.header.height;
      gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([
        left, top, u0, v0, right, top, u1, v0, left, bottom, u0, v1,
        left, bottom, u0, v1, right, top, u1, v0, right, bottom, u1, v1,
      ]), gl.STREAM_DRAW);
      gl.vertexAttribPointer(position, 2, gl.FLOAT, false, 16, 0);
      gl.vertexAttribPointer(texcoord, 2, gl.FLOAT, false, 16, 8);
      gl.bindTexture(gl.TEXTURE_2D, this.texture(tile, kind, masked));
      gl.drawArrays(gl.TRIANGLES, 0, 6);
    }
  }

  destroy() {
    this.canvas.remove();
    for (const texture of this.textures.values()) this.gl.deleteTexture(texture);
    this.textures.clear();
    if (this.maskTexture) this.gl.deleteTexture(this.maskTexture);
    this.gl.deleteBuffer(this.buffer);
    this.gl.deleteProgram(this.program);
  }
}
