"""The Kubernetes integration files are well-formed and agree with the app.

No cluster is needed: the YAML is parsed and checked for the properties the integration
guide promises (single writer for SQLite, probes, non-root, scrape config, no extra egress).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import yaml
from fastapi.testclient import TestClient

from app import config

ROOT = Path(__file__).resolve().parents[2]
K8S = ROOT / "deploy" / "k8s"


def docs(path: Path) -> list[dict]:
    return [d for d in yaml.safe_load_all(path.read_text()) if d]


def base() -> dict[str, dict]:
    kust = docs(K8S / "base" / "kustomization.yaml")[0]
    out = {}
    for res in kust["resources"]:
        for d in docs(K8S / "base" / res):
            out[d["kind"]] = d
    return out


def test_every_yaml_file_parses_and_kustomizations_reference_existing_files():
    files = list((ROOT / "deploy").rglob("*.yaml"))
    assert len(files) >= 12
    for f in files:
        for d in docs(f):
            assert "apiVersion" in d and "kind" in d, f
    for kust in K8S.rglob("kustomization.yaml"):
        for res in docs(kust)[0].get("resources", []) + docs(kust)[0].get("components", []):
            assert (kust.parent / res).exists(), f"{kust}: {res}"


def test_deployment_is_a_single_safe_writer():
    dep = base()["Deployment"]
    spec, pod = dep["spec"], dep["spec"]["template"]["spec"]
    assert spec["replicas"] == 1 and spec["strategy"]["type"] == "Recreate"  # SQLite: one writer
    c = pod["containers"][0]
    assert pod["securityContext"]["runAsNonRoot"] and pod["automountServiceAccountToken"] is False
    assert c["securityContext"]["readOnlyRootFilesystem"] and c["securityContext"]["capabilities"]["drop"] == ["ALL"]
    for probe in ("startupProbe", "readinessProbe", "livenessProbe"):
        assert c[probe]["httpGet"]["path"] == "/api/health"
    assert c["resources"]["limits"]["memory"] and c["resources"]["requests"]["cpu"]
    mounts = {m["mountPath"] for m in c["volumeMounts"]}
    assert base()["ConfigMap"]["data"]["FOODCARE_VAR_DIR"] in mounts
    ann = dep["spec"]["template"]["metadata"]["annotations"]
    assert ann["prometheus.io/path"] == "/metrics" and ann["prometheus.io/port"] == str(c["ports"][0]["containerPort"])


def test_configmap_only_sets_settings_the_app_reads():
    src = (ROOT / "backend" / "app" / "config.py").read_text()
    for key in base()["ConfigMap"]["data"]:
        assert key == "HOME" or f'"{key}"' in src, key
    assert base()["ConfigMap"]["data"]["FOODCARE_BIND_HOST"] == "0.0.0.0"
    assert config.Settings().bind_host == "127.0.0.1"  # a laptop run stays local by default


def test_network_policy_allows_no_general_internet_egress():
    egress = base()["NetworkPolicy"]["spec"]["egress"]
    for rule in egress:
        for peer in rule["to"]:
            assert "ipBlock" not in peer  # only DNS and the labelled local-model namespace


def test_overlays_pick_a_storage_class_per_cloud():
    for cloud, sc in (("gke", "standard-rwo"), ("aks", "managed-csi")):
        patch = yaml.safe_load(docs(K8S / "overlays" / cloud / "kustomization.yaml")[0]["patches"][0]["patch"])
        assert patch[0]["value"] == sc


def test_dashboard_queries_only_metrics_the_app_exports(platform):
    config.configure(metrics_enabled=True)
    from app.main import app

    text = TestClient(app).get("/metrics").text
    exported = set(re.findall(r"^# TYPE (\S+)", text, re.M))
    dash = json.loads((K8S / "monitoring" / "grafana-dashboard.json").read_text())
    used = {m for p in dash["panels"] for t in p["targets"] for m in re.findall(r"foodcare_[a-z_]+", t["expr"])}
    used = {re.sub(r"_(bucket|sum|count)$", "", m) for m in used}
    assert used and used <= exported, used - exported
