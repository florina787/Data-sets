import { CheckSquare, Lock } from "lucide-react";
import { Link } from "react-router-dom";
import { Badge } from "@/components/ui";
import { useApp } from "@/lib/app";
import type { MessageResponse } from "../types";

const TONE = { required: "warn", pending: "blue", approved: "good", not_permitted: "neutral" } as const;

/** Shows which actions need human approval. Approvals are requested and decided only through the approvals workflow. */
export function ApprovalPanel({ items }: { items: MessageResponse["approval_requirements"] }) {
  const { can } = useApp();
  if (!items.length) return null;
  return (
    <section aria-label="Approval requirements" className="rounded-xl border border-warn/30 bg-warn/5 p-3.5">
      <h3 className="mb-2 flex items-center gap-1.5 text-sm font-semibold"><Lock className="h-4 w-4 text-warn" />Human approval gates</h3>
      <ul className="space-y-1.5 text-xs">
        {items.map((a) => (
          <li key={a.action} className="flex flex-wrap items-center gap-2">
            <code className="text-ink">{a.action}</code><Badge tone={TONE[a.status]}>{a.status.replace("_", " ")}</Badge>
            <span className="text-muted">{a.reason}{a.approver_roles.length ? ` Approver: ${a.approver_roles.join(" or ")}.` : ""}</span>
          </li>
        ))}
      </ul>
      {(can("approvals:decide") || can("comms:draft")) && (
        <Link to="/approvals" className="mt-2 inline-flex items-center gap-1 text-xs text-gold hover:underline"><CheckSquare className="h-3.5 w-3.5" />Open the approvals queue</Link>
      )}
    </section>
  );
}
