import pytest
from sqlalchemy import select, update

from backend.db import models as m
from backend.db.session import session_scope
from governance import audit
from privacy.detect import detect, redact_text

pytestmark = pytest.mark.critical


def test_prompt_example_tokenization(st):
    from backend import runtime as R
    svc = R.privacy_service(st)
    with session_scope() as s:
        out = svc.tokenize(s, "Client Sarah Williams has account 123456789.", "t-flo", "scope-example")
    assert out.text == "Client [PERSON_001] has account [ACCOUNT_001]." or out.text == "Client [CLIENT_001] has account [ACCOUNT_001]."
    assert "Sarah" not in out.text and "123456789" not in out.text
    assert all("value" not in t for t in out.tokens)


@pytest.mark.parametrize("text,kind", [
    ("email me at jane.doe@example.com", "EMAIL"), ("call +1-416-555-0199", "PHONE"), ("SIN 046 454 286", "SIN"),
    ("account number 987654321", "ACCOUNT"), ("client C-00042 called", "CLIENT_ID"), ("date of birth: 1961-04-12", "DOB"),
    ("lives at 42 Maple Street", "ADDRESS"), ("postal M5V 2T6", "POSTAL_CODE"), ("key AKIAABCDEFGHIJKLMNOP", "SECRET"),
    ("Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U", "SECRET"),
    ("Mrs. Okafor asked", "PERSON")])
def test_detectors(text, kind):
    assert kind in {f.type for f in detect(text)}


def test_gazetteer_names_and_linked_amounts(st):
    name = st.tables["clients"][5]["full_name"]
    f = detect(f"{name} holds $250,000 in the fund.")
    assert {"PERSON", "LINKED_AMOUNT"} <= {x.type for x in f}


def test_invalid_luhn_not_sin():
    assert "SIN" not in {f.type for f in detect("reference 123 456 789")}


def test_rehydration_authorization(st, P, a001_client, other_client):
    from backend import runtime as R
    svc = R.privacy_service(st)
    name_a = st.idx["client"][a001_client]["full_name"]
    name_o = st.idx["client"][other_client]["full_name"]
    with session_scope() as s:
        tok = svc.tokenize(s, f"Review {name_a} and {name_o} today.", "t-flo", "scope-rehydrate")
        assert name_a not in tok.text
        r1 = svc.rehydrate(s, tok.text, P["u-advisor"], "scope-rehydrate")
        assert name_a in r1["text"] and name_o not in r1["text"] and len(r1["denied"]) == 1
        r2 = svc.rehydrate(s, tok.text, P["u-ceo"], "scope-rehydrate")
        assert r2["restored"] == []
        r3 = svc.rehydrate(s, tok.text, P["u-privacy"], "scope-rehydrate", purpose="privacy_request")
        assert name_a in r3["text"] and name_o in r3["text"]
        r4 = svc.rehydrate(s, tok.text, P["u-nw-advisor"], "scope-rehydrate")
        assert r4["restored"] == []  # other tenant cannot even read the vault entries


def test_secrets_never_vaulted(st):
    from backend import runtime as R
    svc = R.privacy_service(st)
    with session_scope() as s:
        out = svc.tokenize(s, "api_key=sk-live-abcdefghijklmnopqrstuvwxyz123", "t-flo", "scope-secret")
        assert "[REDACTED_SECRET]" in out.text
        assert s.scalar(select(m.VaultEntry).where(m.VaultEntry.token.like("scope-secret:%"))) is None


def test_vault_ciphertext_and_secure_deletion(st):
    from backend import runtime as R
    svc = R.privacy_service(st)
    with session_scope() as s:
        svc.tokenize(s, "write to erase.me@example.com", "t-flo", "scope-erase")
        e = s.scalar(select(m.VaultEntry).where(m.VaultEntry.token.like("scope-erase:%")))
        assert "erase.me" not in e.ciphertext and len(e.value_digest) == 64
        assert svc.vault.erase_subject(s, "t-flo", "EMAIL", "erase.me@example.com") == 1
        assert s.scalar(select(m.VaultEntry).where(m.VaultEntry.token.like("scope-erase:%"))) is None


def test_expired_tokens_not_rehydrated(st, P):
    from backend import runtime as R
    from datetime import datetime, timedelta
    svc = R.privacy_service(st)
    with session_scope() as s:
        out = svc.tokenize(s, "contact old@example.com", "t-flo", "scope-exp", subject={"client_id": None})
        s.execute(update(m.VaultEntry).where(m.VaultEntry.token.like("scope-exp:%")).values(expires_at=datetime.now() - timedelta(days=1)))
        r = svc.rehydrate(s, out.text, P["u-privacy"], "scope-exp", purpose="privacy_request")
        assert r["restored"] == [] and r["denied"][0]["reason"] == "unknown_or_expired"
        assert svc.vault.purge_expired(s) >= 1


def test_audit_chain_valid_and_tamper_evident(st):
    audit.record(tenant_id="t-flo", actor="test", action="test.event", details={"note": "contact jane@example.com"})
    with audit.audit_session() as s:
        assert audit.verify_chain(s)["valid"]
        last = s.scalar(select(m.AuditEvent).order_by(m.AuditEvent.seq.desc()).limit(1))
        assert "jane@example.com" not in str(last.details)  # details redacted before persistence
        original = last.decision
        last.decision = "allow"
        s.flush()
        assert not audit.verify_chain(s)["valid"]
        last.decision = original
        s.flush()
        assert audit.verify_chain(s)["valid"]


def test_redaction():
    assert redact_text("SIN 046 454 286") == "SIN [REDACTED:SIN]"


def test_ambiguous_names_not_linked(st):
    from collections import Counter
    from privacy.detect import _CLIENT_NAMES
    dup = next(n for n, k in Counter(c["full_name"] for c in st.tables["clients"]).items() if k > 1)
    assert dup not in _CLIENT_NAMES
