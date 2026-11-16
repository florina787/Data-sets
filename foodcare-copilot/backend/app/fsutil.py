"""File-system helpers that behave the same on Windows, macOS and Linux."""

from __future__ import annotations

import os
import shutil
import stat
from pathlib import Path


def _make_writable_and_retry(func, path, _exc) -> None:
    # Git marks its object files read-only; Windows refuses to delete read-only files.
    os.chmod(path, stat.S_IWRITE | stat.S_IREAD)
    func(path)


def remove_tree(path: Path | str, ignore_errors: bool = False) -> None:
    """``shutil.rmtree`` that also deletes read-only files (e.g. a git repository on Windows)."""
    try:
        shutil.rmtree(path, onexc=_make_writable_and_retry)
    except TypeError:  # Python < 3.12 has onerror instead of onexc
        shutil.rmtree(path, onerror=_make_writable_and_retry)
    except OSError:
        if not ignore_errors:
            raise
