import io
import zipfile

import pandas as pd
import pytest

from app.data.ingestion import load_dataset, map_columns
from app.data.normalization import normalize_messages, split_noise
from app.data.validation import quality_report
from app.governance.pii import contains_pii, mask_text, pseudonymize


def test_split_noise_removes_trailing_lowercase_filler():
    assert split_noise("It’s urgent. Please expedite. sglcuk scvgay tnah") == ("It’s urgent. Please expedite.", 3)


def test_split_noise_keeps_text_when_tail_is_not_filler():
    assert split_noise("Order 123 failed. Call me Bob")[0] == "Order 123 failed. Call me Bob"
    assert split_noise("no terminator here") == ("no terminator here", 0)


def test_map_columns_aliases_and_missing():
    m = map_columns(["conv_id", "turn_index", "timestamp", "role", "text"])
    assert m["conversation_id"] == "conv_id" and m["speaker_role"] == "role"
    with pytest.raises(ValueError, match="Required columns missing"):
        map_columns(["id", "message"])


def test_load_zip_ignores_macos_resource_forks(tmp_path):
    p = tmp_path / "d.zip"
    csv = "conv_id,turn_index,timestamp,role,text,customer_name,agent_name\nC0000001,0,2025-01-01T00:00:00,customer,Hi there.,A,B\n"
    with zipfile.ZipFile(p, "w") as z:
        z.writestr("cs.csv", csv)
        z.writestr("__MACOSX/._cs.csv", "junk")
    ds = load_dataset(p)
    assert ds.member == "cs.csv" and len(ds.frame) == 1 and ds.delimiter == ","


def test_load_rejects_archive_without_csv(tmp_path):
    p = tmp_path / "d.zip"
    with zipfile.ZipFile(p, "w") as z:
        z.writestr("readme.txt", "x")
    with pytest.raises(ValueError, match="No CSV"):
        load_dataset(p)


def _frame(rows):
    df = pd.DataFrame(rows, columns=["conversation_id", "turn_index", "timestamp", "speaker_role", "text", "customer_name", "agent_name"])
    df["source_row"] = range(2, len(df) + 2)
    return df


def test_normalize_and_quality_checks_detect_problems():
    df = _frame([
        ["C1", "0", "2025-01-02T00:00:00", "customer", "Hi. abc def", "Ann", "AgentX"],
        ["C1", "1", "2025-01-01T00:00:00", "agent", "Hello.", "Ann", "AgentX"],  # timestamp goes backwards
        ["C1", "1", "not a date", "bot", "", "Ann", ""],  # duplicate turn, bad ts, unknown role, empty, no agent
    ])
    m = normalize_messages(df, "original", "x.csv")
    assert m.loc[0, "clean_text"] == "Hi." and m.loc[0, "noise_token_count"] == 2
    assert m.loc[0, "customer_id"].startswith("CUST-") and "Ann" not in m.loc[0, "customer_id"]
    report = {c["check"]: c["count"] for c in quality_report(m)["checks"]}
    assert report["duplicate_turn_index"] == 1
    assert report["missing_timestamp"] == 1
    assert report["unknown_speaker"] == 1
    assert report["empty_text"] == 1
    assert report["missing_agent"] == 1
    assert report["timestamps_not_in_turn_order"] == 1


def test_pii_masking():
    text, counts = mask_text("Mail jane.doe@example.com or call +44 7911 123456, card 4111 1111 1111 1111, upi bob@okaxis")
    assert "example.com" not in text and "7911" not in text and "4111" not in text and "okaxis" not in text
    assert counts["email"] == 1 and counts["card_number"] == 1
    assert not contains_pii("I have issued a refund. You’ll see it in 3-5 business days.")
    assert pseudonymize("x", "CUST") == pseudonymize("x", "CUST") != pseudonymize("y", "CUST")


def test_pipeline_outputs(env, db):
    meta = db.metadata()
    assert meta["label_coverage"]["by_method"]["template"] > 0
    assert meta["label_coverage"]["by_method"]["lexicon"] == 2  # C0000011's opening and its non-template follow-up
    masked = db.scalar("SELECT masked_text FROM messages WHERE message_id='C0000011-T00'")
    assert "[EMAIL]" in masked and "jane.doe" not in masked
    raw = db.scalar("SELECT text FROM messages WHERE message_id='C0000001-T00'")
    assert raw.endswith("zzmqt"), "raw text must be preserved"
