// API contract types (schema_version "1.0"). Mirrors backend/app/schemas.py.

export interface User { id: string; name: string; role: "viewer" | "analyst" | "admin"; workspace_id: string }

export interface AppConfig {
  product: string;
  subtitle: string;
  llm: { provider: string; model: string | null; mode: "llm" | "deterministic-demo"; label: string };
  recalc_engine: string | null;
  limits: { max_upload_mb: number; max_cells: number; max_sheets: number; max_steps: number };
  supported_formats: string[];
  unsupported_formats: string[];
  demo_users: { key: string; name: string; role: string; workspace: string }[];
  retention_days: number;
}

export interface Workbook {
  id: string; name: string; source_format: string; current_version: number; created_at: string; owner_id: string; is_demo: boolean;
}

export interface Version { version_no: number; kind: string; operation_id: string | null; note: string; created_by: string; created_at: string }

export interface ColumnProfile {
  name: string; letter: string; inferred_type: string; semantic: string | null; type_confidence: number;
  missing: number; missing_pct: number; distinct: number; range: string;
}

export interface Issue {
  id: string; kind: string; severity: "error" | "warning" | "info"; sheet: string; column: string | null;
  message: string; count: number; range: string | null; suggested_prompt: string | null; cell?: string; rows?: number[];
}

export interface SheetProfile {
  name: string; state: string; dimensions: string; max_row: number; max_column: number; formula_cells: number;
  merged_ranges: string[]; hidden_rows: number; hidden_columns: number; freeze_panes: string | null; excel_tables: string[];
  table: null | { header_row: number; row_count: number; column_count: number; range: string; header_confidence: number; columns: ColumnProfile[] };
  issues: Issue[];
}

export interface Profile {
  workbook_id: string; version: number; sheets: SheetProfile[]; issues: Issue[]; issue_counts: Record<string, number>;
  fidelity: { at_risk: { feature: string; count: number; risk: string; message: string }[]; requires_acknowledgement: boolean; preserved: string[] };
}

export interface GridCell { c: number; v: string; t: string; raw?: unknown; f?: string; uncalculated?: boolean; s?: { b?: 1; i?: 1; bg?: string; color?: string; align?: string; fmt?: string } }
export interface GridRow { r: number; cells: GridCell[] }
export interface GridWindow {
  sheet: string; version: number; max_row: number; max_col: number; r0: number; r1: number; rows: GridRow[];
  col_widths: Record<string, number>; freeze_panes: string | null; merged: string[]; state: string;
}

export interface Source { id: string; workbook_id: string; version: number; sheet: string; range: string; header: string | null; label: string; status: string; note?: string }

export interface CellState { formula: string | null; type: string; value: unknown }
export interface CellChange { sheet: string; cell: string; before: CellState; after: CellState; number_format: string | null }
export interface Check { name: string; passed: boolean; detail: string }

export interface Operation {
  id: string; workbook_id: string; base_version: number; current_version: number | null; out_of_date: boolean; run_id: string | null;
  action_type: string; status: "PROPOSED" | "APPLYING" | "APPLIED" | "FAILED" | "REJECTED" | "STALE";
  title: string; description: string; sheet: string | null; target_range: string | null; affected_cells: number;
  flags: { overwrites_values: number; replaces_formulas: number; clears_values: number; inserts_formulas: number; deletes_rows: number; adds_sheet: boolean };
  destructive: boolean; warnings: string[]; details: Record<string, any>;
  changes_sample?: CellChange[]; changes_total: number; removed_rows_sample: { row: number; values: CellState[] }[];
  new_sheet: { name: string; header: string[]; rows: unknown[][]; chart: { type: string } | null } | null;
  target_version?: number;
  change_set_hash: string; requires_acknowledgement: boolean; fidelity_at_risk: { feature: string; message: string; risk: string }[];
  dry_run: { passed: boolean; checks: Check[]; fidelity?: { lost: Record<string, unknown> } } | null;
  verification: null | { status: string; engine: string | null; message: string; checked_cells?: number; preview_mismatches?: string[]; values?: Record<string, unknown>; unsupported_by_engine?: number; total_formula_cells?: number };
  validation: { passed: boolean; checks: Check[] } | null; error: { code: string; message: string } | null;
  result_version: number | null; created_at: string; idempotent_replay?: boolean;
}

export interface ChartSpec {
  kind: "chart"; type: "bar" | "line" | "scatter" | "histogram" | "table"; title: string; x_label: string; y_label: string; unit: string | null;
  series: { name: string; points: { x: string | number; y: number | null }[] }[]; filters: unknown[]; sources: Source[]; notes: string[];
  web_only: boolean;
}

export interface ResultTableRow { group?: unknown[]; value?: unknown; rows?: number; pct?: number; [k: string]: unknown }

export interface AssistantResult {
  schema_version: string; type: "answer" | "proposal" | "clarification" | "info" | "error" | "cancelled";
  text: string; intent?: string; role?: string; run_id?: string;
  results?: any[]; chart?: ChartSpec | null; operations?: Operation[]; sources?: Source[];
  assumptions?: string[]; warnings?: string[]; method?: string | null; missing_treatment?: string | null; filters?: unknown[];
  follow_ups?: { label: string; prompt: string }[]; notes?: string[]; engine?: string;
  clarification?: { question: string; options: { label: string; prompt: string }[] };
  usage?: { steps: number; tokens_in: number; tokens_out: number; cost_estimate_usd: number; cost_note: string };
  grounding?: { checked: boolean; ungrounded: string[]; note?: string };
  code?: string; retryable?: boolean;
}

export interface RunStep { type: string; at: string; state?: string; note?: string; tool?: string; role?: string; status?: string; duration_ms?: number; code?: string; message?: string; intent?: string; steps?: string[] }

export interface Run {
  id: string; correlation_id: string; state: string; progress: string; workbook_id: string; workbook_version: number;
  conversation_id: string; intent: string | null; steps: RunStep[]; result: AssistantResult | null; error: string | null;
  model: string; prompt_version: string; usage: { tokens_in: number; tokens_out: number; cost_estimate_usd: number }; created_at: string;
}

export interface Message { id: string; role: "user" | "assistant"; content: any; run_id: string | null; created_at: string }

export interface ApiErrorBody { code: string; message: string; details?: Record<string, unknown>; retryable?: boolean; correlation_id?: string }
