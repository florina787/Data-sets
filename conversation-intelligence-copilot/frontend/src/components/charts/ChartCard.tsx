import { motion } from "framer-motion";
import { AlertCircle, Download, Image as ImageIcon, MousePointerClick, Table2 } from "lucide-react";
import { useRef, useState } from "react";
import { toPng } from "html-to-image";
import { Card, CardHeader, Tip, Button } from "@/components/common/ui";
import { download, toCsv } from "@/lib/csv";
import type { ChartSpec } from "@/types/api";
import { ChartBody, DataTable } from "./ChartRenderer";

export function ChartCard({ spec, height, delay = 0, className }: { spec: ChartSpec; height?: number; delay?: number; className?: string }) {
  const [table, setTable] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const exportPng = async () => {
    if (!ref.current) return;
    try {
      const url = await toPng(ref.current, { backgroundColor: "#111827", pixelRatio: 2 });
      download(`${spec.chart_id}.png`, await (await fetch(url)).blob(), "image/png");
    } catch {
      /* PNG export can fail on some browsers; CSV remains available */
    }
  };
  if (spec.chart_type === "kpi") {
    return (
      <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.35, delay }} className={className}>
        <ChartBody spec={spec} />
      </motion.div>
    );
  }
  return (
    <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4, delay }} className={className}>
      <Card className="h-full overflow-hidden">
        <CardHeader title={spec.title} subtitle={spec.description || undefined}
          actions={<>
            {spec.drilldown && <Tip content="Click a bar, point or row to open the underlying conversations"><span className="mr-1 hidden text-faint sm:inline"><MousePointerClick className="h-3.5 w-3.5" aria-label="Interactive" /></span></Tip>}
            <Tip content={table ? "Show chart" : "Show data table"}><Button size="icon" variant="ghost" onClick={() => setTable((t) => !t)} aria-label="Toggle data table" aria-pressed={table}><Table2 className="h-3.5 w-3.5" /></Button></Tip>
            <Tip content="Export data (CSV)"><Button size="icon" variant="ghost" onClick={() => download(`${spec.chart_id}.csv`, toCsv(spec.data.map(({ cells, ...r }) => ({ ...r, ...(cells ?? {}) }))))} aria-label="Export CSV"><Download className="h-3.5 w-3.5" /></Button></Tip>
            <Tip content="Export image (PNG)"><Button size="icon" variant="ghost" onClick={exportPng} aria-label="Export PNG"><ImageIcon className="h-3.5 w-3.5" /></Button></Tip>
          </>} />
        <div ref={ref} className="px-4 pb-4 pt-3" role="figure" aria-label={`${spec.title}. ${spec.accessibility_summary}`}>
          {table ? <DataTable rows={spec.data.map(({ cells, ...r }) => ({ ...r, ...(cells ?? {}) }))} /> : <ChartBody spec={spec} height={height} />}
          <p className="sr-only">{spec.accessibility_summary}</p>
        </div>
        {spec.uncertainty_note && (
          <div className="flex items-start gap-2 border-t border-line bg-warn/[0.04] px-5 py-2.5 text-[11px] leading-relaxed text-muted">
            <AlertCircle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-warn" aria-hidden /><span>{spec.uncertainty_note}</span>
          </div>
        )}
      </Card>
    </motion.div>
  );
}
