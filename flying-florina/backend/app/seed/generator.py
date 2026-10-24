"""Deterministic synthetic dataset (seed=20261024).

Every aircraft, part, supplier, technician, document and system below is
fictional. Identifiers are invented (AC-001..AC-150) and do not correspond to
real tail numbers. Thresholds are fictional demo thresholds, not maintenance
limits. The same seed always produces the same database.
"""

from __future__ import annotations

import json
import math
import random
import sqlite3
from datetime import date, datetime, timedelta
from typing import Any

from app.core import audit, db
from app.core.config import FIXTURES_DIR, SEED
from app.core.util import DEMO_TODAY, sha256_text

START = date(2025, 4, 24)
END = date.fromisoformat(DEMO_TODAY)  # 2026-10-23, 548 days inclusive

AIRCRAFT_TYPES = [
    ("Kestrel K-200", "Narrowbody transport (fictional)"),
    ("Heron H-400", "Widebody transport (fictional)"),
    ("Osprey O-90", "Utility rotorcraft (fictional)"),
    ("Condor C-700", "Tanker/transport (fictional)"),
]
FLEETS = ["Northern Wing", "Logistics Group Sim", "Training Fleet", "Coastal Utility"]
BASES = ["MAIN-HUB", "NORTH-FIELD", "EAST-DEPOT"]

DEMO_VIBRATION_THRESHOLD = 1.0  # fictional demo threshold, unitless index

CAUSES = ["scheduled_inspection", "unscheduled_component", "parts_delay", "inspection_campaign",
          "avionics_fault", "structural_finding", "documentation_hold"]

SUPPLIERS = [
    ("SUP-01", "Aurora Precision Components (fictional)", "EU", "portal-a"),
    ("SUP-02", "Blue Mesa Aero Supply (fictional)", "NA", "portal-b"),
    ("SUP-03", "Cobalt Rotor Works (fictional)", "NA", "portal-b"),
    ("SUP-04", "Delta Vale Logistics (fictional)", "APAC", "portal-c"),
    ("SUP-05", "Ember Ridge Avionics (fictional)", "EU", "portal-a"),
    ("SUP-06", "Fjord Line Seals (fictional)", "EU", "portal-c"),
]

FIRST = ["Alex", "Bea", "Cam", "Dana", "Eli", "Fen", "Gil", "Hana", "Ira", "Jo", "Kit", "Lee", "Mo", "Nia",
         "Oz", "Pia", "Quin", "Rae", "Sol", "Tam"]
LAST = ["Arden", "Brook", "Cole", "Drake", "Ember", "Frost", "Grove", "Hale", "Isle", "Juniper", "Keel", "Lark",
        "Moss", "North", "Oak", "Pike", "Quill", "Reed", "Stone", "Thorn"]

QUALS = ["Kestrel engine run-up (demo)", "Vibration analysis L2 (demo)", "Borescope inspection (demo)",
         "Heron structures (demo)", "Rotorcraft drivetrain (demo)", "Avionics bench (demo)",
         "NDT eddy current (demo)", "Engine mount replacement (demo)"]

USERS = [
    ("exec.ava", "Ava Lindqvist (synthetic)", "executive", "FF-Demo-MRO", [], "Executive"),
    ("planner.marco", "Marco Ilves (synthetic)", "maintenance_planner", "FF-Demo-MRO", ["restricted-sim"], "Maintenance Planner"),
    ("tech.jun", "Jun Okafor (synthetic)", "technician", "FF-Demo-MRO", ["restricted-sim"], "Technician"),
    ("rel.nadia", "Nadia Varga (synthetic)", "reliability_engineer", "FF-Demo-MRO", ["restricted-sim"], "Reliability Engineer"),
    ("arch.olu", "Olu Brandt (synthetic)", "enterprise_architect", "FF-Demo-MRO", [], "Enterprise Architect"),
    ("sec.ines", "Ines Moreau (synthetic)", "security_officer", "FF-Demo-MRO", ["restricted-sim"], "Security Officer"),
    ("audit.kai", "Kai Sato (synthetic)", "auditor", "FF-Demo-MRO", ["restricted-sim"], "Auditor"),
    ("fde.sam", "Sam Rivera (synthetic)", "fde", "FF-Demo-MRO", [], "Forward Deployed Engineer"),
    ("guest", "Guest viewer (synthetic)", "guest", "FF-Demo-MRO", [], "Guest"),
    ("supplier.lee", "Lee Park, supplier contact (synthetic)", "guest", "Partner-Supplier-Org", [], "Guest"),
]


