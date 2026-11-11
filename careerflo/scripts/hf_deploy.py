"""Stage, verify and (only with --apply) deploy Career_flo AI to a Hugging Face Docker Space.

Default is a DRY RUN: it builds the staging folder, scans it for secrets, checks configuration and prints the plan.
Nothing is uploaded and no Hugging Face resource is created unless --apply is given.

    # from careerflo/  (uses the backend's uv environment for huggingface_hub)
    backend/.venv/bin/python scripts/hf_deploy.py --space OWNER/careerflo                 # dry run
    backend/.venv/bin/python scripts/hf_deploy.py --space OWNER/careerflo --stage-only    # staging folder only (CI docker build)
    HF_TOKEN=... backend/.venv/bin/python scripts/hf_deploy.py --space OWNER/careerflo --apply [--sync-secrets]
    backend/.venv/bin/python scripts/hf_deploy.py --space OWNER/careerflo --git-ref v0.3.0 --apply   # deploy a tag

Notes
* Creating a Docker Space requires a paid Hugging Face plan (PRO for personal accounts) — see docs/HF_FREE_TIER_RESEARCH.md.
* New Spaces are created PRIVATE. Making the app public is a separate, explicit step (--visibility).
* --sync-secrets copies the variables listed in deploy/hf-space/space.env.example from YOUR local environment into the
  Space (secrets as Secrets, the rest as Variables). Values are never printed or written to disk.
"""
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]  # careerflo/
DEPLOY = ROOT / "deploy" / "hf-space"
EXCLUDE = ["**/.venv/**", "**/node_modules/**", "**/dist/**", "**/__pycache__/**", "**/*.db", "**/*.db-*", "**/.env",
           "**/.env.*", "**/*.tsbuildinfo", "backend/tests/**", "backend/scripts/**", "frontend/e2e/**",
           "frontend/test-results/**", "frontend/playwright-report/**", "**/.pytest_cache/**"]
SECRET_PATTERNS = {
    "stripe_secret": re.compile(r"\b(sk|rk)_(live|test)_[A-Za-z0-9]{16,}"),
    "stripe_webhook": re.compile(r"\bwhsec_[A-Za-z0-9]{16,}"),
    "hf_token": re.compile(r"\bhf_[A-Za-z0-9]{30,}"),
    "github_token": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}"),
    "aws_key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "private_key": re.compile(r"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "postgres_password_url": re.compile(r"postgres(?:ql)?://[^:\s/]+:[^@\s<>]{6,}@(?!localhost|127\.0\.0\.1)"),
}
SECRET_KEYS = {"DATABASE_URL", "ADMIN_EMAILS", "STRIPE_SECRET_KEY", "STRIPE_WEBHOOK_SECRET", "JSEARCH_API_KEY", "ADZUNA_APP_ID",
               "ADZUNA_APP_KEY", "GITHUB_TOKEN", "HF_TOKEN", "LOCAL_JWT_SECRET"}
REQUIRED = ["DATABASE_URL", "AUTH_MODE", "SUPABASE_URL", "VITE_SUPABASE_URL", "VITE_SUPABASE_ANON_KEY", "PUBLIC_APP_URL",
            "CORS_ORIGINS", "STRIPE_SECRET_KEY", "STRIPE_WEBHOOK_SECRET", "STRIPE_PRICE_PRO", "STRIPE_PRICE_PREMIUM"]


def _excluded(rel: str) -> bool:
    return any(fnmatch.fnmatch(rel, p) or fnmatch.fnmatch(rel + "/", p) for p in EXCLUDE)


