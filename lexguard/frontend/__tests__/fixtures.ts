import type { CopilotResponse } from "@/types/api";

export const blockedResponse: CopilotResponse = {
  request_id: "REQ-1", user_id: "U-002", matter_id: "M-1002", status: "BLOCKED", risk: "CRITICAL", intent: "external_provider_request",
  answer: "Blocked. NorthStar Holdings prohibits external generative AI.",
  findings: [], evidence: [], citations: [], playbook_deviations: [], actions: [], agent_trace: [
    { step: 1, label: "Matter access verified", agent: "access_control", status: "ok" },
    { step: 2, label: "Requested provider blocked by policy", agent: "ai_policy", status: "blocked", detail: "POL-CLIENT-003" },
  ],
  cards: [{ type: "POLICY_BLOCK", title: "External legal-AI request blocked", severity: "HIGH", body: "External generative AI prohibited.",
    metrics: [{ label: "Data sent externally", value: "None", tone: "good" }], items: [{ rule_id: "POL-CLIENT-003", text: "Client prohibits external AI." }], actions: [] }],
  approval_required: false, approval: null,
  matterguard: { decision: "PROHIBITED", risk: "CRITICAL", risk_score: 6, reasons: ["Client prohibits external AI."], policy_evidence: [
    { rule_id: "POL-CLIENT-003", effect: "PROHIBIT", description: "Client prohibits external AI." }], allowed_tools: ["knowledge_search"],
    blocked_tools: ["external_provider_call"], human_review_level: 3, human_review_label: "LEVEL 3", human_review_required: true,
    external_distribution: "INTERNAL_ONLY", access_granted: true, ethical_wall_blocked: false, ai_allowed_for_matter: true,
    external_ai_allowed_for_matter: false, provider_id: "P-MOCK-LEGAL-AI", provider_permitted: false, destination: "internal",
    alternatives: ["Use LexGuard Internal RAG"], client_policy_summary: "External generative AI prohibited." },
  routing: null, suitability: null, assurance: null, privilege_flags: [], sources: [], draft: null, work_product_id: null,
  analysis: null, review_summary: null, value_estimate: null, injection_flags: [], audit_event_ids: [], errors: [],
  metrics: { latency_ms: 12, est_cost_usd: 0, paid_llm_calls: 0, agents_invoked: ["ai_policy"], tools_invoked: [], tool_calls: 0,
    graph_path: ["matter_context", "access_control", "ethical_wall", "ai_policy", "policy_block", "finalize"], demo_mode: true },
};

export const reviewResponse: CopilotResponse = {
  ...blockedResponse, request_id: "REQ-2", matter_id: "M-1001", status: "REVIEW_REQUIRED", risk: "MEDIUM", intent: "playbook_compare",
  answer: "487 of 500 documents processed; 63 clauses; 11 deviations.",
  cards: [
    { type: "ANALYSIS_SUMMARY", title: "Change-of-control review", metrics: [{ label: "Clauses identified", value: 63 }, { label: "Escalation candidates", value: 3, tone: "bad" }], items: [], actions: [] },
    { type: "PLAYBOOK_DEVIATION", title: "Playbook deviations", severity: "MEDIUM", metrics: [], actions: [], items: [
      { finding_id: "F-1", doc_id: "MAPLE-C-0001", doc_title: "Supply Agreement", result: "ESCALATION_REQUIRED", rule_id: "MA-COC-05", topic: "Unrestricted veto", standard_position: "Partner escalation required." }] },
    { type: "NEXT_ACTION", title: "Recommended actions", metrics: [], items: [], actions: [{ id: "draft-memo", label: "Draft Memo", kind: "copilot", payload: { message: "Draft" } }] },
  ],
};
