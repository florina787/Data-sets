"""Legacy billing adapter (enhancement 3) — SIMULATED source system.

Reads a pipe-delimited legacy export (amounts in cents, coded plan/status/region, YYYYMMDD dates, trailer control
record), validates it, maps it to the raw contract with `mappings/legacy_billing.yaml`, attaches lineage, and
previews the result through the SAME cleaning rules as the ledger — in memory, read-only. Nothing is written to the
analytics database: promoting a source into the ledger would need an explicit, human-approved step (not built).
"""
from __future__ import annotations

import hashlib
import re
from datetime import date
from pathlib import Path

import pandas as pd
import yaml

from ..errors import AppError
from .base import RAW_CONTRACT_COLUMNS, Extract

MAPPING = Path(__file__).parent / "mappings" / "legacy_billing.yaml"
SAMPLE = Path(__file__).resolve().parents[2] / "data" / "samples" / "legacy_billing_export.psv"
MAX_BYTES = 256 * 1024


def _transform(value: str, spec: dict) -> str:
    """Return a raw-contract string; raise ValueError with a reason if the legacy value is invalid."""
    v = (value or "").strip()
    if "map" in spec:
        if v == "" and spec["from"] not in ("STATUS_CD", "PLAN_CODE", "CYCLE"):
            return ""
        if v not in spec["map"]:
            raise ValueError(f"{spec['from']}='{v}' is not a known code")
        return str(spec["map"][v])
    t = spec.get("type")
    if t == "cents":
        if not re.fullmatch(r"-?\d+", v):
            raise ValueError(f"{spec['from']}='{v}' is not an integer amount in cents")
        n = int(v)
        return f"{'-' if n < 0 else ''}{abs(n) // 100}.{abs(n) % 100:02d}"
    if t == "yyyymmdd":
        if v == "":
            return ""
        try:
            return date(int(v[:4]), int(v[4:6]), int(v[6:8])).isoformat() if re.fullmatch(r"\d{8}", v) else _bad(spec, v)
        except ValueError as exc:
            raise ValueError(f"{spec['from']}='{v}' is not a valid YYYYMMDD date") from exc
    if t == "int" and not re.fullmatch(r"\d+", v):
        raise ValueError(f"{spec['from']}='{v}' is not a whole number")
    if t == "number" and v and not re.fullmatch(r"\d+(\.\d+)?", v):
        raise ValueError(f"{spec['from']}='{v}' is not a number")
    return v


def _bad(spec, v):
    raise ValueError(f"{spec['from']}='{v}' is not a valid YYYYMMDD date")


