"""Evidence node: retrieve authorized records and turn them into cited
evidence items with provenance, freshness and support/opposition tags.

Tools (all read-only, tenant-scoped): account_context, support_history,
incident_search, diagnostics, peer_health, on_demand_line_test,
knowledge_search. Support/opposition tags are computed by documented rules
(data/synthetic/diagnostic_rules.json), never by model wording.
"""
from __future__ import annotations

import json
import re
import statistics
from datetime import datetime, timedelta
from functools import lru_cache

from sqlalchemy.orm import Session

from ..config import get_settings
from ..connectors import synthetic as conn
from ..connectors.base import ConnectorError, retry_read
from ..models.orm import Case, DiagnosticSample
from ..retrieval import knowledge
from .contracts import EvidenceBundle, EvidenceItem, EvidencePlanLLM, TriageOutput
from .providers import Provider

SYSTEM_PROMPT = """You plan knowledge retrieval for a telecom support investigation.
Given structured findings (not raw records), propose up to 4 short search queries for
troubleshooting guides, runbooks and policies that are relevant. Do not draw conclusions.
Return JSON matching the schema."""

TOOLS = ("account_context", "support_history", "incident_search", "diagnostics", "peer_health",
         "on_demand_line_test", "knowledge_search")

INJECTION_PATTERNS = [
    r"ignore (all |any )?(previous|prior|above) instructions",
    r"system (note|prompt|message|instruction)",
    r"\byou are now\b",
    r"do not mention",
    r"pre-?approved",
    r"without (supervisor |any )?approval",
    r"note to (the )?(ai|assistant|model)",
]
_INJ = re.compile("|".join(INJECTION_PATTERNS), re.I)


@lru_cache
def rules() -> dict:
    return json.loads((get_settings().data_dir / "synthetic" / "diagnostic_rules.json").read_text())


def detect_injection(text: str) -> re.Match | None:
    return _INJ.search(text)


def quarantine(text: str) -> str:
    m = detect_injection(text)
    if not m:
        return text
    # Keep only the content before the first instruction-like marker.
    safe = text[: m.start()].rstrip(" -—:\n")
    safe = re.sub(r"[-—]{2,}\s*$", "", safe).strip()
    return f"{safe} [instruction-like content quarantined; not used as evidence]".strip()