def source_tree(git_ref: str | None) -> tuple[Path, str, Path | None]:
    """Return (careerflo root to stage from, git sha, temp dir to clean)."""
    sha = subprocess.run(["git", "rev-parse", git_ref or "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    if not git_ref:
        return ROOT, sha, None
    tmp = Path(tempfile.mkdtemp(prefix="careerflo-ref-"))
    archive = subprocess.run(["git", "archive", "--format=tar", sha, "careerflo"], cwd=ROOT.parent, capture_output=True, check=True).stdout
    tar_path = tmp / "src.tar"
    tar_path.write_bytes(archive)
    with tarfile.open(tar_path) as tf:
        tf.extractall(tmp, filter="data")
    return tmp / "careerflo", sha, tmp


def stage(src: Path, out: Path, sha: str, ref: str | None) -> dict:
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    files = []
    for top in ("backend", "frontend"):
        for p in sorted((src / top).rglob("*")):
            rel = p.relative_to(src).as_posix()
            if p.is_dir() or _excluded(rel):
                continue
            dest = out / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, dest)
            files.append(rel)
    dep = src / "deploy" / "hf-space"
    shutil.copy2(dep / "Dockerfile", out / "Dockerfile")
    shutil.copy2(dep / "start.sh", out / "start.sh")
    shutil.copy2(dep / "README.space.md", out / "README.md")
    (out / ".dockerignore").write_text("**/.venv\n**/node_modules\n**/dist\n**/__pycache__\n**/*.db\n.git\n")
    digest = hashlib.sha256()
    for rel in sorted(files):
        digest.update(rel.encode()); digest.update((out / rel).read_bytes())
    manifest = {"app": "careerflo", "git_sha": sha, "git_ref": ref or "working-tree", "content_sha256": digest.hexdigest(),
                "files": len(files), "staged_at": datetime.now(timezone.utc).isoformat()}
    (out / "deploy-manifest.json").write_text(json.dumps(manifest, indent=2))
    return manifest


def scan_secrets(folder: Path) -> list[str]:
    findings = []
    for p in folder.rglob("*"):
        if not p.is_file() or p.stat().st_size > 5_000_000:
            continue
        try:
            text = p.read_text(errors="ignore")
        except OSError:
            continue
        for name, pat in SECRET_PATTERNS.items():
            for m in pat.finditer(text):
                snippet = m.group(0)
                if any(x in snippet for x in ("...", "<", "placeholder", "fake", "XXXX", "test_secret", "should_not")):
                    continue  # documented placeholders / test fixtures
                findings.append(f"{p.relative_to(folder)}: {name}")
    return sorted(set(findings))


def size_mb(folder: Path) -> float:
    return round(sum(p.stat().st_size for p in folder.rglob("*") if p.is_file()) / 1e6, 2)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--space", help="OWNER/NAME of the Docker Space")
    ap.add_argument("--git-ref", help="deploy this git tag/commit instead of the working tree")
    ap.add_argument("--out", default=str(ROOT / ".hf-staging"), help="staging folder")
    ap.add_argument("--stage-only", action="store_true", help="only build the staging folder (for CI docker builds)")
    ap.add_argument("--apply", action="store_true", help="actually create/update the Space (otherwise dry run)")
    ap.add_argument("--sync-secrets", action="store_true", help="copy configuration from local env into Space secrets/variables")
    ap.add_argument("--visibility", choices=["private", "protected", "public"], default=None,
                    help="change visibility (new Spaces are always created private)")
    ap.add_argument("--allow-missing-config", action="store_true", help="apply even if required config names are missing locally")
    a = ap.parse_args(argv)

    src, sha, tmp = source_tree(a.git_ref)
    try:
        out = Path(a.out)
        manifest = stage(src, out, sha, a.git_ref)
    finally:
        if tmp:
            shutil.rmtree(tmp, ignore_errors=True)
    findings = scan_secrets(out)
    print(json.dumps({"staging": str(out), "size_mb": size_mb(out), **manifest}, indent=2))
    if findings:
        print("SECRET SCAN FAILED — refusing to continue:\n  " + "\n  ".join(findings), file=sys.stderr)
        return 2
    print("secret scan: clean")
    if a.stage_only:
        return 0
    missing = [k for k in REQUIRED if not os.environ.get(k)]
    print(f"required configuration present locally: {len(REQUIRED) - len(missing)}/{len(REQUIRED)}"
          + (f" (missing: {', '.join(missing)})" if missing else ""))
    if os.environ.get("STRIPE_ALLOW_LIVE", "false").lower() == "true" or os.environ.get("STRIPE_SECRET_KEY", "").startswith("sk_live"):
        print("REFUSING: live Stripe configuration detected. Live billing needs explicit owner approval and a separate change.", file=sys.stderr)
        return 3
    if not a.apply:
        print("\nDRY RUN — nothing was uploaded. Re-run with --apply (and HF_TOKEN set) after approval.")
        return 0
    if not a.space:
        ap.error("--space is required with --apply")
    if missing and a.sync_secrets and not a.allow_missing_config:
        print("Refusing to sync incomplete configuration (use --allow-missing-config to override).", file=sys.stderr)
        return 4
    token = os.environ.get("HF_TOKEN")
    if not token:
        print("HF_TOKEN is not set.", file=sys.stderr)
        return 5
    from huggingface_hub import HfApi

    api = HfApi(token=token)
    api.create_repo(a.space, repo_type="space", space_sdk="docker", private=True, exist_ok=True)
    if a.sync_secrets:
        for line in (DEPLOY / "space.env.example").read_text().splitlines():
            key = line.split("=", 1)[0].strip().lstrip("# ").strip()
            if not re.fullmatch(r"[A-Z][A-Z0-9_]+", key) or key not in os.environ:
                continue
            (api.add_space_secret if key in SECRET_KEYS else api.add_space_variable)(a.space, key, os.environ[key])
            print(f"  set {'secret' if key in SECRET_KEYS else 'variable'} {key}")
    info = api.upload_folder(repo_id=a.space, repo_type="space", folder_path=str(out), delete_patterns=["*"],
                             commit_message=f"Deploy careerflo {manifest['git_ref']} @ {sha[:12]}",
                             commit_description=json.dumps(manifest))
    if a.visibility:
        api.update_repo_settings(a.space, repo_type="space", visibility=a.visibility)
    print(json.dumps({"deployed": True, "space": a.space, "space_commit": getattr(info, "oid", None),
                      "url": f"https://huggingface.co/spaces/{a.space}", "rollback": f"scripts/hf_rollback.py --space {a.space} --to <previous space_commit>"}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