class LegacyBillingAdapter:
    name, system_type = "legacy_billing", "legacy_billing"

    def __init__(self, text: str, source_name: str = "legacy_billing_export.psv") -> None:
        if len(text.encode()) > MAX_BYTES:
            raise AppError("payload_too_large", f"Legacy export preview is limited to {MAX_BYTES // 1024} KB.", 413)
        self.text, self.source_name = text, source_name
        self.mapping = yaml.safe_load(MAPPING.read_text())

    @classmethod
    def sample(cls) -> "LegacyBillingAdapter":
        return cls(SAMPLE.read_text(), SAMPLE.name)

    def extract(self) -> tuple[Extract, list[dict], dict]:
        m = self.mapping
        lines = [ln for ln in self.text.splitlines() if ln.strip()]
        if not lines:
            raise AppError("empty_export", "The export is empty.", 422)
        header = lines[0].split(m["delimiter"])
        missing = [c for c in m["required_columns"] if c not in header]
        if missing:
            raise AppError("schema_mismatch", f"Export header is missing required columns: {', '.join(missing)}", 422,
                           details={"missing": missing})
        body, control = lines[1:], {"trailer_present": False}
        if body and body[-1].startswith(m["trailer"]["prefix"] + m["delimiter"]):
            declared = body[-1].split(m["delimiter"])[m["trailer"]["count_field"]]
            body = body[:-1]
            control = {"trailer_present": True, "declared_records": int(declared) if declared.isdigit() else None,
                       "actual_records": len(body)}
            control["matches"] = control["declared_records"] == len(body)
            if not control["matches"]:
                raise AppError("control_total_mismatch", f"Trailer declares {declared} records but the file has {len(body)}.",
                               422, details=control)
        sha = hashlib.sha256(self.text.encode()).hexdigest()
        ok_rows, rejected = [], []
        for i, line in enumerate(body, start=2):
            vals = line.split(m["delimiter"])
            lineage = {"source_system": m["source_system"], "source_file": self.source_name, "source_line": i, "source_sha256": sha[:16]}
            if len(vals) != len(header):
                rejected.append({**lineage, "reason": f"expected {len(header)} fields, got {len(vals)}", "raw": line})
                continue
            rec = dict(zip(header, vals))
            try:
                out = {col: _transform(rec.get(spec["from"], ""), spec) for col, spec in m["columns"].items()}
            except ValueError as exc:
                rejected.append({**lineage, "reason": str(exc), "raw": line})
                continue
            ok_rows.append({**out, **{f"_{k}": v for k, v in lineage.items()}})
        df = pd.DataFrame(ok_rows, columns=RAW_CONTRACT_COLUMNS + [f"_{k}" for k in ("source_system", "source_file", "source_line", "source_sha256")])
        prov = {"adapter": self.name, "system_type": self.system_type, "file": self.source_name, "sha256": sha,
                "rows_in_file": len(body), "rows_mapped": len(ok_rows), "rows_rejected_at_mapping": len(rejected), "control": control}
        return Extract(df, prov), rejected, control


def preview(adapter: LegacyBillingAdapter) -> dict:
    """Map → validate → run through the ledger's own cleaning rules in memory. Read-only."""
    from ..config import get_settings
    from ..pipeline.clean import RAW_COLUMNS, clean

    ext, mapping_rejects, control = adapter.extract()
    s = get_settings()
    raw = ext.rows[RAW_COLUMNS].copy()
    raw.insert(0, "raw_row_number", ext.rows["_source_line"].astype(int).tolist())
    result = clean(raw, s.fx_to_usd, s.fx_direction) if len(raw) else None
    lineage = {int(r["_source_line"]): {k[1:]: r[k] for k in r.index if k.startswith("_")} for _, r in ext.rows.iterrows()}
    cleaned = []
    if result is not None:
        for _, r in result.invoices.iterrows():
            cleaned.append({"invoice_id": r["invoice_id"], "account_id": r["account_id"], "plan": r["plan"],
                            "billing_cycle": r["billing_cycle"], "seats": int(r["seats"]), "currency": r["currency"],
                            "amount_local": float(r["amount_local"]), "amount_usd": float(r["amount_usd"]),
                            "expected_amount_usd": float(r["expected_amount_usd"]), "status": r["status"],
                            "invoice_date": r["invoice_date"].isoformat(), "dq_flags": r["dq_flags"],
                            "lineage": lineage[int(r["raw_row_number"])]})
    pipeline_rejects = [] if result is None else [
        {"source_line": int(r["raw_row_number"]), "invoice_id": r["invoice_id"], "reason": r["reason"]}
        for _, r in result.rejected_rows.iterrows()]
    return {
        "mode": "preview (read-only) — nothing was written to the analytics database",
        "provenance": ext.provenance, "control_total": control,
        "mapping": {"file": "app/sources/mappings/legacy_billing.yaml",
                    "columns": {k: v["from"] for k, v in adapter.mapping["columns"].items()}},
        "rejected_at_mapping": mapping_rejects,
        "rejected_by_pipeline": pipeline_rejects,
        "cleaned": cleaned,
        "flags_summary": _flag_counts(cleaned),
    }


def _flag_counts(rows: list[dict]) -> dict:
    out: dict = {}
    for r in rows:
        for f in filter(None, r["dq_flags"].split(";")):
            out[f] = out.get(f, 0) + 1
    return out