def _iso(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds")


def _per_hour(count: int, interval_minutes: int) -> float:
    return count * 60.0 / max(interval_minutes, 1)


def is_healthy(s: DiagnosticSample) -> bool:
    h = rules()["healthy_sample"]
    return (s.link_state == h["link_state"] and s.loss_of_signal_events <= h["loss_of_signal_events_max"]
            and s.link_retrains <= h["link_retrains_max"] and s.packet_loss_pct <= h["packet_loss_pct_max"]
            and s.cpe_unexpected_reboots <= h["cpe_unexpected_reboots_max"])


def series_stats(samples: list[DiagnosticSample]) -> dict:
    """Deterministic statistics; also used by the citation validator."""
    los = [s for s in samples if s.loss_of_signal_events > 0]
    reboots = [s for s in samples if s.cpe_unexpected_reboots > 0]
    unexplained = [s for s in samples if s.link_retrains > 0 and s.loss_of_signal_events == 0
                   and s.cpe_unexpected_reboots == 0]
    snrs = [s.snr_margin_db for s in samples if s.snr_margin_db is not None]
    return {
        "samples": len(samples),
        "first": _iso(samples[0].collected_at) if samples else None,
        "last": _iso(samples[-1].collected_at) if samples else None,
        "median_snr_db": round(statistics.median(snrs), 2) if snrs else None,
        "median_crc_per_hour": round(statistics.median(
            [_per_hour(s.crc_errors, s.interval_minutes) for s in samples]), 1) if samples else None,
        "median_unexplained_retrains_per_hour": round(statistics.median(
            [_per_hour(s.link_retrains, s.interval_minutes) if s in unexplained else 0.0
             for s in samples]), 2) if samples else None,
        "median_packet_loss_pct": round(statistics.median([s.packet_loss_pct for s in samples]), 2)
        if samples else None,
        "los_samples": len(los),
        "first_los_at": _iso(los[0].collected_at) if los else None,
        "unexpected_reboots": sum(s.cpe_unexpected_reboots for s in samples),
        "retrain_samples": sum(1 for s in samples if s.link_retrains > 0),
        "retrain_samples_with_reboot": sum(1 for s in samples if s.link_retrains > 0 and s.cpe_unexpected_reboots > 0),
        "healthy_samples": sum(1 for s in samples if is_healthy(s)),
        "reboot_sample_ids": [s.id for s in reboots],
        "los_sample_ids": [s.id for s in los],
    }


class Collector:
    def __init__(self, now: datetime):
        self.items: list[EvidenceItem] = []
        self.facts: set[str] = set()
        self.missing: list[str] = []
        self.prior_actions: list[dict] = []
        self.now = now

    def add(self, **kw) -> EvidenceItem:
        kw.setdefault("retrieved_at", _iso(self.now))
        item = EvidenceItem(**kw)
        self.items.append(item)
        return item


def _diagnostic_items(c: Collector, samples: list[DiagnosticSample], service_id: str) -> None:
    r = rules()
    st = series_stats(samples)
    ids = [s.id for s in samples]
    span = f"{st['first']} to {st['last']}"
    base = dict(source_type="diagnostic_series", source_version=st["last"], authority="measurement",
                kind="observation", freshness="fresh")
    c.facts.add("fresh_diagnostics")

    snr_low = st["median_snr_db"] is not None and st["median_snr_db"] < r["line"]["snr_min_db"]
    c.add(ref_id="DIAG-SNR", source_id=f"{service_id}:snr", **base,
          excerpt=f"Median SNR margin {st['median_snr_db']} dB across {st['samples']} samples ({span}); "
                  f"threshold {r['line']['snr_min_db']} dB.",
          supports=["LINE_IMPAIRMENT"] if snr_low else [],
          opposes=[] if snr_low else ["LINE_IMPAIRMENT"],
          data={"sample_ids": ids, "metric": "median_snr_db", "value": st["median_snr_db"]})

    crc_high = st["median_crc_per_hour"] > r["line"]["crc_errors_per_hour_max"]
    c.add(ref_id="DIAG-CRC", source_id=f"{service_id}:crc", **base,
          excerpt=f"Median CRC errors {st['median_crc_per_hour']} per hour ({span}); "
                  f"threshold {r['line']['crc_errors_per_hour_max']}.",
          supports=["LINE_IMPAIRMENT"] if crc_high else [],
          data={"sample_ids": ids, "metric": "median_crc_per_hour", "value": st["median_crc_per_hour"]})

    retr_high = st["median_unexplained_retrains_per_hour"] > r["line"]["retrains_per_hour_max"]
    c.add(ref_id="DIAG-RETRAIN", source_id=f"{service_id}:retrains", **base,
          excerpt=f"Median {st['median_unexplained_retrains_per_hour']} link retrains per hour not "
                  f"explained by loss of signal or modem reboots ({span}); threshold "
                  f"{r['line']['retrains_per_hour_max']}.",
          supports=["LINE_IMPAIRMENT"] if retr_high else [],
          data={"sample_ids": ids, "metric": "median_unexplained_retrains_per_hour",
                "value": st["median_unexplained_retrains_per_hour"]})

    if st["los_samples"]:
        c.add(ref_id="DIAG-LOS", source_id=f"{service_id}:los", **base,
              excerpt=f"Loss of signal recorded in {st['los_samples']} of {st['samples']} samples, "
                      f"first at {st['first_los_at']}.",
              supports=["AREA_INCIDENT", "UNDECLARED_AREA_ISSUE"],
              data={"sample_ids": st["los_sample_ids"], "metric": "los_samples", "value": st["los_samples"]})
        c.facts.add("customer_los")
    else:
        c.add(ref_id="DIAG-LOS", source_id=f"{service_id}:los", **base,
              excerpt=f"No loss-of-signal events in {st['samples']} samples ({span}).",
              opposes=["AREA_INCIDENT", "UNDECLARED_AREA_ISSUE"],
              data={"sample_ids": ids, "metric": "los_samples", "value": 0})

    reboots = st["unexpected_reboots"]
    eq_min = r["equipment"]["unexpected_reboots_24h_min"]
    c.add(ref_id="DIAG-REBOOT", source_id=f"{service_id}:reboots", **base,
          excerpt=f"{reboots} unexpected modem reboots in {st['samples']} samples ({span}); "
                  f"equipment-fault indicator at {eq_min} or more in 24 hours.",
          supports=["EQUIPMENT_FAULT"] if reboots >= eq_min else [],
          opposes=["EQUIPMENT_FAULT"] if reboots == 0 else [],
          data={"sample_ids": st["reboot_sample_ids"] or ids, "metric": "unexpected_reboots",
                "value": reboots})
    if reboots >= eq_min and st["retrain_samples"] and st["retrain_samples"] == st["retrain_samples_with_reboot"]:
        c.add(ref_id="DIAG-REBOOT-RETRAIN", source_id=f"{service_id}:retrain_reboot_coincidence", **base,
              excerpt=f"All {st['retrain_samples']} samples with link retrains coincide with an "
                      f"unexpected modem reboot; line metrics between reboots are within thresholds.",
              supports=["EQUIPMENT_FAULT"],
              data={"sample_ids": st["reboot_sample_ids"], "metric": "retrain_samples_with_reboot",
                    "value": st["retrain_samples_with_reboot"]})

    if st["healthy_samples"] == st["samples"]:
        c.facts.add("measured_stable")
        c.add(ref_id="DIAG-STABLE", source_id=f"{service_id}:stability", **base,
              excerpt=f"All {st['samples']} samples ({span}) are healthy: link up, no loss of signal, "
                      f"no retrains, packet loss <= 1%, no unexpected reboots.",
              opposes=["AREA_INCIDENT", "LINE_IMPAIRMENT", "EQUIPMENT_FAULT", "UNDECLARED_AREA_ISSUE"],
              flags=["measured_stable"],
              data={"sample_ids": ids, "metric": "healthy_samples", "value": st["healthy_samples"]})
    if snr_low or crc_high or retr_high:
        c.facts.update({"line_fault", "line_or_equipment_fault"})
    if reboots >= eq_min:
        c.facts.update({"equipment_fault", "line_or_equipment_fault"})


def collect(db: Session, *, tenant_id: str, role: str, case: Case, triage: TriageOutput,
            iteration: int, requested: list[str], now: datetime, provider: Provider,
            budget_used: int, tool_log: list[dict]) -> tuple[EvidenceBundle, object]:
    s = get_settings()
    c = Collector(now)
    fresh_since = now - timedelta(hours=s.diagnostic_freshness_hours)
    symptom_start = now - timedelta(hours=triage.lookback_hours)

    def log(tool: str, ids: list[str]):
        tool_log.append({"tool": tool, "source_ids": ids[:20], "count": len(ids)})

    ctx = retry_read(lambda: conn.account_context.get(db, tenant_id, case))
    mapping, equipment, path = ctx["mapping"], ctx["equipment"], ctx["path"]
    log("account_context", [ctx["account"].id, ctx["service"].id])

    c.add(ref_id="STATEMENT", source_type="customer_statement", source_id=case.id,
          source_version=_iso(case.created_at), authority="customer_statement", kind="statement",
          excerpt=quarantine(case.complaint_text), freshness="n/a",
          flags=["reported_symptom"] + (["prompt_injection"] if detect_injection(case.complaint_text) else []),
          data={"symptom_pattern": triage.symptom_pattern, "onset": triage.onset})

    if mapping is not None:
        path_ids = [a.id for a in path]
        c.add(ref_id="MAPPING", source_type="service_mapping", source_id=mapping.id,
              source_version=_iso(mapping.updated_at), authority="system_record", kind="record",
              excerpt=f"Service {mapping.service_id} is mapped to {mapping.asset_id} port {mapping.port}; "
                      f"network path: {' -> '.join(path_ids)}.",
              freshness="n/a", data={"asset_path": path_ids, "port": mapping.port})
    else:
        c.missing.append("service_mapping")
        path_ids = []
    if equipment is not None:
        c.add(ref_id="EQUIPMENT", source_type="equipment", source_id=equipment.id,
              source_version=_iso(equipment.updated_at), authority="system_record", kind="record",
              excerpt=f"Customer equipment {equipment.model}, firmware {equipment.firmware}.",
              freshness="n/a", data={"model": equipment.model, "firmware": equipment.firmware})

    # ---- Support history (statements/notes, never measurements) ----
    history = conn.support_history.list(db, tenant_id, case.account_id, now - timedelta(days=90))
    log("support_history", [h.id for h in history])
    for h in history:
        raw = f"{h.summary} {h.notes}".strip()
        flags = [f"author:{h.author_type}"]
        injected = detect_injection(raw)
        if injected:
            flags += ["prompt_injection", "untrusted_content"]
            c.facts.add("prompt_injection_detected")
        supports = []
        if re.search(r"snr|line check", h.notes, re.I) and re.search(r"marginal|low", h.notes, re.I):
            supports.append("LINE_IMPAIRMENT")
        if re.search(r"wi-?fi", h.notes, re.I) and re.search(r"connected|pages", h.notes, re.I):
            supports.append("HOME_NETWORK")
        prev = [a.split(":", 1)[1] for a in h.actions_taken if a.startswith("linked_to_incident:")]
        if prev:
            flags.append(f"previous_diagnosis_incident:{prev[0]}")
        authority = {"agent": "agent_note", "customer": "customer_note", "analyst": "analyst_note"}[h.author_type]
        c.add(ref_id=f"HIST-{h.id}", source_type="support_interaction", source_id=h.id,
              source_version=_iso(h.occurred_at), authority=authority, kind="note",
              excerpt=quarantine(raw), freshness="n/a", supports=supports, flags=flags,
              data={"channel": h.channel, "occurred_at": _iso(h.occurred_at),
                    "actions_taken": h.actions_taken, "outcome": h.outcome})
        tried = [a for a in h.actions_taken if not a.startswith("linked_to_incident:")]
        if tried:
            c.prior_actions.append({"source_ref": f"HIST-{h.id}", "actions": tried,
                                    "outcome": h.outcome, "occurred_at": _iso(h.occurred_at)})
    if triage.customer_reported_actions:
        c.prior_actions.append({"source_ref": "STATEMENT", "actions": triage.customer_reported_actions,
                                "outcome": "customer reports symptom continues",
                                "occurred_at": _iso(case.created_at)})

    # ---- Diagnostics ----
    fresh = retry_read(lambda: conn.diagnostics.samples(db, tenant_id, case.service_id, fresh_since))
    log("diagnostics", [x.id for x in fresh])
    if not fresh and "fresh_line_diagnostics" in requested:
        try:
            test = retry_read(lambda: conn.diagnostics.on_demand_test(db, tenant_id, case))
        except ConnectorError as exc:
            test = None
            tool_log.append({"tool": "on_demand_line_test", "error": exc.code})
        log("on_demand_line_test", [test.id] if test else [])
        if test is not None and test.collected_at >= fresh_since:
            fresh = [test]
        else:
            c.add(ref_id="LINE-TEST", source_type="diagnostic_sample", source_id=f"{case.service_id}:on_demand",
                  source_version=_iso(now), authority="system_record", kind="record",
                  excerpt="On-demand line test requested; the simulated test system reported it unavailable.",
                  freshness="n/a", flags=["test_unavailable"])
    if fresh:
        _diagnostic_items(c, fresh, case.service_id)
    else:
        latest = conn.diagnostics.latest(db, tenant_id, case.service_id)
        if latest is not None:
            age_h = (now - latest.collected_at).total_seconds() / 3600
            c.add(ref_id="DIAG-STALE", source_type="diagnostic_sample", source_id=latest.id,
                  source_version=_iso(latest.collected_at), authority="measurement", kind="observation",
                  excerpt=f"Most recent sample collected {age_h:.0f} hours ago at {_iso(latest.collected_at)}; "
                          f"older than the {s.diagnostic_freshness_hours} hour freshness limit.",
                  freshness="stale", flags=["stale"])
        c.facts.add("stale_only")
        c.missing.append("fresh_line_diagnostics")

    # ---- Peer health on the mapped access node ----
    if path:
        access = path[0]
        ph = conn.diagnostics.peer_health(db, tenant_id, access.id, case.service_id, fresh_since)
        log("peer_health", [access.id])
        with_data = ph["peers_with_fresh_data"]
        frac = ph["peers_with_loss_of_signal"] / with_data if with_data else None
        supports, opposes = [], []
        if frac is not None and frac >= rules()["area"]["peer_los_fraction_min"]:
            supports = ["AREA_INCIDENT", "UNDECLARED_AREA_ISSUE"]
            c.facts.add("peers_los")
        elif frac == 0:
            opposes = ["AREA_INCIDENT", "UNDECLARED_AREA_ISSUE"]
            c.facts.add("peers_healthy")
        c.add(ref_id="PEERS", source_type="peer_health", source_id=f"{access.id}:peers",
              source_version=_iso(now), authority="measurement", kind="observation",
              excerpt=f"{ph['peers_with_loss_of_signal']} of {with_data} other services on {access.id} "
                      f"with fresh data show loss of signal in the last {s.diagnostic_freshness_hours} hours.",
              freshness="fresh" if with_data else "n/a", supports=supports, opposes=opposes,
              data=ph)

    # ---- Incidents: mapped path first, proximity separately ----
    on_path = conn.incidents.on_path(db, tenant_id, path_ids)
    log("incident_search", [i.id for i in on_path])
    slack = timedelta(minutes=s.incident_window_slack_minutes)
    for inc in on_path:
        end = inc.ended_at or now
        overlaps = inc.started_at <= now and end + slack >= symptom_start
        active = inc.status == "active"
        flags = ["mapped_path"]
        supports: list[str] = []
        if active and overlaps:
            flags.append("time_overlap")
            supports = ["AREA_INCIDENT"]
            c.facts.update({"active_mapped_incident", "mapped_incident", "incident_time_overlap"})
        elif not active:
            flags += ["closed_before_symptom_window", "not_applicable"] if end < symptom_start else ["closed"]
            c.facts.add("closed_incident_on_path")
        etr = _iso(inc.estimated_restoration_at) if inc.estimated_restoration_at else None
        c.add(ref_id=f"INC-{inc.id}", source_type="incident", source_id=inc.id,
              source_version=_iso(inc.updated_at), authority="system_record", kind="record",
              excerpt=f"{inc.id} '{inc.title}' on {inc.asset_id}; status {inc.status}; started "
                      f"{_iso(inc.started_at)}" + (f"; ended {_iso(inc.ended_at)}" if inc.ended_at else "")
                      + f"; published restoration estimate: {etr or 'none'}.",
              freshness="n/a", supports=supports, flags=flags,
              data={"incident_id": inc.id, "status": inc.status, "asset_id": inc.asset_id,
                    "estimated_restoration_at": etr, "active": active, "overlaps": overlaps})
    if "active_mapped_incident" not in c.facts:
        c.facts.add("no_active_mapped_incident")
    if path:
        nearby = conn.incidents.nearby_unmapped(db, tenant_id, ctx["account"].postal_area, path_ids)
        for inc in nearby:
            c.add(ref_id=f"INC-{inc.id}", source_type="incident", source_id=inc.id,
                  source_version=_iso(inc.updated_at), authority="system_record", kind="record",
                  excerpt=f"{inc.id} '{inc.title}' is active on {inc.asset_id}, which is in the same postal "
                          f"area but NOT on this service's mapped path. Proximity alone does not establish cause.",
                  freshness="n/a", flags=["proximity_only", "not_on_mapped_path"],
                  data={"incident_id": inc.id, "status": inc.status, "asset_id": inc.asset_id})

    # ---- Knowledge ----
    queries = ["recurring disconnection troubleshooting steps", "recovery verification samples"]
    if "customer_los" in c.facts or "active_mapped_incident" in c.facts:
        queries.append("linking case to incident mapped path")
    if "line_fault" in c.facts:
        queries.append("technician dispatch prerequisites line impairment")
    if "equipment_fault" in c.facts:
        queries += ["unexpected reboots power adapter ventilation", "firmware known issue overheating"]
    if "measured_stable" in c.facts:
        queries.append("contradictory evidence telemetry healthy customer reports")
    if "stale_only" in c.facts:
        queries.append("diagnostic freshness stale samples")
    if "restoration_guarantee" in triage.special_requests:
        queries.append("restoration estimate guarantee")
    if {"bill_credit", "compensation"} & set(triage.special_requests):
        queries.append("credits compensation eligibility")
    if "closed_incident_on_path" in c.facts:
        queries.append("closed incidents new complaints")
    usage = None
    if provider.is_live:
        findings = {"facts": sorted(c.facts), "special_requests": triage.special_requests}
        plan, usage = provider.generate(system=SYSTEM_PROMPT, user=json.dumps(findings),
                                        schema=EvidencePlanLLM, budget_used=budget_used)
        queries += [q[:120] for q in plan.knowledge_queries]
    seen: set[str] = set()
    for q in queries:
        for hit in knowledge.search(db, q, tenant_id=tenant_id, role=role, product="home_internet", k=2):
            if hit.chunk_id in seen:
                continue
            seen.add(hit.chunk_id)
            c.add(ref_id=f"KB-{hit.chunk_id}", source_type="knowledge", source_id=hit.chunk_id,
                  source_version=hit.version,
                  authority=hit.authority if hit.authority in ("policy", "runbook", "guide") else "guide",
                  kind="policy" if hit.authority == "policy" else "record",
                  excerpt=hit.text, freshness="n/a",
                  flags=[f"doc:{hit.document_id}", f"heading:{hit.heading}", "synthetic_document"],
                  data={"document_id": hit.document_id, "title": hit.title, "heading": hit.heading,
                        "effective_date": hit.effective_date, "query": q})
    log("knowledge_search", sorted(seen))

    bundle = EvidenceBundle(window_start=_iso(symptom_start), window_end=_iso(now), items=c.items,
                            facts=sorted(c.facts), missing_evidence=c.missing,
                            prior_actions=c.prior_actions, knowledge_queries=queries)
    return bundle, usage
