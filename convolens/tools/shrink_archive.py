"""Shrink a Kaggle "Customer Support on Twitter" archive to a size limit without breaking conversations.

    python shrink_archive.py ~/Downloads/archive.zip                      # writes archive_under_28MB.zip next to it
    python shrink_archive.py archive.zip -o out.zip --limit 28000000 --seed 20240601

Steps
1. Re-compress every member losslessly (Deflate level 9, then bzip2, then LZMA) and keep the first result under
   the limit. Deflate opens everywhere; bzip2 and LZMA ZIPs need 7-Zip, Python, or a recent unzip.
2. If none fits, reduce the largest CSV by selecting COMPLETE reply threads, so no conversation is split:
   - a thread is everything connected through in_response_to_tweet_id;
   - every row keeps its original values and header, and rows stay in their original order;
   - threads are taken in a seeded random order until the compressed ZIP fits;
   - other archive members are kept unchanged.
3. Verify: the ZIP opens, every member passes its CRC check, the CSV parses with the same header, and every
   retained reply's parent is retained too (unless the parent was already missing in the original).

The original archive is only read.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import os
import random
import sys
import tempfile
import zipfile
from collections import defaultdict
from pathlib import Path

csv.field_size_limit(sys.maxsize)
METHODS = [("deflate-9", zipfile.ZIP_DEFLATED, 9), ("bzip2-9", zipfile.ZIP_BZIP2, 9), ("lzma", zipfile.ZIP_LZMA, None)]
ID_COL, PARENT_COL = "tweet_id", "in_response_to_tweet_id"


def norm_id(v: str) -> str:
    v = (v or "").strip()
    return v[:-2] if v.endswith(".0") else v


def write_zip(src: zipfile.ZipFile, out: Path, method: int, level: int | None, replace: dict[str, Path] | None = None) -> int:
    replace = replace or {}
    with zipfile.ZipFile(out, "w", compression=method, compresslevel=level) as z:
        for info in src.infolist():
            if info.is_dir():
                continue
            if info.filename in replace:
                z.write(replace[info.filename], arcname=info.filename)
            else:
                zi = zipfile.ZipInfo(info.filename, date_time=info.date_time)
                zi.compress_type = method  # ZipInfo defaults to ZIP_STORED; set the method explicitly
                zi.compress_level = level
                with src.open(info) as fin, z.open(zi, "w", force_zip64=True) as fout:
                    while chunk := fin.read(1 << 20):
                        fout.write(chunk)
    return out.stat().st_size


def build_threads(path: Path) -> tuple[list[str], dict[str, str], dict[str, int]]:
    """Return header, tweet_id -> thread root, root -> row count. Threads follow reply links; cycles stay together."""
    parent: dict[str, str] = {}
    with open(path, newline="", encoding="utf-8") as f:
        r = csv.reader(f)
        header = next(r)
        if ID_COL not in header or PARENT_COL not in header:
            sys.exit(f"CSV lacks {ID_COL} / {PARENT_COL}; cannot rebuild conversations safely.")
        i_id, i_par = header.index(ID_COL), header.index(PARENT_COL)
        ids = []
        for row in r:
            tid = norm_id(row[i_id])
            ids.append(tid)
            parent[tid] = norm_id(row[i_par])
    # Union-find over reply links (handles branches, missing parents and cycles).
    uf: dict[str, str] = {}

    def find(x: str) -> str:
        uf.setdefault(x, x)
        root = x
        while uf[root] != root:
            root = uf[root]
        while uf[x] != root:
            uf[x], x = root, uf[x]
        return root

    for tid, p in parent.items():
        find(tid)
        if p and p in parent:
            a, b = find(tid), find(p)
            if a != b:
                uf[a] = b
    root_of = {tid: find(tid) for tid in parent}
    sizes: dict[str, int] = defaultdict(int)
    for tid in ids:
        sizes[root_of[tid]] += 1
    return header, root_of, sizes


def write_subset(path: Path, out: Path, root_of: dict[str, str], keep: set[str]) -> int:
    n = 0
    with open(path, newline="", encoding="utf-8") as f, open(out, "w", newline="", encoding="utf-8") as g:
        r = csv.reader(f)
        w = csv.writer(g, lineterminator="\n")
        header = next(r)
        w.writerow(header)
        i_id = header.index(ID_COL)
        for row in r:
            if root_of[norm_id(row[i_id])] in keep:
                w.writerow(row)
                n += 1
    return n


def verify(zpath: Path, csv_name: str | None, header: list[str] | None, original_ids: set[str] | None) -> dict:
    with zipfile.ZipFile(zpath) as z:
        bad = z.testzip()
        if bad:
            raise SystemExit(f"CRC check failed for {bad}")
        if not csv_name:
            return {"members": len(z.namelist())}
        with z.open(csv_name) as fh:
            r = csv.reader(io.TextIOWrapper(fh, encoding="utf-8", newline=""))
            got_header = next(r)
            if header and got_header != header:
                raise SystemExit("Header changed")
            i_id, i_par = got_header.index(ID_COL), got_header.index(PARENT_COL)
            ids, parents, rows = set(), [], 0
            for row in r:
                if len(row) != len(got_header):
                    raise SystemExit(f"Malformed row {rows + 2}")
                ids.add(norm_id(row[i_id]))
                parents.append(norm_id(row[i_par]))
                rows += 1
    broken = sum(1 for p in parents if p and p not in ids and (original_ids is None or p in original_ids))
    if broken:
        raise SystemExit(f"{broken} replies lost their parent: a conversation was split")
    return {"rows": rows, "unique_ids": len(ids)}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("archive", type=Path)
    ap.add_argument("-o", "--output", type=Path)
    ap.add_argument("--limit", type=int, default=28_000_000)
    ap.add_argument("--seed", type=int, default=20240601)
    a = ap.parse_args()
    src_path = a.archive.expanduser().resolve()
    out = (a.output or src_path.with_name("archive_under_28MB.zip")).resolve()
    if out == src_path:
        sys.exit("Output must differ from the original archive.")
    before = hashlib.sha256(src_path.read_bytes()).hexdigest()
    src = zipfile.ZipFile(src_path)
    print(f"Original: {src_path.name} {src_path.stat().st_size:,} bytes; members: {[i.filename for i in src.infolist()]}")

    # Step 1: stronger lossless compression.
    for name, method, level in METHODS:
        size = write_zip(src, out, method, level)
        print(f"  lossless {name}: {size:,} bytes")
        if size <= a.limit:
            print(f"Fits with lossless {name}; no rows removed.")
            print("Verify:", verify(out, None, None, None))
            print(f"FINAL {out} {size:,} bytes (all rows retained)")
            assert hashlib.sha256(src_path.read_bytes()).hexdigest() == before
            return

    # Step 2: reduce the largest CSV by whole conversation threads.
    csvs = [i for i in src.infolist() if i.filename.lower().endswith(".csv")]
    if not csvs:
        sys.exit("No CSV member to reduce.")
    big = max(csvs, key=lambda i: i.file_size)
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        full = td / "full.csv"
        with src.open(big) as fin, open(full, "wb") as fout:
            while chunk := fin.read(1 << 20):
                fout.write(chunk)
        header, root_of, sizes = build_threads(full)
        roots = sorted(sizes)
        random.Random(a.seed).shuffle(roots)
        total_threads, total_rows = len(roots), sum(sizes.values())
        print(f"Reducing {big.filename}: {total_rows:,} rows in {total_threads:,} threads")
        # Proportional search: size the next attempt from the last compressed size, then refine.
        full_size = write_zip(src, td / "probe.zip", zipfile.ZIP_DEFLATED, 9)
        lo, hi, best = 0, total_threads, None
        mid = max(1, int(total_threads * a.limit / full_size * 0.97))
        for _ in range(12):
            mid = max(lo + 1, min(mid, hi))
            sub = td / "subset.csv"
            rows = write_subset(full, sub, root_of, set(roots[:mid]))
            size = write_zip(src, td / "try.zip", zipfile.ZIP_DEFLATED, 9, replace={big.filename: sub})
            print(f"  {mid:,} threads / {rows:,} rows -> {size:,} bytes")
            if size <= a.limit:
                lo, best = mid, (mid, rows, size)
                os.replace(td / "try.zip", out)
                if size >= a.limit * 0.995 or mid == hi:
                    break
                mid = min(hi, max(mid + 1, int(mid * a.limit / size * 0.998)))
            else:
                hi = mid - 1
                if hi <= lo:
                    break
                mid = max(lo + 1, int(mid * a.limit / size * 0.995))
        if best is None:
            sys.exit("Even one thread does not fit under the limit.")
        original_ids = set(root_of)
        v = verify(out, big.filename, header, original_ids)
    assert hashlib.sha256(src_path.read_bytes()).hexdigest() == before, "original archive changed!"
    n_threads, n_rows, size = best
    print(f"Verify: extracted and parsed {v['rows']:,} rows, header unchanged, no split conversations, CRC ok")
    print(f"FINAL {out} {size:,} bytes (limit {a.limit:,}); retained {n_threads:,} of {total_threads:,} conversation threads "
          f"and {n_rows:,} of {total_rows:,} messages (Deflate level 9; seed {a.seed}). Original unchanged.")


if __name__ == "__main__":
    main()
