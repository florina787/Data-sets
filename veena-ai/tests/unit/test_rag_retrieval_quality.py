"""Knowledge retrieval: resume-style questions never come back empty when the document has the answer,
diagnostics explain what was kept or rejected, and durations are computed, not guessed."""

from datetime import date

import pytest

from backend.rag.facts import employment_spans, experience_note
from backend.rag.service import expand_query
from tests.fixtures.resumes import resume_dates_only, resume_with_years

TODAY = date(2026, 11, 12)
ROLES = "Lead ML Engineer - March 2021 to Present\nML Engineer - June 2018 to February 2021\nSoftware Engineer - September 2016 to May 2018"


def test_employment_spans_parse_month_names_numeric_years_and_present():
    spans = employment_spans(ROLES + "\nIntern 06/2015 - 08/2015\nVolunteer 2012 – 2013", TODAY)
    assert [(s.start.isoformat(), s.end.isoformat()) for s in spans] == [
        ("2021-03-01", "2026-11-12"),
        ("2018-06-01", "2021-02-01"),
        ("2016-09-01", "2018-05-01"),
        ("2015-06-01", "2015-08-01"),
        ("2012-01-01", "2013-12-01"),
    ]


def test_experience_note_computes_total_and_lists_the_dates_used():
    note = experience_note("How many years of experience does she have?", [ROLES], TODAY)
    assert "about 10 years 2 months in total" in note and "September 2016" in note and "March 2021 to Present" in note


def test_experience_note_excludes_gaps_and_counts_overlaps_once():
    note = experience_note(
        "years of experience?",
        ["A - January 2010 to December 2011\nB - January 2015 to December 2016\nC - June 2016 to December 2016"],
        TODAY,
    )
    assert "about 6 years 11 months in total" in note  # Jan 2010 .. Dec 2016
    assert "about 3 years 11 months covered" in note  # 24 + 24 months, overlap once, minus 1


def test_explicit_statement_is_preferred():
    note = experience_note("how many years of experience", ["Engineer with 9 years of professional experience in NLP.", ROLES], TODAY)
    assert note.startswith("The document states its experience explicitly: “Engineer with 9 years of professional experience in NLP”")


@pytest.mark.parametrize("q", ["What programming languages are listed?", "Which companies?", "Summarise the resume"])
def test_no_duration_note_for_other_questions(q):
    assert experience_note(q, [ROLES], TODAY) is None


def test_no_note_without_dates_or_statement():
    assert experience_note("How many years of experience?", ["Skills: Python, SQL"], TODAY) is None


def test_query_expansion_bridges_question_and_resume_vocabulary():
    assert "present" in expand_query("most recent role") and "python" in expand_query("programming languages")
    assert expand_query("unrelated words here") == "unrelated words here"


def _ingest(client, name, data):
    cid = client.post("/api/knowledge/collections", json={"name": name, "kind": "resume"}).json()["id"]
    up = client.post(f"/api/knowledge/collections/{cid}/documents", files={"file": ("Resume.pdf", data, "application/pdf")})
    assert up.status_code == 200, up.text
    return cid


def test_search_returns_diagnostics_and_weak_tier(client):
    cid = _ingest(client, "r", resume_dates_only())
    strict = client.post("/api/knowledge/search", json={"query": "zzqx unrelated", "collection_ids": [cid], "min_score": 0.9}).json()
    d = strict["diagnostics"]
    assert d["indexed_passages"] >= 1 and d["candidates"] >= 1 and d["small_collection_mode"] is True
    assert strict["results"] == [] and "relevance floor 0.9" in d["reason"]
    loose = client.post(
        "/api/knowledge/search", json={"query": "health insurance policy", "collection_ids": [cid], "min_score": 0.9, "include_weak": True}
    ).json()
    assert loose["results"] and all(r["weak"] for r in loose["results"]), "keyword-sharing passages offered, flagged weak"
    unrelated = client.post(
        "/api/knowledge/search", json={"query": "zzqx", "collection_ids": [cid], "min_score": 0.9, "include_weak": True}
    ).json()
    assert unrelated["results"] == [] or all(r["vector_score"] >= 0.12 for r in unrelated["results"])


def test_pdf_extraction_and_chunks_keep_the_whole_resume():
    from backend.rag.chunk import chunk_pages
    from backend.rag.extract import extract

    pages = extract(resume_with_years(), ".pdf")
    chunks = chunk_pages(pages)
    assert chunks and all(c.text.strip() for c in chunks)
    text = " ".join(c.text for c in chunks)
    for must in (
        "9 years of professional experience",
        "Northwind Analytics",
        "Contoso Health",
        "Fabrikam Ltd",
        "Python, Java, TypeScript, SQL, Go",
        "LangGraph",
        "MSc Computer Science",
    ):
        assert must in text, must


def test_reindex_rebuilds_the_vector_index(client):
    cid = _ingest(client, "r", resume_with_years())
    out = client.post(f"/api/knowledge/collections/{cid}/reindex").json()
    assert out["passages"] >= 1 and out["indexed"] == out["passages"] and out["empty_passages"] == 0
    assert client.post("/api/knowledge/collections/nope/reindex").status_code == 404
    after = client.post("/api/knowledge/search", json={"query": "Contoso", "collection_ids": [cid]}).json()
    assert after["results"], after["diagnostics"]


def test_relevance_floor_setting_is_validated(client):
    assert client.get("/api/settings").json()["retrieval_min_score"] is None  # automatic: calibrated for the embedder
    assert client.patch("/api/settings", json={"retrieval_min_score": 0.35}).json()["retrieval_min_score"] == 0.35
    assert client.patch("/api/settings", json={"retrieval_min_score": None}).json()["retrieval_min_score"] is None
    for bad in (-0.1, 1.5, "high", True):
        assert client.patch("/api/settings", json={"retrieval_min_score": bad}).status_code == 400


def test_chat_with_resume_gets_evidence_and_computed_duration(client, llm):
    cid = _ingest(client, "r", resume_dates_only())
    sid = client.post("/api/sessions", json={}).json()["id"]
    client.post("/api/chat", json={"session_id": sid, "text": "how many years of experience", "collection_ids": [cid]})
    user = llm.calls[-1]["messages"][-1]["content"]
    assert "Northwind Analytics" in user and "Computed by VEENA from the date ranges" in user
