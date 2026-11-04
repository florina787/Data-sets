/**
 * Pure mapping from LangGraph execution events to what Sherin does. No DOM, no finance, no network:
 * the character only *reflects* state that the harness has already recorded.
 */
import type { Pose } from "./Character";

export type HarnessEventType =
  | "RUN_PLANNED" | "AGENT_STARTED" | "TOOL_RUNNING" | "TOOL_RETRY" | "TOOL_COMPLETED" | "TOOL_FAILED" | "TOOL_DENIED"
  | "VALIDATION_STARTED" | "VALIDATION_PASSED" | "VALIDATION_FAILED" | "APPROVAL_REQUIRED" | "APPROVAL_DECIDED" | "TASK_COMPLETED" | "TASK_FAILED";

export interface HarnessEvent {
  seq: number; event: HarnessEventType; message: string; synthetic: boolean; at?: string;
  agent?: string; tool?: string; step?: number; status?: string; approval_id?: string; approval_status?: string; verified?: boolean; error?: string | null;
  action_outcome?: string; plan?: { step: number; agent: string; tool: string; objective: string }[];
}

export type Target = { kind: "agent"; id: string } | { kind: "node"; id: string } | { kind: "manager" } | null;
export interface Directive { pose: Pose; target: Target; say: string; tone: "info" | "success" | "warning" | "error"; minMs: number }

const label = (a?: string) => (a ?? "agent").replace(/_/g, " ");

export function directiveFor(e: HarnessEvent): Directive {
  switch (e.event) {
    case "RUN_PLANNED": return { pose: "think", target: { kind: "node", id: "plan_task" }, say: `Planned ${e.plan?.length ?? "the"} steps for this request.`, tone: "info", minMs: 1400 };
    case "AGENT_STARTED": return { pose: "point", target: { kind: "agent", id: e.agent! }, say: `${label(e.agent)} agent is starting.`, tone: "info", minMs: 1100 };
    case "TOOL_RUNNING": return { pose: "work", target: null, say: `Running ${e.tool}…`, tone: "info", minMs: 1300 };
    case "TOOL_RETRY": return { pose: "think", target: null, say: e.message, tone: "warning", minMs: 1100 };
    case "TOOL_COMPLETED": return { pose: "idle", target: null, say: `${e.tool} finished.`, tone: "info", minMs: 700 };
    case "TOOL_FAILED": return { pose: "warning", target: null, say: `${e.tool} failed: ${e.error ?? e.message}`, tone: "warning", minMs: 2000 };
    case "TOOL_DENIED": return { pose: "warning", target: null, say: e.message, tone: "warning", minMs: 2000 };
    case "VALIDATION_STARTED": return { pose: "think", target: { kind: "node", id: "verify" }, say: "Walking to the validation station: the Independent Verification Agent checks every step.", tone: "info", minMs: 1500 };
    case "VALIDATION_PASSED": return { pose: "point", target: null, say: "Verification passed.", tone: "success", minMs: 1000 };
    case "VALIDATION_FAILED": return { pose: "warning", target: null, say: "Verification failed. This work will not count as verified savings.", tone: "warning", minMs: 2000 };
    case "APPROVAL_REQUIRED":
      return e.approval_status === "blocked"
        ? { pose: "error", target: { kind: "manager" }, say: "A mandatory policy block applies. No one can approve this request.", tone: "error", minMs: 2200 }
        : { pose: "waiting", target: { kind: "manager" }, say: "This needs an authorized human decision. The workflow is paused.", tone: "info", minMs: 1500 };
    case "APPROVAL_DECIDED":
      return e.status === "approved"
        ? { pose: "point", target: null, say: "Approved by an authorized manager. Finishing the run.", tone: "success", minMs: 1100 }
        : { pose: "warning", target: null, say: `Decision recorded: ${e.status?.replace(/_/g, " ")}. The action will not be applied.`, tone: "warning", minMs: 1800 };
    case "TASK_COMPLETED":
      return e.verified
        ? { pose: "success", target: null, say: "Task completed and verified.", tone: "success", minMs: 2000 }
        : { pose: "warning", target: null, say: "Task finished but is not verified, so it earns no savings credit.", tone: "warning", minMs: 2200 };
    case "TASK_FAILED": return { pose: "error", target: null, say: `The run failed: ${e.message}`, tone: "error", minMs: 2400 };
  }
}

/** Sherin may only celebrate after the workflow has actually completed and been verified. */
export function canCelebrate(events: HarnessEvent[]): boolean {
  const last = [...events].reverse().find((e) => e.event === "TASK_COMPLETED" || e.event === "TASK_FAILED");
  if (!last || last.event !== "TASK_COMPLETED" || !last.verified) return false;
  const decided = events.filter((e) => e.event === "APPROVAL_DECIDED");
  return events.every((e) => e.event !== "APPROVAL_REQUIRED") || (decided.length > 0 && decided[decided.length - 1].status === "approved");
}

export function runPhase(events: HarnessEvent[]): "idle" | "running" | "validating" | "awaiting_approval" | "completed" | "failed" {
  const types = events.map((e) => e.event);
  if (types.includes("TASK_FAILED")) return "failed";
  if (types.includes("TASK_COMPLETED")) return "completed";
  const lastReq = types.lastIndexOf("APPROVAL_REQUIRED");
  if (lastReq >= 0 && types.lastIndexOf("APPROVAL_DECIDED") < lastReq) return "awaiting_approval";
  if (types.includes("VALIDATION_STARTED")) return "validating";
  return types.length ? "running" : "idle";
}

/** Clearly labelled synthetic event script for demonstrations without a live run. */
export function syntheticEvents(plan: { step: number; agent: string; tool: string; objective: string }[], decision?: "approved" | "rejected"): HarnessEvent[] {
  const out: HarnessEvent[] = [];
  const push = (e: Omit<HarnessEvent, "seq" | "synthetic">) => out.push({ ...e, seq: out.length, synthetic: true });
  push({ event: "RUN_PLANNED", message: `Planned ${plan.length} step(s)`, plan });
  for (const s of plan) {
    push({ event: "AGENT_STARTED", message: s.objective, agent: s.agent, tool: s.tool, step: s.step });
    push({ event: "TOOL_RUNNING", message: s.tool, agent: s.agent, tool: s.tool, step: s.step });
    push({ event: "TOOL_COMPLETED", message: "ok", agent: s.agent, tool: s.tool, step: s.step, status: "ok" });
  }
  push({ event: "VALIDATION_STARTED", message: "verifying", agent: "verification" });
  push({ event: "VALIDATION_PASSED", message: "verified", agent: "verification" });
  push({ event: "APPROVAL_REQUIRED", message: "waiting", approval_id: "DEMO-APPROVAL", approval_status: "pending" });
  if (decision) {
    push({ event: "APPROVAL_DECIDED", message: decision, status: decision, approval_id: "DEMO-APPROVAL" });
    push({ event: "TASK_COMPLETED", message: "done", verified: decision === "approved", action_outcome: decision === "approved" ? "applied (synthetic demo)" : decision });
  }
  return out;
}
