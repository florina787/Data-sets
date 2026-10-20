"""Make an upload-sized CSV of COMPLETE conversation threads from the Kaggle archive.

Paste into a file and run:  python3 make_upload_csv.py
Reads archive.zip (unchanged), writes customer_support_under_19MB.csv next to it.
Keeps the header, original values (IDs stay strings), original row order and whole reply threads.
"""
import csv
import io
import random
import sys
import zipfile
from collections import defaultdict
from pathlib import Path

ZIP_PATH = Path("/Users/jerome/Downloads/archive.zip")
LIMIT = 19_000_000  # bytes; stays under the 20 MB upload limit
SEED = 20240601

csv.field_size_limit(sys.maxsize)
zip_path = Path(sys.argv[1]) if len(sys.argv) > 1 else ZIP_PATH
output = zip_path.parent / "customer_support_under_19MB.csv"


def norm(v):
    v = (v or "").strip()
    return v[:-2] if v.endswith(".0") else v


buf = io.StringIO(newline="")
w = csv.writer(buf)


def encode(row):
    buf.seek(0)
    buf.truncate(0)
    w.writerow(row)
    return buf.getvalue().encode("utf-8")


with zipfile.ZipFile(zip_path) as archive:
    name = next(n for n in archive.namelist() if Path(n).name == "twcs.csv")

    def rows():
        with archive.open(name) as fh:
            yield from csv.reader(io.TextIOWrapper(fh, encoding="utf-8-sig", newline=""))

    # Pass 1: reply links -> thread of each message, and bytes per thread.
    it = rows()
    header = next(it)
    i_id, i_par = header.index("tweet_id"), header.index("in_response_to_tweet_id")
    parent, nbytes = {}, {}
    for r in it:
        t = norm(r[i_id])
        parent[t] = norm(r[i_par])
        nbytes[t] = len(encode(r))
    uf = {}

    def find(x):
        uf.setdefault(x, x)
        while uf[x] != x:
            uf[x] = uf[uf[x]]
            x = uf[x]
        return x

    for t, p in parent.items():
        if p and p in parent:
            a, b = find(t), find(p)
            if a != b:
                uf[a] = b
    size, msgs = defaultdict(int), defaultdict(int)
    for t in parent:
        root = find(t)
        size[root] += nbytes[t]
        msgs[root] += 1

    # Choose whole threads in a fixed random order until the byte budget is used.
    roots = sorted(size)
    random.Random(SEED).shuffle(roots)
    budget = LIMIT - len(encode(header))
    keep, used, kept_msgs = set(), 0, 0
    for root in roots:
        if used + size[root] <= budget:
            keep.add(root)
            used += size[root]
            kept_msgs += msgs[root]

    # Pass 2: write selected threads unchanged, in original order.
    with output.open("wb") as out:
        it = rows()
        out.write(encode(next(it)))
        for r in it:
            if find(norm(r[i_id])) in keep:
                out.write(encode(r))

# Verify: parses, and no kept reply lost a parent that existed in the original.
with output.open(newline="", encoding="utf-8") as f:
    r = csv.reader(f)
    head = next(r)
    ids, pars, n = set(), [], 0
    for row in r:
        ids.add(norm(row[i_id]))
        pars.append(norm(row[i_par]))
        n += 1
split = sum(1 for p in pars if p and p in parent and p not in ids)
print(f"Saved {n:,} messages in {len(keep):,} complete conversation threads")
print(f"Size: {output.stat().st_size:,} bytes ({output.stat().st_size / 1_000_000:.2f} MB)")
print(f"Split conversations: {split} (should be 0)")
print(f"File: {output}")
