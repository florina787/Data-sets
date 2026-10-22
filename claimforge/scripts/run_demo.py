"""Run the V1 end-to-end demo from the command line (DEMO_MODE, zero LLM calls)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.requirements.analyzer import DEMO_CLARIFICATIONS, DEMO_REQUIREMENT  # noqa: E402
from app.services.platform import ClaimForgePlatform  # noqa: E402

if __name__ == "__main__":
    p = ClaimForgePlatform()
    print("1) Analyze (expect human clarification):", p.run_workflow(DEMO_REQUIREMENT)["status"])
    st = p.run_workflow(DEMO_REQUIREMENT, clarifications=DEMO_CLARIFICATIONS)
    print("2) Assess release:", st["status"], st["release_risk"].decision.value, st["release_risk"].score)
    st = p.run_workflow(DEMO_REQUIREMENT, clarifications=DEMO_CLARIFICATIONS,
                        approval={"approver": "Demo Release Manager", "role": "Release Manager", "decision": "APPROVED", "comment": ""})
    print("3) Closed loop:", st["status"])
    print()
    print(st["summary"]["text"])
    print()
    print("Node order:", " → ".join(st["observability"]["node_order"]))
    print("Paid LLM calls:", p.llm.paid_calls)
