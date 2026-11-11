import * as echarts from "echarts/core";
import { BarChart, LineChart, SankeyChart, ScatterChart } from "echarts/charts";
import { DataZoomComponent, GridComponent, LegendComponent, MarkLineComponent, TooltipComponent } from "echarts/components";
import { SVGRenderer } from "echarts/renderers";
import { useEffect, useRef } from "react";

echarts.use([BarChart, LineChart, SankeyChart, ScatterChart, GridComponent, TooltipComponent, LegendComponent, DataZoomComponent, MarkLineComponent, SVGRenderer]);

export type ChartOption = echarts.EChartsCoreOption;

export function Chart({ option, height = 280, onClick, label }: { option: ChartOption; height?: number; onClick?: (p: { data?: unknown; name?: string }) => void; label: string }) {
  const el = useRef<HTMLDivElement>(null);
  const inst = useRef<echarts.ECharts | null>(null);
  useEffect(() => {
    if (!el.current || typeof window === "undefined" || !("ResizeObserver" in window)) return;
    const c = echarts.init(el.current, undefined, { renderer: "svg" });
    inst.current = c;
    const ro = new ResizeObserver(() => c.resize());
    ro.observe(el.current);
    return () => {
      ro.disconnect();
      c.dispose();
    };
  }, []);
  useEffect(() => {
    const reduce = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    inst.current?.setOption({ animation: !reduce, ...option }, true);
  }, [option]);
  useEffect(() => {
    const c = inst.current;
    if (!c || !onClick) return;
    c.on("click", onClick as never);
    return () => void c.off("click");
  }, [onClick]);
  return <div ref={el} role="img" aria-label={label} style={{ height, width: "100%" }} />;
}
