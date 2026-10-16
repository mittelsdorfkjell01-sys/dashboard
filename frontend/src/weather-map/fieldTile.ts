export interface FieldTileHeader {
  schema: "swd-field-tile-v2";
  width: number;
  height: number;
  overlap: number;
  z: number;
  x: number;
  y: number;
  valid_time: string;
  variables: Array<{ name: string; scale: number; offset: number; nodata: number }>;
}

export interface DecodedFieldTile {
  key: string;
  header: FieldTileHeader;
  arrays: Record<string, Float32Array>;
}

export interface FieldSeriesEntry {
  validTime: string;
  payload: ArrayBuffer;
}

async function ungzip(payload: ArrayBuffer): Promise<ArrayBuffer> {
  if (!("DecompressionStream" in globalThis)) {
    throw new Error("Dieser Browser unterstützt die Windfeld-Dekomprimierung nicht.");
  }
  const stream = new Blob([payload]).stream().pipeThrough(new DecompressionStream("gzip"));
  return new Response(stream).arrayBuffer();
}

export async function decodeFieldTile(key: string, packed: ArrayBuffer): Promise<DecodedFieldTile> {
  const raw = await ungzip(packed);
  const bytes = new Uint8Array(raw);
  if (bytes.length < 8 || new TextDecoder().decode(bytes.slice(0, 4)) !== "SWF2") {
    throw new Error("Ungültiges Weather-Field-Tile.");
  }
  const view = new DataView(raw);
  const headerSize = view.getUint32(4, true);
  const headerEnd = 8 + headerSize;
  if (headerEnd > bytes.length) throw new Error("Unvollständiger Weather-Field-Header.");
  const header = JSON.parse(new TextDecoder().decode(bytes.slice(8, headerEnd))) as FieldTileHeader;
  if (header.schema !== "swd-field-tile-v2") throw new Error("Nicht unterstützte Field-Version.");
  const count = header.width * header.height;
  const arrays: Record<string, Float32Array> = {};
  let offset = headerEnd;
  for (const variable of header.variables) {
    if (offset + count * 2 > bytes.length) throw new Error("Unvollständige Weather-Field-Daten.");
    const stored = new Int16Array(raw.slice(offset, offset + count * 2));
    const values = new Float32Array(count);
    for (let index = 0; index < count; index += 1) {
      values[index] = stored[index] === variable.nodata
        ? Number.NaN
        : stored[index] * variable.scale + variable.offset;
    }
    arrays[variable.name] = values;
    offset += count * 2;
  }
  return { key, header, arrays };
}

export function decodeFieldSeries(packed: ArrayBuffer): FieldSeriesEntry[] {
  const bytes = new Uint8Array(packed);
  if (bytes.length < 8 || new TextDecoder().decode(bytes.slice(0, 4)) !== "SWS1") {
    throw new Error("Ungültige Forecast-Zeitreihe.");
  }
  const view = new DataView(packed);
  const headerSize = view.getUint32(4, true);
  const headerEnd = 8 + headerSize;
  if (headerEnd > bytes.length) throw new Error("Unvollständiger Zeitreihen-Header.");
  const header = JSON.parse(new TextDecoder().decode(bytes.slice(8, headerEnd))) as {
    schema: string;
    entries: Array<{ valid_time: string; offset: number; length: number }>;
  };
  if (header.schema !== "swd-field-series-v1" || !Array.isArray(header.entries)) {
    throw new Error("Nicht unterstützte Zeitreihen-Version.");
  }
  let previousEnd = 0;
  const entries = header.entries.map((entry) => {
    if (entry.offset !== previousEnd || entry.length <= 0 || headerEnd + entry.offset + entry.length > bytes.length) {
      throw new Error("Beschädigter Zeitreihen-Index.");
    }
    previousEnd = entry.offset + entry.length;
    return {
      validTime: entry.valid_time,
      payload: packed.slice(headerEnd + entry.offset, headerEnd + previousEnd),
    };
  });
  if (!entries.length || headerEnd + previousEnd !== bytes.length) {
    throw new Error("Zeitreihen-Daten stimmen nicht mit dem Index überein.");
  }
  return entries;
}
