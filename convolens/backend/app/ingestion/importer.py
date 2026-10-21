"""Import pipeline: validate -> hash -> reply graph -> eligibility -> seeded sample -> redact ->
language detection -> rules analysis -> persist -> manifest."""
from __future__ import annotations

import hashlib
import logging
from collections import Counter
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import delete, insert, select

from app.analytics.labels import apply_effective_labels
from app.analytics.rules import RULES_VERSION, Msg, analyze, message_stages, validate_evidence
from app.config import get_settings
from app.db import session_scope
from app.ingestion import twcs
from app.models.orm import Analysis, Conversation, Dataset, Exclusion, Message
from app.multilingual.language import DETECTOR_VERSION, detect_language
from app.security.redaction import REDACTOR_VERSION, pseudonymize, redact

log = logging.getLogger(__name__)

ProgressFn = Callable[[str, float], None]


def dataset_id_for(file_hash: str, kind: str, seed: int, n: int, max_msgs: int) -> str:
    return "ds_" + hashlib.sha256(f"{file_hash}:{kind}:{seed}:{n}:{max_msgs}:{twcs.PARSER_VERSION}".encode()).hexdigest()[:12]


def run_import(
    path: Path,
    *,
    kind: str,
    name: str,
    source_label: str,
    synthetic: bool,
    seed: int | None = None,
    sample_size: int | None = None,
    progress: ProgressFn | None = None,
    should_cancel: Callable[[], bool] | None = None,
) -> str:
    settings = get_settings()
    seed = settings.sample_seed if seed is None else seed
    n = settings.sample_size if sample_size is None else sample_size
    max_msgs = settings.max_conversation_messages
    prog = progress or (lambda s, p: None)
    started = datetime.now(timezone.utc)

    prog("validating schema", 0.01)
    schema = twcs.inspect_schema(path)
    prog("hashing file", 0.02)
    fhash = twcs.file_sha256(path)
    ds_id = dataset_id_for(fhash, kind, seed, n, max_msgs)

    with session_scope() as s:
        existing = s.get(Dataset, ds_id)
        if existing and existing.status == "ready":
            prog("already imported (same file, seed and parameters)", 1.0)
            return ds_id
        if existing:  # recovery from an interrupted or failed import
            s.execute(delete(Dataset).where(Dataset.id == ds_id))
        s.add(Dataset(id=ds_id, name=name, kind=kind, synthetic=synthetic, status="importing", source=source_label,
                      file_hash=fhash, sample_seed=seed, manifest={}, active_analysis=f"rules:{RULES_VERSION}"))

    try:
        graph = twcs.build_graph(path, progress=lambda st, p: prog(st, 0.03 + 0.45 * p), should_cancel=should_cancel)
        reasons = twcs.apply_eligibility(graph, kind, max_msgs)
        eligible = [t for t in graph.threads if t.eligible]
        selected = twcs.sample_threads(graph.threads, n, seed)
        selected_roots = {t.root for t in selected}
        wanted = {m for t in selected for m in t.members}
        texts = twcs.load_texts(path, wanted, should_cancel=should_cancel, progress=lambda st, p: prog(st, 0.48 + 0.2 * p))
        support_handles = {graph.nodes[m].author for t in selected for m in t.members if not graph.nodes[m].inbound}

        redaction_totals: Counter[str] = Counter()
        lang_counts: Counter[str] = Counter()
        completeness: Counter[str] = Counter()
        missing_text = 0
        for bi in range(0, len(selected), 200):
            if should_cancel and should_cancel():
                raise twcs.Cancelled()
            batch = selected[bi:bi + 200]
            with session_scope() as s:
                for t in batch:
                    nodes = [graph.nodes[m] for m in t.members]
                    order = sorted(t.members, key=lambda mid: (graph.nodes[mid].created_at or started, t.depth[mid], int(mid)))
                    msgs: list[Msg] = []
                    rows = []
                    for pos, mid in enumerate(order):
                        nd = graph.nodes[mid]
                        raw = texts.get(mid)
                        if raw is None:
                            missing_text += 1
                            raw = ""
                        red, counts = redact(raw, support_handles)
                        redaction_totals.update(counts)
                        lang = detect_language(red)
                        lang_counts[lang["language"]] += 1
                        role = "customer" if nd.inbound else "support"
                        msgs.append(Msg(mid, role, red, lang["language"]))
                        rows.append(dict(source_id=mid, parent_source_id=nd.parent, role=role,
                                         author_ref=nd.author if not nd.inbound else pseudonymize(nd.author),
                                         created_at=nd.created_at, position=pos, depth=t.depth[mid],
                                         child_count=len(t.children.get(mid, [])), text=red, redactions=counts,
                                         language=lang["language"], language_confidence=lang["confidence"],
                                         language_detail=lang["detail"]))
                    stages = message_stages(msgs)
                    content_hash = hashlib.sha256("\n".join(f"{m.role}|{m.source_id}|{m.text}" for m in msgs).encode()).hexdigest()
                    created = [nd.created_at for nd in nodes if nd.created_at]
                    root_dt = graph.nodes[t.root].created_at
                    first_sup = min((graph.nodes[m].created_at for m in t.members if not graph.nodes[m].inbound and graph.nodes[m].created_at), default=None)
                    comp = "partial" if t.dangling_children or any(r["text"] == "" for r in rows) else "complete"
                    completeness[comp] += 1
                    brand = next((graph.nodes[m].author for m in order if not graph.nodes[m].inbound), None)
                    conv = Conversation(
                        dataset_id=ds_id, key=t.key, root_source_id=t.root, brand=brand, message_count=len(order),
                        customer_turns=t.customer, support_turns=t.support, branch_count=t.branch_count,
                        max_depth=t.max_depth, completeness=comp,
                        started_at=min(created) if created else None, ended_at=max(created) if created else None,
                        first_response_s=(first_sup - root_dt).total_seconds() if first_sup and root_dt else None,
                        content_hash=content_hash,
                        languages=sorted({r["language"] for r in rows}),
                    )
                    s.add(conv)
                    s.flush()
                    for r, st in zip(rows, stages):
                        s.add(Message(dataset_id=ds_id, conversation_id=conv.id, stage=st, **r))
                    result = analyze(msgs)
                    valid, invalid = validate_evidence(result["evidence"], {m.source_id: m.text for m in msgs})
                    result["evidence"] = valid
                    result["invalid_evidence"] = invalid
                    a = Analysis(conversation_id=conv.id, method="rules", model_id=None, prompt_version=RULES_VERSION,
                                 content_hash=content_hash, fields=result)
                    s.add(a)
                    s.flush()
                    apply_effective_labels(conv, a.fields, a.id)
            prog("redacting, detecting language and analysing", 0.7 + 0.25 * min((bi + 200) / max(len(selected), 1), 1))

        prog("recording exclusions", 0.96)
        excl_rows = [dict(dataset_id=ds_id, root_source_id=t.root, reason=t.reason or "not_sampled", message_count=len(t.members))
                     for t in graph.threads if t.root not in selected_roots]
        with session_scope() as s:
            for i in range(0, len(excl_rows), 5000):
                s.execute(insert(Exclusion), excl_rows[i:i + 5000])

        not_sampled = len(eligible) - len(selected)
        manifest = {
            "source": source_label,
            "source_kind": kind,
            "synthetic": synthetic,
            "file_name": path.name,
            "file_bytes": path.stat().st_size,
            "file_hash_sha256": fhash,
            "schema": schema,
            "parser_version": twcs.PARSER_VERSION,
            "redactor_version": REDACTOR_VERSION,
            "language_detector": DETECTOR_VERSION,
            "analysis": f"rules:{RULES_VERSION}",
            "unit_of_analysis": "conversation = one reply tree (connected component of in_response_to_tweet_id links); "
                                "each message belongs to exactly one conversation",
            "sampling": {"seed": seed, "method": twcs.SELECTION_METHOD, "requested": n, "eligible": len(eligible),
                         "selected": len(selected), "not_sampled": not_sampled,
                         "coverage_of_eligible": round(len(selected) / len(eligible), 4) if eligible else None,
                         "eligibility_rules": ["root is customer-initiated (inbound=True)", "root's parent present in file",
                                               "at least one support reply", f"at most {max_msgs} messages",
                                               "no cycle", "no conflicting duplicate ids"]},
            "counts": {**graph.stats, "selected_messages": len(wanted), "selected_messages_missing_text": missing_text},
            "exclusions": dict(reasons) | {"not_sampled": not_sampled},
            "completeness": dict(completeness),
            "branching": {"selected": twcs.branching_stats(selected), "eligible": twcs.branching_stats(eligible)},
            "languages": dict(lang_counts),
            "redactions": dict(redaction_totals),
            "import_started_at": started.isoformat(),
            "import_completed_at": datetime.now(timezone.utc).isoformat(),
        }
        with session_scope() as s:
            ds = s.get(Dataset, ds_id)
            ds.manifest = manifest
            ds.status = "ready"
            ds.imported_at = datetime.now(timezone.utc)
        prog("completed", 1.0)
        return ds_id
    except BaseException:
        with session_scope() as s:
            s.execute(delete(Dataset).where(Dataset.id == ds_id))
        raise


def dataset_exists(kind: str) -> str | None:
    with session_scope() as s:
        return s.scalar(select(Dataset.id).where(Dataset.kind == kind, Dataset.status == "ready"))
