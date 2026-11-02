import { useEffect, useRef, useState } from "react";
import * as echarts from "echarts/core";
import { BarChart, HeatmapChart, LineChart, PieChart, ScatterChart } from "echarts/charts";
import { AriaComponent, DataZoomComponent, GridComponent, LegendComponent, MarkLineComponent, TitleComponent, TooltipComponent, VisualMapComponent } from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";
import type { ChartSpec } from "@/lib/types";
import { useSession } from "@/lib/store";
import { fmt } from "@/lib/format";

echarts.use([LineChart, BarChart, PieChart, ScatterChart, HeatmapChart, GridComponent, TooltipComponent, LegendComponent, MarkLineComponent, TitleComponent,
  AriaComponent, DataZoomComponent, VisualMapComponent, CanvasRenderer]);

/** Flying Florina 3.0 chart palette (cyan, teal, sky, emerald, amber, gold, red). */
export const PALETTE = ["#22D3EE", "#14B8A6", "#38BDF8", "#10B981", "#F59E0B", "#FBBF24", "#EF4444"];

export function buildOption(spec: ChartSpec, dark: boolean): echarts.EChartsCoreOption {
  const text = dark ? "#94A3B8" : "#475569";
  const grid = dark ? "rgba(148,163,184,0.08)" : "rgba(15,23,42,0.08)";
  const tooltip = { backgroundColor: dark ? "#10213A" : "#FFFFFF", borderColor: "rgba(148,163,184,0.2)", textStyle: { color: dark ? "#F8FAFC" : "#0B1020", fontSize: 12 }, extraCssText: "border-radius:12px;" };
  if (spec.kind === "heatmap") {
    const max = Math.max(1, ...(spec.cells ?? []).map((c) => Number(c[2]) || 0));
    return {
      aria: { enabled: true }, tooltip: { ...tooltip, position: "top" },
      grid: { left: 70, right: 16, top: 16, bottom: 56, containLabel: true },
      xAxis: { type: "category", data: spec.x, axisLabel: { color: text, rotate: spec.x.length > 6 ? 30 : 0 }, splitArea: { show: true } },
      yAxis: { type: "category", data: spec.y ?? [], axisLabel: { color: text } },
      visualMap: { min: 0, max, calculable: true, orient: "horizontal", left: "center", bottom: 0, textStyle: { color: text },
        inRange: { color: ["rgba(20,184,166,0.08)", "#14B8A6", "#22D3EE", "#F59E0B", "#EF4444"] } },
      series: [{ type: "heatmap", data: spec.cells ?? [], label: { show: (spec.cells ?? []).length <= 60, color: dark ? "#F8FAFC" : "#0B1020", fontSize: 10 },
        emphasis: { itemStyle: { borderColor: "#22D3EE", borderWidth: 1 } } }],
    };
  }
  if (spec.kind === "scatter") {
    return {
      color: PALETTE, aria: { enabled: true }, tooltip: { ...tooltip, trigger: "item", formatter: (p: { data: (string | number)[] }) => `${p.data[2] ?? ""}<br/>${spec.xLabel ?? "x"}: ${p.data[0]}<br/>${spec.yLabel ?? "y"}: ${p.data[1]}` },
      grid: { left: 48, right: 16, top: 24, bottom: 40, containLabel: true },
      xAxis: { type: "value", name: spec.xLabel, nameTextStyle: { color: text }, axisLabel: { color: text }, splitLine: { lineStyle: { color: grid } } },
      yAxis: { type: "value", name: spec.yLabel, nameTextStyle: { color: text }, axisLabel: { color: text }, splitLine: { lineStyle: { color: grid } } },
      series: spec.series.map((s) => ({ name: s.name, type: "scatter", data: s.points ?? [], symbolSize: 12, itemStyle: { opacity: 0.85 } })),
    };
  }
  if (spec.kind === "pie") {
    return {
      color: PALETTE,
      aria: { enabled: true },
      tooltip: { ...tooltip, trigger: "item" },
      legend: { bottom: 0, textStyle: { color: text } },
      series: [{ type: "pie", radius: ["48%", "72%"], itemStyle: { borderColor: dark ? "#0A1628" : "#FFFFFF", borderWidth: 2, borderRadius: 6 },
        data: spec.x.map((x, i) => ({ name: String(x), value: spec.series[0]?.data[i] ?? 0 })), label: { show: false }, emphasis: { label: { show: true, color: text } } }],
    };
  }
  const longX = spec.x.length > 40;
  return {
    color: PALETTE,
    aria: { enabled: true },
    tooltip: { ...tooltip, trigger: "axis", axisPointer: { type: spec.kind === "bar" ? "shadow" : "line", shadowStyle: { color: "rgba(148,163,184,0.06)" } } },
    legend: { top: 0, textStyle: { color: text }, icon: "roundRect" },
    grid: { left: 48, right: 16, top: 32, bottom: longX ? 56 : 40, containLabel: true },
    xAxis: { type: "category", data: spec.x, axisLabel: { color: text, hideOverlap: true, rotate: spec.kind === "bar" && spec.x.length > 4 ? 20 : 0 }, axisLine: { lineStyle: { color: grid } } },
    yAxis: { type: "value", scale: spec.kind === "line", name: spec.yLabel, nameTextStyle: { color: text }, axisLabel: { color: text }, splitLine: { lineStyle: { color: grid } } },
    dataZoom: longX ? [{ type: "inside" }, { type: "slider", height: 16, bottom: 8 }] : undefined,
    series: spec.series.map((s, i) => ({
      name: s.name,
      type: spec.kind,
      data: s.data,
      connectNulls: false,
      showSymbol: false,
      smooth: spec.kind === "line" && spec.x.length < 40,
      barMaxWidth: 28,
      itemStyle: spec.kind === "bar" ? { borderRadius: [6, 6, 0, 0] } : undefined,
      lineStyle: spec.kind === "line" ? { width: i === 0 ? 2.5 : 1.5, type: i === 0 ? "solid" : "dashed" } : undefined,
      areaStyle: spec.kind === "line" && i === 0 && spec.series.length === 1 ? { opacity: 0.12 } : undefined,
      markLine:
        i === 0 && spec.markLine
          ? { symbol: "none", lineStyle: { type: "dashed", color: "#F87171" }, label: { formatter: spec.markLine.label, color: "#F87171" }, data: [{ yAxis: spec.markLine.y }] }
          : undefined,
    })),
  };
}

