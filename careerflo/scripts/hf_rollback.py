"""Roll a Career_flo Hugging Face Space back to a known-good deployment.

The Space repository itself is the deployment history: every deploy is one commit whose description holds the
deploy manifest (git sha, content hash). Rollback downloads the files of a previous Space commit and commits them
again as the new head, which triggers a rebuild of exactly that version. Default is a DRY RUN.

    backend/.venv/bin/python scripts/hf_rollback.py --space OWNER/careerflo --list
    HF_TOKEN=... backend/.venv/bin/python scripts/hf_rollback.py --space OWNER/careerflo --to <space_commit_sha> --apply

Alternative: redeploy a git tag with `scripts/hf_deploy.py --git-ref <tag> --apply`.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--space", required=True)
    ap.add_argument("--list", action="store_true", help="list recent deployments")
    ap.add_argument("--to", help="Space commit sha to restore")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args(argv)
    from huggingface_hub import HfApi

    api = HfApi(token=os.environ.get("HF_TOKEN"))
    commits = api.list_repo_commits(a.space, repo_type="space")
    if a.list or not a.to:
        for c in commits[:20]:
            print(f"{c.commit_id[:12]}  {c.created_at:%Y-%m-%d %H:%M}  {c.title}")
        return 0
    match = [c for c in commits if c.commit_id.startswith(a.to)]
    if len(match) != 1:
        print(f"Commit {a.to!r} not found (or ambiguous) in {a.space}.", file=sys.stderr)
        return 2
    target = match[0]
    print(f"Rollback target: {target.commit_id[:12]} — {target.title}")
    if not a.apply:
        print("DRY RUN — re-run with --apply to restore this version.")
        return 0
    with tempfile.TemporaryDirectory() as tmp:
        api.snapshot_download(a.space, repo_type="space", revision=target.commit_id, local_dir=tmp)
        info = api.upload_folder(repo_id=a.space, repo_type="space", folder_path=tmp, delete_patterns=["*"],
                                 ignore_patterns=[".cache/**"],
                                 commit_message=f"Rollback to {target.commit_id[:12]}",
                                 commit_description=json.dumps({"rollback_of": target.commit_id}))
    print(json.dumps({"rolled_back_to": target.commit_id, "new_head": getattr(info, "oid", None)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
