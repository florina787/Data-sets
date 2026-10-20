import { useState, type ReactNode } from "react";
import { Download, MessageSquare, RotateCcw, Table2 } from "lucide-react";
import { Button, Card, Empty, Table } from "../components/ui";
import { downloadCSV } from "../lib/csv";
import { useApp } from "../lib/state";

export type ChartTable = { head: string[]; rows: (string | number | null)[][] };

/**
 * Shared chart frame: title, scope, units and denominator, accessible data table, CSV export,
 * filter reset and "Ask Flo about this". Every chart in the app renders through this component.
 */
export function ChartCard({
  title, scope, units, table, children, empty, askQuestion, onReset, filterActive, footnote, id,
}: {
  title: string; scope: string; units: string; table: ChartTable; children: ReactNode; empty?: string | null;
  askQuestion: string; onReset?: () => void; filterActive?: boolean; footnote?: ReactNode; id?: string;
}) {
  const [showTable, setShowTable] = useState(false);
  const { ask, busy } = useApp();
  return (
    <Card
      id={id}
      title={title}
      subtitle={<span><span className="font-medium">Scope:</span> {scope} · <span className="font-medium">Units:</span> {units}</span>}
      actions={
        <>
          {filterActive && onReset && <Button size="sm" variant="ghost" onClick={onReset}><RotateCcw className="h-3.5 w-3.5" aria-hidden />Reset filter</Button>}
          <Button size="sm" variant="ghost" aria-pressed={showTable} onClick={() => setShowTable((s) => !s)}><Table2 className="h-3.5 w-3.5" aria-hidden />{showTable ? "Show chart" : "Table"}</Button>
          <Button size="sm" variant="ghost" disabled={!table.rows.length} onClick={() => downloadCSV(`${title}.csv`, table.head, table.rows)}><Download className="h-3.5 w-3.5" aria-hidden />CSV</Button>
          <Button size="sm" variant="ghost" disabled={busy || !!empty} onClick={() => ask(askQuestion)}><MessageSquare className="h-3.5 w-3.5" aria-hidden />Ask Flo about this</Button>
        </>
      }
    >
      {empty ? (
        <Empty title="Not available for this scope">{empty}</Empty>
      ) : showTable ? (
        <Table caption={title} head={table.head} rows={table.rows.map((r) => r.map((c) => (c === null ? "–" : c)))} />
      ) : (
        <div>
          {children}
          {/* Screen-reader table always present */}
          <div className="sr-only"><Table caption={`${title} data`} head={table.head} rows={table.rows.map((r) => r.map((c) => (c === null ? "–" : c)))} /></div>
        </div>
      )}
      {footnote && <div className="mt-3 text-xs text-muted">{footnote}</div>}
    </Card>
  );
}
