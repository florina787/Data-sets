import { describe, expect, it } from "vitest";
import { toCsv } from "@/lib/csv";
import { formatValue, pct, score } from "@/lib/format";

describe("format", () => {
  it("formats percent, sentiment and missing values", () => {
    expect(pct(0.3504)).toBe("35.0%");
    expect(score(1)).toBe("+1.00");
    expect(formatValue(-0.6, "sentiment")).toBe("-0.60");
    expect(formatValue(null)).toBe("—");
    expect(formatValue(3000, "count")).toBe("3,000");
  });
});

describe("csv export", () => {
  it("quotes and neutralises spreadsheet formulas", () => {
    const out = toCsv([{ a: "=HYPERLINK(\"x\")", b: "plain, text", c: 1 }, { a: "+1", b: null, c: "@SUM" }]);
    const lines = out.split("\n");
    expect(lines[0]).toBe("a,b,c");
    expect(lines[1].startsWith("\"'=HYPERLINK")).toBe(true);
    expect(lines[1]).toContain("\"plain, text\"");
    expect(lines[2]).toBe("'+1,,'@SUM");
  });
});
