"""Encrypted, access-controlled token vault.

* Values are encrypted with Fernet (AES-128-CBC + HMAC-SHA256). The key comes from FLO_VAULT_KEY (secret manager in
  production); in development a key is generated once into var/dev_vault.key with 0600 permissions.
* Lookups use an HMAC digest of the value, never the plaintext.
* Mappings live only in this service's database table; they are never returned to the frontend or placed in LLM
  context. Rehydration is mediated by privacy.service.PrivacyService, which checks policy and writes audit events.
* Retention: every mapping has an expiry (policies/retention.yaml). `purge_expired` and `erase_subject` overwrite the
  ciphertext before deleting the row. Note: physical erasure from database pages/backups depends on the database
  engine and backup retention — documented in docs/PRIVACY.md.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
from datetime import datetime, timedelta, timezone

from cryptography.fernet import Fernet
from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from backend.config import ROOT, get_settings
from backend.db import models as m


def _key() -> bytes:
    k = get_settings().vault_key
    if k:
        return k.encode()
    path = ROOT / "var" / "dev_vault.key"
    path.parent.mkdir(exist_ok=True)
    if not path.exists():
        path.write_bytes(Fernet.generate_key())
        os.chmod(path, 0o600)
    return path.read_bytes().strip()


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class TokenVault:
    def __init__(self):
        key = _key()
        self.fernet = Fernet(key)
        self.mac_key = hashlib.sha256(b"flo-vault-digest:" + base64.urlsafe_b64decode(key)).digest()

    def digest(self, entity_type: str, value: str) -> str:
        return hmac.new(self.mac_key, f"{entity_type}|{value.strip().lower()}".encode(), hashlib.sha256).hexdigest()

    def put(self, s: Session, tenant_id: str, scope: str, entity_type: str, label: str, value: str, purpose: str,
            ttl_days: int, attrs: dict | None = None) -> str:
        dg = self.digest(entity_type, value)
        existing = s.scalar(select(m.VaultEntry.token).where(
            m.VaultEntry.tenant_id == tenant_id, m.VaultEntry.value_digest == dg, m.VaultEntry.deleted.is_(False),
            m.VaultEntry.token.like(f"{scope}:{label}_%")))
        if existing:
            return existing.split(":", 1)[1]
        n = s.scalar(select(func.count()).select_from(m.VaultEntry).where(
            m.VaultEntry.tenant_id == tenant_id, m.VaultEntry.token.like(f"{scope}:{label}_%"))) or 0
        token = f"{label}_{n + 1:03d}"
        ct = self.fernet.encrypt(json.dumps({"v": value, "attrs": attrs or {}}).encode()).decode()
        s.add(m.VaultEntry(tenant_id=tenant_id, token=f"{scope}:{token}", entity_type=entity_type, value_digest=dg, ciphertext=ct,
                           purpose=purpose, created_at=_now(), expires_at=_now() + timedelta(days=ttl_days), deleted=False))
        s.flush()
        return token

    def get(self, s: Session, tenant_id: str, scope: str, token: str) -> dict | None:
        e = s.scalar(select(m.VaultEntry).where(m.VaultEntry.tenant_id == tenant_id, m.VaultEntry.token == f"{scope}:{token}"))
        if e is None or e.deleted or e.expires_at < _now():
            return None
        data = json.loads(self.fernet.decrypt(e.ciphertext.encode()))
        return {"entity_type": e.entity_type, "value": data["v"], "attrs": data["attrs"]}

    def _shred(self, s: Session, where) -> int:
        ids = list(s.scalars(select(m.VaultEntry.id).where(where)))
        if not ids:
            return 0
        s.execute(update(m.VaultEntry).where(m.VaultEntry.id.in_(ids)).values(ciphertext=secrets.token_urlsafe(64), deleted=True))
        s.execute(delete(m.VaultEntry).where(m.VaultEntry.id.in_(ids)))
        return len(ids)

    def purge_expired(self, s: Session) -> int:
        return self._shred(s, m.VaultEntry.expires_at < _now())

    def erase_subject(self, s: Session, tenant_id: str, entity_type: str, value: str) -> int:
        return self._shred(s, (m.VaultEntry.tenant_id == tenant_id) & (m.VaultEntry.value_digest == self.digest(entity_type, value)))
