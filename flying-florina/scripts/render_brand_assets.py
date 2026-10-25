"""Regenerates docs/assets/banner.svg and architecture.svg (run from anywhere)."""
from html import escape as e
from pathlib import Path
OUT = str(Path(__file__).resolve().parents[1] / "docs" / "assets") + "/"
NAVY, PURPLE, LAV, GOLD, OFF, TEAL, AMBER, RED = "#0B1230", "#5C35B7", "#A78BFA", "#D7B46A", "#F7F8FC", "#0F8B8D", "#B7791F", "#C53030"
FONT = "font-family=\"Inter, 'Segoe UI', system-ui, -apple-system, Helvetica, Arial, sans-serif\""

def text(x, y, s, size=14, fill=NAVY, weight=400, anchor="start", extra=""):
    return f'<text x="{x}" y="{y}" {FONT} font-size="{size}" font-weight="{weight}" fill="{fill}" text-anchor="{anchor}" {extra}>{e(s)}</text>'

def box(x, y, w, h, fill="#fff", stroke=PURPLE, r=12, sw=1.5, dash=None, extra=""):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"{d} {extra}/>'

def chip(x, y, label, fill, color, w=None, h=30, size=12.5, stroke=None):
    w = w or (len(label) * size * 0.56 + 22)
    return box(x, y, w, h, fill, stroke or fill, r=h / 2, sw=1) + text(x + w / 2, y + h / 2 + size * 0.36, label, size, color, 600, "middle"), w

# ------------------------------------------------------------------ banner
b = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 360" width="1280" height="360" role="img" aria-label="Flying_Florina banner">',
     '<defs><linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#0B1230"/><stop offset="0.6" stop-color="#1B1650"/><stop offset="1" stop-color="#3A2380"/></linearGradient>',
     '<radialGradient id="glow" cx="0.82" cy="0.25" r="0.5"><stop offset="0" stop-color="#A78BFA" stop-opacity="0.35"/><stop offset="1" stop-color="#A78BFA" stop-opacity="0"/></radialGradient>',
     '<linearGradient id="mark" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#5C35B7"/><stop offset="1" stop-color="#0B1230"/></linearGradient></defs>',
     '<rect width="1280" height="360" rx="22" fill="url(#bg)"/><rect width="1280" height="360" rx="22" fill="url(#glow)"/>']
for i in range(14):  # subtle flight-path grid
    b.append(f'<path d="M{-100 + i * 110} 360 L{260 + i * 110} 0" stroke="#A78BFA" stroke-opacity="0.06" stroke-width="1"/>')
b.append('<path d="M640 300 C 840 260, 980 160, 1210 70" stroke="#D7B46A" stroke-opacity="0.55" stroke-width="2" stroke-dasharray="6 8" fill="none"/>')
b.append('<g transform="translate(1150,40) rotate(-20)"><path d="M0 18 L70 0 L52 14 L70 22 L46 24 L32 44 Z" fill="#F7F8FC" opacity="0.92"/></g>')
b.append('<g transform="translate(70,70)"><circle cx="70" cy="70" r="70" fill="url(#mark)"/><circle cx="70" cy="70" r="61" fill="none" stroke="#D7B46A" stroke-width="2.5"/>'
         '<path d="M30 84 L110 48 L88 66 L110 75 L84 79 L66 101 Z" fill="#F7F8FC"/>' + text(70, 128, "FF", 16, GOLD, 800, "middle") + '</g>')
b.append(text(250, 120, "Flying_Florina", 58, OFF, 800))
b.append(text(252, 160, "Aerospace & Defense Industrial AI Transformation Command Center", 21, LAV, 500))
b.append(text(252, 205, "From legacy systems to trusted industrial intelligence.", 25, OFF, 600))
b.append(text(252, 238, "Ask. Analyze. Modernize. Govern. Act — with approval.", 19, GOLD, 600))
x = 252
for lbl, f, c in [("100% synthetic data", "#2A2468", GOLD), ("Offline · $0 paid APIs", "#2A2468", OFF), ("Deny-by-default policy", "#2A2468", LAV),
                  ("Human approval gates", "#2A2468", OFF), ("Runnable API + MCP bridges", "#2A2468", GOLD)]:
    s, w = chip(x, 270, lbl, f, c, size=13.5, stroke="#4B3C9A")
    b.append(s)
    x += w + 10
