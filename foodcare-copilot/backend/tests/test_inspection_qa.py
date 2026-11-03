"""Ask Copilot about stored potato inspections (SYNTHETIC rendered images)."""

from __future__ import annotations

from app.copilot import engine
from app.vision import service, synthetic

from conftest import user


def _batch(seed: int, supplier: str = "Synthetic farm A") -> dict:
    b = service.create_batch("val.viewer", f"seed {seed}", supplier=supplier, lot_code=f"LOT-{seed}")
    return service.add_image(b["id"], "val.viewer", synthetic.render(seed=seed)[0], "s.png")["batch"]


def ask(q: str, conv: str | None = None) -> dict:
    return engine.ask(q, user("val.viewer"), conv)


def test_counts_and_defective_potatoes_come_from_the_stored_batch(platform):
    b = _batch(1)
    a = ask("How many potatoes are detected and which are defective?")
    assert a["intents"] == ["inspection"] and a["answered"]
    assert "12 potatoes detected" in a["answer"] and b["id"] in a["answer"]
    flagged = [x for x in b["potatoes"] if x["grade"] in ("Not Good", "Moderate")]
    for x in flagged:
        assert f"#{x['potato_no']} {x['grade']}" in a["answer"]
    assert "not a trained or validated defect classifier" in a["answer"]
    assert {s["ref"] for s in a["sources"]} == {f"inspection_batches:{b['id']}"}


def test_individual_potato_and_pronoun_follow_up(platform):
    b = _batch(1)
    bad = next(x for x in b["potatoes"] if x["grade"] == "Not Good")
    first = ask(f"Show me potato #{bad['potato_no']}")
    assert f"**Potato #{bad['potato_no']}**" in first["answer"] and "**Not Good**" in first["answer"]
    assert first["attachments"] == [{"type": "potato", "batch_id": b["id"], "potato_no": bad["potato_no"]}]
    why = ask("Why was it rejected?", first["conversation_id"])
    assert f"Potato #{bad['potato_no']}" in why["answer"] and bad["reasons"][0] in why["answer"]
    missing = ask("Show me potato #99", first["conversation_id"])
    assert "there is no #99" in missing["answer"]


def test_spec_supplier_comparison_and_history(platform):
    older = _batch(2, supplier="Synthetic farm B")
    newer = _batch(3)
    spec = ask("How many meet the selected processing specifications?")
    assert f"Good: {newer['summary']['meets_spec']} of" in spec["answer"]
    supplier = ask("Which supplier provided these potatoes?")
    assert "Synthetic farm A" in supplier["answer"] and "not verified" in supplier["answer"]
    compare = ask(f"Compare {newer['id']} with the previous batch")
    assert newer["id"] in compare["answer"] and older["id"] in compare["answer"] and "points" in compare["answer"]
    history = ask("Show my inspection history")
    assert older["id"] in history["answer"] and newer["id"] in history["answer"]


def test_conversation_is_linked_to_its_batch(platform):
    b = _batch(1)
    a = ask("Which potatoes are defective?")
    _batch(2)  # a newer batch must not hijack the conversation
    follow = ask("How many potatoes are detected?", a["conversation_id"])
    assert b["id"] in follow["answer"]


def test_no_inspections_and_other_users_batches(platform):
    assert "No potato inspections are recorded" in ask("Which potatoes are defective?")["answer"]
    _batch(1)
    other = engine.ask("Which potatoes are defective?", user("maya.marketing"))
    assert "No potato inspections are recorded" in other["answer"]


def test_yield_and_money_questions_are_not_invented(platform):
    _batch(1)
    a = ask("What is the financial impact of this batch of potatoes?")
    assert "not calculated from inspections yet" in a["answer"] and "$" not in a["answer"]
