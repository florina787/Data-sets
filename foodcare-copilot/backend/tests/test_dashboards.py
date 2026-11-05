"""Data-source status and the quality overview are computed from stored records only."""

from __future__ import annotations

from app import datasources, quality
from app.enterprise import data
from app.vision import service, synthetic


def _batch(seed: int, supplier: str) -> dict:
    b = service.create_batch("val.viewer", f"seed {seed}", supplier=supplier)
    return service.add_image(b["id"], "val.viewer", synthetic.render(seed=seed)[0], "s.png")["batch"]


def test_data_sources_report_real_counts_and_planned_sources(platform):
    data.seed()
    before = {s["key"]: s for s in datasources.sources("val.viewer")}
    assert before["photos"]["status"] == "empty" and before["photos"]["records"] == 0
    assert before["sales"]["status"] == "synthetic" and before["sales"]["records"] > 0
    assert {k for k, s in before.items() if s["status"] == "not_connected"} == {"storage", "weather", "erp", "scales",
                                                                                  "video"}
    assert all(s["records"] == 0 for s in before.values() if s["status"] == "not_connected")
    _batch(1, "Synthetic farm A")
    after = {s["key"]: s for s in datasources.sources("val.viewer")}
    assert after["photos"]["status"] == "connected" and after["photos"]["records"] == 1
    assert after["suppliers"]["records"] == 1
    assert datasources.sources("maya.marketing")[0]["records"] == 0  # per-user


def test_quality_overview_totals_queue_and_filters(platform):
    a = _batch(1, "Synthetic farm A")
    _batch(2, "Synthetic farm B")
    o = quality.overview("val.viewer")
    assert o["totals"]["batches"] == 2 and o["totals"]["potatoes"] == 24
    assert o["recommendations"][0]["grade"] == "Not Good"  # worst first
    assert o["recommendations"][0]["action"] == "Reject candidate · needs approval"
    flagged = sum(1 for r in o["recommendations"] if r["grade"] in ("Moderate", "Not Good"))
    assert o["review"]["queue"] == flagged and o["review"]["rules_agreement_pct"] == 100.0
    bad = next(p for p in a["potatoes"] if p["grade"] == "Not Good")
    service.correct_potato(a["id"], "val.viewer", bad["potato_no"], "Good", "soil, not rot")
    o2 = quality.overview("val.viewer")
    assert o2["review"]["corrections"] == 1 and o2["review"]["queue"] == flagged - 1
    assert o2["review"]["rules_agreement_pct"] < 100
    only_a = quality.overview("val.viewer", supplier="Synthetic farm A")
    assert only_a["totals"]["batches"] == 1 and only_a["filters"]["suppliers"] == ["Synthetic farm A",
                                                                                  "Synthetic farm B"]
    assert quality.overview("maya.marketing")["totals"]["potatoes"] == 0