b.append(text(1250, 342, "Independent concept demo · Not affiliated with or endorsed by IFS", 12, "#9EA6CF", 400, "end"))
b.append('</svg>')
open(OUT + "banner.svg", "w").write("\n".join(b))

# ------------------------------------------------------------------ architecture
W, H = 1600, 1180
a = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-label="Flying_Florina architecture">',
     '<defs><marker id="ar" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0 L10 5 L0 10 z" fill="#5C35B7"/></marker>',
     '<marker id="arr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0 L10 5 L0 10 z" fill="#C53030"/></marker>',
     '<linearGradient id="trust" x1="0" x2="1"><stop offset="0" stop-color="#5C35B7"/><stop offset="1" stop-color="#3A2380"/></linearGradient>',
     '<filter id="sh" x="-5%" y="-5%" width="110%" height="120%"><feDropShadow dx="0" dy="2" stdDeviation="3" flood-color="#0B1230" flood-opacity="0.12"/></filter></defs>',
     f'<rect width="{W}" height="{H}" rx="24" fill="{OFF}"/>',
     text(48, 62, "Flying_Florina — system architecture", 30, NAVY, 800),
     text(48, 92, "Everything runs on one machine. Every consequential step passes the deterministic policy engine before it executes.", 16, "#4B5375")]

# offline boundary
a.append(box(250, 120, 1320, 1030, "none", NAVY, r=20, sw=2, dash="10 8"))
a.append(chip(1160, 108, "LOCAL MACHINE · OFFLINE_MODE · EGRESS GUARD", NAVY, GOLD, size=12)[0])

# users column
a.append(box(30, 140, 190, 1000, "#fff", "#DCD8EC", extra='filter="url(#sh)"'))
a.append(text(125, 175, "People", 18, NAVY, 800, "middle"))
a.append(text(125, 196, "10 synthetic personas", 12.5, "#4B5375", 400, "middle"))
for i, p in enumerate(["Executive", "Maintenance Planner", "Technician", "Reliability Engineer", "Enterprise Architect", "Security Officer", "Auditor", "Fwd Deployed Engineer", "Guest (read-only)", "External supplier"]):
    y = 215 + i * 50
    a.append(box(45, y, 160, 38, "#F1EEFB", "#DCD8EC", r=10))
    a.append(text(125, y + 24, p, 12.5, NAVY, 600, "middle"))
a.append(text(125, 735, "Persona changes the view;", 12, "#4B5375", 400, "middle"))
a.append(text(125, 752, "the backend decides rights.", 12, "#4B5375", 400, "middle"))
a.append(f'<path d="M220 300 L 268 300" stroke="{PURPLE}" stroke-width="2.5" marker-end="url(#ar)"/>')

def layer(y, h, title, subtitle, fill="#fff", stroke="#DCD8EC", tcolor=NAVY, scolor="#4B5375"):
    a.append(box(270, y, 1280, h, fill, stroke, r=16, extra='filter="url(#sh)"'))
    a.append(text(292, y + 30, title, 17, tcolor, 800))
    a.append(text(292, y + 50, subtitle, 12.5, scolor))

def tiles(y, items, x0=292, gap=12, h=54, fill="#F1EEFB", stroke="#DCD8EC", tc=NAVY, sc="#4B5375", widths=None, total=1236):
    n = len(items)
    w = (total - gap * (n - 1)) / n
    x = x0
    for i, (t, s) in enumerate(items):
        ww = widths[i] if widths else w
        a.append(box(x, y, ww, h, fill, stroke, r=10))
        a.append(text(x + ww / 2, y + 23, t, 13.5, tc, 700, "middle"))
        if s:
            a.append(text(x + ww / 2, y + 41, s, 11.5, sc, 400, "middle"))
        x += ww + gap

def down(x, y1, y2, color=PURPLE, label=None):
    a.append(f'<path d="M{x} {y1} L{x} {y2}" stroke="{color}" stroke-width="2.5" marker-end="url(#ar)"/>')
    if label:
        a.append(text(x + 14, (y1 + y2) / 2 + 4, label, 11.5, "#4B5375", 600))

