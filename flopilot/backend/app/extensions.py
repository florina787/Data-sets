"""Extension interfaces for later integrations. NONE of these are implemented or connected.

They document the seams where integrations plug in without touching workbook logic:

* WorkbookSource      - OneDrive / SharePoint via Microsoft Graph (open + save back a file).
* ExcelHostBridge     - an Excel task-pane add-in (Office.js) that sends a selection and receives
                        an approved change set to apply inside the user's live Excel session.
* DataDictionary      - business definitions ("revenue means Net Revenue") from a catalogue.
* CalculationRules    - organisation-specific calculation rules (fiscal calendars, FX policy).

Implementations must keep the existing guarantees: deterministic calculations, approval bound to
an exact change set and version, and least-privilege scopes (for Graph: Files.ReadWrite on the
selected file via the file picker - never Files.ReadWrite.All or Sites.ReadWrite.All by default).
"""
from __future__ import annotations

from typing import Protocol


class WorkbookSource(Protocol):
    def open(self, item_id: str) -> tuple[str, bytes]: ...           # (file name, bytes)
    def save_new_version(self, item_id: str, data: bytes, expected_etag: str) -> str: ...  # returns new etag


class ExcelHostBridge(Protocol):
    def selection(self) -> dict: ...                                  # {"sheet", "range"}
    def apply(self, change_set: dict, approval_id: str) -> dict: ...  # applies inside Excel, returns result


class DataDictionary(Protocol):
    def definition(self, term: str) -> dict | None: ...               # {"term", "sheet", "column", "source"}


class CalculationRules(Protocol):
    def fiscal_period(self, iso_date: str) -> str: ...


class NotConfigured(Exception):
    """Raised by placeholder integrations so nothing silently pretends to be connected."""


class GraphWorkbookSource:  # pragma: no cover - placeholder only
    def open(self, item_id: str) -> tuple[str, bytes]:
        raise NotConfigured("OneDrive/SharePoint integration is not implemented in this build.")

    def save_new_version(self, item_id: str, data: bytes, expected_etag: str) -> str:
        raise NotConfigured("OneDrive/SharePoint integration is not implemented in this build.")
