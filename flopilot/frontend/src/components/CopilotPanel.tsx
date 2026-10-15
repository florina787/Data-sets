import { useEffect, useRef, useState } from "react";
import { AnswerCard } from "./AnswerCard";
import { ChartIcon, FloMinIcon, FloMinInline, FormulaIcon, SendIcon, TrendIcon } from "./Brand";
import type { AssistantResult, Operation, Run, Source } from "../lib/types";

export type ChatItem =
  | { kind: "user"; id: string; text: string; selection?: string | null }
  | { kind: "bot"; id: string; result: AssistantResult; prompt?: string };

const SUGGESTIONS = [
  {
    key: "analyze", title: "Analyze data", desc: "Find insights and trends in your data", Icon: ChartIcon,
    prompts: ["Summarize net revenue by region", "Which products had the largest month-over-month decline in net revenue?",
      "Compare actual spending with budget", "Find potential duplicate invoices", "Identify unusually large transactions in Net Revenue",
      "Show missing values by column"],
  },
  {
    key: "formulas", title: "Create formulas", desc: "Build or explain Excel formulas", Icon: FormulaIcon,
    prompts: ["Add a profit-margin column using net revenue", "Add the customer Segment from Customers to Sales",
      "Explain the formula in Expenses!H2", "Fix the formula error in Expenses!H23", "Check formula consistency in Profit on Sales"],
  },
  {
    key: "chart", title: "Build a chart", desc: "Create the right chart for your data", Icon: TrendIcon,
    prompts: ["Create a net revenue trend chart", "Chart net revenue by product", "Show the distribution of Units on Sales"],
  },
  {
    key: "clean", title: "Clean & restore", desc: "Fix data issues, then undo if needed", Icon: FormulaIcon,
    prompts: ["Clean the Sales sheet", "Normalize the Region categories on Sales", "Standardize the dates in Order Date",
      "Remove the duplicates on Customers", "Undo the last change"],
  },
];

interface Props {
  collapsed: boolean;
  onToggle: () => void;
  items: ChatItem[];
  activeRun: Run | null;
  modeLabel: string;
  selectionLabel: string | null;
  operations: Record<string, Operation>;
  canApprove: boolean;
  previewOpId: string | null;
  disabled: boolean;
  justApplied: boolean;
  onSend: (text: string) => void;
  onCancel: () => void;
  onSource: (s: Source) => void;
  onPreview: (op: Operation | null) => void;
  onApprove: (op: Operation, acknowledge: boolean, key: string) => Promise<void>;
  onReject: (op: Operation) => Promise<void>;
  onRefresh: (op: Operation) => Promise<void>;
  onNewConversation: () => void;
}