export function Chart({ spec, title, height = 280, onSelect }: { spec: ChartSpec; title: string; height?: number; onSelect?: (p: { name: string; value: unknown; data: unknown }) => void }) {
  const ref = useRef<HTMLDivElement>(null);
  const theme = useSession((s) => s.theme);
  const [showData, setShowData] = useState(false);
  useEffect(() => {
    if (!ref.current) return;
    const chart = echarts.init(ref.current, undefined, { renderer: "canvas" });
    chart.setOption(buildOption(spec, theme === "dark"));
    if (onSelect) chart.on("click", (p: { name: string; value: unknown; data: unknown }) => onSelect(p));
    const ro = new ResizeObserver(() => chart.resize());
    ro.observe(ref.current);
    return () => {
      ro.disconnect();
      chart.dispose();
    };
  }, [spec, theme, onSelect]);
  return (
    <div>
      <div ref={ref} role="img" aria-label={`Chart: ${title}`} style={{ height }} data-testid="chart" />
      <button className="muted mt-1 text-[11px] underline" onClick={() => setShowData((v) => !v)} aria-expanded={showData}>
        {showData ? "Hide data" : "View data table"}
      </button>
      {showData && (
        <div className="mt-2 max-h-56 overflow-auto">
          <table className="ff">
            <thead>
              <tr>
                <th>{spec.kind === "pie" ? "Category" : "X"}</th>
                {spec.series.map((s) => (
                  <th key={s.name}>{s.name}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {(spec.kind === "heatmap" || spec.kind === "scatter" ? [] : spec.x).map((x, i) => (
                <tr key={String(x) + i}>
                  <td>{String(x)}</td>
                  {spec.series.map((s) => (
                    <td key={s.name}>{fmt(s.data[i])}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
