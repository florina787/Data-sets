from datetime import timezone

import pytest
from sqlalchemy import func, select

from app.db import session_scope
from app.ingestion import twcs
from app.models.orm import Conversation, Dataset, Exclusion, Message
from tests.conftest import FIXTURES

MINI = FIXTURES / "mini_twcs.csv"


@pytest.mark.parametrize("raw,expected", [("True", True), ("false", False), ("1", True), ("0", False), (" TRUE ", True)])
def test_explicit_boolean_parsing(raw, expected):
    assert twcs.parse_bool(raw) is expected


@pytest.mark.parametrize("raw", ["maybe", "", "yes please", None, "2"])
def test_boolean_rejects_ambiguous_values(raw):
    with pytest.raises(ValueError):
        twcs.parse_bool(raw)


def test_timestamp_parsing_twitter_and_iso():
    dt = twcs.parse_timestamp("Tue Oct 31 22:10:47 +0000 2017")
    assert (dt.year, dt.month, dt.day, dt.hour, dt.tzinfo) == (2017, 10, 31, 22, timezone.utc)
    assert twcs.parse_timestamp("2017-10-31T22:10:47Z").hour == 22
    with pytest.raises(ValueError):
        twcs.parse_timestamp("not-a-date")


def test_string_safe_ids():
    assert twcs.parse_id("119237.0") == "119237"
    assert twcs.parse_id("00012") == "12"
    assert twcs.parse_id("98765432109876543210") == "98765432109876543210"  # beyond float precision, kept exact
    assert twcs.parse_id_list("1,2, 3") == ["1", "2", "3"]
    with pytest.raises(ValueError):
        twcs.parse_id("12abc")


def test_schema_validation_rejects_missing_columns(tmp_path):
    p = tmp_path / "bad.csv"
    p.write_text("id,text\n1,hello\n")
    with pytest.raises(twcs.SchemaError):
        twcs.inspect_schema(p)


def test_reply_graph_branches_missing_parents_cycles_duplicates():
    g = twcs.build_graph(MINI)
    st = g.stats
    assert st["exact_duplicates_dropped"] == 1
    assert st["rejected_invalid_boolean"] == 1
    assert st["invalid_timestamp"] == 1
    assert st["messages_with_missing_parent"] == 1
    assert st["messages_in_cycles"] == 2
    threads = {t.root: t for t in g.threads}
    t1 = threads["1"]
    assert t1.members[0] == "1" and set(t1.members) == {"1", "2", "3", "4", "5"}
    assert t1.branch_count == 1  # message 1 has two support replies -> one branch point, one conversation
    assert t1.children["1"] == ["2", "3"]
    assert "30" not in threads and "31" not in threads  # cycle members never become a conversation
    reasons = twcs.apply_eligibility(g, "kaggle_twcs", 50)
    assert reasons["root_parent_missing"] == 1
    assert reasons["single_message"] == 1
    assert reasons["not_customer_initiated"] == 1
    eligible = sorted(t.root for t in g.threads if t.eligible)
    assert eligible == ["1", "10", "60", "80"]


def test_messages_never_shared_between_conversations():
    g = twcs.build_graph(MINI)
    seen = [m for t in g.threads for m in t.members]
    assert len(seen) == len(set(seen))


def test_same_author_does_not_merge_conversations():
    g = twcs.build_graph(MINI)
    roots_by_support = [t.root for t in g.threads if any(g.nodes[m].author == "AcmeHelp" for m in t.members)]
    assert len(roots_by_support) > 1


def test_stable_ids_and_reproducible_sampling():
    g = twcs.build_graph(MINI)
    twcs.apply_eligibility(g, "kaggle_twcs", 50)
    a = [t.key for t in twcs.sample_threads(g.threads, 2, seed=7)]
    b = [t.key for t in twcs.sample_threads(g.threads, 2, seed=7)]
    c_all = [t.key for t in twcs.sample_threads(g.threads, 10, seed=7)]
    assert a == b and len(a) == 2
    assert len(c_all) == 4  # never more than the eligible count
    assert twcs.conversation_key("kaggle_twcs", "1") == twcs.conversation_key("kaggle_twcs", "1")
    seeds = {tuple(t.key for t in twcs.sample_threads(g.threads, 2, seed=s)) for s in range(10)}
    assert len(seeds) > 1


def test_import_persists_manifest_roles_and_redaction(imported_id):
    with session_scope() as s:
        ds = s.get(Dataset, imported_id)
        m = ds.manifest
        assert m["sampling"]["selected"] == 4 and m["sampling"]["eligible"] == 4
        assert m["file_hash_sha256"] and m["parser_version"] == twcs.PARSER_VERSION
        assert m["branching"]["selected"]["branched_threads"] == 1
        assert set(m["exclusions"]) >= {"root_parent_missing", "single_message", "not_customer_initiated"}
        assert s.scalar(select(func.count()).where(Exclusion.dataset_id == imported_id)) >= 3
        # Unit of analysis: messages belong to exactly one conversation; counts add up.
        msgs = s.scalar(select(func.count()).where(Message.dataset_id == imported_id))
        total = s.scalar(select(func.sum(Conversation.message_count)).where(Conversation.dataset_id == imported_id))
        assert msgs == total == m["counts"]["selected_messages"]
        roles = dict(s.execute(select(Message.source_id, Message.role).where(Message.dataset_id == imported_id)).all())
        assert roles["1"] == "customer" and roles["2"] == "support"
        texts = s.scalars(select(Message.text).where(Message.dataset_id == imported_id)).all()
        assert all("@115001" not in t for t in texts)  # customer handles redacted
        assert any("@AcmeHelp" in t for t in texts)  # public brand support handle kept
        authors = s.scalars(select(Message.author_ref).where(Message.dataset_id == imported_id, Message.role == "customer")).all()
        assert all(a.startswith("cust_") for a in authors)


def test_reimport_is_idempotent(imported_id):
    from app.ingestion.importer import run_import
    again = run_import(MINI, kind="kaggle_twcs", name="mini", source_label="test fixture", synthetic=False)
    assert again == imported_id
    with session_scope() as s:
        assert s.scalar(select(func.count()).where(Conversation.dataset_id == imported_id)) == 4


def test_cancellation_removes_partial_dataset():
    from app.ingestion.importer import run_import
    with pytest.raises(twcs.Cancelled):
        run_import(MINI, kind="cancel_test", name="x", source_label="t", synthetic=False, should_cancel=lambda: True)
    with session_scope() as s:
        assert s.scalar(select(func.count()).where(Dataset.kind == "cancel_test")) == 0
