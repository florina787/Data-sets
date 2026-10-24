import { describe, expect, it } from "vitest";
import { readNdjson } from "../services/api";
import { encodeFrame } from "../services/audio";
import { hamming, hashFromRGBA } from "../services/screen";

function streamOf(chunks: string[]): ReadableStream<Uint8Array> {
  const enc = new TextEncoder();
  return new ReadableStream({
    start(c) {
      chunks.forEach((x) => c.enqueue(enc.encode(x)));
      c.close();
    },
  });
}

describe("readNdjson", () => {
  it("reassembles events split across network chunks", async () => {
    const out = [];
    for await (const ev of readNdjson<{ type: string; t?: string }>(streamOf(['{"type":"meta"}\n{"type":"tok', 'en","t":"Hel"}\n', '{"type":"done"}']))) out.push(ev);
    expect(out).toEqual([{ type: "meta" }, { type: "token", t: "Hel" }, { type: "done" }]);
  });
});

describe("encodeFrame", () => {
  it("writes a float64 timestamp header and clipped int16 PCM", () => {
    const buf = encodeFrame(1234.5, new Float32Array([0, 1, -1, 2, -2, 0.5]));
    const v = new DataView(buf);
    expect(buf.byteLength).toBe(8 + 6 * 2);
    expect(v.getFloat64(0, true)).toBe(1234.5);
    const pcm = Array.from({ length: 6 }, (_, i) => v.getInt16(8 + i * 2, true));
    expect(pcm).toEqual([0, 32767, -32768, 32767, -32768, 16383]);
  });
});

describe("frame hashing", () => {
  it("is stable for identical frames and differs for changed ones", () => {
    const w = 17, h = 16;
    const a = new Uint8ClampedArray(w * h * 4);
    for (let i = 0; i < w * h; i++) a.set([(i * 13) % 256, (i * 7) % 256, (i * 3) % 256, 255], i * 4);
    const b = new Uint8ClampedArray(a);
    const c = new Uint8ClampedArray(a).reverse();
    expect(hamming(hashFromRGBA(a, w, h), hashFromRGBA(b, w, h))).toBe(0);
    expect(hamming(hashFromRGBA(a, w, h), hashFromRGBA(c, w, h))).toBeGreaterThan(12);
  });
});
