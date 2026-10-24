// Enforces the design rule: only white, ivory, cream and brown colours anywhere in the UI.
import fs from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

const APPROVED = new Set(["#ffffff", "#fcfaf7", "#f7f1e9", "#efe2d2", "#d6b79b", "#b87848", "#99613e", "#75462d", "#4a2c1c", "#2c1a12"]);
// Code-block syntax colours: lighter tints of the same ginger/caramel hues on espresso.
const CODE_TINTS = new Set(["#b39478", "#e7b98c", "#f0c9a0", "#e9d5bf"]);
const FORBIDDEN_UTILS = /\b(?:bg|text|border|ring|fill|stroke|from|to|via|outline|decoration|accent|shadow)-(?:slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose|black)(?:-\d+)?\b/;

function files(dir: string): string[] {
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap((e) => {
    const p = path.join(dir, e.name);
    if (e.isDirectory()) return e.name === "test" ? [] : files(p);
    return /\.(tsx?|css|mjs)$/.test(e.name) ? [p] : [];
  });
}

const src = path.resolve(__dirname, "..");

describe("design system palette", () => {
  it("uses only approved hex colours", () => {
    const offenders: string[] = [];
    for (const f of files(src)) {
      const text = fs.readFileSync(f, "utf8");
      for (const m of text.matchAll(/#[0-9a-fA-F]{6}\b/g)) {
        const hex = m[0].toLowerCase();
        if (!APPROVED.has(hex) && !(f.endsWith("index.css") && CODE_TINTS.has(hex))) offenders.push(`${path.relative(src, f)}: ${m[0]}`);
      }
    }
    expect(offenders).toEqual([]);
  });

  it("never uses Tailwind's default (non-brown) colour utilities", () => {
    const offenders = files(src).filter((f) => FORBIDDEN_UTILS.test(fs.readFileSync(f, "utf8"))).map((f) => path.relative(src, f));
    expect(offenders).toEqual([]);
  });

  it("removes the default Tailwind palette in the theme", () => {
    expect(fs.readFileSync(path.join(src, "styles/index.css"), "utf8")).toContain("--color-*: initial;");
  });
});
