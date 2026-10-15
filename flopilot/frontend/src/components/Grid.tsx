import { useCallback, useEffect, useMemo, useRef, useState, type CSSProperties, type KeyboardEvent } from "react";
import { api } from "../lib/api";
import { blocksFor, cellRef, colLetter, displayCellState, formatWithNumberFormat, selectionStats, visibleRows, type SelectionStats } from "../lib/format";
import type { CellChange, GridCell, GridRow } from "../lib/types";

export const ROW_H = 22;
const ROW_HEADER_W = 46;
const DEFAULT_COL_W = 84;
const BLOCK = 100;

export interface Pos { col: number; row: number }
export interface Selection { sheet: string; anchor: Pos; focus: Pos }
export interface ActiveInfo { ref: string; display: string; formula: string | null; uncalculated: boolean }

interface Props {
  workbookId: string;
  version: number;
  sheet: string;
  selection: Selection | null;
  onSelect: (s: Selection) => void;
  changes: Map<string, CellChange> | null;
  compareMode: "before" | "after";
  filterRows: GridRow[] | null;
  onInfo: (info: ActiveInfo | null, stats: SelectionStats | null) => void;
  onError: (message: string) => void;
}

type RowMap = Map<number, Map<number, GridCell>>;

export function Grid(props: Props) {
  const { workbookId, version, sheet, selection, onSelect, changes, compareMode, filterRows, onInfo, onError } = props;
  const wrap = useRef<HTMLDivElement>(null);
  const rows = useRef<RowMap>(new Map());
  const loaded = useRef<Set<number>>(new Set());
  const [meta, setMeta] = useState<{ maxRow: number; maxCol: number; widths: Record<string, number>; frozen: number } | null>(null);
  const [tick, setTick] = useState(0);
  const [view, setView] = useState({ top: 0, height: 600 });
  const dragging = useRef(false);

  const loadBlock = useCallback(async (b: number) => {
    if (loaded.current.has(b)) return;
    loaded.current.add(b);
    try {
      const w = await api.cells(workbookId, sheet, version, b * BLOCK + 1, (b + 1) * BLOCK);
      for (const row of w.rows) rows.current.set(row.r, new Map(row.cells.map((c) => [c.c, c])));
      if (b === 0) {
        const frozen = w.freeze_panes ? Math.max(0, Number(/\d+/.exec(w.freeze_panes)?.[0] ?? 1) - 1) : 0;
        setMeta({ maxRow: w.max_row, maxCol: w.max_col, widths: w.col_widths, frozen: Math.min(frozen, 3) });
      }
      setTick((t) => t + 1);
    } catch (e) {
      loaded.current.delete(b);
      onError(e instanceof Error ? e.message : "Could not load cells.");
    }
  }, [workbookId, sheet, version, onError]);

  useEffect(() => {
    rows.current = new Map();
    loaded.current = new Set();
    setMeta(null);
    wrap.current?.scrollTo({ top: 0, left: 0 });
    void loadBlock(0);
  }, [workbookId, sheet, version, loadBlock]);

  useEffect(() => {
    const el = wrap.current;
    if (!el) return;
    const measure = () => setView({ top: el.scrollTop, height: el.clientHeight });
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const displayCols = meta ? Math.min(Math.max(meta.maxCol + 3, 26), 120) : 26;
  const displayRows = meta ? Math.max(meta.maxRow + 30, 60) : 60;
  const frozen = filterRows ? 0 : meta?.frozen ?? 0;
  const widths = useMemo(() => {
    const out: number[] = [0];
    for (let c = 1; c <= displayCols; c++) out.push(meta?.widths[colLetter(c)] ?? DEFAULT_COL_W);
    return out;
  }, [meta, displayCols]);
  const lefts = useMemo(() => {
    const out: number[] = [0, ROW_HEADER_W];
    for (let c = 1; c <= displayCols; c++) out.push(out[c] + widths[c]);
    return out;
  }, [widths, displayCols]);
  const totalWidth = lefts[displayCols + 1];

  const { first, last } = visibleRows(view.top, view.height, ROW_H, displayRows);
  useEffect(() => {
    if (!meta || filterRows) return;
    for (const b of blocksFor(first, Math.min(last, meta.maxRow), BLOCK)) void loadBlock(b);
  }, [first, last, meta, loadBlock, filterRows]);

  // Selection geometry
  const sel = selection && selection.sheet === sheet ? selection : null;
  const r0 = sel ? Math.min(sel.anchor.row, sel.focus.row) : 0;
  const r1 = sel ? Math.max(sel.anchor.row, sel.focus.row) : -1;
  const c0 = sel ? Math.min(sel.anchor.col, sel.focus.col) : 0;
  const c1 = sel ? Math.max(sel.anchor.col, sel.focus.col) : -1;

  // Report active cell + selection statistics (Excel-style status bar).
  useEffect(() => {
    if (!sel) { onInfo(null, null); return; }
    const cell = (filterRows ? lookupFiltered(filterRows, sel.focus.row) : rows.current.get(sel.focus.row))?.get(sel.focus.col);
    const ref = cellRef(sel.focus.col, sel.focus.row);
    const change = changes?.get(`${sheet}!${ref}`);
    const info: ActiveInfo = change
      ? { ref, display: displayCellState(compareMode === "before" ? change.before : change.after), formula: (compareMode === "before" ? change.before : change.after).formula, uncalculated: false }
      : { ref, display: cell?.v ?? "", formula: cell?.f ?? null, uncalculated: !!cell?.uncalculated };
    let stats: SelectionStats | null = null;
    if (r1 > r0 || c1 > c0) {
      const values: unknown[] = [];
      for (let r = r0; r <= Math.min(r1, r0 + 5000); r++) {
        const row = rows.current.get(r);
        for (let c = c0; c <= c1; c++) values.push(row?.get(c)?.raw);
      }
      stats = selectionStats(values);
    }
    onInfo(info, stats);
  }, [sel?.focus.row, sel?.focus.col, r0, r1, c0, c1, tick, changes, compareMode, sheet, filterRows]); // eslint-disable-line react-hooks/exhaustive-deps

  // Keep the active cell visible when the selection changes (keyboard, sources, previews).
  useEffect(() => {
    const el = wrap.current;
    if (!el || !sel || filterRows) return;
    if (sel.focus.row > frozen) {
      // Row r starts at r * ROW_H in scroll space (column header + frozen rows + preceding rows).
      const rowTop = sel.focus.row * ROW_H;
      const pinned = ROW_H * (1 + frozen);
      if (rowTop < el.scrollTop + pinned) el.scrollTop = Math.max(0, rowTop - pinned);
      else if (rowTop + ROW_H > el.scrollTop + el.clientHeight) el.scrollTop = rowTop + ROW_H - el.clientHeight;
    }
    const left = lefts[sel.focus.col];
    const right = lefts[sel.focus.col + 1];
    if (left < el.scrollLeft + ROW_HEADER_W) el.scrollLeft = Math.max(0, left - ROW_HEADER_W);
    else if (right > el.scrollLeft + el.clientWidth) el.scrollLeft = right - el.clientWidth + 8;
  }, [sel?.focus.row, sel?.focus.col]); // eslint-disable-line react-hooks/exhaustive-deps

  const select = (pos: Pos, extend: boolean) => {
    onSelect({ sheet, anchor: extend && sel ? sel.anchor : pos, focus: pos });
  };

  const onKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    const moves: Record<string, [number, number]> = { ArrowUp: [0, -1], ArrowDown: [0, 1], ArrowLeft: [-1, 0], ArrowRight: [1, 0], Enter: [0, 1], Tab: [1, 0] };
    const page = e.key === "PageDown" ? 20 : e.key === "PageUp" ? -20 : 0;
    const mv = moves[e.key] ?? (page ? [0, page] : null);
    if (!mv) return;
    e.preventDefault();
    const cur = sel?.focus ?? { col: 1, row: 1 };
    const next = { col: Math.min(displayCols, Math.max(1, cur.col + mv[0])), row: Math.min(displayRows, Math.max(1, cur.row + mv[1])) };
    select(next, e.shiftKey && e.key.startsWith("Arrow"));
  };

  const renderRow = (r: number, data: Map<number, GridCell> | undefined, style: CSSProperties, extraClass = "") => (
    <div key={r} className={`row ${extraClass}`} style={{ ...style, width: totalWidth }} role="row" aria-rowindex={r}>
      <div className={`row-h ${r >= r0 && r <= r1 ? "sel" : ""}`} role="rowheader">{r}</div>
      {Array.from({ length: displayCols }, (_, i) => {
        const c = i + 1;
        const cell = data?.get(c);
        const ref = cellRef(c, r);
        const change = changes?.get(`${sheet}!${ref}`);
        const state = change ? (compareMode === "before" ? change.before : change.after) : null;
        const text = state
          ? state.formula && compareMode === "after" && state.value !== null && state.value !== ""
            ? formatWithNumberFormat(state.value, change?.number_format)   // preview value, shown in the proposed format
            : displayCellState(state).replace("(empty)", "")
          : cell?.v ?? "";
        const kind = state ? state.type : cell?.t;
        const numeric = kind === "number" || kind === "date" || kind === "datetime";
        const inRange = r >= r0 && r <= r1 && c >= c0 && c <= c1;
        const active = sel && sel.focus.row === r && sel.focus.col === c;
        const s = cell?.s;
        const style: CSSProperties = { width: widths[c] };
        if (!change && s) {
          if (s.b) style.fontWeight = 700;
          if (s.i) style.fontStyle = "italic";
          if (s.bg) style.background = s.bg;
          if (s.color) style.color = s.color;
          if (s.align === "center" || s.align === "right" || s.align === "left") style.textAlign = s.align;
        }
        return (
          <div key={c} role="gridcell" aria-selected={inRange || undefined} aria-colindex={c}
            className={`cell${numeric ? " num" : ""}${kind === "error" ? " err" : ""}${cell?.uncalculated && !change ? " uncalc" : ""}${inRange && !active ? " in-range" : ""}${active ? " active" : ""}${change ? " changed" : ""}`}
            style={style}
            title={change ? `Before: ${displayCellState(change.before)}\nAfter: ${displayCellState(change.after)}` : cell?.f ? `${cell.f}` : undefined}
            onMouseDown={(e) => { dragging.current = true; select({ col: c, row: r }, e.shiftKey); }}
            onMouseEnter={() => { if (dragging.current && sel) onSelect({ sheet, anchor: sel.anchor, focus: { col: c, row: r } }); }}>
            {cell?.uncalculated && !change ? "(not calculated)" : text}
          </div>
        );
      })}
    </div>
  );

  void tick; // re-render trigger for loaded blocks
  return (
    <div className="grid-wrap" ref={wrap} tabIndex={0} role="grid" aria-label={`Sheet ${sheet}`} aria-rowcount={displayRows} aria-colcount={displayCols}
      onKeyDown={onKeyDown} onMouseUp={() => { dragging.current = false; }} onMouseLeave={() => { dragging.current = false; }}
      onScroll={(e) => { const t = e.currentTarget.scrollTop; requestAnimationFrame(() => setView((v) => (v.top === t ? v : { ...v, top: t }))); }}>
      <div className="grid-head" style={{ width: totalWidth }} role="row">
        <div className="corner col-h" style={{ width: ROW_HEADER_W }} />
        {Array.from({ length: displayCols }, (_, i) => (
          <div key={i} role="columnheader" className={`col-h ${i + 1 >= c0 && i + 1 <= c1 ? "sel" : ""}`} style={{ width: widths[i + 1] }}>{colLetter(i + 1)}</div>
        ))}
      </div>
      {!meta && <div className="grid-loading">Loading cells…</div>}
      {filterRows ? (
        <div>
          {filterRows.map((row) => renderRow(row.r, new Map(row.cells.map((c) => [c.c, c])), { position: "relative" }))}
          {filterRows.length === 0 && <div className="grid-loading">No rows match.</div>}
        </div>
      ) : (
        <>
          {frozen > 0 && (
            <div style={{ position: "sticky", top: ROW_H, zIndex: 3, height: frozen * ROW_H, width: totalWidth }}>
              {Array.from({ length: frozen }, (_, i) => renderRow(i + 1, rows.current.get(i + 1), { position: "relative" }, "frozen-row"))}
            </div>
          )}
          <div className="grid-inner" style={{ height: (displayRows - frozen) * ROW_H, width: totalWidth }}>
            {Array.from({ length: Math.max(0, last - Math.max(first, frozen + 1) + 1) }, (_, i) => {
              const r = Math.max(first, frozen + 1) + i;
              return renderRow(r, rows.current.get(r), { top: (r - 1 - frozen) * ROW_H });
            })}
          </div>
        </>
      )}
    </div>
  );
}

function lookupFiltered(rows: GridRow[], r: number): Map<number, GridCell> | undefined {
  const row = rows.find((x) => x.r === r);
  return row ? new Map(row.cells.map((c) => [c.c, c])) : undefined;
}
