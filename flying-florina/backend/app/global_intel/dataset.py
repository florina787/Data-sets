"""Reproducible SYNTHETIC global dataset for Flying Florina 3.0.

Everything here is fictional and generated from a fixed seed. Facility and supplier names are invented; facilities sit in real civilian
cities only so the map is readable. There are no military sites, no defense assets and no real operational figures.

Assumptions (also returned by `assumptions()` and shown in the UI):
* History: 104 weekly periods ending on the demo date (2026-10-23). Forecast origin = the demo date.
* Component removals per (MRO facility, category) follow a Poisson process whose rate = fleet positions / mean Weibull life,
  scaled by a seasonal utilisation curve, a slow utilisation trend and two planned surge campaigns.
* Tracked units (the digital-twin layer) follow Weibull lifetimes; a health index degrades as 1 - 0.8 (age/life)^p with sensor noise;
  removal happens when the unit's life is reached. 3% of health readings are missing (sensor dropout).
  2% of unit-weeks carry an injected sensor anomaly (labelled ground truth); the 3 weeks before a failure show precursor vibration.
* Supplier lead time = promised days x supplier reliability factor x regional congestion + noise; 2% of actual lead times are missing.
"""

from __future__ import annotations

import math
import random
import sqlite3
from datetime import date, timedelta
from typing import Any

from app.core.util import DEMO_TODAY

GLOBAL_SEED = 20261102
DATASET_VERSION = "global-v1"
N_WEEKS = 104
TRACKED_POSITIONS = 4  # per (MRO facility, category)

SCHEMA = """
CREATE TABLE IF NOT EXISTS g_facilities (id TEXT PRIMARY KEY, name TEXT, kind TEXT, city TEXT, country TEXT, region TEXT,
  lat REAL, lon REAL, capacity_hours_week REAL, synthetic INTEGER DEFAULT 1);
CREATE TABLE IF NOT EXISTS g_suppliers (id TEXT PRIMARY KEY, name TEXT, city TEXT, country TEXT, region TEXT, lat REAL, lon REAL,
  reliability REAL, synthetic INTEGER DEFAULT 1);
CREATE TABLE IF NOT EXISTS g_categories (id TEXT PRIMARY KEY, name TEXT, family TEXT, unit_cost_usd REAL, weibull_k REAL,
  weibull_eta_weeks REAL, labor_hours REAL, repair_tat_days REAL, positions_per_hub INTEGER);
CREATE TABLE IF NOT EXISTS g_supply_links (supplier_id TEXT, category_id TEXT, share REAL, promised_days INTEGER,
  PRIMARY KEY (supplier_id, category_id));
CREATE TABLE IF NOT EXISTS g_demand (facility_id TEXT, category_id TEXT, week INTEGER, week_start TEXT, removals INTEGER,
  PRIMARY KEY (facility_id, category_id, week));
CREATE TABLE IF NOT EXISTS g_units (id TEXT PRIMARY KEY, serial TEXT, facility_id TEXT, category_id TEXT, position INTEGER,
  install_week INTEGER, removal_week INTEGER, removal_reason TEXT, life_weeks REAL, degradation_p REAL, status TEXT,
  engineering_revision TEXT);
CREATE TABLE IF NOT EXISTS g_unit_weeks (unit_id TEXT, week INTEGER, health REAL, vibration REAL, temperature REAL, pressure REAL,
  operating_hours REAL, anomaly INTEGER, PRIMARY KEY (unit_id, week));
CREATE INDEX IF NOT EXISTS ix_guw_week ON g_unit_weeks(week);
CREATE TABLE IF NOT EXISTS g_unit_events (id TEXT PRIMARY KEY, unit_id TEXT, week INTEGER, date TEXT, kind TEXT, description TEXT,
  work_order TEXT, doc_ref TEXT);
CREATE INDEX IF NOT EXISTS ix_gue_unit ON g_unit_events(unit_id);
CREATE TABLE IF NOT EXISTS g_inventory (facility_id TEXT, category_id TEXT, on_hand INTEGER, reorder_point INTEGER, as_of TEXT,
  PRIMARY KEY (facility_id, category_id));
CREATE TABLE IF NOT EXISTS g_open_orders (id TEXT PRIMARY KEY, supplier_id TEXT, category_id TEXT, facility_id TEXT, qty INTEGER,
  ordered TEXT, ordered_week INTEGER, promised_days INTEGER);
CREATE TABLE IF NOT EXISTS g_deliveries (id TEXT PRIMARY KEY, supplier_id TEXT, category_id TEXT, facility_id TEXT, qty INTEGER,
  ordered TEXT, ordered_week INTEGER, promised_days INTEGER, actual_days REAL);
CREATE TABLE IF NOT EXISTS g_repairs (id TEXT PRIMARY KEY, center_id TEXT, category_id TEXT, received_week INTEGER, tat_days REAL);
CREATE TABLE IF NOT EXISTS g_disruptions (id TEXT PRIMARY KEY, title TEXT, kind TEXT, lat REAL, lon REAL, region TEXT,
  facility_id TEXT, supplier_id TEXT, start_day INTEGER, duration_days INTEGER, severity TEXT, capacity_cut REAL,
  lead_time_add_days REAL, source TEXT, verified INTEGER DEFAULT 0, synthetic INTEGER DEFAULT 1);
"""

