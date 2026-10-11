"""Versioned, deterministic policy engine: PASS / FAIL / INCONCLUSIVE.

Rules of thumb encoded here
* Missing information (insufficient samples, missing evidence, unresolved ambiguity, missing
  configuration) -> INCONCLUSIVE. Violations (regression, digest mismatch, failed control test,
  stale or invalid approval) -> FAIL. Overall = FAIL if any FAIL, else INCONCLUSIVE if any
  INCONCLUSIVE, else PASS. Insufficient data can never yield PASS.
* Thresholds = the stricter of the policy file and the approved acceptance criteria.
* No agent output is an input to this module.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

PASS, FAIL, INCONCLUSIVE = "PASS", "FAIL", "INCONCLUSIVE"


@dataclass
class Gate:
    gate_id: str
    rule: str
    observed: str
    status: str
    owner_role: str
    evidence: list = field(default_factory=list)

    def dict(self) -> dict:
        return asdict(self)


def overall(gates: list[Gate]) -> str:
    st = {g.status for g in gates}
    if FAIL in st:
        return FAIL
    if INCONCLUSIVE in st or not gates:
        return INCONCLUSIVE
    return PASS


def effective_thresholds(policy: dict, criteria: dict | None) -> dict:
    t = dict(policy["thresholds"])
    sources = {k: "policy" for k in t}
    c = criteria or {}
    if c.get("min_samples_per_cell") is not None and c["min_samples_per_cell"] > t["min_samples_per_cell"]:
        t["min_samples_per_cell"], sources["min_samples_per_cell"] = c["min_samples_per_cell"], "acceptance_criteria"
    if c.get("max_regression_pp") is not None and c["max_regression_pp"] < t["max_regression_pp"]:
        t["max_regression_pp"], sources["max_regression_pp"] = c["max_regression_pp"], "acceptance_criteria"
    if c.get("target_min_improvement_pp") is not None and c["target_min_improvement_pp"] > t["target_min_improvement_pp"]:
        t["target_min_improvement_pp"], sources["target_min_improvement_pp"] = c["target_min_improvement_pp"], "acceptance_criteria"
    t["_sources"] = sources
    return t


def _ref(section: str, version: str = "2.1") -> dict:
    return {"source_id": "POL-REL-005", "source_version": version, "section": section}


def evaluation_gates(*, policy: dict, thresholds: dict, cells: dict, required_cells: list[str], target_cell: str,
                     controls: list[dict], unresolved_required: int, requirement_approved: bool,
                     evidence_check: dict, artifact_check: dict, config_present: bool, integrity: dict) -> list[Gate]:
    owners = policy["gate_owners"]
    g: list[Gate] = []

    g.append(Gate("G-CONFIG", "Evaluation configuration and versioned policy are present",
                  f"config present={config_present}; policy {policy['policy_version']}",
                  PASS if config_present else INCONCLUSIVE, owners["G-CONFIG"], [_ref("§1")]))

    mism = [k for k, v in artifact_check.items() if v["registered"] != v["computed"]]
    g.append(Gate("G-ARTIFACT", "Registered digests equal digests recomputed from artifact and dataset files",
                  "all digests match" if not mism else "MISMATCH: " + ", ".join(mism),
                  PASS if not mism else FAIL, owners["G-ARTIFACT"], [{"record": f"digest:{k}"} for k in artifact_check]))

    amb_ok = unresolved_required == 0 and requirement_approved
    g.append(Gate("G-AMBIGUITY", "No unresolved required ambiguity; requirement version approved",
                  f"unresolved required={unresolved_required}; requirement approved={requirement_approved}",
                  PASS if amb_ok else INCONCLUSIVE, owners["G-AMBIGUITY"], [_ref("§1")]))

    if evidence_check["missing"]:
        ev_status, ev_obs = INCONCLUSIVE, "missing required evidence: " + ", ".join(evidence_check["missing"])
    elif evidence_check["invalid"]:
        ev_status, ev_obs = FAIL, "citations not valid: " + ", ".join(evidence_check["invalid"])
    else:
        ev_status, ev_obs = PASS, f"{evidence_check['valid']} citations resolve to current approved sources"
    g.append(Gate("G-EVIDENCE", "Required evidence cited from current approved documents and every citation resolves",
                  ev_obs, ev_status, owners["G-EVIDENCE"], evidence_check.get("refs", [])))

    nmin = thresholds["min_samples_per_cell"]
    short = {c: cells[c]["baseline"]["n_eligible"] if c in cells else 0 for c in required_cells
             if c not in cells or cells[c]["baseline"]["n_eligible"] < nmin}
    g.append(Gate("G-SAMPLES", f"Every required cell has ≥ {nmin} eligible paired samples",
                  "min n = " + str(min((cells[c]["baseline"]["n_eligible"] for c in required_cells if c in cells), default=0))
                  + ("; insufficient: " + ", ".join(f"{c} (n={n})" for c, n in short.items()) if short else ""),
                  PASS if not short else INCONCLUSIVE, owners["G-SAMPLES"], [_ref("§1")]))

    tmin = thresholds["target_min_improvement_pp"]
    if target_cell not in cells or target_cell in short:
        g.append(Gate("G-TARGET", f"Target cell {target_cell} top-1 improves by ≥ {tmin} pp",
                      "insufficient data", INCONCLUSIVE, owners["G-TARGET"], [_ref("§1")]))
    else:
        d = cells[target_cell]["delta"]["top1_delta_pp"]
        ci = cells[target_cell]["delta_ci95_pp"]
        g.append(Gate("G-TARGET", f"Target cell {target_cell} top-1 improves by ≥ {tmin} pp",
                      f"{d:+.2f} pp (95% paired bootstrap CI {ci[0]:+.2f} to {ci[1]:+.2f})",
                      PASS if d >= tmin else FAIL, owners["G-TARGET"], [_ref("§1"), {"record": f"metric:{target_cell}"}]))

    rmax = thresholds["max_regression_pp"]
    viol = [(c, cells[c]["delta"]["top1_delta_pp"]) for c in required_cells
            if c in cells and c not in short and cells[c]["delta"]["top1_delta_pp"] < -rmax]
    worst = min(((c, cells[c]["delta"]["top1_delta_pp"]) for c in required_cells if c in cells), key=lambda x: x[1], default=None)
    obs = (f"worst cell {worst[0]} {worst[1]:+.2f} pp" if worst else "no data") + \
          ("; VIOLATIONS: " + ", ".join(f"{c} {d:+.2f} pp" for c, d in viol) if viol else "")
    g.append(Gate("G-NO-REGRESSION", f"No required cell loses more than {rmax} pp top-1 vs baseline",
                  obs, FAIL if viol else (INCONCLUSIVE if short else PASS), owners["G-NO-REGRESSION"],
                  [_ref("§1")] + [{"record": f"metric:{c}"} for c, _ in viol]))

    cmax = thresholds["max_coverage_drop_pp"]
    cov = [(c, cells[c]["delta"]["coverage_delta_pp"]) for c in required_cells
           if c in cells and cells[c]["delta"]["coverage_delta_pp"] < -cmax]
    g.append(Gate("G-COVERAGE", f"No required cell's coverage (answered/eligible) drops more than {cmax} pp",
                  "within limit" if not cov else "; ".join(f"{c} {d:+.2f} pp" for c, d in cov),
                  FAIL if cov else PASS, owners["G-COVERAGE"], [{"source_id": "PROT-EVAL-008", "source_version": "2.0", "section": "§4"}]))

    g.append(Gate("G-ABSTENTION-DENOMINATOR", "Abstentions remain in the denominator; every eligible sample has a prediction record",
                  integrity["observed"], PASS if integrity["ok"] else FAIL, owners["G-ABSTENTION-DENOMINATOR"],
                  [{"source_id": "SPEC-SHADE-001", "source_version": "1.2", "section": "§2"}]))

    failed = [c["test_id"] for c in controls if c["status"] != "PASS"]
    g.append(Gate("G-CONTROLS", "All required privacy and authorization control tests pass",
                  f"{len(controls) - len(failed)}/{len(controls)} passed" + (f"; failed: {', '.join(failed)}" if failed else ""),
                  PASS if controls and not failed else (FAIL if failed else INCONCLUSIVE), owners["G-CONTROLS"],
                  [{"source_id": "POL-CONSENT-006", "source_version": "1.3", "section": "§1"}]))
    return g
