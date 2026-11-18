import { describe, expect, it } from "vitest";
import { buildOption, isRenderable, specRows, type Tokens } from "./chartOptions";
import { formatDelta, formatValue } from "./format";
import { parseSSE } from "./sse";
import type { ChartSpec } from "./types";

const tk: Tokens = { dark: true, series: ["#1", "#2", "#3", "#4", "#5", "#6", "#7", "#8"], ink: "#fff", muted: "#999", grid: "#333", surface: "#000",
  seq: ["#a", "#b"], div: ["#c", "#d", "#e"] };
const base = (over: Partial<ChartSpec>): ChartSpec => ({
  schema_version: "flo.viz/1.0", chart_id: "c", chart_type: "line", title: "T", subtitle: "", metrics: [], categories: ["2026-08-31", "2026-09-30"],
  series: [{ name: "s", values: [1, 2], unit: "CAD", render: "auto", role: "primary" }], nodes: [], edges: [], x_labels: [], y_labels: [], cells: [],
  x_axis: { label: "", unit: "" }, y_axis: { label: "", unit: "" }, unit: "CAD", reference_lines: [], filters: {}, available_filters: [], drilldown: null,
  interactions: ["tooltip"], lineage: { sources: [], methodology: "", synthetic: true, tools: [] }, provenance: "platform_synthetic", agent: "a", note: "", ...over,
});

describe("chart option builder", () => {
  it("rejects specs outside the allowlisted schema", () => {
    expect(isRenderable(base({ chart_type: "custom" as any }))).toBe(false);
    expect(isRenderable(base({ schema_version: "flo.viz/9" }))).toBe(false);
    expect(() => buildOption(base({ chart_type: "eval" as any }), tk)).toThrow();
  });
  it("formats month categories and builds every cartesian type", () => {
    for (const t of ["line", "area", "stacked_area", "bar", "hbar", "stacked_bar", "grouped_bar", "combo", "tornado", "donut"] as const) {
      const o = buildOption(base({ chart_type: t }), tk)!;
      expect(o).toBeTruthy();
    }
    const o = buildOption(base({}), tk)!;
    expect(o.xAxis.data[0]).toMatch(/Aug/);
  });
  it("computes waterfall running totals with exact labels", () => {
    const o = buildOption(base({ chart_type: "waterfall", categories: ["open", "up", "down", "close"],
      series: [{ name: "w", values: [100, 30, -10, 120], unit: "CAD", render: "auto", role: "primary" }] }), tk)!;
    const [baseS, shown] = o.series;
    expect(baseS.data).toEqual([0, 100, 120, 0]);
    expect(shown.data.map((d: any) => d.value)).toEqual([100, 30, 10, 120]);
  });
  it("starts a bridge above zero only when steps would be illegible, and says so", () => {
    const o = buildOption(base({ chart_type: "waterfall", categories: ["a", "b", "c", "d"],
      series: [{ name: "w", values: [657.8e6, 72.3e6, -36.9e6, 690e6], unit: "CAD", render: "auto", role: "primary" }] }), tk)!;
    expect(o.yAxis.min).toBeGreaterThan(0);
    expect(o.yAxis.name).toContain("above zero");
  });
  it("builds heatmap, matrix, treemap, scatter and agent graph; HTML types return null", () => {
    expect(buildOption(base({ chart_type: "heatmap", categories: [], series: [], x_labels: ["1", "2"], y_labels: ["1"], cells: [[0, 0, 1], [1, 0, 3]] }), tk)!.series[0].type).toBe("heatmap");
    expect(buildOption(base({ chart_type: "matrix", categories: [], series: [], x_labels: ["a"], y_labels: ["a"], cells: [[0, 0, 1]] }), tk)!.visualMap.min).toBe(-1);
    const tm = buildOption(base({ chart_type: "treemap", categories: [], series: [], nodes: [{ id: "g", name: "G", meta: {} }, { id: "p", name: "P", parent: "g", value: 5, color_value: 0.2, meta: {} }] }), tk)!;
    expect(tm.series[0].data[0].children[0].value).toEqual([5, 0.2]);
    const sc = buildOption(base({ chart_type: "scatter", categories: [], series: [], nodes: [{ id: "a", name: "A", x: 1, y: 2, group: "g", meta: {} }] }), tk)!;
    expect(sc.series[0].data[0].value).toEqual([1, 2]);
    const g = buildOption(base({ chart_type: "agent_graph", categories: [], series: [], nodes: [{ id: "u", name: "U", meta: {} }, { id: "s", name: "S", status: "denied", meta: {} }],
      edges: [{ source: "u", target: "s", label: "" }] }), tk)!;
    expect(g.series[0].data[1].x).toBeGreaterThan(g.series[0].data[0].x);
    expect(buildOption(base({ chart_type: "scorecard", categories: [], series: [], nodes: [{ id: "a", name: "A", meta: {} }] }), tk)).toBeNull();
  });
  it("derives table rows from data only", () => {
    expect(specRows(base({}))).toEqual([{ category: "2026-08-31", s: 1 }, { category: "2026-09-30", s: 2 }]);
  });
});

describe("formatting", () => {
  it("formats contract units", () => {
    expect(formatValue(50.81e9, "CAD")).toBe("CAD 50.81bn");
    expect(formatValue(0.2785, "%")).toBe("27.9%");
    expect(formatValue(0.0308, "%")).toBe("3.08%");
    expect(formatValue(138.52, "bps")).toBe("138.5 bps");
    expect(formatValue(null, "CAD")).toBe("—");
    expect(formatDelta(-0.0284, "pp")).toBe("−2.84 pp");
    expect(formatDelta(0.0919, "%")).toBe("+9.19%");
  });
});

describe("SSE parser", () => {
  it("parses complete events across chunk boundaries and ignores keep-alives", () => {
    const a = parseSSE(": stream open\n\nevent: stage\ndata: {\"id\":\"understanding\"}\n\nevent: res");
    expect(a.events).toEqual([{ event: "stage", data: { id: "understanding" } }]);
    const b = parseSSE(a.rest + "ult\ndata: {\"ok\":true}\n\n");
    expect(b.events).toEqual([{ event: "result", data: { ok: true } }]);
    expect(b.rest).toBe("");
  });
});