FACILITIES = [
    ("F01", "Northwind MRO Hub", "mro", "Hamburg", "DE", "Europe", 53.63, 9.99, 5200),
    ("F02", "Alpine Component Works", "manufacturing", "Toulouse", "FR", "Europe", 43.63, 1.37, 0),
    ("F03", "Atlantic Repair Center", "repair_center", "Shannon", "IE", "Europe", 52.70, -8.92, 2600),
    ("F04", "Great Lakes MRO", "mro", "Chicago", "US", "North America", 41.98, -87.90, 5600),
    ("F05", "Cascade Avionics Repair", "repair_center", "Seattle", "US", "North America", 47.45, -122.31, 2400),
    ("F06", "Sonoran Logistics Warehouse", "warehouse", "Phoenix", "US", "North America", 33.43, -112.01, 0),
    ("F07", "Gulf Gateway MRO", "mro", "Dubai", "AE", "Middle East", 25.25, 55.36, 4800),
    ("F08", "Monsoon Component Depot", "warehouse", "Singapore", "SG", "Asia-Pacific", 1.36, 103.99, 0),
    ("F09", "Kanto Precision Manufacturing", "manufacturing", "Nagoya", "JP", "Asia-Pacific", 34.86, 136.81, 0),
    ("F10", "Southern Cross MRO", "mro", "Brisbane", "AU", "Asia-Pacific", -27.38, 153.12, 4200),
    ("F11", "Andes Regional MRO", "mro", "Santiago", "CL", "Latin America", -33.39, -70.79, 3400),
    ("F12", "Savanna Line Maintenance", "mro", "Nairobi", "KE", "Africa", -1.32, 36.93, 2800),
]
SUPPLIERS = [
    ("S1", "Veltrion Hydraulics", "Milan", "IT", "Europe", 45.46, 9.19, 1.05),
    ("S2", "Corvalis Avionics", "Austin", "US", "North America", 30.27, -97.74, 1.10),
    ("S3", "Tessarine Thermal Systems", "Montreal", "CA", "North America", 45.50, -73.57, 1.18),
    ("S4", "Meridane Power Systems", "Bengaluru", "IN", "Asia-Pacific", 12.97, 77.59, 1.32),
    ("S5", "Kestrava Landing Systems", "Queretaro", "MX", "Latin America", 20.59, -100.39, 1.22),
    ("S6", "Nordvik Sensorworks", "Gothenburg", "SE", "Europe", 57.71, 11.97, 1.02),
    ("S7", "Lumora Communications", "Seoul", "KR", "Asia-Pacific", 37.57, 126.98, 1.12),
    ("S8", "Duneval Fuel Controls", "Casablanca", "MA", "Africa", 33.57, -7.59, 1.40),
]
# id, name, family, unit cost, weibull k, eta (weeks), labor hours, repair TAT days, positions/hub, suppliers [(id, share, promised)]
CATEGORIES = [
    ("hydraulic_pump", "Hydraulic pumps", "Hydraulics", 48000, 2.2, 120, 9, 21, 60, [("S1", 0.8, 28), ("S5", 0.2, 35)]),
    ("landing_gear_actuator", "Landing gear actuators", "Landing gear", 61000, 2.6, 160, 14, 30, 50, [("S5", 0.7, 42), ("S1", 0.3, 38)]),
    ("fuel_control_unit", "Fuel control units", "Fuel", 92000, 2.0, 140, 11, 28, 30, [("S8", 0.6, 45), ("S3", 0.4, 40)]),
    ("avionics_module", "Avionics modules", "Avionics", 35000, 1.4, 90, 4, 14, 90, [("S2", 0.7, 21), ("S7", 0.3, 28)]),
    ("engine_temp_sensor", "Engine temperature sensors", "Engine sensors", 4200, 1.6, 70, 2, 7, 160, [("S6", 0.8, 14), ("S2", 0.2, 18)]),
    ("cabin_env_system", "Cabin environmental systems", "Environmental", 57000, 2.3, 150, 12, 26, 30, [("S3", 1.0, 35)]),
    ("electrical_generator", "Electrical generators", "Electrical", 74000, 2.1, 130, 10, 24, 40, [("S4", 0.7, 40), ("S3", 0.3, 36)]),
    ("cooling_component", "Cooling components", "Thermal", 12500, 1.8, 95, 5, 12, 80, [("S3", 0.6, 21), ("S4", 0.4, 30)]),
    ("comm_equipment", "Communication equipment", "Communications", 22000, 1.5, 110, 4, 16, 60, [("S7", 0.8, 24), ("S2", 0.2, 26)]),
    ("apu", "Auxiliary power units", "APU", 410000, 2.4, 180, 30, 45, 20, [("S4", 1.0, 60)]),
    ("brake_assembly", "Brake assemblies", "Landing gear", 28000, 3.0, 75, 6, 10, 100, [("S5", 0.6, 30), ("S1", 0.4, 28)]),
    ("fuel_pump", "Fuel pumps", "Fuel", 19000, 2.0, 115, 6, 18, 60, [("S8", 0.7, 35), ("S1", 0.3, 30)]),
    ("bleed_air_valve", "Bleed air valves", "Pneumatics", 15500, 1.7, 85, 5, 15, 70, [("S3", 1.0, 25)]),
    ("flight_control_computer", "Flight control computers", "Avionics", 145000, 1.3, 200, 8, 20, 20, [("S2", 1.0, 35)]),
    ("weather_radar", "Weather radar units", "Avionics", 88000, 1.5, 170, 6, 22, 20, [("S7", 0.6, 32), ("S2", 0.4, 30)]),
    ("oxygen_system", "Oxygen system components", "Environmental", 6800, 1.9, 100, 3, 9, 90, [("S6", 0.5, 18), ("S3", 0.5, 20)]),
    ("starter_motor", "Starter motors", "Electrical", 33000, 2.2, 125, 7, 17, 40, [("S4", 0.8, 38), ("S6", 0.2, 30)]),
    ("hydraulic_accumulator", "Hydraulic accumulators", "Hydraulics", 9800, 2.5, 140, 4, 12, 60, [("S1", 1.0, 24)]),
    ("cabin_pressure_controller", "Cabin pressure controllers", "Environmental", 26000, 1.6, 150, 5, 16, 40, [("S3", 0.7, 30), ("S6", 0.3, 28)]),
    ("navigation_receiver", "Navigation receivers", "Communications", 31000, 1.4, 160, 3, 14, 40, [("S7", 0.5, 26), ("S2", 0.5, 24)]),
]
MRO = [f for f in FACILITIES if f[2] == "mro"]
REPAIR_CENTERS = ["F03", "F05"]
DISRUPTIONS = [
    # id, title, kind, facility, supplier, region, start_day, duration, severity, capacity_cut, lead_time_add
    ("D01", "Severe winter weather slows ground handling", "severe_weather", "F01", None, "Europe", 18, 9, "medium", 0.25, 4),
    ("D02", "Port congestion delays sea freight", "logistics", "F08", None, "Asia-Pacific", -6, 34, "high", 0.0, 9),
    ("D03", "Runway resurfacing reduces night movements", "airport_notice", "F07", None, "Middle East", 5, 21, "low", 0.10, 0),
    ("D04", "Supplier furnace rebuild (planned)", "supplier_production", None, "S4", "Asia-Pacific", 12, 28, "high", 0.0, 14),
    ("D05", "Licensed engineer shortage (seasonal leave)", "workforce", "F10", None, "Asia-Pacific", 40, 21, "medium", 0.30, 0),
    ("D06", "Regional logistics strike notice", "logistics", None, "S8", "Africa", 25, 10, "medium", 0.0, 7),
    ("D07", "Hangar fire-suppression upgrade", "facility_outage", "F11", None, "Latin America", 55, 14, "high", 0.45, 0),
    ("D08", "Tropical storm season advisory", "severe_weather", "F04", None, "North America", 70, 6, "low", 0.15, 2),
]


