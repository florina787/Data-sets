"""Engineering tools: patches, sandboxed runner, retrieval, static checks."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from app.config import ROOT, get_settings
from app.errors import ToolRejected
from app.tools import runner, static_checks, testing, workspace
from app.tools.retrieval import get_index

PLAN_V1 = ["test_campaign_rules.py", "test_checkout.py", "test_returns.py"]


def test_fixture_patches_match_stage_trees():
    result = subprocess.run([sys.executable, str(ROOT / "scripts" / "regen_fixture_patches.py"), "--check"],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("bad", [
    "diff --git a/../outside.py b/../outside.py\n",
    "diff --git a/tests/test_x.py b/tests/test_x.py\n",
    "diff --git a/storefront/x.py b/storefront/x.py\nnew file mode 120000\n",
    "diff --git a/storefront/a.py b/storefront/b.py\nrename from storefront/a.py\nrename to storefront/b.py\n",
    "diff --git a/storefront/x.bin b/storefront/x.bin\nGIT binary patch\n",
])
def test_patch_validation_rejects_unsafe_changes(bad):
    with pytest.raises(ToolRejected):
        workspace.validate_patch(bad)


def test_source_reading_is_scoped_to_the_workspace(platform):
    workspace.create_workspace("RUN-00000000AA", platform["base"])
    assert "CODE_VERSION" in workspace.read_source("RUN-00000000AA", "storefront/__init__.py")
    for path in ("../../platform.db", "/etc/passwd", ".git/config"):
        with pytest.raises(ToolRejected):
            workspace.read_source("RUN-00000000AA", path)
    with pytest.raises(ToolRejected):
        workspace.workspace_path("../RUN-1")


def test_runner_enforces_allow_list_cwd_timeout_and_credential_scrubbing(platform, monkeypatch):
    var = get_settings().var_dir
    with pytest.raises(ToolRejected):
        runner.run(["bash", "-c", "echo hi"], cwd=var, env={})
    with pytest.raises(ToolRejected):
        runner.run([sys.executable, "-c", "print(1)"], cwd=Path("/tmp"), env={})
    with pytest.raises(ToolRejected):
        runner.scrubbed_env({"ANTHROPIC_API_KEY": "x"})
    monkeypatch.setenv("ANTHROPIC_API_KEY", "should-not-leak")
    leaked = runner.run([sys.executable, "-c", "import os; print(os.environ.get('ANTHROPIC_API_KEY'))"],
                        cwd=var, env=runner.scrubbed_env(home=var))
    assert leaked.output.strip() == "None"
    slow = runner.run([sys.executable, "-c", "import time; time.sleep(10)"], cwd=var,
                      env=runner.scrubbed_env(home=var), timeout_s=1)
    assert slow.timed_out and slow.exit_code == -9 and slow.duration_s < 5


def test_faulty_candidate_fails_regression_and_repair_passes_same_tests(platform):
    workspace.create_workspace("RUN-00000000BB", platform["base"])
    plan = testing.plan_hashes(PLAN_V1)
    faulty = workspace.apply_patch("RUN-00000000BB",
                                   workspace.load_fixture_patch("01-campaign-implementation.patch"), "impl")
    failing = testing.run_acceptance(run_id=None, revision=faulty.revision, suite_version=1, plan=plan, purpose="t")
    assert failing["status"] == "failed" and failing["exit_code"] == 1
    assert any("removing_qualifying_paid_units" in n for n in failing["failed"])
    fixed = workspace.apply_patch("RUN-00000000BB",
                                  workspace.load_fixture_patch("02-free-unit-recompute-fix.patch"), "fix")
    passing = testing.run_acceptance(run_id=None, revision=fixed.revision, suite_version=1, plan=plan, purpose="t")
    assert passing["status"] == "passed" and passing["exit_code"] == 0 and passing["total"] == failing["total"]
    checks = static_checks.run_static_checks(None, fixed.revision)
    assert [c["status"] for c in checks] == ["passed", "passed"]


def test_timeout_regression_fails_on_campaign_release_and_passes_on_repair(platform):
    workspace.create_workspace("RUN-00000000CC", platform["base"])
    plan = testing.plan_hashes(PLAN_V1 + ["test_resilience.py"])
    for name in ("01-campaign-implementation.patch", "02-free-unit-recompute-fix.patch"):
        released = workspace.apply_patch("RUN-00000000CC", workspace.load_fixture_patch(name), name)
    before = testing.run_acceptance(run_id=None, revision=released.revision, suite_version=2, plan=plan, purpose="t")
    assert before["status"] == "failed"
    assert all("test_resilience.py" in n for n in before["failed"])
    repaired = workspace.apply_patch("RUN-00000000CC",
                                     workspace.load_fixture_patch("03-inventory-timeout-repair.patch"), "repair")
    after = testing.run_acceptance(run_id=None, revision=repaired.revision, suite_version=2, plan=plan, purpose="t")
    assert after["status"] == "passed", after


def test_modified_protected_tests_are_refused(platform):
    plan = testing.plan_hashes(PLAN_V1)
    plan["hashes"]["test_campaign_rules.py"] = "0" * 64
    plan["tests_hash"] = "1" * 64
    with pytest.raises(ToolRejected):
        testing.run_acceptance(run_id=None, revision=platform["base"], suite_version=1, plan=plan, purpose="t")


def test_retrieval_returns_versioned_sections_and_gaps():
    hits = get_index().search("customer limits scope redemptions per customer")
    assert hits[0]["ref"] == "POL-PROMO v3.2 §5"
    assert "does not define a default scope" in hits[0]["excerpt"]
