// Turns a validated `flo.viz/1.0` chart spec into an ECharts option. Pure data mapping: the spec carries data and a
// declared, allowlisted type; nothing from the server is ever evaluated as code. Unknown types are rejected.
import { CHART_TYPES, VIZ_SCHEMA_VERSION, type ChartSpec, type Series } from "./types";
import { categoryLabel, formatValue } from "./format";

export type Tokens = { dark: boolean; series: string[]; ink: string; muted: string; grid: string; surface: string; seq: string[]; div: string[] };
const STATUS_COLOR = { ok: "#10B981", warn: "#F59E0B", crit: "#EF4444", neutral: "#64748b", denied: "#EF4444", skipped: "#64748b" } as const;
const HTML_TYPES = new Set(["scorecard", "geo"]);

export function isRenderable(spec: Partial<ChartSpec> | null | undefined): spec is ChartSpec {
  return !!spec && spec.schema_version === VIZ_SCHEMA_VERSION && (CHART_TYPES as readonly string[]).includes(spec.chart_type as string)
    && typeof spec.chart_id === "string" && typeof spec.title === "string";
}

const fmt = (unit: string) => (v: number) => formatValue(v, unit);
const axisFmt = (unit: string) => (v: number) => (unit === "%" ? `${Math.round(v * 1000) / 10}%` : unit === "CAD" ? formatValue(v, "CAD").replace("CAD ", "") : unit === "bps" ? `${v}` : formatValue(v, unit));

function base(tk: Tokens, animate: boolean) {
  return {
    animation: animate, animationDuration: 600, animationEasing: "cubicOut" as const,
    aria: { enabled: true, decal: { show: false } }, color: tk.series,
    textStyle: { color: tk.muted, fontFamily: "Inter, system-ui, sans-serif" },
    grid: { left: 12, right: 18, top: 40, bottom: 24, containLabel: true },
    tooltip: { backgroundColor: tk.surface, borderColor: tk.grid, textStyle: { color: tk.ink }, confine: true },
    legend: { textStyle: { color: tk.muted }, top: 0, icon: "roundRect", itemWidth: 10, itemHeight: 10, type: "scroll" as const },
  };
}

const axis = (tk: Tokens, extra: object = {}) => ({ axisLine: { lineStyle: { color: tk.grid } }, axisLabel: { color: tk.muted, hideOverlap: true },
  splitLine: { lineStyle: { color: tk.grid } }, axisTick: { show: false }, ...extra });

function refLines(spec: ChartSpec, tk: Tokens, axisKey: "yAxis" | "xAxis" = "yAxis") {
  const data = spec.reference_lines.flatMap((r) => (r.type === "average" ? [{ type: "average", name: String(r.label) }]
    : typeof r.value === "number" && (r.axis ?? (axisKey === "xAxis" ? "x" : "y")) === (axisKey === "xAxis" ? "x" : "y") ? [{ [axisKey]: r.value, name: String(r.label) }] : []));
  return data.length ? { markLine: { silent: true, symbol: "none", lineStyle: { color: tk.muted, type: "dashed" }, data,
    label: { color: tk.muted, position: "insideEndTop", formatter: (p: any) => `${p.name} ${formatValue(p.value, spec.unit)}` } } } : {};
}

function seriesColor(s: Series, i: number, tk: Tokens) {
  if (s.role === "baseline") return tk.muted;
  return tk.series[i % tk.series.length];
}

