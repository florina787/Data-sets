from datetime import UTC, datetime, timedelta

from backend.memory.db import make_engine
from backend.memory.db import session as db_session
from backend.memory.store import Store
from backend.memory.tables import ChatSession


def make_store(tmp_path):
    return Store(make_engine(tmp_path / "t.db"))


def test_session_lifecycle_and_title(tmp_path):
    st = make_store(tmp_path)
    cs = st.create_session()
    st.add_message(cs.id, "user", "How do I index PDFs?\nmore")
    st.add_message(cs.id, "assistant", "Use FAISS [1]", citations=[{"n": 1, "filename": "guide.pdf", "page": 2}])
    assert st.get_session(cs.id).title == "How do I index PDFs?"
    msgs = st.messages(cs.id)
    assert [m["role"] for m in msgs] == ["user", "assistant"] and msgs[1]["citations"][0]["page"] == 2
    assert st.recent_history(cs.id, 4) == [
        {"role": "user", "content": "How do I index PDFs?\nmore"},
        {"role": "assistant", "content": "Use FAISS [1]"},
    ]


def test_search_export_delete(tmp_path):
    st = make_store(tmp_path)
    a = st.create_session("Alpha")
    b = st.create_session("Beta")
    st.add_message(b.id, "user", "kubernetes autoscaling question")
    assert [s["id"] for s in st.list_sessions(query="kubernetes")] == [b.id]
    md = st.export_session(b.id)
    assert md.startswith("# Beta") and "kubernetes" in md
    assert '"messages"' in st.export_session(b.id, "json")
    assert st.delete_session(a.id) and st.get_session(a.id) is None
    assert st.clear_history() == 1 and st.list_sessions() == []


def test_retention_purge(tmp_path):
    st = make_store(tmp_path)
    old = st.create_session("old")
    new = st.create_session("new")
    with db_session(st.engine) as s:
        row = s.get(ChatSession, old.id)
        row.updated_at = datetime.now(UTC) - timedelta(days=40)
        s.add(row)
        s.commit()
    assert st.purge_expired(0) == 0  # 0 keeps everything
    assert st.purge_expired(30) == 1
    assert st.get_session(new.id) and not st.get_session(old.id)


def test_settings_validation(tmp_path):
    st = make_store(tmp_path)
    assert st.get_settings()["retention_days"] == 30
    assert st.update_settings({"retention_days": 7})["retention_days"] == 7
    try:
        st.update_settings({"evil": True})
    except KeyError:
        pass
    else:
        raise AssertionError("unknown settings must be rejected")
