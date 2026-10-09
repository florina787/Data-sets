"""Storefront source control: repository, candidate workspaces, patches, diffs.

The storefront lives in a local git repository (``var/storefront-repo``).
Each delivery run gets an isolated git worktree. Patches are validated and
applied with ``git apply``; every candidate revision is a real commit.
"""

from __future__ import annotations

import hashlib
import io
import re
import shutil
import subprocess
import tarfile
from dataclasses import dataclass
from pathlib import Path

from app.config import FIXTURES, get_settings
from app.errors import ToolRejected
from app.tools import runner

GIT_IDENTITY = ["-c", "user.name=FoodLaunch AI", "-c", "user.email=agents@foodlaunch.invalid",
                "-c", "core.autocrlf=false", "-c", "commit.gpgsign=false"]
EDITABLE_PREFIX = "storefront/"
PATCH_NAME = re.compile(r"^[0-9]{2}-[a-z0-9-]+\.patch$")
REVISION = re.compile(r"^[0-9a-f]{40}$")
RUN_ID = re.compile(r"^RUN-[0-9A-F]{10}$")


@dataclass
class AppliedPatch:
    revision: str
    base_revision: str
    patch_hash: str
    files: list[str]
    diff: str


def _git(args: list[str], cwd: Path, check: bool = True) -> runner.CommandResult:
    settings = get_settings()
    result = runner.run(["git", *GIT_IDENTITY, *args], cwd=cwd,
                        env=runner.scrubbed_env(home=settings.var_dir / "sandbox-home"),
                        timeout_s=60)
    if check and result.exit_code != 0:
        raise ToolRejected(f"git {args[0]} failed", output=result.output[-2000:])
    return result


def repo() -> Path:
    return get_settings().storefront_repo


def init_repository() -> str:
    """Create the storefront repository with the v1.0 baseline commit. Returns its SHA."""
    settings = get_settings()
    path = repo()
    (settings.var_dir / "sandbox-home").mkdir(parents=True, exist_ok=True)
    if path.exists():
        shutil.rmtree(path)
    shutil.copytree(FIXTURES / "storefront" / "stages" / "v1.0-baseline", path,
                    ignore=shutil.ignore_patterns("__pycache__", ".ruff_cache", "*.pyc"))
    _git(["init", "-q", "-b", "main"], path)
    _git(["add", "-A"], path)
    _git(["commit", "-q", "-m", "FreshSip storefront v1.0 baseline (seeded known-good release)"],
         path)
    return head(path)


def head(cwd: Path) -> str:
    return _git(["rev-parse", "HEAD"], cwd).output.strip()


def validate_revision(revision: str) -> str:
    if not REVISION.match(revision or ""):
        raise ToolRejected("Revision must be a full 40-character commit SHA", revision=revision)
    return revision


def workspace_path(run_id: str) -> Path:
    if not RUN_ID.match(run_id):
        raise ToolRejected("Invalid run id", run_id=run_id)
    return get_settings().workspaces_dir / run_id


def create_workspace(run_id: str, base_revision: str) -> Path:
    path = workspace_path(run_id)
    validate_revision(base_revision)
    if path.exists():
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    _git(["worktree", "add", "-q", "-B", f"candidate/{run_id.lower()}", str(path), base_revision],
         repo())
    return path


def reset_workspace_to(run_id: str, revision: str) -> None:
    """Point the candidate branch at an existing revision (e.g. the released one)."""
    validate_revision(revision)
    _git(["reset", "-q", "--hard", revision], workspace_path(run_id))


def validate_patch(text: str) -> list[str]:
    """Reject anything except text edits to files under storefront/."""
    files: list[str] = []
    for line in text.splitlines():
        if line.startswith("GIT binary patch") or line.startswith("Binary files"):
            raise ToolRejected("Binary patches are not allowed")
        if line.startswith(("new file mode 120000", "old mode", "new mode", "deleted file mode")):
            if "120000" in line or line.startswith(("old mode", "new mode")):
                raise ToolRejected("Mode changes and symlinks are not allowed", line=line)
        if line.startswith(("rename from", "rename to", "copy from", "copy to")):
            raise ToolRejected("Renames and copies are not allowed", line=line)
        if line.startswith("diff --git "):
            parts = line.split()
            for raw in parts[2:4]:
                path = raw[2:] if raw[:2] in ("a/", "b/") else raw
                if (path.startswith("/") or ".." in Path(path).parts or "\\" in path
                        or not path.startswith(EDITABLE_PREFIX)):
                    raise ToolRejected("Patch touches a path outside the candidate source tree",
                                       path=path)
                if path not in files:
                    files.append(path)
    if not files:
        raise ToolRejected("Patch contains no file changes")
    return files


