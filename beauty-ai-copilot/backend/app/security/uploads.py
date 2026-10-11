"""Optional image sandbox (disabled by default). The SDLC workflow never needs photographs.

Validation: magic bytes, size, dimensions and format; metadata stripping (JPEG APPn/COM segments,
PNG ancillary text/EXIF chunks). No inference of identity or protected traits is performed.
Storage is a private local directory addressed by random IDs; files are never logged or sent to a
language provider. Deletion removes the raw file and every derived record tracked in the storage
inventory and reports any exception; backups are not edited in place and expire on schedule.
"""
from __future__ import annotations

import struct
import uuid
from datetime import timedelta
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import get_settings
from app.errors import Forbidden, NotFound, ValidationFailed
from app.models.orm import ImageUpload, User, utcnow
from app.services import audit

MAX_BYTES = 5 * 1024 * 1024
MAX_DIM = 4096
MIN_DIM = 64
ALLOWED_PURPOSES = {"sandbox_preview", "evaluation_candidate"}
CONSENT_TEXT_VERSION = "IMG-CONSENT-DEMO-1"
BACKUP_EXPIRY_DAYS = 35


def _png(data: bytes) -> tuple[int, int, bytes, list[str]]:
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValidationFailed("bad_signature", "Not a PNG")
    out, pos, stripped = bytearray(data[:8]), 8, []
    w = h = 0
    while pos + 8 <= len(data):
        ln, typ = struct.unpack(">I4s", data[pos:pos + 8])
        end = pos + 12 + ln
        if end > len(data):
            raise ValidationFailed("truncated", "Truncated PNG chunk")
        if typ == b"IHDR":
            w, h = struct.unpack(">II", data[pos + 8:pos + 16])
        if typ in (b"tEXt", b"zTXt", b"iTXt", b"eXIf", b"tIME"):
            stripped.append(typ.decode())
        else:
            out += data[pos:end]
        pos = end
        if typ == b"IEND":
            break
    if not w or not h:
        raise ValidationFailed("no_header", "PNG header missing")
    return w, h, bytes(out), stripped


def _jpeg(data: bytes) -> tuple[int, int, bytes, list[str]]:
    if not data.startswith(b"\xff\xd8\xff"):
        raise ValidationFailed("bad_signature", "Not a JPEG")
    out, pos, stripped, w, h = bytearray(b"\xff\xd8"), 2, [], 0, 0
    while pos + 4 <= len(data):
        if data[pos] != 0xFF:
            raise ValidationFailed("malformed", "Malformed JPEG segment")
        marker = data[pos + 1]
        if marker == 0xDA:  # start of scan: copy the rest
            out += data[pos:]
            break
        ln = struct.unpack(">H", data[pos + 2:pos + 4])[0]
        seg = data[pos:pos + 2 + ln]
        if 0xC0 <= marker <= 0xC3:
            h, w = struct.unpack(">HH", data[pos + 5:pos + 9])
        if (0xE1 <= marker <= 0xEF) or marker == 0xFE:
            stripped.append(f"APP{marker - 0xE0}" if marker != 0xFE else "COM")
        else:
            out += seg
        pos += 2 + ln
    if not w or not h:
        raise ValidationFailed("no_dimensions", "JPEG dimensions missing")
    return w, h, bytes(out), stripped


def validate_image(data: bytes) -> dict:
    if not data:
        raise ValidationFailed("empty", "Empty upload")
    if len(data) > MAX_BYTES:
        raise ValidationFailed("too_large", f"Upload exceeds {MAX_BYTES} bytes")
    if data.startswith(b"\x89PNG"):
        w, h, clean, stripped = _png(data)
        mt = "image/png"
    elif data.startswith(b"\xff\xd8\xff"):
        w, h, clean, stripped = _jpeg(data)
        mt = "image/jpeg"
    else:
        raise ValidationFailed("unsupported_format", "Only PNG and JPEG are accepted (signature check)")
    if not (MIN_DIM <= w <= MAX_DIM and MIN_DIM <= h <= MAX_DIM):
        raise ValidationFailed("bad_dimensions", f"Dimensions {w}x{h} outside {MIN_DIM}-{MAX_DIM}")
    return {"media_type": mt, "width": w, "height": h, "clean": clean, "stripped": stripped}


