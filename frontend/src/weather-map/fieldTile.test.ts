import { describe, expect, it } from "vitest";
import { decodeFieldSeries } from "./fieldTile";

function series(entries: Array<[string, Uint8Array]>): ArrayBuffer {
  let offset = 0;
  const index = entries.map(([validTime, payload]) => {
    const item = { valid_time: validTime, offset, length: payload.length };
    offset += payload.length;
    return item;
  });
  const header = new TextEncoder().encode(JSON.stringify({ schema: "swd-field-series-v1", entries: index }));
  const output = new Uint8Array(8 + header.length + offset);
  output.set(new TextEncoder().encode("SWS1"), 0);
  new DataView(output.buffer).setUint32(4, header.length, true);
  output.set(header, 8);
  let cursor = 8 + header.length;
  for (const [, payload] of entries) {
    output.set(payload, cursor);
    cursor += payload.length;
  }
  return output.buffer;
}

describe("field series codec", () => {
  it("returns the immutable time-tile slices", () => {
    const decoded = decodeFieldSeries(series([
      ["20261011T00Z", new Uint8Array([1, 2])],
      ["20261011T03Z", new Uint8Array([3])],
    ]));

    expect(decoded.map((entry) => entry.validTime)).toEqual(["20261011T00Z", "20261011T03Z"]);
    expect([...new Uint8Array(decoded[0].payload)]).toEqual([1, 2]);
    expect([...new Uint8Array(decoded[1].payload)]).toEqual([3]);
  });

  it("rejects a truncated container", () => {
    const valid = series([["20261011T00Z", new Uint8Array([1, 2])]]);
    expect(() => decodeFieldSeries(valid.slice(0, -1))).toThrow(/Index|stimmen/);
  });
});
