"""Extract about N messages of COMPLETE conversation threads from the Kaggle archive into a CSV.

    python sample_threads.py ~/Downloads/archive.zip --messages 5000

Unlike reading the first N rows, this keeps whole reply threads (no split conversations), keeps every value
as the original string (IDs are never turned into floats), and preserves the header and original row order.
"""
from __future__ import annotations

import argparse
import csv
import io
import random
import sys
import zipfile
from collections import defaultdict
from pathlib import Path

csv.field_size_limit(sys.maxsize)


def norm(v: str) -> str:
    v = (v or "").strip()
    return v[:-2] if v.endswith(".0") else v


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("archive", type=Path)
    ap.add_argument("--messages", type=int, default=5000, help="target number of messages (whole threads only)")
    ap.add_argument("--seed", type=int, default=20240601)
    ap.add_argument("-o", "--output", type=Path)
    a = ap.parse_args()
    zp = a.archive.expanduser()
    out = a.output or zp.parent / f"customer_support_{a.messages}.csv"

    with zipfile.ZipFile(zp) as z:
        name = next(n for n in z.namelist() if Path(n).name == "twcs.csv")

        def rows():
            with z.open(name) as fh:
                yield from csv.reader(io.TextIOWrapper(fh, encoding="utf-8", newline=""))

        # Pass 1: reply graph -> thread of every message (union-find; branches and cycles stay together).
        it = rows()
        header = next(it)
        i_id, i_par = header.index("tweet_id"), header.index("in_response_to_tweet_id")
        parent = {norm(r[i_id]): norm(r[i_par]) for r in it}
        uf: dict[str, str] = {}

        def find(x: str) -> str:
            uf.setdefault(x, x)
            while uf[x] != x:
                uf[x] = uf[uf[x]]
                x = uf[x]
            return x

        for t, p in parent.items():
            if p and p in parent:
                a_, b_ = find(t), find(p)
                if a_ != b_:
                    uf[a_] = b_
        size: dict[str, int] = defaultdict(int)
        for t in parent:
            size[find(t)] += 1
        roots = sorted(size)
        random.Random(a.seed).shuffle(roots)
        keep, total = set(), 0
        for r in roots:
            if total + size[r] > a.messages:
                continue
            keep.add(r)
            total += size[r]
            if total >= a.messages:
                break

        # Pass 2: write the selected threads, unchanged and in original order.
        with open(out, "w", newline="", encoding="utf-8") as g:
            w = csv.writer(g)
            it = rows()
            w.writerow(next(it))
            for r in it:
                if find(norm(r[i_id])) in keep:
                    w.writerow(r)

    print(f"Saved {total:,} messages in {len(keep):,} complete conversation threads to: {out}")


if __name__ == "__main__":
    main()
