"""Browser role (Wren 🧭): simulated navigation over fictional fixture pages.

No real browser is launched and no network request is made.
"""
from __future__ import annotations

from agents.base import AgentResult, TransientSimulatedError, agent_node
from services import scenario_loader as fixtures
from services.tool_registry import ToolRecorder
from workflows.context import MuseContext
from workflows.state import MuseState


@agent_node("browser", "browser")
def browser(state: MuseState, ctx: MuseContext, tools: ToolRecorder) -> AgentResult:
    params = state.get("params") or {}
    task_key = params.get("task", "hotel_search")
    task = fixtures.browser_fixture()["tasks"][task_key]
    steps = [{"step": "Browser action requested", "detail": task["title"]}]

    page = tools.call("browser.simulate_navigate", {"task": task_key})
    attempts = (state.get("retries") or {}).get("browser", 0)
    if task["flaky_first_attempt"] and attempts == 0:
        raise TransientSimulatedError(f"Simulated page-load timeout on {page['url'].split('/')[2]}")
    steps.append({"step": "Navigation simulated", "detail": page["url"]})
    results = page["page_data"]["results"]
    steps.append({"step": "Page data retrieved from fixture", "detail": f"{len(results)} item(s)"})

    form = page.get("form")
    if form:
        tools.call("browser.simulate_fill_form", {"form": form})
        steps.append({"step": "Form populated", "detail": ", ".join(form)})

    updates = {}
    if task["action_tool"]:
        verb = "booking" if task["action_tool"].endswith("booking") else "form submission"
        updates["action"] = {
            "tool": task["action_tool"], "agent": "browser",
            "summary": f"Simulate the {verb} on {page['url']} — fictional site, no real transaction.",
            "args": {"url": page["url"], "task": task_key, "form": form or {},
                     "item": results[0]["name"] if results else "", "price": results[0]["price"] if results else 0},
        }
        steps.append({"step": "Approval requested", "detail": "Consequential step handed to Pearl & Cora"})

    best = min((r for r in results if r.get("rating")), key=lambda r: (-r["rating"], r["price"]), default=None)
    head = f"{task['title']}: read {len(results)} item(s) from {page['url'].split('/')[2]}"
    head += f"; top pick {best['name']} ({best['price']} ✦)." if best else "."
    return AgentResult(
        output={"kind": "browser", "task": task_key, "url": page["url"], "results": results, "form": form,
                "steps": steps, "attempts": attempts + 1, "top_pick": best, "headline": head},
        message=f"Completed simulated navigation after {attempts + 1} attempt(s).",
        updates=updates,
    )
