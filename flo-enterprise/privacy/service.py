"""Privacy service: data minimization, tokenization / pseudonymization and authorized rehydration.

Example:  "Client Sarah Williams has account 123456789."  ->  "Client [CLIENT_001] has account [ACCOUNT_001]."
Pseudonymized text is still treated as personal information (classification is not lowered by tokenization)."""
from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from governance import audit
from governance.identity import Principal
from governance.policy import PolicyEngine, Resource
from privacy.detect import _CLIENT_NAMES, detect
from privacy.vault import TokenVault

LABELS = {"PERSON": "PERSON", "EMAIL": "EMAIL", "PHONE": "PHONE", "SIN": "SIN", "ACCOUNT": "ACCOUNT", "CLIENT_ID": "CLIENT",
          "DOB": "DOB", "ADDRESS": "ADDRESS", "POSTAL_CODE": "POSTAL", "SECRET": "SECRET", "LINKED_AMOUNT": "AMOUNT"}
TOKEN_RX = re.compile(r"\[([A-Z]+_\d{3})\]")


@dataclass
class TokenizeResult:
    text: str
    tokens: list[dict] = field(default_factory=list)  # [{token, entity_type}] - never values

    @property
    def entity_counts(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for t in self.tokens:
            out[t["entity_type"]] = out.get(t["entity_type"], 0) + 1
        return out


class PrivacyService:
    def __init__(self, engine: PolicyEngine, client_resolver: Callable[[str], dict | None] | None = None):
        self.vault = TokenVault()
        self.engine = engine
        self.resolve_client = client_resolver or (lambda _cid: None)
        self.ttl = engine.bundle.retention["token_vault_ttl_days"]

    def tokenize(self, s: Session, text: str, tenant_id: str, scope: str, purpose: str = "llm_context",
                 subject: dict | None = None, mask_amounts: bool = False) -> TokenizeResult:
        """Replace detected identifiers with scope-stable tokens. Secrets are always fully redacted (never vaulted)."""
        out, last, toks = [], 0, []
        for f in detect(text):
            if f.type == "LINKED_AMOUNT" and not mask_amounts:
                continue
            out.append(text[last:f.start])
            last = f.end
            if f.type == "SECRET":
                out.append("[REDACTED_SECRET]")
                toks.append({"token": "REDACTED_SECRET", "entity_type": "SECRET"})
                continue
            attrs = dict(subject or {})
            label = LABELS[f.type]
            if f.type == "PERSON" and f.text in _CLIENT_NAMES:
                label, attrs["client_id"] = "CLIENT", _CLIENT_NAMES[f.text]
            if f.type == "CLIENT_ID":
                attrs["client_id"] = f.text
            tok = self.vault.put(s, tenant_id, scope, f.type, label, f.text, purpose, self.ttl, attrs)
            out.append(f"[{tok}]")
            toks.append({"token": tok, "entity_type": f.type})
        out.append(text[last:])
        return TokenizeResult("".join(out), toks)

    def rehydrate(self, s: Session, text: str, principal: Principal, scope: str, purpose: str | None = None) -> dict:
        """Replace tokens with original values ONLY where policy allows privacy:rehydrate for the underlying subject."""
        restored, denied = [], []

        def repl(mt: re.Match) -> str:
            tok = mt.group(1)
            entry = self.vault.get(s, principal.tenant_id, scope, tok)
            if entry is None:
                denied.append({"token": tok, "reason": "unknown_or_expired"})
                return mt.group(0)
            cid = entry["attrs"].get("client_id")
            client = self.resolve_client(cid) if cid else None
            res = Resource("client", cid or f"unlinked:{tok}", principal.tenant_id,
                           {"advisor_id": (client or {}).get("advisor_id"), "classification": "confidential"})
            if client and client.get("tenant_id") != principal.tenant_id:
                res = Resource("client", cid, client.get("tenant_id"), {})
            d = self.engine.authorize(principal, "privacy:rehydrate", res, {"purpose": purpose})
            if not d.allowed:
                denied.append({"token": tok, "reason": ",".join(d.denial_codes)})
                return mt.group(0)
            restored.append(tok)
            return entry["value"]

        out = TOKEN_RX.sub(repl, text)
        audit.record(tenant_id=principal.tenant_id, actor=principal.user_id, action="privacy:rehydrate", resource_type="token_scope",
                     resource_id=scope, decision="allow" if restored and not denied else ("partial" if restored else "deny"),
                     reasons=[{"rule": "PRIVACY-REHYDRATE", "restored": restored, "denied": denied}],
                     policy_version=self.engine.version, details={"purpose": purpose or "-"})
        return {"text": out, "restored": restored, "denied": denied}
