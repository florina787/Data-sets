"""Regenerate (or --check) fixture patches from the storefront stage trees.

The stage trees under fixtures/storefront/stages are the readable source of the
seeded proposals. The platform never copies a stage tree into a candidate
workspace: it applies the generated unified diff with ``git apply``, so every
candidate revision is a real commit produced by a real patch.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGES = ROOT / "fixtures" / "storefront" / "stages"
PATCHES = ROOT / "fixtures" / "patches"

PAIRS = [
    ("v1.0-baseline", "v1.1-campaign-faulty", "01-campaign-implementation.patch"),
    ("v1.1-campaign-faulty", "v1.1-campaign-fixed", "02-free-unit-recompute-fix.patch"),
    ("v1.1-campaign-fixed", "v1.2-timeout-repair", "03-inventory-timeout-repair.patch"),
]
IGNORE = shutil.ignore_patterns("__pycache__", ".ruff_cache", "*.pyc")


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-c", "user.name=fixture", "-c", "user.email=fixture@example.invalid",
         "-c", "core.autocrlf=false", *args],
        cwd=cwd, check=True, capture_output=True, text=True,
    ).stdout


def build_patch(before: str, after: str) -> str:
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        # copy without preserving mtimes: same-size edits with equal timestamps would
        # otherwise be invisible to git's stat cache and silently drop from the patch
        shutil.copytree(STAGES / before, repo, ignore=IGNORE, copy_function=shutil.copy)
        git(repo, "init", "-q")
        git(repo, "add", "-A")
        git(repo, "commit", "-q", "-m", before)
        for child in repo.iterdir():
            if child.name != ".git":
                shutil.rmtree(child) if child.is_dir() else child.unlink()
        shutil.copytree(STAGES / after, repo, dirs_exist_ok=True, ignore=IGNORE, copy_function=shutil.copy)
        git(repo, "update-index", "-q", "--really-refresh")
        git(repo, "add", "-A")
        return git(repo, "diff", "--cached", "--no-color", "--full-index")


def main() -> int:
    check = "--check" in sys.argv
    stale = []
    PATCHES.mkdir(parents=True, exist_ok=True)
    for before, after, name in PAIRS:
        patch = build_patch(before, after)
        target = PATCHES / name
        if check:
            if not target.exists() or target.read_text() != patch:
                stale.append(name)
        else:
            target.write_text(patch)
            print(f"wrote {target.relative_to(ROOT)} ({len(patch.splitlines())} lines)")
    if stale:
        print("stale fixture patches:", ", ".join(stale))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