def load_fixture_patch(name: str) -> str:
    if not PATCH_NAME.match(name):
        raise ToolRejected("Invalid patch name", name=name)
    return (FIXTURES / "patches" / name).read_text(encoding="utf-8")


def apply_patch(run_id: str, patch_text: str, message: str) -> AppliedPatch:
    path = workspace_path(run_id)
    files = validate_patch(patch_text)
    base = head(path)
    digest = hashlib.sha256(patch_text.encode()).hexdigest()
    patch_file = get_settings().var_dir / "patch-inbox" / f"{run_id}-{digest[:12]}.patch"
    patch_file.parent.mkdir(parents=True, exist_ok=True)
    patch_file.write_text(patch_text, encoding="utf-8")
    check = _git(["apply", "--check", "--whitespace=nowarn", str(patch_file)], path, check=False)
    if check.exit_code != 0:
        raise ToolRejected("Patch does not apply to the candidate revision", output=check.output)
    _git(["apply", "--index", "--whitespace=nowarn", str(patch_file)], path)
    _git(["commit", "-q", "-m", message], path)
    revision = head(path)
    return AppliedPatch(revision=revision, base_revision=base,
                        patch_hash=hashlib.sha256(patch_text.encode()).hexdigest(),
                        files=files, diff=diff(base, revision))


def diff(base: str, revision: str) -> str:
    validate_revision(base)
    validate_revision(revision)
    return _git(["diff", "--no-color", f"{base}..{revision}"], repo()).output


def changed_files(base: str, revision: str) -> list[str]:
    validate_revision(base)
    validate_revision(revision)
    out = _git(["diff", "--name-only", f"{base}..{revision}"], repo()).output
    return [line for line in out.splitlines() if line]


def export_revision(revision: str, target: Path) -> Path:
    """Materialise a revision into ``target`` (used for test runs and releases)."""
    validate_revision(revision)
    runner.ensure_within(target, get_settings().var_dir)
    target.mkdir(parents=True, exist_ok=True)
    data = _archive_bytes(revision)
    with tarfile.open(fileobj=io.BytesIO(data)) as tar:
        for member in tar.getmembers():
            dest = (target / member.name).resolve()
            if target.resolve() not in dest.parents and dest != target.resolve():
                raise ToolRejected("Archive member escapes target", member=member.name)
            if member.issym() or member.islnk():
                raise ToolRejected("Links are not allowed in revisions", member=member.name)
        tar.extractall(target, filter="data")
    return target


def _archive_bytes(revision: str) -> bytes:
    """Binary-safe ``git archive`` (fixed argv, validated revision, scrubbed env)."""
    settings = get_settings()
    result = subprocess.run(
        ["git", *GIT_IDENTITY, "archive", "--format=tar", validate_revision(revision)],
        cwd=repo(), capture_output=True, timeout=60,
        env=runner.scrubbed_env(home=settings.var_dir / "sandbox-home"),
    )
    if result.returncode != 0:
        raise ToolRejected("git archive failed", output=result.stderr.decode()[-500:])
    return result.stdout


def read_source(run_id: str, relative: str, max_bytes: int = 200_000) -> str:
    """Scoped source reading for agents: only files inside the run's workspace."""
    root = workspace_path(run_id)
    if relative.startswith("/") or ".." in Path(relative).parts:
        raise ToolRejected("Path traversal rejected", path=relative)
    target = runner.ensure_within(root / relative, root)
    if ".git" in target.relative_to(root.resolve()).parts:
        raise ToolRejected("Repository metadata is not readable", path=relative)
    if not target.is_file():
        raise ToolRejected("Not a file", path=relative)
    return target.read_text(encoding="utf-8")[:max_bytes]


def log(limit: int = 30) -> list[dict]:
    out = _git(["log", "--all", f"-n{limit}", "--format=%H%x09%ad%x09%s", "--date=iso-strict"],
               repo()).output
    entries = []
    for line in out.splitlines():
        sha, date, subject = line.split("\t", 2)
        entries.append({"revision": sha, "date": date, "subject": subject})
    return entries
