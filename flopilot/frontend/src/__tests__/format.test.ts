import { describe, expect, it } from "vitest";
import {
  blocksFor, colIndex, colLetter, formatWithNumberFormat, inlineSegments, niceTicks, parseRange, selectionStats, visibleRows,
} from "../lib/format";

describe("cell addressing", () => {
  it("converts column letters both ways", () => {
    expect([1, 26, 27, 52, 703].map(colLetter)).toEqual(["A", "Z", "AA", "AZ", "AAA"]);
    expect(["A", "Z", "AA", "AZ", "AAA"].map(colIndex)).toEqual([1, 26, 27, 52, 703]);
  });
  it("parses ranges with absolute markers and reversed corners", () => {
    expect(parseRange("$B$3:A1")).toEqual({ c0: 1, r0: 1, c1: 2, r1: 3 });
    expect(parseRange("K2:K121")).toEqual({ c0: 11, r0: 2, c1: 11, r1: 121 });
    expect(parseRange("nonsense")).toBeNull();
  });
});

describe("virtualization math", () => {
  it("computes the visible window with overscan and clamps to the sheet", () => {
    expect(visibleRows(0, 220, 22, 1000, 2)).toEqual({ first: 1, last: 12 });
    expect(visibleRows(2200, 220, 22, 1000, 2)).toEqual({ first: 99, last: 112 });
    expect(visibleRows(100000, 220, 22, 50, 2).last).toBe(50);
  });
  it("maps rows to fetch blocks", () => {
    expect(blocksFor(1, 100, 100)).toEqual([0]);
    expect(blocksFor(95, 210, 100)).toEqual([0, 1, 2]);
  });
});

describe("status bar statistics", () => {
  it("counts non-empty cells and sums only numbers", () => {
    const s = selectionStats([1, 2, "x", null, "", 3.5, undefined]);
    expect(s).toEqual({ count: 4, numericCount: 3, sum: 6.5, average: 6.5 / 3 });
  });
});

describe("number formats for previews", () => {
  it("formats percent, currency and plain numbers like Excel", () => {
    expect(formatWithNumberFormat(0.2842105, "0.0%")).toBe("28.4%");
    expect(formatWithNumberFormat(1234.5, '"$"#,##0.00')).toBe("$1,234.50");
    expect(formatWithNumberFormat(-50, "#,##0")).toBe("-50");
    expect(formatWithNumberFormat(0.45, null)).toBe("0.45");
    expect(formatWithNumberFormat("", "0.0%")).toBe("");
  });
});

describe("safe rich text", () => {
  it("splits bold and code without producing HTML", () => {
    expect(inlineSegments("Total **$5** via `=SUM(A1:A3)` <img src=x>")).toEqual([
      { kind: "text", text: "Total " }, { kind: "bold", text: "$5" }, { kind: "text", text: " via " },
      { kind: "code", text: "=SUM(A1:A3)" }, { kind: "text", text: " <img src=x>" },
    ]);
  });
});

describe("chart ticks", () => {
  it("produces round tick values covering the range", () => {
    const t = niceTicks(0, 390624.5, 4);
    expect(t[0]).toBe(0);
    expect(t[t.length - 1]).toBeGreaterThanOrEqual(390624.5);
    expect(t.every((v) => v % 50000 === 0)).toBe(true);
  });
});
