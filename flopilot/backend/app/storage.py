"""Blob storage for workbook versions.

Versions are immutable: a key is written once (atomically, via temp file + rename) and never
overwritten. `LocalStorage` is used for development; `ObjectStorage` documents the interface
an S3/Azure Blob adapter must satisfy.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Protocol

from .common import AppError
from .config import get_settings


class Storage(Protocol):
    def put_immutable(self, key: str, data: bytes) -> None: ...
    def get(self, key: str) -> bytes: ...
    def path_for(self, key: str) -> Path: ...
    def delete(self, key: str) -> None: ...


class LocalStorage:
    def __init__(self, root: Path):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def path_for(self, key: str) -> Path:
        path = (self.root / key).resolve()
        if self.root.resolve() not in path.parents:
            raise AppError("invalid_storage_key", "Invalid storage key.", 400)
        return path

    def put_immutable(self, key: str, data: bytes) -> None:
        path = self.path_for(key)
        if path.exists():
            raise AppError("version_exists", "This workbook version already exists.", 409)
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".tmp-", suffix=".part")
        try:
            with os.fdopen(fd, "wb") as fh:
                fh.write(data)
                fh.flush()
                os.fsync(fh.fileno())
            os.chmod(tmp, 0o440)
            os.replace(tmp, path)  # atomic publication on the same filesystem
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)

    def get(self, key: str) -> bytes:
        path = self.path_for(key)
        if not path.exists():
            raise AppError("version_missing", "The stored workbook version could not be found.", 404)
        return path.read_bytes()

    def delete(self, key: str) -> None:
        path = self.path_for(key)
        if path.exists():
            os.chmod(path, 0o640)
            path.unlink()

    def cleanup_temp_files(self) -> int:
        removed = 0
        for tmp in self.root.rglob(".tmp-*.part"):
            tmp.unlink(missing_ok=True)
            removed += 1
        return removed


_storage: LocalStorage | None = None


def get_storage() -> LocalStorage:
    global _storage
    root = get_settings().data_dir / "blobs"
    if _storage is None or _storage.root != root:
        _storage = LocalStorage(root)
    return _storage