def _days() -> list[date]:
    return [START + timedelta(days=i) for i in range((END - START).days + 1)]


def _parts(rng: random.Random) -> list[dict[str, Any]]:
    named = [
        ("P-7731", "Engine mount isolator kit", "71", 18400.0, "critical", ["Kestrel K-200"], "SUP-03", 6,
         [{"part_number": "P-7731A", "authority_doc": "DOC-019", "status": "approved"},
          {"part_number": "P-7731B", "authority_doc": None, "status": "unverified"}]),
        ("P-7731A", "Engine mount isolator kit, alt. vendor", "71", 19900.0, "critical", ["Kestrel K-200"], "SUP-01", 3, []),
        ("P-7731B", "Engine mount isolator kit, gray-market listing", "71", 9100.0, "critical", ["Kestrel K-200"], "SUP-04", 2, []),
        ("P-2210", "Fan blade dampener set", "72", 7300.0, "high", ["Kestrel K-200", "Heron H-400"], "SUP-01", 10, []),
        ("P-3302", "Vibration sensor, accelerometer", "77", 2650.0, "high", ["Kestrel K-200", "Heron H-400", "Condor C-700"], "SUP-05", 5, []),
        ("P-4415", "Hydraulic pump seal kit", "29", 940.0, "medium", ["Heron H-400", "Condor C-700"], "SUP-06", 8, []),
        ("P-5120", "Main rotor damper", "65", 22800.0, "critical", ["Osprey O-90"], "SUP-03", 21, []),
        ("P-6008", "Avionics cooling fan", "21", 1180.0, "medium", ["Kestrel K-200", "Heron H-400", "Osprey O-90", "Condor C-700"], "SUP-05", 4, []),
    ]
    out = []
    for pn, name, ata, cost, crit, types, sup, lead, subs in named:
        out.append(dict(part_number=pn, name=f"{name} (fictional)", ata_chapter=ata, unit_cost_usd=cost, criticality=crit,
                        compatible_types=types, supplier_id=sup, lead_time_days=lead, substitutes=subs))
    generic = ["Bracket", "Seal", "Bearing", "Filter element", "Harness clamp", "Valve actuator", "Gasket set",
               "Bushing", "Sensor connector", "Pressure switch"]
    for i in range(52):
        pn = f"P-{8000 + i * 7}"
        types = sorted(rng.sample([t for t, _ in AIRCRAFT_TYPES], rng.randint(1, 3)))
        out.append(dict(part_number=pn, name=f"{rng.choice(generic)} {chr(65 + i % 26)}{i} (fictional)",
                        ata_chapter=str(rng.choice([21, 24, 27, 29, 32, 36, 49, 52, 71, 72, 77])),
                        unit_cost_usd=round(rng.uniform(80, 6500), 2),
                        criticality=rng.choice(["low", "medium", "medium", "high"]),
                        compatible_types=types, supplier_id=rng.choice(SUPPLIERS)[0],
                        lead_time_days=rng.randint(2, 30), substitutes=[]))
    return out


