import { flexRender, getCoreRowModel, getFilteredRowModel, getSortedRowModel, useReactTable, type ColumnDef, type SortingState } from "@tanstack/react-table";
import { ArrowDownUp } from "lucide-react";
import { useState } from "react";
import { Input, cn } from "./ui";

export function DataTable<T>({ data, columns, onRowClick, search = true, pageSize = 50, label }: {
  data: T[]; columns: ColumnDef<T, any>[]; onRowClick?: (r: T) => void; search?: boolean; pageSize?: number; label: string;
}) {
  const [sorting, setSorting] = useState<SortingState>([]);
  const [filter, setFilter] = useState("");
  const [limit, setLimit] = useState(pageSize);
  const table = useReactTable({ data, columns, state: { sorting, globalFilter: filter }, onSortingChange: setSorting, onGlobalFilterChange: setFilter,
    getCoreRowModel: getCoreRowModel(), getSortedRowModel: getSortedRowModel(), getFilteredRowModel: getFilteredRowModel() });
  const rows = table.getRowModel().rows;
  return (
    <div className="space-y-2">
      {search && <Input placeholder="Filter rows…" value={filter} onChange={(e) => setFilter(e.target.value)} aria-label={`Filter ${label}`} className="max-w-xs" />}
      <div className="overflow-auto scroll-thin rounded-md border border-line">
        <table className="w-full text-sm" aria-label={label}>
          <thead className="bg-side">
            {table.getHeaderGroups().map((hg) => (
              <tr key={hg.id}>{hg.headers.map((h) => (
                <th key={h.id} className="px-3 py-2 text-left text-xs font-medium text-muted whitespace-nowrap">
                  {h.isPlaceholder ? null : (
                    <button className="inline-flex items-center gap-1 hover:text-ink" onClick={h.column.getToggleSortingHandler()}>
                      {flexRender(h.column.columnDef.header, h.getContext())}<ArrowDownUp className="h-3 w-3 opacity-50" />
                    </button>
                  )}
                </th>
              ))}</tr>
            ))}
          </thead>
          <tbody>
            {rows.slice(0, limit).map((r) => (
              <tr key={r.id} tabIndex={onRowClick ? 0 : undefined} onClick={() => onRowClick?.(r.original)}
                onKeyDown={(e) => e.key === "Enter" && onRowClick?.(r.original)}
                className={cn("border-t border-line/60", onRowClick && "cursor-pointer hover:bg-line/30 focus:bg-line/30")}>
                {r.getVisibleCells().map((c) => <td key={c.id} className="px-3 py-1.5 whitespace-nowrap tabular-nums">{flexRender(c.column.columnDef.cell, c.getContext())}</td>)}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="flex items-center justify-between text-xs text-muted">
        <span>{rows.length} rows</span>
        {rows.length > limit && <button className="text-gold" onClick={() => setLimit(limit + pageSize)}>Show more</button>}
      </div>
    </div>
  );
}
