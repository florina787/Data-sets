"""Citation verification, PlaybookGuard, PrivilegeGuard, assurance and drafting rules."""

from app.access.matter_access import build_access_scope
from app.assurance import pipeline
from app.citations import verifier
from app.playbooks import guard as playbookguard
from app.privilege import guard as privilegeguard


def _scope(store):
    return build_access_scope(store, store.users["U-002"], "M-1001")


def test_citation_supported(store):
    v = verifier.verify(store, _scope(store), "p", "Sole-discretion consent rights are a playbook deviation to be negotiated.",
                        {"doc_id": "KN-PB-MA", "section_id": "s2", "quote": "Sole-discretion consent is a deviation to be negotiated"})
    assert v.status == "SUPPORTED"


def test_citation_partially_supported_wrong_figure(store):
    v = verifier.verify(store, _scope(store), "p", "The M&A playbook treats post-completion notice within 60 days as acceptable.",
                        {"doc_id": "KN-PB-MA", "section_id": "s1", "quote": "Post-completion notice of a change of control within 30 days is acceptable"})
    assert v.status == "PARTIALLY_SUPPORTED" and "60" in " ".join(v.reasons)


def test_citation_partially_supported_placeholder(store):
    doc = next(d for d in store.matter_documents("M-1001") if "[NTD" in d.sections[0].text)
    v = verifier.verify(store, _scope(store), "p", "'Change of Control' is defined in the definitions clause of the agreement.",
                        {"doc_id": doc.doc_id, "section_id": "s1", "quote": doc.sections[0].text.split(" \"Effective")[0]})
    assert v.status == "PARTIALLY_SUPPORTED" and v.checks["placeholder"]


def test_citation_unsupported(store):
    v = verifier.verify(store, _scope(store), "p", "Maple Industries has agreed to indemnify the buyer for all consent costs.",
                        {"doc_id": "KN-PREC-001", "section_id": "s1", "quote": "Maple Industries has agreed to indemnify the buyer"})
    assert v.status == "UNSUPPORTED"


def test_missing_citation_is_not_invented(store):
    v = verifier.verify(store, _scope(store), "p", "Courts always enforce consent requirements.", None)
    assert v.status == "UNSUPPORTED" and v.doc_id is None


def test_source_not_found(store):
    assert verifier.verify(store, _scope(store), "p", "x", {"doc_id": "KN-PB-MA", "section_id": "schedule-4"}).status == "SOURCE_NOT_FOUND"
    assert verifier.verify(store, _scope(store), "p", "x", {"doc_id": "NOPE-1", "section_id": "s1"}).status == "SOURCE_NOT_FOUND"


def test_citation_to_unauthorised_source_reported_not_found(store):
    v = verifier.verify(store, _scope(store), "p", "The limitation defence is strong.",
                        {"doc_id": "KN-BETA-RN", "section_id": "s1", "quote": "strong prospect"})
    assert v.status == "SOURCE_NOT_FOUND" and v.evidence_text is None


def test_hallucinated_memo_8_1_1(store):
    memo = store.pregenerated["WP-MEMO-MAPLE-001"]
    res = [verifier.verify(store, _scope(store), p["pid"], p["claim"], p["citation"]) for p in memo["propositions"]]
    s = verifier.summarize_results(res)
    assert (s["SUPPORTED"], s["PARTIALLY_SUPPORTED"], s["UNSUPPORTED"]) == (8, 1, 1)
    a = pipeline.evaluate(propositions=memo["propositions"], verifications=[r.model_dump() for r in res], playbook_results=[],
                          policy_decision="PERMITTED_WITH_CONTROLS", privilege_flags=[], destination="external_client")
    assert a.status == "REVIEW_REQUIRED" and not a.external_delivery_allowed
    assert "NOT a measure of legal correctness" in a.meaning


def test_playbook_clause_and_recommendation(store):
    pb = store.playbooks["PB-MA-COC"]
    assert playbookguard.classify_clause(pb, "c", "consent which may be withheld in the Supplier's sole discretion").result == "DEVIATION"
    assert playbookguard.classify_clause(pb, "c", "shall terminate automatically upon a Change of Control").result == "ESCALATION_REQUIRED"
    r = playbookguard.check_recommendation(pb, "R1", "Accept unrestricted counterparty veto over the Change of Control.")
    assert r.result == "ESCALATION_REQUIRED" and r.rule_id == "MA-COC-05"


def test_privilege_guard_never_definitive():
    flags = privilegeguard.evaluate(active_matter_id="M-1004", active_client_id="C-004", destination="external_client",
                                    sources=[{"doc_id": "X", "matter_id": "M-1004", "client_id": "C-004", "sensitivity": "privileged",
                                              "title": "Memo", "text": "Attorney work product prepared in anticipation of litigation."}])
    assert any(f.label == "POTENTIAL PRIVILEGE RISK" and f.requires_lawyer_review for f in flags)
    assert all("not a privilege determination" in f.detail or f.flag_type != "POTENTIAL_PRIVILEGE" for f in flags)
    cross = privilegeguard.evaluate(active_matter_id="M-1001", active_client_id="C-001", destination="internal",
                                    sources=[{"doc_id": "B", "matter_id": "M-1003", "client_id": "C-003", "sensitivity": "confidential",
                                              "title": "t", "text": "t"}])
    assert {f.flag_type for f in cross} >= {"CROSS_MATTER_EXPOSURE", "CROSS_CLIENT_EXPOSURE"}


def test_assurance_score_formula_is_deterministic():
    props = [{"pid": f"P{i}", "claim": "c", "citation": {"doc_id": "d"}, "material": True} for i in range(4)]
    vers = [{"pid": "P0", "status": "SUPPORTED"}, {"pid": "P1", "status": "SUPPORTED"},
            {"pid": "P2", "status": "PARTIALLY_SUPPORTED"}, {"pid": "P3", "status": "SOURCE_NOT_FOUND"}]
    a = pipeline.evaluate(propositions=props, verifications=vers, playbook_results=[], policy_decision="PERMITTED",
                          privilege_flags=[])
    # 0.2*1 + 0.3*0.625 + 0.1*1 + 0.15*1 + 0.1*1 + 0.15*1 - 0.5*0.25 = 0.7625 -> REVIEW_REQUIRED (>= FAIL threshold)
    assert a.score == 0.7625 and a.status == "REVIEW_REQUIRED"
