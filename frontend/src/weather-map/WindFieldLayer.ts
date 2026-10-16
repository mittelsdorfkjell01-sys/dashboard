import type { Map as MapLibreMap } from "maplibre-gl";
import type { DecodedFieldTile } from "./fieldTile";
import { layerColor, layerOpacity, layerValue } from "./fieldColor";
import type { FieldLayer } from "./contracts";

function latitudeAt(y: number, zoom: number): number {
  return (Math.atan(Math.sinh(Math.PI * (1 - (2 * y) / 2 ** zoom))) * 180) / Math.PI;
}

/** How far from the edge of the model's domain the fade reaches, in cells. */
const EDGE_FADE_RADIUS = 2;
/** However exposed a cell is, it never drops below this share of its opacity:
 *  a one-cell island is still data and has to stay visible. */
const EDGE_FADE_MIN = 0.22;

function compile(gl: WebGLRenderingContext, kind: number, source: string) {
  const shader = gl.createShader(kind);
  if (!shader) throw new Error("WebGL shader could not be created.");
  gl.shaderSource(shader, source);
  gl.compileShader(shader);
  if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(shader) || "WebGL shader failed.");
  return shader;
}

export class WindFieldLayer {
  readonly canvas = document.createElement("canvas");
  private readonly gl: WebGLRenderingContext;
  private readonly program: WebGLProgram;
  private readonly buffer: WebGLBuffer;
  private readonly textures = new Map<string, WebGLTexture>();

