"""Bounded concurrency with a bounded wait queue: extra work is refused, never piled up."""

from __future__ import annotations

import threading
from contextlib import contextmanager
from typing import Iterator

from app.errors import Overloaded


class BoundedGate:
    def __init__(self, name: str, concurrency: int, queue_size: int, wait_s: float) -> None:
        self.name = name
        self._slots = threading.BoundedSemaphore(max(1, concurrency))
        self._lock = threading.Lock()
        self.queue_size, self.wait_s = queue_size, wait_s
        self.waiting = self.running = self.rejected = self.completed = 0

    @contextmanager
    def slot(self) -> Iterator[None]:
        if not self._slots.acquire(blocking=False):
            with self._lock:
                if self.waiting >= self.queue_size:
                    self.rejected += 1
                    raise Overloaded(f"{self.name} is busy (queue full). Try again shortly.", queue=self.queue_size)
                self.waiting += 1
            try:
                acquired = self._slots.acquire(timeout=self.wait_s)
            finally:
                with self._lock:
                    self.waiting -= 1
            if not acquired:
                with self._lock:
                    self.rejected += 1
                raise Overloaded(f"{self.name} is busy (waited {self.wait_s:g}s in the queue).")
        with self._lock:
            self.running += 1
        try:
            yield
        finally:
            with self._lock:
                self.running -= 1
                self.completed += 1
            self._slots.release()

    def status(self) -> dict:
        with self._lock:
            return {"running": self.running, "queued": self.waiting, "queue_limit": self.queue_size,
                    "rejected": self.rejected, "completed": self.completed}


