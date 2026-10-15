"""Workbook-fidelity checks.

openpyxl rewrites the whole package on save. It keeps cell values, formulas, number formats,
basic styles, column widths/row heights, merged cells, frozen panes, auto-filters, defined
names, data validation and conditional formatting. It does NOT reliably keep: charts and
images it cannot fully parse, pivot-table caches, slicers, timelines, sparklines and other
x14 extensions, form controls/shapes, threaded comments, VBA, Power Query connections, and
external-link caches.

Rather than promising round-tripping, FloPilot inventories the package *before* editing
(`detect_features`) and compares inventories *after* writing a candidate (`compare_packages`).
"""
from __future__ import annotations

import io
import re
import zipfile
from collections import Counter

# feature -> (part-name regex, risk if present, user-facing explanation)
FEATURES: dict[str, tuple[str, str, str]] = {
    "charts": (r"^xl/charts/chart\d+\.xml$", "high", "Native Excel charts may be dropped or simplified in the modified copy."),
    "pivot_tables": (r"^xl/pivotTables/", "high", "Pivot tables and their caches may not survive editing."),
    "slicers": (r"^xl/slicers/|^xl/slicerCaches/", "high", "Slicers will be removed in the modified copy."),
    "timelines": (r"^xl/timelines/|^xl/timelineCaches/", "high", "Timelines will be removed in the modified copy."),
    "images_and_shapes": (r"^xl/media/|^xl/drawings/vmlDrawing", "medium", "Images, shapes and form controls may be lost."),
    "drawings": (r"^xl/drawings/drawing\d+\.xml$", "medium", "Drawing layers (charts/images/shapes) may be rebuilt or lost."),
    "external_links": (r"^xl/externalLinks/", "medium", "External workbook links are kept as text but never refreshed or followed."),
    "data_connections": (r"^xl/connections\.xml$|^customXml/|^xl/queryTables/", "high", "Power Query / data connections may be removed."),
    "threaded_comments": (r"^xl/threadedComments/|^xl/persons/", "medium", "Threaded comments may be converted to legacy notes or lost."),
    "macros": (r"^xl/vbaProject\.bin$", "high", "Macros are not supported and are never executed."),
    "custom_ui": (r"^customUI/", "medium", "Custom ribbon UI will be removed."),
}

_X14_EXT = re.compile(rb"<x14:(sparklineGroups|slicerList|conditionalFormattings|dataValidations)")


def _inventory(data: bytes) -> dict:
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        names = zf.namelist()
        features: Counter = Counter()
        for feature, (pattern, _, _) in FEATURES.items():
            features[feature] = sum(1 for n in names if re.search(pattern, n))
        x14 = Counter()
        for n in names:
            if re.match(r"^xl/worksheets/sheet\d+\.xml$", n):
                for m in _X14_EXT.finditer(zf.read(n)):
                    x14[m.group(1).decode()] += 1
        defined_names = 0
        if "xl/workbook.xml" in names:
            defined_names = zf.read("xl/workbook.xml").count(b"<definedName ")
    inv = {k: v for k, v in features.items() if v}
    if x14.get("sparklineGroups"):
        inv["sparklines"] = x14["sparklineGroups"]
    if x14:
        inv["x14_extensions"] = sum(x14.values())
    inv["defined_names"] = defined_names
    return inv


def detect_features(data: bytes) -> dict:
    """Features that may not be preserved by an edit, with risk level and explanation."""
    inv = _inventory(data)
    at_risk = []
    for feature, count in inv.items():
        if feature in FEATURES and count:
            _, risk, why = FEATURES[feature]
            at_risk.append({"feature": feature, "count": count, "risk": risk, "message": why})
        elif feature == "sparklines":
            at_risk.append({"feature": "sparklines", "count": count, "risk": "high", "message": "Sparklines will be removed in the modified copy."})
        elif feature == "x14_extensions" and count and "sparklines" not in inv:
            at_risk.append({"feature": "x14_extensions", "count": count, "risk": "medium",
                            "message": "Newer Excel extensions (e.g. advanced validation or conditional formats) may be simplified."})
    requires_ack = any(item["risk"] in ("high", "medium") for item in at_risk)
    return {
        "inventory": inv,
        "at_risk": at_risk,
        "requires_acknowledgement": requires_ack,
        "preserved": [
            "sheet names and order", "cell values and formulas", "number formats", "basic styling",
            "row heights and column widths", "merged cells", "frozen panes", "auto-filters",
            "Excel tables", "defined names", "data validation", "conditional formatting",
        ],
    }


def compare_packages(before: bytes, after: bytes) -> dict:
    """Measured difference between the package inventories of two versions."""
    a, b = _inventory(before), _inventory(after)
    lost = {k: {"before": v, "after": b.get(k, 0)} for k, v in a.items() if b.get(k, 0) < v}
    return {"before": a, "after": b, "lost": lost, "lossless_inventory": not lost}
