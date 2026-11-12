import { describe, expect, it } from "vitest";
import { describeSources, isBlankBitmap, type RawSource } from "../../electron/sources";

const px = (w: number, h: number, f: (i: number) => [number, number, number, number]) => {
  const a = new Uint8Array(w * h * 4);
  for (let i = 0; i < w * h; i++) a.set(f(i), i * 4);
  return a;
};
const black = px(36, 22, () => [0, 0, 0, 255]);
const transparent = px(36, 22, () => [0, 0, 0, 0]);
const picture = px(36, 22, (i) => [(i * 7) % 255, (i * 13) % 255, (i * 3) % 255, 255]);
const src = (id: string, name: string, bitmap: Uint8Array | null, display_id?: string): RawSource => ({ id, name, display_id, thumbnailEmpty: bitmap === null, bitmap });
const displays = [
  { id: 1, width: 1280, height: 720, scaleFactor: 2, primary: true },
  { id: 2, width: 1920, height: 1080, scaleFactor: 1, primary: false },
];

describe("screen source picker", () => {
  it("detects blank thumbnails", () => {
    expect(isBlankBitmap(black)).toBe(true);
    expect(isBlankBitmap(transparent)).toBe(true);
    expect(isBlankBitmap(null)).toBe(true);
    expect(isBlankBitmap(picture)).toBe(false);
  });

  it("names real displays with physical resolution and primary flag", () => {
    const out = describeSources([src("screen:1:0", "Screen 1", picture, "1"), src("screen:2:0", "Screen 2", picture, "2")], displays, [], "win32");
    expect(out.map((s) => s.name)).toEqual(["Display 1 · 2560×1440 (primary)", "Display 2 · 1920×1080"]);
    expect(out.every((s) => s.kind === "screen" && s.previewable)).toBe(true);
  });

  it("marks minimized/protected windows unshareable instead of showing blank tiles", () => {
    const raw = [
      src("screen:1:0", "Entire screen", picture, "1"),
      src("window:10:0", "Report.docx - Word", picture),
      src("window:11:0", "Microsoft Text Input Application", null),
      src("window:12:0", "Minimized Notes", black),
      src("window:13:0", "", picture),
      src("window:14:0", "VEENA.AI", picture),
    ];
    const out = describeSources(raw, displays.slice(0, 1), ["VEENA.AI"], "win32");
    expect(out.map((s) => [s.name, s.previewable])).toEqual([
      ["Display 1 · 2560×1440 (primary)", true],
      ["Report.docx - Word", true],
      ["Microsoft Text Input Application", false],
      ["Minimized Notes", false],
    ]);
    expect(out[2].note).toMatch(/minimized, on another desktop, or protected/);
  });

  it("explains blank screens on macOS as a permission problem", () => {
    const out = describeSources([src("screen:1:0", "Built-in Retina Display", black, "1")], displays.slice(0, 1), [], "darwin");
    expect(out[0].previewable).toBe(false);
    expect(out[0].note).toMatch(/Screen Recording/);
  });
});
