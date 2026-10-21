"""Parser and reply-graph reconstruction for the Kaggle "Customer Support on Twitter" CSV (twcs.csv).

Observed schema (thoughtvector/customer-support-on-twitter, file twcs/twcs.csv):

    tweet_id                 integer id, string-safe here (never float-coerced)
    author_id                brand handle (support) or anonymised numeric id (customer)
    inbound                  "True" (customer) / "False" (company)
    created_at               "Tue Oct 31 22:10:47 +0000 2017"
    text                     tweet text
    response_tweet_id        comma-separated ids of replies (may be empty)
    in_response_to_tweet_id  parent id (may be empty; some exports write "123.0")

Unit of analysis: one conversation = one reply tree. Each message has at most one parent
(``in_response_to_tweet_id``), so trees are disjoint and every message belongs to exactly
one conversation. Branches (a message with several replies) are preserved, never flattened
into separate conversations, and conversations are never merged because authors match.
"""
from __future__ import annotations

import csv
import hashlib
import io
import random
import re
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

PARSER_VERSION = "twcs-parser-1.0"
REQUIRED_COLUMNS = ("tweet_id", "author_id", "inbound", "created_at", "text", "response_tweet_id", "in_response_to_tweet_id")
SELECTION_METHOD = (
    "Eligible threads sorted by stable conversation key; uniform random sample without replacement "
    "via Python random.Random(seed).sample; selected keys re-sorted."
)

_ID = re.compile(r"^\d{1,25}$")
_FLOAT_ID = re.compile(r"^(\d{1,25})\.0+$")
csv.field_size_limit(10_000_000)


class SchemaError(ValueError):
    pass


class Cancelled(Exception):
    pass


def parse_id(raw: str | None) -> str | None:
    """String-safe id. Accepts '123' and the float artefact '123.0'. Returns None for blank, raises for junk."""
    if raw is None:
        return None
    s = raw.strip()
    if not s or s.lower() in {"nan", "null", "none"}:
        return None
    if _ID.match(s):
        return s.lstrip("0") or "0"
    m = _FLOAT_ID.match(s)
    if m:
        return m.group(1).lstrip("0") or "0"
    raise ValueError(f"invalid id {s!r}")


def parse_id_list(raw: str | None) -> list[str]:
    if not raw or not raw.strip():
        return []
    return [i for i in (parse_id(p) for p in raw.split(",")) if i]


_TRUE = {"true", "1", "yes", "t"}
_FALSE = {"false", "0", "no", "f"}


def parse_bool(raw: str | None) -> bool:
    """Explicit boolean parsing. Anything not clearly true/false raises (never truthy-string coercion)."""
    s = (raw or "").strip().lower()
    if s in _TRUE:
        return True
    if s in _FALSE:
        return False
    raise ValueError(f"invalid boolean {raw!r}")


_TS_FORMATS = ("%a %b %d %H:%M:%S %z %Y", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d %H:%M:%S%z", "%Y-%m-%d %H:%M:%S")


def parse_timestamp(raw: str | None) -> datetime:
    s = (raw or "").strip()
    if not s:
        raise ValueError("empty timestamp")
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    for fmt in _TS_FORMATS:
        try:
            dt = datetime.strptime(s, fmt)
        except ValueError:
            continue
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    try:
        dt = datetime.fromisoformat(s)
        return (dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)).astimezone(timezone.utc)
    except ValueError as exc:
        raise ValueError(f"invalid timestamp {raw!r}") from exc


def conversation_key(source_kind: str, root_id: str) -> str:
    return "cv_" + hashlib.sha256(f"{source_kind}:{root_id}".encode()).hexdigest()[:16]


@dataclass(slots=True)
class Node:
    id: str
    parent: str | None
    inbound: bool
    author: str
    created_at: datetime | None
    declared_children: tuple[str, ...]
    row_hash: int


@dataclass
class Thread:
    root: str
    members: list[str]  # BFS order
    depth: dict[str, int]
    children: dict[str, list[str]]
    root_missing_parent: str | None
    branch_count: int
    max_depth: int
    dangling_children: int
    customer: int
    support: int
    key: str = ""
    eligible: bool = False
    reason: str | None = None


@dataclass
class GraphResult:
    nodes: dict[str, Node]
    threads: list[Thread]
    cycle_message_ids: set[str]
    stats: dict = field(default_factory=dict)


class _CountingReader(io.RawIOBase):
    def __init__(self, raw):
        self.raw = raw
        self.count = 0

    def readable(self):
        return True

    def readinto(self, b):
        n = self.raw.readinto(b)
        self.count += n or 0
        return n


