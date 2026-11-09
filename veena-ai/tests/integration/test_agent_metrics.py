"""Agent measurement end to end: every chat turn is traced and scored."""

from tests.conftest import ndjson


def _session(client):
    return client.post("/api/sessions", json={}).json()["id"]


def _docs(client):
    col = client.post("/api/knowledge/collections", json={"name": "Docs"}).json()
    doc = "VEENA stores vectors in FAISS using an IndexIDMap2 index.\n\nSessions live in SQLite with WAL journaling."
    client.post(f"/api/knowledge/collections/{col['id']}/documents", files={"file": ("notes.md", doc.encode(), "text/markdown")})
    return col["id"]


def test_turns_are_traced_and_scored(client, llm):
    cid = _docs(client)
    sid = _session(client)
    llm.reply = "FAISS uses IndexIDMap2 [1]."
    good = ndjson(client.post("/api/chat", json={"session_id": sid, "text": "Which FAISS index is used?", "collection_ids": [cid]}))[-1]
    assert good["spine"]["outcome"] == "resolved" and good["spine"]["support_rate"] == 1.0
    assert good["spine"]["path"] == ["supervisor", "retrieve", "compose", "generate", "govern"]

    llm.reply = "FAISS uses HNSW from Google Brain with 97% recall [1]."
    bad = ndjson(client.post("/api/chat", json={"session_id": sid, "text": "Which FAISS index is used?", "collection_ids": [cid]}))[-1]
    assert bad["spine"]["support_rate"] < 0.5 and "google brain" in bad["spine"]["unsupported"]
    assert bad["spine"]["outcome"] == "flagged"
    assert any(f["kind"] == "unbacked_claims" and "97%" in f["detail"] for f in bad["governance"]["flags"])

    llm.reply = "The documents do not cover this."
    ndjson(client.post("/api/chat", json={"session_id": sid, "text": "Kubernetes autoscaling thresholds?", "collection_ids": [cid]}))

    sc = client.get("/api/agents/scorecard").json()
    assert sc["turns"] == 3
    assert sc["outcomes"] == {"resolved": 1, "flagged": 1, "escalated": 1, "cancelled": 0, "failed": 0}
    assert sc["procedure"]["adherence"] == 1.0
    assert {"from": "supervisor", "to": "retrieve", "count": 3} in sc["procedure"]["transitions"]
    assert sc["agents"][0]["agent"] == "knowledge" and sc["agents"][0]["turns"] == 3
    assert 0 < sc["knowledge"]["support_rate"] < 1
    assert sc["ontology"]["figure"] >= 1  # the invented "97%"
    assert sc["context"]["latest"]["graph"]["nodes"]
    assert len(sc["recent"]) == 3 and sc["recent"][0]["outcome"] == "escalated"
    assert sc["daily"][-1]["turns"] == 3


def test_plain_question_path_skips_retrieval(client, llm):
    sid = _session(client)
    llm.reply = "A hash map stores key-value pairs."
    done = ndjson(client.post("/api/chat", json={"session_id": sid, "text": "What is a hash map?"}))[-1]
    assert done["spine"]["path"] == ["supervisor", "compose", "generate", "govern"]
    assert done["spine"]["citation_rate"] is None
    saved = client.get(f"/api/sessions/{sid}").json()["messages"][-1]
    assert saved["meta"]["spine"]["outcome"] == "resolved"


def test_failed_generation_is_traced(client, llm):
    sid = _session(client)
    llm.fail_next = True
    ndjson(client.post("/api/chat", json={"session_id": sid, "text": "hello?"}))
    sc = client.get("/api/agents/scorecard").json()
    assert sc["outcomes"]["failed"] == 1 and sc["success_rate"] == 0.0
    assert sc["recent"][0]["path"] == ["supervisor", "compose", "generate"]


def test_deleting_a_session_deletes_its_traces(client, llm):
    sid = _session(client)
    ndjson(client.post("/api/chat", json={"session_id": sid, "text": "hi?"}))
    assert client.get("/api/agents/scorecard").json()["turns"] == 1
    client.delete(f"/api/sessions/{sid}")
    assert client.get("/api/agents/scorecard").json()["turns"] == 0


def test_knowledge_graph_endpoint(client):
    cid = _docs(client)
    g = client.get(f"/api/agents/knowledge-graph?collection_id={cid}").json()
    ids = {n["id"] for n in g["nodes"]}
    assert {"faiss", "veena", "sqlite", "wal"} <= ids
    assert any({e["a"], e["b"]} == {"faiss", "veena"} for e in g["edges"])
    assert client.get("/api/agents/knowledge-graph?collection_id=nope").status_code == 404


def test_earlier_answers_do_not_back_later_claims(client, llm):
    cid = _docs(client)
    sid = _session(client)
    llm.reply = "It was built by Initech in 2011 [1]."
    first = ndjson(client.post("/api/chat", json={"session_id": sid, "text": "Who built it?", "collection_ids": [cid]}))[-1]
    assert {"initech", "2011"} <= set(first["spine"]["unsupported"])
    # Repeating its own invention does not make it backed.
    second = ndjson(client.post("/api/chat", json={"session_id": sid, "text": "Say that again?", "collection_ids": [cid]}))[-1]
    assert {"initech", "2011"} <= set(second["spine"]["unsupported"])
    first_saved = [m for m in client.get(f"/api/sessions/{sid}").json()["messages"] if m["role"] == "assistant"][0]
    assert any(f["kind"] == "unbacked_claims" for f in first_saved["meta"]["governance"]["flags"])
