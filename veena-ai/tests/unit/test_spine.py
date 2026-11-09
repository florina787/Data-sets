"""Semantic-spine measures: ontology, knowledge, context and procedure."""

from backend.agents import spine


def test_extracts_each_ontology_type():
    ents = spine.extract_entities(
        "The index uses FAISS IndexIDMap2 [1]. Meta AI Research built it in 2017; it searches 1,000,000 vectors in 3 ms. Call build_index first."
    )
    assert ents["faiss"] == "acronym"
    assert ents["indexidmap2"] == "name"
    assert ents["meta ai research"] == "name"
    assert ents["build_index"] == "identifier"
    assert {"2017", "1000000", "3 ms"} <= {e for e, t in ents.items() if t == "figure"}
    assert "1" not in ents  # citation markers are not claims


def test_sentence_openers_and_code_blocks_are_not_entities():
    ents = spine.extract_entities("This works. Then restart it.\n```python\nMyClass = Foo()\n```\n1. Install it")
    assert ents == {}


def test_knowledge_graph_links_cooccurring_entities():
    g = spine.knowledge_graph(["FAISS stores vectors for VEENA.", "VEENA keeps sessions in SQLite.", "FAISS and VEENA again."])
    ids = {n["id"] for n in g["nodes"]}
    assert {"faiss", "veena", "sqlite"} <= ids
    edges = {(e["a"], e["b"]): e["weight"] for e in g["edges"]}
    assert edges[("faiss", "veena")] == 2 and edges[("sqlite", "veena")] == 1
    assert g["ontology"]["acronym"] == 2 and g["ontology"]["name"] == 1 and g["passages"] == 3


def _measure(answer, *, documents="", evidence=None, cited=(), path=None, has_image=False, needs_retrieval=False, outcome="resolved"):
    evidence = evidence if evidence is not None else ([{"n": 1, "text": documents}] if documents else [])
    return spine.measure_turn(
        question="Which index does FAISS use?",
        answer=answer,
        context_blocks={"documents": documents},
        evidence=evidence,
        cited=list(cited),
        path=path or spine.expected_path(has_image, needs_retrieval),
        has_image=has_image,
        needs_retrieval=needs_retrieval,
        outcome=outcome,
    )


DOC = "VEENA stores vectors in FAISS using an IndexIDMap2 inner product index built in 2017."


def test_grounded_answer_scores_full_support():
    m = _measure("FAISS uses IndexIDMap2 [1].", documents=DOC, cited=[1], needs_retrieval=True)
    assert m["knowledge"]["support_rate"] == 1.0 and m["knowledge"]["unsupported"] == []
    assert m["context"]["citation_rate"] == 1.0
    assert m["context"]["utilization"] > 0
    assert m["procedure"]["adherent"] is True


def test_invented_names_and_figures_are_caught():
    m = _measure("FAISS uses HNSW, made by Google Brain in 2019, with 99% recall [1].", documents=DOC, cited=[1], needs_retrieval=True)
    k = m["knowledge"]
    assert k["support_rate"] < 0.5
    assert {"hnsw", "google brain", "2019", "99%"} <= set(k["unsupported"])
    assert k["unsupported_figures"] == 2


def test_no_claims_gives_no_rate_rather_than_a_perfect_one():
    m = _measure("It depends on what you need.", documents=DOC, needs_retrieval=True)
    assert m["knowledge"]["claims"] == 0 and m["knowledge"]["support_rate"] is None


def test_skipped_step_breaks_adherence():
    # Documents were requested, but the path went straight to compose.
    m = _measure("ok", documents=DOC, path=["supervisor", "compose", "generate", "govern"], needs_retrieval=True)
    assert m["procedure"]["adherent"] is False
    assert m["procedure"]["expected"] == ["supervisor", "retrieve", "compose", "generate", "govern"]


def test_illegal_transition_is_detected():
    m = _measure("ok", path=["supervisor", "generate", "govern"])
    assert m["procedure"]["legal_transitions"] is False and m["procedure"]["adherent"] is False


def test_cancelled_turn_is_adherent_up_to_where_it_stopped():
    m = _measure("partial", path=["supervisor", "compose", "generate"], outcome="cancelled")
    assert m["procedure"]["adherent"] is True


def test_outcomes():
    assert spine.classify_outcome({"flags": []}, False) == "resolved"
    assert spine.classify_outcome({"flags": [{"kind": "uncited"}]}, False) == "flagged"
    assert spine.classify_outcome({"flags": [{"kind": "no_evidence"}]}, False) == "escalated"
    assert spine.classify_outcome(None, True) == "cancelled"
    assert spine.classify_outcome(None, False, failed=True) == "failed"


def test_no_material_means_no_fact_score():
    # A general question with nothing handed to the agent: entities may be known, not invented.
    m = spine.measure_turn(
        question="What is Python?",
        answer="Python was created by Guido van Rossum in 1991.",
        context_blocks={"history": "earlier chat"},
        evidence=[],
        cited=[],
        path=spine.expected_path(False, False),
        has_image=False,
        needs_retrieval=False,
        outcome="resolved",
    )
    assert m["knowledge"]["claims"] >= 2 and m["knowledge"]["support_rate"] is None
    assert m["knowledge"]["grounded_context"] is False


def test_clock_times_are_one_figure():
    ents = spine.extract_entities("Ingestion runs at 02:00 UTC.")
    assert ents.get("02:00") == "figure" and "00" not in ents and "02" not in ents


def test_unbacked_flag_rules():
    assert spine.unbacked_flag({"support_rate": None, "unsupported": ["x"]}) is None  # nothing was given
    assert spine.unbacked_flag({"support_rate": 0.8, "unsupported": ["redis"], "unsupported_figures": 0}) is None
    assert spine.unbacked_flag({"support_rate": 0.9, "unsupported": ["42%"], "unsupported_figures": 1})["kind"] == "unbacked_claims"
    assert spine.unbacked_flag({"support_rate": 0.25, "unsupported": ["anthropic", "openai"], "unsupported_figures": 0}) is not None


def test_screen_only_answers_are_flagged_for_figures_not_general_names():
    k = {"support_rate": 0.2, "unsupported": ["python", "dictionary"], "unsupported_figures": 0}
    assert spine.unbacked_flag(k, ["question", "screen"]) is None
    assert spine.unbacked_flag(k, ["documents", "question"]) is not None  # documents: names still count
    k2 = {"support_rate": 0.5, "unsupported": ["99%"], "unsupported_figures": 1}
    assert spine.unbacked_flag(k2, ["question", "screen"]) is not None  # an invented figure on screen still counts
