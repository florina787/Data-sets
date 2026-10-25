import { useEffect, useRef, useState } from "react";
import * as echarts from "echarts/core";
import { BarChart, LineChart, PieChart } from "echarts/charts";
import { AriaComponent, DataZoomComponent, GridComponent, LegendComponent, MarkLineComponent, TitleComponent, TooltipComponent } from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";
import type { ChartSpec } from "@/lib/types";
import { useSession } from "@/lib/store";
import { fmt } from "@/lib/format";

echarts.use([LineChart, BarChart, PieChart, GridComponent, TooltipComponent, LegendComponent, MarkLineComponent, TitleComponent, AriaComponent, DataZoomComponent, CanvasRenderer]);

const PALETTE = ["#5C35B7", "#0F8B8D", "#D7B46A", "#A78BFA", "#B7791F", "#3B6FB6", "#C53030"];

export function buildOption(spec: ChartSpec, dark: boolean): echarts.EChartsCoreOption {
  const text = dark ? "#EEF0FA" : "#0B1230";
  const grid = dark ? "#2B3566" : "#E4E1F0";
  if (spec.kind === "pie") {
    return {
      color: PALETTE,
      aria: { enabled: true },
      tooltip: { trigger: "item" },
      legend: { bottom: 0, textStyle: { color: text } },
      series: [{ type: "pie", radius: ["40%", "70%"], data: spec.x.map((x, i) => ({ name: String(x), value: spec.series[0]?.data[i] ?? 0 })), label: { color: text } }],
    };
  }
  const longX = spec.x.length > 40;
  return {
    color: PALETTE,
    aria: { enabled: true },
    tooltip: { trigger: "axis" },
    legend: { top: 0, textStyle: { color: text } },
    grid: { left: 48, right: 16, top: 32, bottom: longX ? 56 : 40, containLabel: true },
    xAxis: { type: "category", data: spec.x, axisLabel: { color: text, hideOverlap: true, rotate: spec.kind === "bar" && spec.x.length > 4 ? 20 : 0 }, axisLine: { lineStyle: { color: grid } } },
    yAxis: { type: "value", name: spec.yLabel, nameTextStyle: { color: text }, axisLabel: { color: text }, splitLine: { lineStyle: { color: grid } } },
    dataZoom: longX ? [{ type: "inside" }, { type: "slider", height: 16, bottom: 8 }] : undefined,
    series: spec.series.map((s, i) => ({
      name: s.name,
      type: spec.kind,
      data: s.data,
      connectNulls: false,
      showSymbol: false,
      smooth: false,
      barMaxWidth: 36,
      markLine:
        i === 0 && spec.markLine
          ? { symbol: "none", lineStyle: { type: "dashed", color: "#C53030" }, label: { formatter: spec.markLine.label, color: "#C53030" }, data: [{ yAxis: spec.markLine.y }] }
          : undefined,
    })),
  };
}

export function Chart({ spec, title, height = 280 }: { spec: ChartSpec; title: string; height?: number }) {
  const ref = useRef<HTMLDivElement>(null);
  const theme = useSession((s) => s.theme);
  const [showData, setShowData] = useState(false);
  useEffect(() => {
    if (!ref.current) return;
    const chart = echarts.init(ref.current, undefined, { renderer: "canvas" });
    chart.setOption(buildOption(spec, theme === "dark"));
    const ro = new ResizeObserver(() => chart.resize());
    ro.observe(ref.current);
    return () => {
      ro.disconnect();
      chart.dispose();
    };
  }, [spec, theme]);
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
              {spec.x.map((x, i) => (
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
