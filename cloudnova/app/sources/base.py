"""Source adapters: the seam between CloudNova's systems of record and the spec-driven pipeline.

Every adapter's only job is to emit rows in the **raw contract** (the 19 string columns of
specs/cloudnova_data_contract.md §1) plus provenance. Normalization, dedup and metrics stay in one place
(`app/pipeline`), so adding a source never forks the business logic. See docs/INTEGRATION_ARCHITECTURE.md.

Implemented: `csv_ledger` (the finance export). Other adapters are documented mappings, not shipped code.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

import pandas as pd

RAW_CONTRACT_COLUMNS = ["invoice_id", "account_id", "account_name", "contact_email", "region", "industry", "plan",
                        "billing_cycle", "seats", "currency", "amount", "discount_pct", "status", "payment_method",
                        "signup_date", "invoice_date", "churned", "csat_score", "support_tickets"]


@dataclass
class Extract:
    rows: pd.DataFrame                      # raw-contract columns, all strings, nothing coerced
    provenance: dict = field(default_factory=dict)


class SourceAdapter(Protocol):
    name: str
    system_type: str                        # legacy_billing | crm | saas_billing | file_export

    def extract(self) -> Extract: ...


class CsvLedgerAdapter:
    """The finance team's stitched export (old billing tool + CRM + hand-kept spreadsheet), read as strings."""
    name, system_type = "csv_ledger", "file_export"

    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def extract(self) -> Extract:
        if not self.path.exists():
            raise FileNotFoundError(f"ledger export not found: {self.path}")
        data = self.path.read_bytes()
        df = pd.read_csv(self.path, dtype=str, keep_default_na=False)
        missing = set(RAW_CONTRACT_COLUMNS) - set(df.columns)
        if missing:
            raise ValueError(f"{self.path.name} does not satisfy the raw contract; missing columns: {sorted(missing)}")
        return Extract(df[RAW_CONTRACT_COLUMNS].copy(), {"adapter": self.name, "system_type": self.system_type,
                                                         "file": self.path.name, "sha256": hashlib.sha256(data).hexdigest(),
                                                         "rows": int(len(df))})


def get_source(settings) -> SourceAdapter:
    return CsvLedgerAdapter(settings.raw_csv)