# 1 experience
layer(140, 140, "1 · Experience — React + TypeScript + Vite", "Mission Control chat · live execution timeline · agent graph · 15 pages · light/dark · responsive")
tiles(206, [("Mission Control", "ask · timeline · replay"), ("Fleet · AOG · MRO", "dashboards"), ("Parts · Quality", "supply chain"),
            ("Legacy X-Ray", "dependency map"), ("Bridge Studio", "10-step wizard"), ("Trust Center", "10 tabs"), ("Executive Studio", "ROI · roadmap")])
down(910, 280, 312, label="Bearer token · JSON envelope")

# 2 API
layer(312, 110, "2 · API — FastAPI", "")
tiles(352, [("Identity", "HMAC token · audience · expiry"), ("Security headers", "CSP · nosniff · no-store"), ("Validation", "Pydantic · upload limits"),
            ("Envelope", "request_id · typed errors"), ("OpenAPI", "61 paths")], h=50)
down(910, 422, 454)

# 3 orchestration
layer(454, 170, "3 · Orchestration — deterministic, no hosted LLM", "")
tiles(494, [("Intake & Intent Agent", "rules router · clarification"), ("Workflow engine", "DAG waves · retries · timeouts · cancel · checkpoints")],
      widths=[300, 924], h=50)
agents = ["Telemetry", "Retrieval", "Diagnostics", "Parts", "Planner", "Compliance", "Legacy Discovery", "Integration Architect", "Simulator", "Reporting", "Security & Gov."]
x = 292
for ag in agents:
    s, w = chip(x, 560, ag, "#fff", PURPLE, size=12, stroke=LAV, h=32)
    a.append(s)
    x += w + 8
a.append(text(292, 612, "13 typed agents with bounded tool access · agent rights = own grants ∩ requesting human's grants", 12, "#4B5375"))
down(910, 624, 656, label="every tool call")

# 4 trust (purple band)
a.append(box(270, 656, 1280, 170, "url(#trust)", PURPLE, r=16, extra='filter="url(#sh)"'))
a.append(text(292, 686, "4 · Trust layer — policy-as-code, deny by default", 17, "#fff", 800))
a.append(text(292, 706, "Evaluated before execution · decisions recorded with ordered checks · no model decides what is allowed", 12.5, "#DCD3FF"))
tiles(722, [("Tool gateway", "pinned · schema SHA-256"), ("Policy engine", "13 policies · POL-001…013"), ("Approvals", "SoD · expiry · idempotency"),
            ("Audit chain", "SHA-256 hash-linked"), ("Kill switch", "POL-009"), ("Injection guard", "POL-011 quarantine")],
      fill="#2A1B66", stroke="#7C5CD6", tc="#fff", sc="#C9BCFF", h=58)
a.append(text(292, 808, "ALLOW → tool runs · DENY → tool never runs (export demo: 0 executions)", 12.5, GOLD, 700))
down(910, 826, 858, label="ALLOW only")

# 5 capabilities
layer(858, 120, "5 · Capabilities", "")
tiles(898, [("Retrieval", "SQL label filter → FTS5/BM25 → TF-IDF"), ("Simulation & ROI", "deterministic · seeded Monte Carlo"), ("Legacy X-Ray", "parse only · never execute"),
            ("Bridge generator", "adapter + MCP + tests"), ("Reports", "PDF · HTML · MD · CSV · JSON")], h=58)
down(910, 978, 1008)

# 6 data
layer(1008, 128, "6 · Data & integration", "")
tiles(1048, [("SQLite", "synthetic · seed 20261024"), ("Fixtures", "schemas · OpenAPI · docs"), ("Demo MCP server", "stdio · official SDK"),
             ("Generated adapter", "sandboxed pytest 14/14")], widths=[220, 220, 220, 240], h=58)
a.append(box(1260, 1048, 268, 58, "#fff", RED, r=10, dash="6 5"))
a.append(text(1394, 1071, "IFS Cloud / live ERP", 13.5, RED, 700, "middle"))
a.append(text(1394, 1089, "not connected · documented APIs only", 11.5, RED, 400, "middle"))

# right callouts
a.append(text(1550, 1170, "Independent concept demo · Not affiliated with or endorsed by IFS · All data fictional", 12, "#4B5375", 400, "end"))
a.append('</svg>')
open(OUT + "architecture.svg", "w").write("\n".join(a))
print("ok")
