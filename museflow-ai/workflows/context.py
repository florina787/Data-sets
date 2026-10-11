"""Run-time dependencies injected into every node (LangGraph ``context_schema``).

Injecting the stores and tool registry (instead of importing globals) keeps each visitor's
data isolated and lets tests swap in fakes.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from services.audit_logger import AuditLogger
from services.memory_store import SessionStores
from services.tool_registry import ToolRegistry


@dataclass
class MuseContext:
    session_id: str
    stores: SessionStores
    tools: ToolRegistry
    audit: AuditLogger
    today: date