def _guard() -> None:
    if not get_settings().image_sandbox_enabled:
        raise Forbidden("image_sandbox_disabled", "Image sandbox is disabled (IMAGE_SANDBOX_ENABLED=false). The SDLC workflow does not need photographs.")


def upload(db: Session, user: User, data: bytes, *, purpose: str, consent: bool, retention_days: int, training_consent: bool) -> ImageUpload:
    _guard()
    if not consent:
        raise ValidationFailed("consent_required", "Explicit consent is required")
    if purpose not in ALLOWED_PURPOSES:
        raise ValidationFailed("purpose_invalid", f"Purpose must be one of {sorted(ALLOWED_PURPOSES)}")
    if not 1 <= retention_days <= 30:
        raise ValidationFailed("retention_invalid", "Retention must be 1-30 days")
    v = validate_image(data)
    iid = f"IMG-{uuid.uuid4().hex[:16]}"
    d = get_settings().storage_dir / "private" / user.tenant_id
    d.mkdir(parents=True, exist_ok=True)
    raw = d / f"{iid}.bin"
    raw.write_bytes(v["clean"])
    ann = d / f"{iid}.annotation.json"
    ann.write_text('{"note": "no inference performed; placeholder annotation record for deletion tracking"}')
    up = ImageUpload(id=iid, tenant_id=user.tenant_id, uploaded_by=user.id, purpose=purpose, consent_text_version=CONSENT_TEXT_VERSION,
                     training_consent=training_consent, retention_days=retention_days, media_type=v["media_type"], width=v["width"],
                     height=v["height"], size_bytes=len(v["clean"]), metadata_stripped=v["stripped"],
                     storage_inventory=[{"kind": "raw_image", "path": str(raw)}, {"kind": "annotation", "path": str(ann)},
                                        {"kind": "thumbnail", "path": None, "note": "not generated"},
                                        {"kind": "embedding", "path": None, "note": "not generated"}],
                     delete_after=utcnow() + timedelta(days=retention_days))
    db.add(up)
    audit.record(db, tenant_id=user.tenant_id, actor_id=user.id, action="image.upload", status="STORED",
                 reason=f"purpose={purpose}; training_consent={training_consent}; retention={retention_days}d",
                 input_refs={"image_id": iid, "metadata_stripped": v["stripped"]})
    return up


def delete(db: Session, user: User, image_id: str) -> dict:
    _guard()
    up = db.get(ImageUpload, image_id)
    if up is None or up.tenant_id != user.tenant_id:
        raise NotFound("image_not_found", "Image not found")
    if up.status == "DELETED":
        return up.deletion_report
    items, exceptions = [], []
    for it in up.storage_inventory:
        if not it.get("path"):
            items.append({**it, "result": "nothing stored"})
            continue
        p = Path(it["path"])
        try:
            if p.exists():
                p.unlink()
                items.append({**it, "result": "deleted"})
            else:
                items.append({**it, "result": "already absent"})
        except OSError as exc:
            exceptions.append({**it, "error": str(exc)})
    report = {"image_id": up.id, "items": items, "exceptions": exceptions, "completed_at": utcnow().isoformat(),
              "backups": f"Not edited in place; demo design states backups expire within {BACKUP_EXPIRY_DAYS} days.",
              "status": "DELETED" if not exceptions else "DELETE_PARTIAL"}
    up.status, up.deletion_report = report["status"], report
    audit.record(db, tenant_id=user.tenant_id, actor_id=user.id, action="image.delete", status=report["status"],
                 input_refs={"image_id": up.id, "exceptions": len(exceptions)})
    return report