  constructor(private readonly map: MapLibreMap) {
    this.canvas.className = "swd-field-webgl";
    this.canvas.setAttribute("aria-hidden", "true");
    map.getContainer().appendChild(this.canvas);
    // The colour field is event-driven rather than redrawn every animation
    // frame. Mobile browsers may discard a non-preserved drawing buffer after
    // compositing it, which leaves the arrows visible over a grey ocean until
    // the next map movement. Keep the last completed field frame resident.
    const gl = this.canvas.getContext("webgl", {
      alpha: true,
      antialias: false,
      premultipliedAlpha: true,
      preserveDrawingBuffer: true,
    });
    if (!gl) throw new Error("WebGL ist auf diesem Gerät nicht verfügbar.");
    this.gl = gl;
    const program = gl.createProgram();
    const buffer = gl.createBuffer();
    if (!program || !buffer) throw new Error("WebGL-Ressourcen konnten nicht erstellt werden.");
    gl.attachShader(program, compile(gl, gl.VERTEX_SHADER, `
      attribute vec2 a_position;
      attribute vec2 a_texcoord;
      varying vec2 v_texcoord;
      void main(){ gl_Position=vec4(a_position,0.0,1.0); v_texcoord=a_texcoord; }
    `));
    // Plain hardware bilinear filtering. A smoothstepped sample position was
    // tried on 2026-10-12 to iron out the texel lattice; it also pushed the
    // sample toward the texel centre at the quad's own border, and where two
    // tiles meet that left a 3px transparent seam — the grey line that ran
    // north between Britain and Norway. The smoothness now comes from the
    // alpha feather in `texture()` instead, which cannot fall between quads.
    gl.attachShader(program, compile(gl, gl.FRAGMENT_SHADER, `
      precision mediump float;
      varying vec2 v_texcoord;
      uniform sampler2D u_texture;
      void main(){ gl_FragColor = texture2D(u_texture, v_texcoord); }
    `));
    gl.linkProgram(program);
    if (!gl.getProgramParameter(program, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(program) || "WebGL link failed.");
    this.program = program;
    this.buffer = buffer;
  }

  private resize() {
    const ratio = Math.min(window.devicePixelRatio || 1, 2);
    const width = Math.max(1, Math.floor(this.map.getContainer().clientWidth * ratio));
    const height = Math.max(1, Math.floor(this.map.getContainer().clientHeight * ratio));
    if (this.canvas.width !== width || this.canvas.height !== height) {
      this.canvas.width = width;
      this.canvas.height = height;
    }
    this.gl.viewport(0, 0, width, height);
    return ratio;
  }

  private texture(tile: DecodedFieldTile, layer: FieldLayer): WebGLTexture {
    const textureKey = `${tile.key}/${layer}`;
    const existing = this.textures.get(textureKey);
    if (existing) {
      this.textures.delete(textureKey);
      this.textures.set(textureKey, existing);
      return existing;
    }
    const gl = this.gl;
    const texture = gl.createTexture();
    if (!texture) throw new Error("Windfeld-Textur konnte nicht erstellt werden.");
    // The published overlap ring is kept in the texture (and excluded again by
    // the draw's texture coordinates). Without it, CLAMP_TO_EDGE flattens the
    // outermost half texel of every tile and the seam between two tiles shows
    // as a hairline band; with it, the filter has the neighbour's values to
    // interpolate against.
    const width = tile.header.width;
    const height = tile.header.height;
    const pixels = new Uint8Array(width * height * 4);
    const published = (x: number, y: number): number | undefined => {
      if (x < 0 || y < 0 || x >= width || y >= height) return undefined;
      const value = layerValue(layer, tile.arrays, y * width + x);
      return value !== undefined && Number.isFinite(value) ? value : undefined;
    };
    // ONE-CELL HOLES are repaired from their two neighbours on the same axis
    // (2026-10-12). A single missing cell with data on both sides is a defect
    // in the source, not a coastline: global wave grids repeat their wrap
    // column, and where that repeated column carries the GRIB's missing value
    // the published tiles hold a one-cell gap down the whole meridian — the
    // grey line that ran north between Britain and Norway. The generator no
    // longer produces it (`normalize_global_axes`), but runs published before
    // that still carry it. Filling exactly one cell between two known ones is
    // the same linear interpolation the renderer already applies between
    // cells; anything wider stays a hole.
    const values = new Float32Array(width * height);
    for (let y = 0; y < height; y += 1) {
      for (let x = 0; x < width; x += 1) {
        const own = published(x, y);
        if (own !== undefined) { values[y * width + x] = own; continue; }
        const west = published(x - 1, y), east = published(x + 1, y);
        const north = published(x, y - 1), south = published(x, y + 1);
        values[y * width + x] = west !== undefined && east !== undefined
          ? (west + east) / 2
          : north !== undefined && south !== undefined
            ? (north + south) / 2
            : Number.NaN;
      }
    }
    const has = (x: number, y: number) => {
      // Outside this tile is "unknown", never "no data": the neighbouring
      // tile carries those cells. Treating it as missing faded the outermost
      // ring of every tile and drew a faint cross-hatch of seams over the
      // whole field (2026-10-12).
      if (x < 0 || y < 0 || x >= width || y >= height) return true;
      return Number.isFinite(values[y * width + x]);
    };
    for (let y = 0; y < height; y += 1) {
      for (let x = 0; x < width; x += 1) {
        const source = y * width + x;
        const target = source * 4;
        const value = values[source];
        if (!Number.isFinite(value)) continue;
        const color = layerColor(layer, value);
        // EDGE FADE (2026-10-12). A wave model stops at its own coarse land
        // mask, so the field used to end in a cliff from fully opaque to
        // nothing within one cell — a staircase of squares along every coast
        // ("das muss ein komplett flüssiger Übergang geben"). Each cell is
        // attenuated by how much of its neighbourhood carries data, weighted
        // by distance: 1 deep inside the domain, and falling away over about
        // two cells towards the edge. That is a blur of the domain mask, so
        // the rectangular outline becomes a gradient that follows the coast.
        // Nothing is painted outside the model's domain — the published
        // values stay where they are, only our own boundary cells fade.
        let covered = 0;
        let weight = 0;
        for (let dy = -EDGE_FADE_RADIUS; dy <= EDGE_FADE_RADIUS; dy += 1) {
          for (let dx = -EDGE_FADE_RADIUS; dx <= EDGE_FADE_RADIUS; dx += 1) {
            const w = 1 / (1 + Math.hypot(dx, dy));
            weight += w;
            if (has(x + dx, y + dy)) covered += w;
          }
        }
        const edge = Math.max(EDGE_FADE_MIN, covered / weight);
        const alpha = Math.round(layerOpacity(layer, value) * edge);
        // PREMULTIPLIED. The texture is sampled with LINEAR filtering, so every
        // edge pixel is blended with its neighbours — and a cell without data
        // is transparent BLACK. Unpremultiplied, that blend drags the colour
        // toward black and draws a grey seam along every coastline and along
        // the edge of the model's domain (2026-10-11: "eine graue Linie über
        // Frankreich"). Premultiplied, the same blend fades out cleanly.
        const scale = alpha / 255;
        pixels[target] = Math.round(color[0] * scale);
        pixels[target + 1] = Math.round(color[1] * scale);
        pixels[target + 2] = Math.round(color[2] * scale);
        pixels[target + 3] = alpha;
      }
    }
    gl.bindTexture(gl.TEXTURE_2D, texture);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, width, height, 0, gl.RGBA, gl.UNSIGNED_BYTE, pixels);
    this.textures.set(textureKey, texture);
    while (this.textures.size > 320) {
      const oldest = this.textures.keys().next().value as string | undefined;
      if (!oldest) break;
      const removed = this.textures.get(oldest);
      if (removed) gl.deleteTexture(removed);
      this.textures.delete(oldest);
    }
    return texture;
  }

