"""Write a small seeded synthetic claims sample to synthetic_data/claims/ (SYNTHETIC DEMO DATA)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.simulation.generator import generate_dataset  # noqa: E402

if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 1_000
    ds = generate_dataset(n, 42)
    out = ROOT / "synthetic_data" / "claims"
    out.mkdir(parents=True, exist_ok=True)
    header = "# SYNTHETIC DEMO DATA — NOT FOR REAL CLAIM ADJUDICATION.\n"
    for name, df in (("claims_sample.csv", ds.claims.drop(columns=["service_day"])),
                     ("members_sample.csv", ds.members.drop(columns=["coverage_start_day", "coverage_end_day"])),
                     ("providers_sample.csv", ds.providers), ("authorizations_sample.csv", ds.authorizations)):
        (out / name).write_text(header + df.to_csv(index=False), encoding="utf-8")
    print(ds.summary())