def _documents() -> list[dict[str, Any]]:
    """Load fictional technical references from fixtures/documents/documents.json."""
    with open(FIXTURES_DIR / "documents" / "documents.json", encoding="utf-8") as fh:
        docs = json.load(fh)["documents"]
    for d in docs:
        if d.get("provenance", True):
            d["provenance_sha256"] = sha256_text(f"{d['id']}|{d['revision']}|{d['body']}")
        else:
            d["provenance_sha256"] = None
    return docs


def generate(conn: sqlite3.Connection) -> dict[str, int]:
    rng = random.Random(SEED)
    days = _days()
    counts: dict[str, int] = {}

    # Users
    for uid, name, role, org, clear, persona in USERS:
        conn.execute("INSERT INTO users VALUES (?,?,?,?,?,?)", (uid, name, role, org, json.dumps(clear), persona))
    counts["users"] = len(USERS)

    # Suppliers
    for s in SUPPLIERS:
        conn.execute("INSERT INTO suppliers VALUES (?,?,?,?)", s)
    counts["suppliers"] = len(SUPPLIERS)

    # Parts
    parts = _parts(rng)
    for p in parts:
        conn.execute("INSERT INTO parts VALUES (?,?,?,?,?,?,?,?,?)", (
            p["part_number"], p["name"], p["ata_chapter"], p["unit_cost_usd"], p["criticality"],
            json.dumps(p["compatible_types"]), p["supplier_id"], p["lead_time_days"], json.dumps(p["substitutes"])))
    counts["parts"] = len(parts)

    # Supplier delivery history: reliability is computed from this, never hard-coded.
    reliability_bias = {"SUP-01": 0.92, "SUP-02": 0.85, "SUP-03": 0.62, "SUP-04": 0.55, "SUP-05": 0.88, "SUP-06": 0.8}
    n = 0
    for i in range(720):
        p = rng.choice(parts)
        sup = p["supplier_id"]
        ordered = START + timedelta(days=rng.randint(0, len(days) - 40))
        promised = p["lead_time_days"]
        on_time = rng.random() < reliability_bias[sup]
        actual = promised - rng.randint(0, 1) if on_time else promised + rng.randint(1, max(2, promised))
        # Seeded incident: SUP-03 slips badly in October 2026
        if sup == "SUP-03" and ordered >= date(2026, 9, 20):
            actual = promised + rng.randint(5, 12)
        conn.execute("INSERT INTO supplier_deliveries VALUES (?,?,?,?,?,?,?)",
                     (f"DLV-{i:04d}", sup, p["part_number"], ordered.isoformat(), promised, max(1, actual), f"LOT-{rng.randint(10000, 99999)}"))
        n += 1
    counts["supplier_deliveries"] = n

    # Inventory (multiple systems of record)
    inv = 0
    for p in parts:
        for loc in rng.sample(BASES, rng.randint(1, 3)):
            qty = rng.randint(0, 14)
            verified = END - timedelta(days=rng.randint(1, 120))
            conn.execute("INSERT INTO inventory VALUES (?,?,?,?,?,?,?)",
                         (f"INV-{inv:04d}", p["part_number"], loc, qty, f"LOT-{rng.randint(10000, 99999)}",
                          verified.isoformat(), "ERP-SIM"))
            inv += 1
    # Seeded incident: inconsistent inventory for P-7731 between ERP and the nightly flat file.
    conn.execute("DELETE FROM inventory WHERE part_number IN ('P-7731', 'P-7731A', 'P-7731B')")
    seeded_inv = [
        ("INV-9001", "P-7731", "MAIN-HUB", 2, "LOT-55120", "2026-07-02", "ERP-SIM"),
        ("INV-9002", "P-7731", "MAIN-HUB", 0, "LOT-55120", "2026-10-22", "NIGHTLY-CSV"),
        ("INV-9003", "P-7731", "EAST-DEPOT", 1, "LOT-55188", "2026-10-21", "ERP-SIM"),
        ("INV-9004", "P-7731A", "NORTH-FIELD", 3, "LOT-61002", "2026-10-20", "ERP-SIM"),
        ("INV-9005", "P-7731B", "EXTERNAL-LISTING", 6, "UNKNOWN", "2026-03-11", "SUPPLIER-PORTAL"),
    ]
    for r in seeded_inv:
        conn.execute("INSERT INTO inventory VALUES (?,?,?,?,?,?,?)", r)
    counts["inventory"] = inv

    # Technicians
    techs = []
    for i in range(40):
        quals = []
        for q in rng.sample(QUALS, rng.randint(2, 4)):
            exp = END + timedelta(days=rng.randint(-60, 400))
            quals.append({"name": q, "expires": exp.isoformat()})
        tid = f"T-{100 + i}"
        base = BASES[i % 3]
        shift = ["day", "swing", "night"][i % 3]
        name = f"{FIRST[i % 20]} {LAST[(i * 7) % 20]} (synthetic)"
        techs.append((tid, base, quals))
        conn.execute("INSERT INTO technicians VALUES (?,?,?,?,?)", (tid, name, base, shift, json.dumps(quals)))
    # Make sure the AC-204 scenario has a deterministic mix of qualified/expired technicians at MAIN-HUB.
    conn.execute("UPDATE technicians SET qualifications = ? WHERE id = 'T-100'", (json.dumps([
        {"name": "Vibration analysis L2 (demo)", "expires": "2027-03-01"},
        {"name": "Engine mount replacement (demo)", "expires": "2027-01-15"}]),))
    conn.execute("UPDATE technicians SET qualifications = ? WHERE id = 'T-103'", (json.dumps([
        {"name": "Engine mount replacement (demo)", "expires": "2026-09-30"},
        {"name": "Kestrel engine run-up (demo)", "expires": "2027-02-01"}]),))
    conn.execute("UPDATE technicians SET qualifications = ? WHERE id = 'T-106'", (json.dumps([
        {"name": "Engine mount replacement (demo)", "expires": "2027-05-20"},
        {"name": "Kestrel engine run-up (demo)", "expires": "2027-04-11"},
        {"name": "Vibration analysis L2 (demo)", "expires": "2026-12-31"}]),))
    counts["technicians"] = 40

    # Hangar slots for the next 10 days
    slot = 0
    for d in range(1, 11):
        day = END + timedelta(days=d)
        for base in BASES:
            for bay, hour in (("B1", 6), ("B2", 14)):
                status = "available" if rng.random() < 0.55 else "booked"
                conn.execute("INSERT INTO hangar_slots VALUES (?,?,?,?,?,?)",
                             (f"SLOT-{slot:03d}", base, bay, datetime(day.year, day.month, day.day, hour).isoformat(), 8.0, status))
                slot += 1
    # Deterministic MAIN-HUB plan for the AC-204 scenario (fictional): the next
    # free bays are uneven, so a longer part delay can cost a whole extra day.
    main_plan = {(1, 6): "available", (1, 14): "available", (2, 6): "booked", (2, 14): "booked",
                 (3, 6): "available", (3, 14): "booked", (4, 6): "available", (4, 14): "booked"}
    for (d, hour), status in main_plan.items():
        day = END + timedelta(days=d)
        conn.execute("UPDATE hangar_slots SET status=? WHERE base='MAIN-HUB' AND start = ?",
                     (status, datetime(day.year, day.month, day.day, hour).isoformat()))
    counts["hangar_slots"] = slot

    # Aircraft and telemetry
    readings = []
    ac_rows = []
    for i in range(1, 151):
        ac = f"AC-{i:03d}"
        t, _ = AIRCRAFT_TYPES[(i * 3) % 4] if i != 204 else AIRCRAFT_TYPES[0]
        fleet = FLEETS[i % 4]
        base = BASES[i % 3]
        in_service = date(2004 + i % 19, 1 + i % 12, 1 + i % 27)
        hours = rng.randint(4000, 52000)
        cycles = int(hours / rng.uniform(1.2, 3.5))
        ac_rows.append([ac, t, fleet, base, "in_service", in_service.isoformat(), hours, cycles])
    # AC-204 is the seeded incident aircraft. The fleet has 150 aircraft; AC-204
    # replaces AC-150's identifier so the fleet count stays exactly 150.
    ac_rows[-1] = ["AC-204", "Kestrel K-200", "Northern Wing", "MAIN-HUB", "aog", "2009-05-14", 38410, 21950]
    statuses = ["in_service"] * 120 + ["scheduled_maintenance"] * 18 + ["unscheduled_maintenance"] * 8 + ["aog"] * 3
    rng.shuffle(statuses)
    for idx, r in enumerate(ac_rows[:-1]):
        r[4] = statuses[idx]
    for r in ac_rows:
        conn.execute("INSERT INTO aircraft VALUES (?,?,?,?,?,?,?,?,1)", r)
    counts["aircraft"] = len(ac_rows)

    for ac, _t, *_ in ac_rows:
        base_vib = rng.uniform(0.28, 0.55)
        base_egt = rng.uniform(-4, 4)
        base_oil = rng.uniform(0.9, 1.1)
        drift = rng.uniform(-0.00005, 0.00015)
        for k, d in enumerate(days):
            if rng.random() < 0.012:  # sensor dropouts for data-quality checks
                readings.append((ac, d.isoformat(), None, None, None))
                continue
            vib = base_vib + drift * k + rng.gauss(0, 0.035) + 0.04 * math.sin(k / 29.0)
            egt = base_egt + rng.gauss(0, 1.6)
            oil = base_oil + rng.gauss(0, 0.025)
            if ac == "AC-204" and d >= date(2026, 10, 9):
                ramp = (d - date(2026, 10, 9)).days
                vib += 0.06 * ramp + (0.15 if ramp > 10 else 0)
                egt += 0.4 * ramp
            if ac == "AC-077" and d == date(2026, 2, 3):  # isolated spike, likely sensor glitch
                vib += 1.2
            readings.append((ac, d.isoformat(), round(vib, 4) if vib is not None else None, round(egt, 2), round(oil, 4)))
    conn.executemany("INSERT INTO sensor_readings VALUES (?,?,?,?,?)", readings)
    counts["sensor_readings"] = len(readings)

    # Maintenance events + work orders
    pn_by_type: dict[str, list[str]] = {}
    for p in parts:
        for t in p["compatible_types"]:
            pn_by_type.setdefault(t, []).append(p["part_number"])
    ev = 0
    wo = 0
    ac_type = {r[0]: r[1] for r in ac_rows}
    for ac, _t, *_ in ac_rows:
        k = 0
        while k < len(days):
            k += rng.randint(18, 48)
            if k >= len(days):
                break
            d = days[k]
            october_2026 = d >= date(2026, 10, 1)
            cause = rng.choices(CAUSES, weights=[40, 22, 8, 3, 12, 8, 7])[0]
            if october_2026 and rng.random() < 0.55:
                cause = rng.choice(["parts_delay", "inspection_campaign", "parts_delay"])
            base_hours = {"scheduled_inspection": 18, "unscheduled_component": 26, "parts_delay": 52,
                          "inspection_campaign": 30, "avionics_fault": 14, "structural_finding": 40,
                          "documentation_hold": 9}[cause]
            downtime = round(max(2.0, rng.gauss(base_hours, base_hours * 0.3)), 1)
            pn = rng.choice(pn_by_type[ac_type[ac]])
            cost = round(downtime * rng.uniform(900, 1600) + rng.uniform(500, 9000), 2)
            wo_id = f"WO-{24000 + wo}"
            conn.execute("INSERT INTO maintenance_events VALUES (?,?,?,?,?,?,?,?,?)",
                         (f"ME-{ev:05d}", ac, d.isoformat(), "scheduled" if cause in ("scheduled_inspection", "inspection_campaign") else "unscheduled",
                          f"{cause.replace('_', ' ').title()} on {ac} (synthetic)", downtime, cause, cost, wo_id))
            closed = (d + timedelta(days=max(1, int(downtime // 24)))).isoformat()
            status = "closed" if d < END - timedelta(days=12) else rng.choice(["open", "in_progress", "awaiting_parts"])
            conn.execute("INSERT INTO work_orders VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                         (wo_id, ac, status, rng.choice(["routine", "routine", "urgent"]), d.isoformat(),
                          closed if status == "closed" else None, f"{cause.replace('_', ' ')} - {pn}", pn,
                          f"T-{100 + rng.randint(0, 39)}", None, rng.choice(["MRO-APP-SIM", "ERP-SIM"]),
                          rng.choice(["INTERNAL", "INTERNAL", "RESTRICTED"])))
            ev += 1
            wo += 1
    # AC-204 history: previous vibration-related work
    seeded_wo = [
        ("WO-90001", "AC-204", "closed", "routine", "2026-03-14", "2026-03-15", "Engine mount visual inspection, no findings (synthetic)", "P-7731", "T-106", None, "MRO-APP-SIM", "RESTRICTED"),
        ("WO-90002", "AC-204", "open", "urgent", "2026-10-22", None, "Vibration index exceedance vs fictional demo threshold - troubleshoot (synthetic)", "P-7731", "T-100", None, "MRO-APP-SIM", "RESTRICTED"),
        ("WO-90003", "AC-118", "open", "routine", "2026-10-18", None, "Hydraulic seal replacement (synthetic)", "P-4415", "T-112", None, "ERP-SIM", "INTERNAL"),
        ("WO-90004", "AC-118", "open", "routine", "2026-10-18", None, "Hydraulic seal replacement (synthetic)", "P-4415", "T-112", "WO-90003", "MRO-APP-SIM", "INTERNAL"),
    ]
    for r in seeded_wo:
        conn.execute("INSERT INTO work_orders VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", r)
    conn.execute("INSERT INTO maintenance_events VALUES (?,?,?,?,?,?,?,?,?)",
                 ("ME-90001", "AC-204", "2026-03-14", "scheduled", "Engine mount visual inspection (synthetic)", 6.0, "scheduled_inspection", 4200.0, "WO-90001"))
    counts["maintenance_events"] = ev + 1
    counts["work_orders"] = wo + len(seeded_wo)

    # Documents + FTS index
    docs = _documents()
    for d in docs:
        conn.execute("INSERT INTO documents VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", (
            d["id"], d["title"], d["revision"], d["effective_date"], d["review_due"], d["classification"],
            json.dumps(d["permitted_roles"]), d["source"], d["status"], d["provenance_sha256"], d.get("superseded_by"),
            d["body"], " ".join(d.get("tags", []))))
        conn.execute("INSERT INTO documents_fts (doc_id, title, body, tags) VALUES (?,?,?,?)",
                     (d["id"], d["title"], d["body"], " ".join(d.get("tags", []))))
    counts["documents"] = len(docs)

    # Enterprise applications and dependency graph
    with open(FIXTURES_DIR / "legacy" / "dependency_graph.json", encoding="utf-8") as fh:
        graph = json.load(fh)
    for a in graph["applications"]:
        conn.execute("INSERT INTO applications VALUES (?,?,?,?,?,?,?,?,?,?,?)", (
            a["id"], a["name"], a["kind"], a["technology"], a["owner"], a["criticality"], json.dumps(a["interfaces"]),
            a.get("batch_window"), a["auth_method"], a["last_doc_update"], a.get("notes", "")))
    for e in graph["dependencies"]:
        conn.execute("INSERT INTO app_dependencies VALUES (?,?,?,?,?)", (e["source"], e["target"], e["kind"], e["protocol"], e["frequency"]))
    counts["applications"] = len(graph["applications"])

    # Seeded incidents
    incidents = [
        ("INC-001", "Engine vibration anomaly on AC-204", "engine_vibration", "high", "2026-10-22", "open", "AC-204,WO-90002",
         "Vibration index on AC-204 rising since 2026-10-09 and above the fictional demo threshold."),
        ("INC-002", "Supplier SUP-03 lead-time slip", "part_delay", "medium", "2026-10-02", "open", "SUP-03,P-7731,P-5120",
         "Recent SUP-03 deliveries arrived 5-12 days after promise."),
        ("INC-003", "Inventory mismatch for P-7731 at MAIN-HUB", "inventory_inconsistency", "high", "2026-10-22", "open", "P-7731,INV-9001,INV-9002",
         "ERP-SIM shows 2 units, nightly CSV physical count shows 0."),
        ("INC-004", "Expired document revision in use", "expired_revision", "medium", "2026-10-15", "open", "DOC-007",
         "DOC-007 rev B was superseded by DOC-008 rev C but is still referenced by a task card."),
        ("INC-005", "Work order closed without recorded approval", "missing_approval", "medium", "2026-09-28", "open", "WO-24310",
         "Synthetic record shows closure without a quality approval entry."),
        ("INC-006", "Attempted export of restricted records", "unauthorized_export", "high", "2026-10-19", "closed", "POL-004",
         "Seeded historic attempt to e-mail restricted records externally; denied by POL-004."),
        ("INC-007", "Duplicate work order", "duplicate_work_order", "low", "2026-10-18", "open", "WO-90003,WO-90004",
         "WO-90004 duplicates WO-90003 across ERP-SIM and MRO-APP-SIM."),
        ("INC-008", "Integration timeout ERP-SIM -> MRO-APP-SIM", "integration_timeout", "medium", "2026-10-20", "open", "APP-01,APP-02",
         "Nightly sync exceeded its 30 minute batch window three times this month."),
    ]
    conn.executemany("INSERT INTO incidents VALUES (?,?,?,?,?,?,?,?)", incidents)
    counts["incidents"] = len(incidents)

    # Counts are read back from the database so they always match what was stored.
    for table in list(counts):
        counts[table] = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]  # noqa: S608 - fixed table names

    conn.execute("INSERT INTO governance_state VALUES ('kill_switch', 'off')")
    conn.execute("INSERT INTO meta VALUES ('seed', ?)", (str(SEED),))
    conn.execute("INSERT INTO meta VALUES ('demo_today', ?)", (DEMO_TODAY,))
    conn.execute("INSERT INTO meta VALUES ('counts', ?)", (json.dumps(counts),))
    return counts


def seed_historic_governance(conn: sqlite3.Connection) -> None:
    """Seed a few historic governance records so the Trust Center is not empty."""
    audit.append("system", "demo.seeded", f"Synthetic dataset generated with seed {SEED}", {"seed": SEED}, conn)


def reset_database() -> dict[str, int]:
    """Drop and regenerate the demo database."""
    from app.core.config import get_settings

    settings = get_settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    path = settings.db_path
    for suffix in ("", "-wal", "-shm"):
        p = path.with_name(path.name + suffix)
        if p.exists():
            p.unlink()
    with db.session(write=True) as conn:
        db.init_schema(conn)
        counts = generate(conn)
        seed_historic_governance(conn)
    return counts


def ensure_seeded() -> None:
    from app.core.config import get_settings

    if not get_settings().db_path.exists():
        reset_database()
        return
    with db.session() as conn:
        try:
            ok = conn.execute("SELECT value FROM meta WHERE key='seed'").fetchone()
        except sqlite3.OperationalError:
            ok = None
    if not ok:
        reset_database()


if __name__ == "__main__":
    print(json.dumps(reset_database(), indent=2))