  draw(tiles: DecodedFieldTile[], layer: FieldLayer = "wind") {
    const gl = this.gl;
    const ratio = this.resize();
    gl.clearColor(0, 0, 0, 0);
    gl.clear(gl.COLOR_BUFFER_BIT);
    gl.enable(gl.BLEND);
    // Source is premultiplied (see `texture`), so it is added as it is.
    gl.blendFunc(gl.ONE, gl.ONE_MINUS_SRC_ALPHA);
    gl.useProgram(this.program);
    gl.bindBuffer(gl.ARRAY_BUFFER, this.buffer);
    const position = gl.getAttribLocation(this.program, "a_position");
    const texcoord = gl.getAttribLocation(this.program, "a_texcoord");
    gl.enableVertexAttribArray(position);
    gl.enableVertexAttribArray(texcoord);
    for (const tile of tiles) {
      const n = 2 ** tile.header.z;
      const west = (tile.header.x / n) * 360 - 180;
      const east = ((tile.header.x + 1) / n) * 360 - 180;
      const north = latitudeAt(tile.header.y, tile.header.z);
      const south = latitudeAt(tile.header.y + 1, tile.header.z);
      const nw = this.map.project([west, north]), se = this.map.project([east, south]);
      const left = (nw.x * ratio / this.canvas.width) * 2 - 1;
      const right = (se.x * ratio / this.canvas.width) * 2 - 1;
      const top = 1 - (nw.y * ratio / this.canvas.height) * 2;
      const bottom = 1 - (se.y * ratio / this.canvas.height) * 2;
      // Texture coordinates skip the overlap ring: the quad still shows
      // exactly the tile's own extent, the ring only feeds the filter.
      const overlap = tile.header.overlap ?? 0;
      const u0 = overlap / tile.header.width;
      const u1 = (tile.header.width - overlap) / tile.header.width;
      const v0 = overlap / tile.header.height;
      const v1 = (tile.header.height - overlap) / tile.header.height;
      const vertices = new Float32Array([
        left, top, u0, v0, right, top, u1, v0, left, bottom, u0, v1,
        left, bottom, u0, v1, right, top, u1, v0, right, bottom, u1, v1,
      ]);
      gl.bufferData(gl.ARRAY_BUFFER, vertices, gl.STREAM_DRAW);
      gl.vertexAttribPointer(position, 2, gl.FLOAT, false, 16, 0);
      gl.vertexAttribPointer(texcoord, 2, gl.FLOAT, false, 16, 8);
      gl.bindTexture(gl.TEXTURE_2D, this.texture(tile, layer));
      gl.drawArrays(gl.TRIANGLES, 0, 6);
    }
  }

  destroy() {
    this.canvas.remove();
    for (const texture of this.textures.values()) this.gl.deleteTexture(texture);
    this.textures.clear();
    this.gl.deleteBuffer(this.buffer);
    this.gl.deleteProgram(this.program);
  }
}
