"""Repository hygiene: no credentials committed, secret files ignored."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATTERNS = [
    re.compile(r"sk-ant-api\d{2}-[A-Za-z0-9_\-]{20,}"),
    re.compile(r"sk-[A-Za-z0-9]{32,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"ghp_[A-Za-z0-9]{36}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),
]
SKIP_DIRS = {".git", "__pycache__", ".venv", "venv", ".pytest_cache"}


def _files():
    for p in ROOT.rglob("*"):
        if p.is_file() and not (set(p.parts) & SKIP_DIRS) and p.suffix not in {".png", ".jpg", ".pyc"}:
            yield p


def test_no_secrets_in_repository():
    offenders = []
    for path in _files():
        text = path.read_text(encoding="utf-8", errors="ignore")
        for pattern in PATTERNS:
            if pattern.search(text):
                offenders.append(f"{path.relative_to(ROOT)}: {pattern.pattern}")
    assert not offenders, offenders


def test_gitignore_protects_secrets():
    gitignore = (ROOT / ".gitignore").read_text().splitlines()
    for entry in [".env", ".env.*", "!.env.example", "*.key", "secrets/", "__pycache__/", ".venv/", "venv/"]:
        assert entry in gitignore, entry


def test_env_example_has_placeholder_only():
    text = (ROOT / ".env.example").read_text()
    assert "DEMO_MODE=true" in text
    assert "ANTHROPIC_API_KEY=your_own_key_here" in text
