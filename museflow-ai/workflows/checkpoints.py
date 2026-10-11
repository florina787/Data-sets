"""Session-isolated checkpoint storage.

Each visitor session owns its own ``InMemorySaver``; thread ids are namespaced by session id.
Checkpoints are never written to disk or shared between sessions.
"""
from __future__ import annotations

from typing import Any

from langgraph.checkpoint.memory import InMemorySaver

RECURSION_LIMIT = 100


class SessionCheckpointStore:
    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        self.saver = InMemorySaver()
        self._threads: set[str] = set()

    def thread_id(self, run_id: str) -> str:
        return f"{self.session_id}:{run_id}"

    def config_for(self, run_id: str) -> dict[str, Any]:
        thread = self.thread_id(run_id)
        self._threads.add(thread)
        return {"configurable": {"thread_id": thread}, "recursion_limit": RECURSION_LIMIT}

    def owns(self, thread_id: str) -> bool:
        return thread_id.startswith(f"{self.session_id}:") and thread_id in self._threads

    def threads(self) -> list[str]:
        return sorted(self._threads)

    def checkpoint_count(self, run_id: str) -> int:
        return sum(1 for _ in self.saver.list(self.config_for(run_id)))
