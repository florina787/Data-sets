import type { EChartsOption } from "echarts";
import ReactECharts from "echarts-for-react";
import { forwardRef } from "react";
import { useApp } from "@/lib/app";

type Props = { option: EChartsOption; height?: number; onClick?: (p: any) => void; ariaLabel: string };

export const EChart = forwardRef<ReactECharts, Props>(({ option, height = 280, onClick, ariaLabel }, ref) => {
  const { theme } = useApp();
  return (
    <div role="img" aria-label={ariaLabel}>
      <ReactECharts ref={ref} key={theme} option={option} style={{ height }} notMerge lazyUpdate
        onEvents={onClick ? { click: onClick } : undefined} opts={{ renderer: "canvas" }} />
    </div>
  );
});