def _week_start(week: int) -> str:
    end = date.fromisoformat(DEMO_TODAY)
    return (end - timedelta(weeks=N_WEEKS - week)).isoformat()


def _poisson(rng: random.Random, lam: float) -> int:
    if lam <= 0:
        return 0
    if lam > 30:
        return max(0, int(round(rng.gauss(lam, math.sqrt(lam)))))
    lim, k, p = math.exp(-lam), 0, 1.0
    while True:
        p *= rng.random()
        if p <= lim:
            return k
        k += 1


def seasonal(week: int) -> float:
    """Northern-summer utilisation peak plus a slow upward trend (shared by history and assumptions)."""
    return (1.0 + 0.18 * math.sin(2 * math.pi * (week - 20) / 52)) * (1.0 + 0.0015 * week)


def generate(conn: sqlite3.Connection) -> dict[str, int]:
    rng = random.Random(GLOBAL_SEED)
    conn.executescript(SCHEMA)
    for t in ("g_facilities", "g_suppliers", "g_categories", "g_supply_links", "g_demand", "g_units", "g_unit_weeks", "g_unit_events",
              "g_inventory", "g_open_orders", "g_deliveries", "g_repairs", "g_disruptions"):
        conn.execute(f"DELETE FROM {t}")  # noqa: S608 - fixed table names
    conn.executemany("INSERT INTO g_facilities VALUES (?,?,?,?,?,?,?,?,?,1)", FACILITIES)
    conn.executemany("INSERT INTO g_suppliers VALUES (?,?,?,?,?,?,?,?,1)", SUPPLIERS)
    for c in CATEGORIES:
        conn.execute("INSERT INTO g_categories VALUES (?,?,?,?,?,?,?,?,?)", c[:9])
        for sid, share, promised in c[9]:
            conn.execute("INSERT INTO g_supply_links VALUES (?,?,?,?)", (sid, c[0], share, promised))

    # --- position-level removal demand (forecasting target)
    hub_scale = {f[0]: f[8] / 4800 for f in MRO}
    surges = {("F07", "brake_assembly"): (60, 70, 1.8), ("F01", "avionics_module"): (80, 92, 1.6)}
    demand_rows = []
    for f in MRO:
        for c in CATEGORIES:
            cid, k, eta, positions = c[0], c[4], c[5], c[8]
            mean_life = eta * math.gamma(1 + 1 / k)
            base = positions * hub_scale[f[0]] / mean_life
            for w in range(N_WEEKS):
                lam = base * seasonal(w)
                s = surges.get((f[0], cid))
                if s and s[0] <= w < s[1]:
                    lam *= s[2]
                demand_rows.append((f[0], cid, w, _week_start(w), _poisson(rng, lam)))
    conn.executemany("INSERT INTO g_demand VALUES (?,?,?,?,?)", demand_rows)

    # --- tracked units (digital twin, RUL, anomaly)
    units, weeks, events = [], [], []
    revs = ["A", "B", "C"]
    for f in MRO:
        for ci, c in enumerate(CATEGORIES):
            cid, k, eta = c[0], c[4], c[5]
            for pos in range(TRACKED_POSITIONS):
                # first unit was installed before the window: random age at week 0
                life = eta * (-math.log(1 - rng.random())) ** (1 / k)
                install = -int(rng.random() * min(life, eta) * 0.9)
                n = 0
                while install < N_WEEKS:
                    p = rng.uniform(1.6, 2.6)
                    removal = install + max(3, int(round(life)))
                    uid = f"U-{f[0]}-C{ci + 1:02d}-P{pos}-{n}"
                    serial = f"SN{rng.randrange(10**6, 10**7)}"
                    failed = removal < N_WEEKS
                    units.append((uid, serial, f[0], cid, pos, install, removal if failed else None,
                                  "unscheduled_removal" if failed else None, round(life, 2), round(p, 3),
                                  "removed" if failed else "installed", f"{cid[:3].upper()}-REV-{rng.choice(revs)}"))
                    if install >= 0:
                        events.append((f"EV-{uid}-I", uid, install, _week_start(install), "installation",
                                       f"Installed at {f[1]} position {pos}", f"WO-G{rng.randrange(10**5, 10**6)}", None))
                    for w in range(max(0, install), min(removal, N_WEEKS)):
                        age = w - install
                        frac = min(1.0, age / max(life, 1))
                        health = max(0.0, 1 - 0.8 * frac ** p + rng.gauss(0, 0.02))
                        weeks_to_fail = removal - w
                        precursor = failed and weeks_to_fail <= 3
                        vib = 1.0 + 0.6 * frac ** 2 + rng.gauss(0, 0.08) + (0.55 if precursor else 0)
                        temp = 0.0 + 0.4 * frac + rng.gauss(0, 0.1)
                        pres = 1.0 - 0.15 * frac + rng.gauss(0, 0.04)
                        anomaly = 1 if precursor else 0
                        if rng.random() < 0.02:  # injected sensor anomaly (ground truth label)
                            anomaly = 1
                            ch = rng.choice(("vib", "temp", "pres"))
                            if ch == "vib":
                                vib += rng.uniform(0.6, 1.2)
                            elif ch == "temp":
                                temp += rng.uniform(0.7, 1.4)
                            else:
                                pres -= rng.uniform(0.25, 0.45)
                        h = None if rng.random() < 0.03 else round(health, 4)  # sensor dropout
                        weeks.append((uid, w, h, round(vib, 4), round(temp, 4), round(pres, 4), round(age * rng.uniform(55, 70), 1), anomaly))
                        if w > install + 6 and rng.random() < 0.015:
                            events.append((f"EV-{uid}-{w}", uid, w, _week_start(w), "inspection",
                                           "Borescope/visual inspection, no defect recorded" if health > 0.5 else "Inspection: wear within limits, monitor",
                                           f"WO-G{rng.randrange(10**5, 10**6)}", f"DOC-{rng.choice(['003', '007', '011'])}"))
                    if failed:
                        events.append((f"EV-{uid}-R", uid, removal, _week_start(removal), "removal",
                                       "Unscheduled removal after degradation", f"WO-G{rng.randrange(10**5, 10**6)}", "DOC-003"))
                    install = removal + 1
                    life = eta * (-math.log(1 - rng.random())) ** (1 / k)
                    n += 1
    conn.executemany("INSERT INTO g_units VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", units)
    conn.executemany("INSERT INTO g_unit_weeks VALUES (?,?,?,?,?,?,?,?)", weeks)
    conn.executemany("INSERT INTO g_unit_events VALUES (?,?,?,?,?,?,?,?)", events)

    # --- supplier deliveries (lead-time model), open orders, inventory
    sup = {s[0]: s for s in SUPPLIERS}
    stock_sites = [f[0] for f in MRO] + ["F06", "F08"]
    deliveries, n = [], 0
    for c in CATEGORIES:
        for sid, share, promised in c[9]:
            for _ in range(int(40 * share) + 8):
                w = rng.randrange(0, N_WEEKS)
                congestion = 1.0 + 0.12 * math.sin(2 * math.pi * (w - 40) / 52)
                actual = promised * sup[sid][7] * congestion * math.exp(rng.gauss(0, 0.18))
                n += 1
                deliveries.append((f"DL{n:05d}", sid, c[0], rng.choice(stock_sites), rng.randint(1, 12), _week_start(w), w, promised,
                                   None if rng.random() < 0.02 else round(actual, 1)))
    conn.executemany("INSERT INTO g_deliveries VALUES (?,?,?,?,?,?,?,?,?)", deliveries)
    orders, inv = [], []
    for site in stock_sites:
        for c in CATEGORIES:
            weekly = c[8] / (c[5] * math.gamma(1 + 1 / c[4])) * (1.0 if site.startswith("F0") or site in ("F10", "F11", "F12") else 0.0)
            hub = site in [m[0] for m in MRO]
            mean_weekly = weekly * (hub_scale.get(site, 1.0)) if hub else 0.0
            if hub:
                on_hand = max(0, int(round(mean_weekly * rng.uniform(2.5, 9) + rng.randint(-1, 2))))
                rop = max(1, int(round(mean_weekly * 5)))
            else:
                on_hand, rop = rng.randint(2, 14), 4
            inv.append((site, c[0], on_hand, rop, DEMO_TODAY))
            if hub and rng.random() < 0.55:
                sid, _, promised = rng.choice(c[9])
                ow = N_WEEKS - rng.randint(0, 5)
                orders.append((f"PO-{site}-{c[0]}", sid, c[0], site, max(1, int(round(mean_weekly * rng.uniform(3, 6)))),
                               _week_start(ow), ow, promised))
    conn.executemany("INSERT INTO g_inventory VALUES (?,?,?,?,?)", inv)
    conn.executemany("INSERT INTO g_open_orders VALUES (?,?,?,?,?,?,?,?)", orders)

    reps, n = [], 0
    for center in REPAIR_CENTERS:
        for c in CATEGORIES:
            for _ in range(rng.randint(10, 26)):
                n += 1
                w = rng.randrange(0, N_WEEKS)
                load = 1.0 + (0.25 if center == "F05" and w > 70 else 0.0)
                reps.append((f"RO{n:05d}", center, c[0], w, round(c[7] * load * math.exp(rng.gauss(0, 0.25)), 1)))
    conn.executemany("INSERT INTO g_repairs VALUES (?,?,?,?,?)", reps)

    fac = {f[0]: f for f in FACILITIES}
    for d in DISRUPTIONS:
        site = fac[d[3]] if d[3] else None
        s = sup[d[4]] if d[4] else None
        lat, lon = (site[6], site[7]) if site else (s[5], s[6])
        conn.execute("INSERT INTO g_disruptions VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,0,1)",
                     (d[0], d[1], d[2], lat, lon, d[5], d[3], d[4], d[6], d[7], d[8], d[9], d[10], "synthetic scenario notice"))
    conn.execute("INSERT INTO meta(key, value) VALUES ('global_dataset', ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                 (f"{DATASET_VERSION}:{GLOBAL_SEED}",))
    return {"facilities": len(FACILITIES), "suppliers": len(SUPPLIERS), "categories": len(CATEGORIES), "demand_rows": len(demand_rows),
            "units": len(units), "unit_weeks": len(weeks), "deliveries": len(deliveries), "repairs": len(reps)}


def ensure(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    r = conn.execute("SELECT value FROM meta WHERE key='global_dataset'").fetchone()
    if not r or r[0] != f"{DATASET_VERSION}:{GLOBAL_SEED}":
        generate(conn)


def assumptions() -> list[str]:
    return [
        "All facilities, suppliers, components and events are fictional (seed 20261102). Not live operational data.",
        f"History: {N_WEEKS} weekly periods ending {DEMO_TODAY}; forecasts start at that date.",
        "Removal demand is a seasonal Poisson process driven by Weibull component lives; two planned surge campaigns are included.",
        "Lead times = promised days x supplier reliability x regional congestion x noise; 2% of actuals missing.",
        "3% of health readings are missing (sensor dropout); 2% of unit-weeks carry labelled injected anomalies.",
        "Labour cost assumption: USD 95 per labour hour. Unit costs are illustrative list prices.",
        "Disruption notices are synthetic scenario events, not verified civilian notices.",
    ]


def describe() -> dict[str, Any]:
    return {"version": DATASET_VERSION, "seed": GLOBAL_SEED, "weeks": N_WEEKS, "as_of": DEMO_TODAY, "synthetic": True}