def file_sha256(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def inspect_schema(path: Path) -> dict:
    """Read the header and a few rows; validate required columns before any import work."""
    with open(path, newline="", encoding="utf-8-sig", errors="replace") as f:
        reader = csv.reader(f)
        try:
            header = [h.strip() for h in next(reader)]
        except StopIteration as exc:
            raise SchemaError("File is empty.") from exc
        sample = [row for _, row in zip(range(5), reader)]
    missing = [c for c in REQUIRED_COLUMNS if c not in header]
    if missing:
        raise SchemaError(f"Missing required columns: {', '.join(missing)}. Found: {', '.join(header[:20])}")
    return {"columns": header, "extra_columns": [c for c in header if c not in REQUIRED_COLUMNS], "sample_rows": len(sample)}


ProgressFn = Callable[[str, float], None]


def build_graph(
    path: Path,
    progress: ProgressFn | None = None,
    should_cancel: Callable[[], bool] | None = None,
) -> GraphResult:
    """Pass 1: validate rows, detect duplicates, and build the reply graph (text is not held in memory)."""
    total_bytes = max(path.stat().st_size, 1)
    stats: Counter[str] = Counter()
    nodes: dict[str, Node] = {}
    conflicting: set[str] = set()
    raw = open(path, "rb")
    counter = _CountingReader(raw)
    try:
        text = io.TextIOWrapper(io.BufferedReader(counter), encoding="utf-8-sig", errors="replace", newline="")
        reader = csv.DictReader(text)
        if reader.fieldnames is None or any(c not in reader.fieldnames for c in REQUIRED_COLUMNS):
            raise SchemaError("Missing required columns.")
        for i, row in enumerate(reader):
            stats["rows_read"] += 1
            if i % 20000 == 0:
                if should_cancel and should_cancel():
                    raise Cancelled()
                if progress:
                    progress("building reply graph", min(counter.count / total_bytes, 1.0))
            try:
                tid = parse_id(row.get("tweet_id"))
                if tid is None:
                    raise ValueError("missing id")
            except ValueError:
                stats["rejected_invalid_id"] += 1
                continue
            try:
                inbound = parse_bool(row.get("inbound"))
            except ValueError:
                stats["rejected_invalid_boolean"] += 1
                continue
            try:
                created = parse_timestamp(row.get("created_at"))
            except ValueError:
                created = None
                stats["invalid_timestamp"] += 1
            try:
                parent = parse_id(row.get("in_response_to_tweet_id"))
                declared = tuple(parse_id_list(row.get("response_tweet_id")))
            except ValueError:
                stats["rejected_invalid_reference"] += 1
                continue
            author = (row.get("author_id") or "").strip()
            if not author:
                stats["rejected_missing_author"] += 1
                continue
            rh = hash((tid, author, inbound, row.get("created_at"), row.get("text"), parent))
            if tid in nodes:
                if nodes[tid].row_hash == rh:
                    stats["exact_duplicates_dropped"] += 1
                else:
                    stats["conflicting_duplicates"] += 1
                    conflicting.add(tid)
                continue
            if parent == tid:
                stats["self_reply"] += 1
            nodes[tid] = Node(tid, parent, inbound, author, created, declared, rh)
    finally:
        raw.close()
    stats["unique_messages"] = len(nodes)

    # Reply graph: children from in_response_to (authoritative), cross-checked against response_tweet_id.
    children: dict[str, list[str]] = defaultdict(list)
    missing_parent_roots = 0
    for n in nodes.values():
        if n.parent and n.parent in nodes and n.parent != n.id:
            children[n.parent].append(n.id)
        elif n.parent and n.parent not in nodes:
            missing_parent_roots += 1
    declared_mismatch = 0
    for n in nodes.values():
        for c in n.declared_children:
            if c in nodes and nodes[c].parent != n.id:
                declared_mismatch += 1
    stats["messages_with_missing_parent"] = missing_parent_roots
    stats["response_reference_mismatches"] = declared_mismatch

    # Cycle detection: walk parent pointers with colouring.
    state: dict[str, int] = {}
    cycle_ids: set[str] = set()
    for start in nodes:
        if start in state:
            continue
        path_ids: list[str] = []
        pos: dict[str, int] = {}
        cur: str | None = start
        while cur is not None and cur in nodes and cur not in state:
            pos[cur] = len(path_ids)
            path_ids.append(cur)
            state[cur] = 1
            nxt = nodes[cur].parent
            if nxt == cur:
                cycle_ids.add(cur)
                break
            if nxt in pos:
                cycle_ids.update(path_ids[pos[nxt]:])
                break
            cur = nxt
        for pid in path_ids:
            state[pid] = 2
    # Anything that descends from a cycle is also unreachable from a proper root.
    stack = list(cycle_ids)
    tainted = set(cycle_ids)
    while stack:
        x = stack.pop()
        for c in children.get(x, ()):
            if c not in tainted:
                tainted.add(c)
                stack.append(c)
    stats["messages_in_cycles"] = len(cycle_ids)
    stats["messages_unreachable_due_to_cycles"] = len(tainted)

    roots = [n.id for n in nodes.values() if n.id not in tainted and (n.parent is None or n.parent not in nodes or n.parent == n.id)]
    threads: list[Thread] = []
    for r in roots:
        depth = {r: 0}
        order = [r]
        kids: dict[str, list[str]] = {}
        i = 0
        branch = 0
        dangling = 0
        while i < len(order):
            x = order[i]
            i += 1
            ch = sorted(children.get(x, ()), key=lambda c: (nodes[c].created_at or datetime.max.replace(tzinfo=timezone.utc), int(c)))
            kids[x] = ch
            if len(ch) > 1:
                branch += 1
            dangling += sum(1 for c in nodes[x].declared_children if c not in nodes)
            for c in ch:
                depth[c] = depth[x] + 1
                order.append(c)
        cust = sum(1 for m in order if nodes[m].inbound)
        rp = nodes[r].parent
        threads.append(Thread(
            root=r, members=order, depth=depth, children=kids,
            root_missing_parent=rp if rp and rp not in nodes else None,
            branch_count=branch, max_depth=max(depth.values()), dangling_children=dangling,
            customer=cust, support=len(order) - cust,
        ))
    # A conflicting duplicate taints its thread.
    conflict_threads = 0
    if conflicting:
        for t in threads:
            if conflicting.intersection(t.members):
                t.reason = "conflicting_duplicate"
                conflict_threads += 1
    stats["threads_total"] = len(threads)
    if progress:
        progress("reply graph built", 1.0)
    return GraphResult(nodes=nodes, threads=threads, cycle_message_ids=tainted, stats=dict(stats))


def apply_eligibility(graph: GraphResult, source_kind: str, max_messages: int) -> Counter:
    """Eligibility rules (v1). Returns exclusion counts by reason."""
    reasons: Counter[str] = Counter()
    for t in graph.threads:
        t.key = conversation_key(source_kind, t.root)
        if t.reason is None:
            root = graph.nodes[t.root]
            if t.root_missing_parent:
                t.reason = "root_parent_missing"  # conversation start not in file -> incomplete
            elif not root.inbound:
                t.reason = "not_customer_initiated"
            elif len(t.members) < 2:
                t.reason = "single_message"
            elif t.support == 0:
                t.reason = "no_support_reply"
            elif len(t.members) > max_messages:
                t.reason = "exceeds_max_messages"
        if t.reason:
            reasons[t.reason] += 1
        else:
            t.eligible = True
    if graph.cycle_message_ids:
        reasons["cycle_component_messages"] = len(graph.cycle_message_ids)
    return reasons


def sample_threads(threads: Iterable[Thread], n: int, seed: int) -> list[Thread]:
    eligible = sorted((t for t in threads if t.eligible), key=lambda t: t.key)
    if len(eligible) <= n:
        return eligible
    picked = random.Random(seed).sample(eligible, n)
    return sorted(picked, key=lambda t: t.key)


def load_texts(path: Path, wanted: set[str], should_cancel: Callable[[], bool] | None = None,
               progress: ProgressFn | None = None) -> dict[str, str]:
    """Pass 2: fetch text only for selected message ids (first occurrence wins, as in pass 1)."""
    out: dict[str, str] = {}
    total_bytes = max(path.stat().st_size, 1)
    raw = open(path, "rb")
    counter = _CountingReader(raw)
    try:
        text = io.TextIOWrapper(io.BufferedReader(counter), encoding="utf-8-sig", errors="replace", newline="")
        for i, row in enumerate(csv.DictReader(text)):
            if i % 20000 == 0:
                if should_cancel and should_cancel():
                    raise Cancelled()
                if progress:
                    progress("loading selected text", min(counter.count / total_bytes, 1.0))
            try:
                tid = parse_id(row.get("tweet_id"))
            except ValueError:
                continue
            if tid in wanted and tid not in out:
                out[tid] = row.get("text") or ""
                if len(out) == len(wanted):
                    break
    finally:
        raw.close()
    return out


def branching_stats(threads: list[Thread]) -> dict:
    if not threads:
        return {"threads": 0}
    sizes = sorted(len(t.members) for t in threads)
    branched = [t for t in threads if t.branch_count > 0]
    return {
        "threads": len(threads),
        "branched_threads": len(branched),
        "branch_points": sum(t.branch_count for t in threads),
        "median_messages": sizes[len(sizes) // 2],
        "max_messages": sizes[-1],
        "max_depth": max(t.max_depth for t in threads),
        "with_dangling_reply_refs": sum(1 for t in threads if t.dangling_children),
    }