export function buildOption(spec: ChartSpec, tk: Tokens, animate = true): Record<string, any> | null {
  if (!isRenderable(spec)) throw new Error(`unsupported chart spec: ${String((spec as any)?.chart_type)}`);
  if (HTML_TYPES.has(spec.chart_type)) return null;
  const b = base(tk, animate);
  const cats = spec.categories.map(categoryLabel);
  const u = spec.unit;
  const tip = { ...b.tooltip, trigger: "axis" as const, valueFormatter: fmt(u) };
  switch (spec.chart_type) {
    case "line":
    case "area":
    case "stacked_area":
      return { ...b, tooltip: tip, xAxis: axis(tk, { type: "category", data: cats, boundaryGap: false }),
        yAxis: axis(tk, { type: "value", scale: u !== "CAD", axisLabel: { color: tk.muted, formatter: axisFmt(u) } }),
        series: spec.series.map((s, i) => ({ name: s.name, type: "line", data: s.values, symbol: "none", smooth: false,
          stack: spec.chart_type === "stacked_area" ? "total" : undefined, lineStyle: { width: 2, type: s.role === "baseline" ? "dashed" : "solid", color: seriesColor(s, i, tk) },
          itemStyle: { color: seriesColor(s, i, tk) }, areaStyle: spec.chart_type === "line" ? undefined : { opacity: spec.chart_type === "stacked_area" ? 0.5 : 0.18 },
          emphasis: { focus: "series" }, ...(i === 0 ? refLines(spec, tk) : {}) })) };
    case "bar":
    case "stacked_bar":
    case "grouped_bar":
    case "combo":
      return { ...b, tooltip: tip, xAxis: axis(tk, { type: "category", data: cats, axisLabel: { color: tk.muted, hideOverlap: true, rotate: cats.length > 8 && cats[0].length > 6 ? 30 : 0 } }),
        yAxis: axis(tk, { type: "value", axisLabel: { color: tk.muted, formatter: axisFmt(u) } }),
        series: spec.series.map((s, i) => {
          const line = s.render === "line" || (spec.chart_type === "combo" && s.render === "auto" && i === spec.series.length - 1 && spec.series.length > 1);
          return { name: s.name, type: line ? "line" : "bar", data: s.values, barMaxWidth: 36,
            stack: line ? undefined : spec.chart_type === "stacked_bar" || (spec.chart_type === "combo" && s.stack) ? s.stack ?? "total" : undefined,
            symbolSize: 6, lineStyle: line ? { width: 2, color: tk.ink } : undefined, itemStyle: { color: line ? tk.ink : seriesColor(s, i, tk), borderRadius: line ? 0 : 3 },
            emphasis: { focus: "series" }, ...(i === 0 ? refLines(spec, tk) : {}) };
        }) };
    case "hbar":
      return { ...b, tooltip: tip, grid: { ...b.grid, left: 8 },
        yAxis: axis(tk, { type: "category", data: cats, inverse: true, axisLabel: { color: tk.muted, width: 150, overflow: "truncate" } }),
        xAxis: axis(tk, { type: "value", axisLabel: { color: tk.muted, formatter: axisFmt(u) } }),
        series: spec.series.map((s, i) => ({ name: s.name, type: "bar", data: s.values, barMaxWidth: 16, itemStyle: { color: seriesColor(s, i, tk), borderRadius: 3 },
          ...(i === 0 ? refLines(spec, tk, "xAxis") : {}) })) };
    case "tornado":
      return { ...b, tooltip: tip, yAxis: axis(tk, { type: "category", data: cats, inverse: true }),
        xAxis: axis(tk, { type: "value", axisLabel: { color: tk.muted, formatter: axisFmt(u) } }),
        series: spec.series.map((s, i) => ({ name: s.name, type: "bar", stack: "t", data: s.values, barMaxWidth: 18, itemStyle: { color: tk.series[i === 0 ? 1 : 0], borderRadius: 3 } })) };
    case "waterfall": {
      const v = spec.series[0].values.map((x) => x ?? 0);
      // running totals; when the steps are small relative to the totals the axis starts at a labelled floor so they stay legible
      const tops: number[] = [];
      let run = 0;
      v.forEach((x, i) => { run = i === 0 ? x : i === v.length - 1 ? x : run + x; tops.push(run); });
      const lows = v.map((x, i) => (i === 0 || i === v.length - 1 ? 0 : x >= 0 ? tops[i] - x : tops[i]));
      const maxStep = Math.max(0, ...v.slice(1, -1).map(Math.abs));
      const minTotal = Math.min(...tops.map(Math.abs));
      const lowest = Math.min(...tops, ...lows.filter((_, i) => i > 0 && i < v.length - 1));
      const mag = 10 ** Math.floor(Math.log10(Math.max(1, minTotal)) - 1);
      const floor = maxStep > 0 && maxStep < 0.15 * minTotal && lowest > 0 ? Math.floor((lowest * 0.92) / mag) * mag : 0;
      const baseVals = v.map((x, i) => (i === 0 || i === v.length - 1 ? floor : x >= 0 ? tops[i] - x : tops[i]));
      const shown = v.map((x, i) => (i === 0 || i === v.length - 1 ? x - floor : Math.abs(x)));
      const colors = v.map((x, i) => (i === 0 || i === v.length - 1 ? tk.series[0] : x >= 0 ? tk.series[2] : tk.series[1]));
      return { ...b, grid: { ...b.grid, bottom: 36 }, tooltip: { ...b.tooltip, trigger: "axis", formatter: (p: any) => `${p[1].name}: ${formatValue(v[p[1].dataIndex], u)}` },
        xAxis: axis(tk, { type: "category", data: cats, axisLabel: { color: tk.muted, interval: 0, width: 84, overflow: "break", fontSize: 11 } }),
        yAxis: axis(tk, { type: "value", min: floor || undefined, name: floor ? "axis starts above zero" : "", nameTextStyle: { color: tk.muted, fontSize: 10 },
          axisLabel: { color: tk.muted, formatter: axisFmt(u) } }),
        series: [{ type: "bar", stack: "w", silent: true, itemStyle: { color: "transparent" }, data: baseVals },
          { type: "bar", stack: "w", barMaxWidth: 56, data: shown.map((x, i) => ({ value: x, itemStyle: { color: colors[i], borderRadius: 3 } })),
            label: { show: true, position: "top", color: tk.ink, fontSize: 11, formatter: (p: any) => formatValue(v[p.dataIndex], u) } }] };
    }
    case "donut":
      return { ...b, tooltip: { ...b.tooltip, trigger: "item", formatter: (p: any) => `${p.name}<br/>${formatValue(p.value, u)} (${p.percent}%)` },
        legend: { ...b.legend, top: "bottom" },
        series: [{ type: "pie", radius: ["52%", "78%"], center: ["50%", "45%"], avoidLabelOverlap: true, itemStyle: { borderColor: tk.surface, borderWidth: 2 },
          label: { color: tk.muted, formatter: "{d}%" }, data: cats.map((c, i) => ({ name: c, value: spec.series[0].values[i] })) }] };
    case "treemap": {
      const roots = spec.nodes.filter((n) => !n.parent);
      const kids = (id: string) => spec.nodes.filter((n) => n.parent === id);
      return { ...b, tooltip: { ...b.tooltip, trigger: "item", formatter: (p: any) => {
        const m = p.data?.meta;
        return m && m.margin != null ? `${p.name}<br/>Revenue ${formatValue(p.value, u)}<br/>Contribution margin ${formatValue(Number(m.margin), "%")}<br/>Fee ${m.fee_bps} bps`
          : `${p.name}: ${formatValue(p.value, u)}`;
      } },
        visualMap: { show: false, type: "continuous", dimension: 1, inRange: { color: tk.div },
          ...(() => { const m = Math.max(0.05, ...spec.nodes.map((n) => Math.abs(n.color_value ?? 0))); return { min: -m, max: m }; })() },
        series: [{ type: "treemap", roam: false, nodeClick: false, breadcrumb: { show: false }, top: 8, bottom: 8, left: 0, right: 0,
          itemStyle: { borderColor: tk.surface, gapWidth: 2 }, levels: [{ itemStyle: { borderWidth: 3, gapWidth: 3 }, upperLabel: { show: true, color: tk.ink, height: 18 } }, {}],
          data: roots.map((r) => ({ name: r.name, children: kids(r.id).map((k) => ({ name: k.name, value: [k.value ?? 0, k.color_value ?? 0], meta: k.meta })) })) }] };
    }
    case "heatmap":
    case "matrix": {
      const vals = spec.cells.map((c) => c[2]);
      const isMatrix = spec.chart_type === "matrix";
      return { ...b, grid: { ...b.grid, left: 8, bottom: 8 },
        tooltip: { ...b.tooltip, trigger: "item", formatter: (p: any) => `${spec.y_labels[p.data[1]]} × ${spec.x_labels[p.data[0]]}: ${isMatrix ? Number(p.data[2]).toFixed(2) : p.data[2]}` },
        xAxis: axis(tk, { type: "category", data: spec.x_labels, name: spec.x_axis.label, nameLocation: "middle", nameGap: 26, axisLabel: { color: tk.muted, rotate: isMatrix ? 45 : 0, interval: 0, width: 80, overflow: "truncate" } }),
        yAxis: axis(tk, { type: "category", data: spec.y_labels, name: spec.y_axis.label, nameLocation: "middle", nameGap: isMatrix ? 0 : 30, axisLabel: { color: tk.muted, width: 110, overflow: "truncate" } }),
        visualMap: { show: false, min: isMatrix ? -1 : 0, max: isMatrix ? 1 : Math.max(1, ...vals), inRange: { color: isMatrix ? tk.div : tk.seq } },
        series: [{ type: "heatmap", data: spec.cells, label: { show: !isMatrix || spec.x_labels.length <= 8, color: tk.ink, formatter: (p: any) => (isMatrix ? Number(p.data[2]).toFixed(1) : p.data[2]) },
          itemStyle: { borderColor: tk.surface, borderWidth: 2, borderRadius: 3 } }] };
    }
    case "scatter": {
      const groups = [...new Set(spec.nodes.map((n) => n.group ?? "All"))];
      const top = groups.slice(0, 7);
      const maxSize = Math.max(1, ...spec.nodes.map((n) => Math.abs(n.size ?? 1)));
      const gname = (g: string) => (top.includes(g) ? g : "Other");
      const names = [...new Set(spec.nodes.map((n) => gname(n.group ?? "All")))];
      return { ...b, tooltip: { ...b.tooltip, trigger: "item", formatter: (p: any) => `${p.data.name}<br/>${spec.x_axis.label}: ${formatValue(p.data.value[0], spec.x_axis.unit)}<br/>${spec.y_axis.label}: ${formatValue(p.data.value[1], spec.y_axis.unit)}` },
        xAxis: axis(tk, { type: "value", scale: true, name: spec.x_axis.label, nameLocation: "middle", nameGap: 26, axisLabel: { color: tk.muted, formatter: axisFmt(spec.x_axis.unit) } }),
        yAxis: axis(tk, { type: "value", scale: true, name: spec.y_axis.label, axisLabel: { color: tk.muted, formatter: axisFmt(spec.y_axis.unit) } }),
        series: names.map((g, i) => ({ name: g, type: "scatter", itemStyle: { color: tk.series[i % tk.series.length], opacity: 0.85 },
          data: spec.nodes.filter((n) => gname(n.group ?? "All") === g).map((n) => ({ name: n.name, id: n.id, value: [n.x, n.y],
            symbolSize: 6 + 16 * Math.sqrt(Math.abs(n.size ?? 1) / maxSize), itemStyle: n.status === "warn" ? { color: STATUS_COLOR.warn } : undefined })),
          ...(i === 0 ? refLines(spec, tk, "xAxis") : {}) })) };
    }
    case "agent_graph": {
      const depth: Record<string, number> = {};
      const out: Record<string, string[]> = {};
      spec.edges.forEach((e) => (out[e.source] = [...(out[e.source] ?? []), e.target]));
      const rootId = spec.nodes[0]?.id;
      const q = rootId ? [rootId] : [];
      if (rootId) depth[rootId] = 0;
      while (q.length) {
        const n = q.shift()!;
        for (const t of out[n] ?? []) if (depth[t] == null) { depth[t] = depth[n] + 1; q.push(t); }
      }
      const byDepth: Record<number, string[]> = {};
      spec.nodes.forEach((n) => (byDepth[depth[n.id] ?? 0] = [...(byDepth[depth[n.id] ?? 0] ?? []), n.id]));
      return { ...b, tooltip: { ...b.tooltip, trigger: "item", formatter: (p: any) => (p.dataType === "node" ? `${p.data.name}<br/>status: ${p.data.status}${p.data.tools ? `<br/>tools: ${p.data.tools}` : ""}` : "") },
        series: [{ type: "graph", layout: "none", roam: false, edgeSymbol: ["none", "arrow"], edgeSymbolSize: 7, lineStyle: { color: tk.muted, width: 1.2, curveness: 0.12 },
          label: { show: true, color: tk.ink, position: "bottom", fontSize: 11 },
          data: spec.nodes.map((n) => {
            const d = depth[n.id] ?? 0;
            const col = byDepth[d];
            return { id: n.id, name: n.name, status: n.status ?? "ok", tools: n.meta?.tools ?? "", x: d * 160, y: (col.indexOf(n.id) - (col.length - 1) / 2) * 70,
              symbolSize: d === 0 ? 18 : 24, itemStyle: { color: STATUS_COLOR[(n.status ?? "ok") as keyof typeof STATUS_COLOR], borderColor: tk.surface, borderWidth: 2 } };
          }),
          links: spec.edges.map((e) => ({ source: e.source, target: e.target })) }] };
    }
    default:
      return null;
  }
}

/** Rows for table view / CSV export, derived from the spec's data only. */
export function specRows(spec: ChartSpec): Record<string, string | number | null>[] {
  if (spec.categories.length && spec.series.length)
    return spec.categories.map((c, i) => ({ category: c, ...Object.fromEntries(spec.series.map((s) => [s.name, s.values[i] ?? null])) }));
  if (spec.cells.length) return spec.cells.map((c) => ({ x: spec.x_labels[c[0]], y: spec.y_labels[c[1]], value: c[2] }));
  return spec.nodes.map((n) => ({ name: n.name, value: n.value ?? null, x: n.x ?? null, y: n.y ?? null, group: n.group ?? null, parent: n.parent ?? null }));
}