export function CopilotPanel(p: Props) {
  const [text, setText] = useState("");
  const [open, setOpen] = useState<string | null>(null);
  const scroller = useRef<HTMLDivElement>(null);
  const busy = !!p.activeRun;

  useEffect(() => {
    scroller.current?.scrollTo({ top: scroller.current.scrollHeight, behavior: "smooth" });
  }, [p.items.length, p.activeRun?.state]);

  if (p.collapsed) {
    return (
      <aside className="copilot collapsed" aria-label="FloPilot (collapsed)">
        <button className="icon-btn" style={{ margin: 8 }} onClick={p.onToggle} aria-label="Open FloPilot"><FloMinIcon size={24} /></button>
      </aside>
    );
  }

  const send = (value: string) => {
    const v = value.trim();
    if (!v || busy || p.disabled) return;
    p.onSend(v);
    setText("");
  };

  return (
    <aside className="copilot" aria-label="FloPilot assistant">
      <div className="copilot-head">
        <FloMinIcon size={24} />
        <h2>FloPilot</h2>
        <span className="chip neutral" title={p.modeLabel} style={{ maxWidth: 170, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{p.modeLabel}</span>
        <span style={{ marginLeft: "auto" }} />
        {p.items.length > 0 && <button className="btn ghost small" onClick={p.onNewConversation}>New chat</button>}
        <button className="icon-btn" onClick={p.onToggle} aria-label="Close FloPilot panel">✕</button>
      </div>

      <div className="copilot-scroll" ref={scroller} aria-live="polite">
        {p.items.length === 0 && (
          <div className="welcome">
            <FloMinInline size={92} blink wave={p.justApplied} label="FloMin waving hello" />
            <p className="greet">Hi, I’m FloMin.</p>
            <h3>How can I help with your workbook?</h3>
            {SUGGESTIONS.map(({ key, title, desc, Icon, prompts }) => (
              <div key={key}>
                <button className="action-card" aria-expanded={open === key} onClick={() => setOpen(open === key ? null : key)}>
                  <Icon />
                  <span><span className="t">{title}</span><br /><span className="d">{desc}</span></span>
                  <span className="chev" aria-hidden="true">{open === key ? "▾" : "›"}</span>
                </button>
                {open === key && (
                  <div className="prompt-list">
                    {prompts.map((q) => <button key={q} onClick={() => send(q)} disabled={busy || p.disabled}>{q}</button>)}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}

        {p.items.map((item) =>
          item.kind === "user" ? (
            <div key={item.id} className="msg-user">{item.text}{item.selection && <span className="sel">Selection: {item.selection}</span>}</div>
          ) : (
            <div key={item.id} className="msg-bot">
              <span className="avatar"><FloMinIcon size={24} /></span>
              <AnswerCard result={item.result} operations={p.operations} canApprove={p.canApprove} previewOpId={p.previewOpId}
                onSource={p.onSource} onPrompt={send} onPreview={p.onPreview} onApprove={p.onApprove} onReject={p.onReject}
                onRefresh={p.onRefresh} onRetry={item.prompt ? () => send(item.prompt!) : undefined} />
            </div>
          ),
        )}

        {p.activeRun && (
          <div className="progress" role="status">
            <div className="row1"><span className="spinner" aria-hidden="true" />{p.activeRun.progress}
              <button className="btn small" style={{ marginLeft: "auto" }} onClick={p.onCancel}>Cancel</button>
            </div>
            <ol>
              {p.activeRun.steps.filter((s) => s.type === "tool_call").map((s, i) => (
                <li key={i}>{toolLabel(s.tool ?? "")}{s.status === "error" ? " — failed" : ""}{s.duration_ms !== undefined ? ` (${s.duration_ms} ms)` : ""}</li>
              ))}
            </ol>
          </div>
        )}
      </div>

      <div className="composer">
        {p.selectionLabel && <div className="ctx">Using selection <span className="chip neutral">{p.selectionLabel}</span></div>}
        <div className="composer-box">
          <label htmlFor="ask" className="sr-only">Ask FloPilot</label>
          <textarea id="ask" rows={1} placeholder="Ask FloPilot…" value={text} disabled={p.disabled}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(e.currentTarget.value); } }} />
          <button className="send" onClick={() => send(text)} disabled={busy || p.disabled || !text.trim()} aria-label="Send"><SendIcon /></button>
        </div>
      </div>
    </aside>
  );
}

const TOOL_LABELS: Record<string, string> = {
  inspect_workbook: "Inspected the workbook structure", profile_sheet: "Profiled the sheet", calculate_aggregate: "Calculated totals",
  time_series: "Built the monthly series", period_change: "Compared the latest two months", compare_measures: "Compared actual vs budget",
  missing_by_column: "Counted missing values", find_duplicates: "Searched for duplicates", find_outliers: "Checked for unusual values",
  explain_formula: "Explained the formula", diagnose_formula: "Diagnosed the formula", check_formula_consistency: "Checked formula consistency",
  propose_formula: "Prepared a formula proposal", propose_formula_fix: "Prepared a formula fix", propose_cleaning: "Prepared a cleaning proposal",
  create_chart: "Built the chart", propose_report_sheet: "Prepared a report sheet", propose_restore: "Prepared a restore",
  correlation: "Calculated correlation", histogram: "Built the distribution", read_range: "Read a range", query_table: "Queried rows",
};

export function toolLabel(tool: string): string {
  return TOOL_LABELS[tool] ?? tool.replace(/_/g, " ");
}
