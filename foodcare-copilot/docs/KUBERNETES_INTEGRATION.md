# Kubernetes integration (read-only service health)

**Status in this repository: adapter built and contract-tested against a mock API server. The
default deployment does not call the Kubernetes API.**

## What Jerry can read

`connectors.kubernetes_health()` issues only two `GET` requests per allowlisted namespace:

* `/apis/apps/v1/namespaces/{ns}/deployments` → name, desired, ready and updated replicas
* `/api/v1/namespaces/{ns}/pods` → name, phase, restart count

Nothing else leaves the function: no environment variables, annotations, images, logs, events or
secrets. There is no exec, port-forward, scale, delete or apply, and no free-form `kubectl` from
conversations. Containment that would pause a workload is preview/dry-run only (see
`DEFENSE_COMMAND.md`).

## Enable it

1. Add the optional component to your overlay:

   ```yaml
   components:
     - ../../components/jerry-readonly-rbac
   ```

   It creates a namespaced `Role` with `get`/`list` on `deployments` and `pods` only, binds it to
   the `foodcare-copilot` ServiceAccount, and turns on the service-account token (the base keeps it
   off). Never bind Jerry to `cluster-admin` or any ClusterRole.
2. Allow egress from the pod to your cluster's API endpoint. The base NetworkPolicy blocks it;
   add an `ipBlock` rule for the control-plane address on 443/6443.
3. Set `FOODCARE_K8S_NAMESPACES` (comma-separated, default `foodcare`). Only these namespaces can be queried.

Outside a cluster, set `FOODCARE_K8S_API_URL`, `FOODCARE_K8S_TOKEN` and optionally `FOODCARE_K8S_CA`.

## Related

* Deployment manifests: `deploy/k8s/` (base, AKS/GKE overlays, ServiceMonitor component).
* The app also publishes Prometheus metrics at `/metrics` for your monitoring stack.

Tests: `test_kubernetes_is_read_only_allowlisted_and_drops_sensitive_fields` in
`backend/tests/test_command.py` (mock API server returns secrets and env vars; they never appear).
