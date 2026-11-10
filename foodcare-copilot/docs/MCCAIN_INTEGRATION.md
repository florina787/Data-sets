# Integrating Food Copilot into a large food manufacturer's platform (McCain Foods case study)

> **What this page is.** A research note on how McCain Foods' technology platform appears from
> public sources, and how this prototype would plug into a platform like it: Kubernetes
> deployment, system metrics and LLM token usage.
>
> **What it is not.** It is not based on inside knowledge, and it is not endorsed by McCain
> Foods. Nobody at McCain reviewed it. Every claim below comes from a public page (linked) and has
> a confidence label. The app itself carries no McCain branding.

---

## 1. Plain-language summary

| Question | Short answer | Confidence |
|---|---|---|
| Does McCain run Kubernetes? | Yes. Its DevSecOps job postings ask for hands-on Kubernetes skills. | **High** (several postings) |
| Which Kubernetes? | The postings name **GKE** (Google Kubernetes Engine) as preferred, together with **Helm** and **kubectl**. None of the postings we found names **AKS** (Azure). | **Medium** (job postings, not architecture documents) |
| Which cloud? | **More than one.** The same posting lists Azure as a must-have and GCP and AWS as well. Data and reporting roles mention Azure, Databricks and Power BI. | **Medium** |
| How are deployments run? | **GitOps** (Flux is named), with Terraform/Ansible for infrastructure and Jenkins, Azure DevOps, GitHub Actions or Bamboo for CI. | **Medium** |
| How is it monitored? | **Prometheus and Grafana**, with ELK and Splunk for logs. | **Medium** |
| What are the core business systems? | **SAP** (moving from ECC to S/4HANA, with SAP MDG for master data) and **OneStream** for finance consolidation. | **Medium–high** (job postings plus vendor case studies) |
| Is there AI on the plant floor already? | A vendor case study describes a "Digital Centerline" operator-recommendation tool that started at the Florenceville plant. We found **no public source** naming a computer-vision defect system on McCain lines. | **Low–medium** (vendor-reported) |

**The design choice that follows from this:** the integration does not bet on one cloud. It is
plain Kubernetes (Kustomize) with thin GKE and AKS overlays, it exposes metrics in the
Prometheus format, it ships a Grafana dashboard, and it ships a Flux example, because those are
the tools the postings name.

---

## 2. What we found, with sources

### 2.1 Platform and DevOps

- **DevSecOps Engineer, McCain Foods (Delhi listing).** Lists Docker and Kubernetes, with *"GKE
  preferred"*. Asks the candidate to *"support Kubernetes environments (GKE, Helm, kubectl)"*. Names
  Azure DevOps, Grafana/Prometheus, ELK/Splunk, Terraform/Ansible and Flux-style GitOps.
  Source: [builtindelhi.in/job/devsecops-engineer/8477231](https://builtindelhi.in/job/devsecops-engineer/8477231)
- **Azure DevSecOps Engineer, McCain Foods (Gurugram).** *"Must have experience in Kubernetes (GKE,
  Kubectl, Helm) and containers (Docker)"*, plus DevSecOps, task automation and GitOps.
  Source: [getmereferred.com listing](https://getmereferred.com/job-listing/azure-devsecops-engineer-mccain-foods-gurugram-2-to-5-years-experience-597f23ee-50cc-4169-b39d-1fa1422dfdd4)
- **Why this is only "medium" confidence.** A job posting describes skills a team wants. It does
  not show how production is built. AKS may well exist alongside GKE; we simply found no public
  evidence of it.

### 2.2 Enterprise data and business systems

- **SAP ECC → S/4HANA.** Postings describe a multi-year, multi-region S/4HANA programme with a
  system-integrator partner, and data cleansing in legacy ECC as a prerequisite.
  Sources: [S/4HANA Functional Project Manager](https://www.builtinchicago.org/job/s-4hana-functional-project-manager/9529930),
  [Project Manager, SAP S/4 Functional](https://www.builtinchicago.org/job/project-manager-sap-s4-functional/4817199),
  [Project Manager, S/4 Data](https://builtin.com/job/project-manager-s4-data/4419909)
- **SAP Master Data Governance (MDG).** Source: [SAP MDG Engineer](https://freehire.me/jobs/sap-master-data-governance-engineer-mccain-foods-so35v3k4)
- **SAP S/4HANA Investment Management (2022), with reporting on Azure and Power BI.** This comes
  from a third-party vendor directory.
  Source: [Apps Run The World](https://www.appsruntheworld.com/customers-database/customers/view/mccain-foods-limited-canada)
- **OneStream for financial consolidation** (moved off SAP BPC).
  Source: [OneStream case study (PDF)](https://www.performanceanalytics.com/wp-content/uploads/2024/04/McCainFood-Case-Study.pdf)
- **Data and AI roles mention Power BI, Databricks and Microsoft Copilot.**
  Sources: [Senior Product Owner, Data AI Analytics](https://builtin.com/job/senior-ai-engineer/4509422),
  [Forward Deployed Engineer, AI Strategist](https://builtin.com/job/forward-deployed-engineer-ai-strategist/8512655),
  [Product Owner, Digital Data Acquisition](https://builtintoronto.com/job/product-owner-digital-data-acquisition/4381090)

### 2.3 AI and analytics on the plant and the farm

- **Digital Centerline Management (TribalScale).** An operator tool that gives AI-driven
  recommendations from live and historical line data. It started at the Florenceville plant.
  The vendor reports a 70% drop in defect submissions; **we could not verify that figure
  independently**, and this repository does not reuse it.
  Source: [tribalscale.com/work/mccain](https://www.tribalscale.com/work/mccain)
- **Fiddlehead Technology.** McCain took a significant minority stake in 2021 to strengthen its
  analytics capability.
  Source: [McCain press release](https://www.mccain.com/information-centre/news/mccain-foods-bolsters-its-data-science-capabilities-with-investment-in-fiddlehead-technology/)
- **Ceres AI.** A grower pilot that improves field visibility across the North American potato
  supply. This concerns crop data, not factory vision.
  Source: [Consumer Goods Technology](https://consumergoods.com/mccain-foods-streamlines-agricultural-visibility-ai-tool)

### 2.4 What we could not find

- Any public architecture diagram, cluster count, service mesh, or ingress choice.
- Any confirmation of AKS, EKS or on-premises Kubernetes in production.
- Any computer-vision defect-detection system named on McCain production lines.
- Any statement about self-hosted LLMs, or about which model gateway is approved.

Each of these is a **question to ask the platform team**, not an assumption baked into the code.
See section 6.

---

## 3. How the integration fits that platform

```
              ┌──────────── plant / regional Kubernetes cluster (GKE · AKS · EKS · on-prem) ────────────┐
  operators   │  ingress / gateway ──► Service foodcare-copilot ──► Pod (1 replica, non-root, read-only FS) │
  & QA ──────►│                                         │                 │                               │
              │                                         │  /metrics       │ OpenAI-compatible HTTP         │
              │  Prometheus ◄── scrape (annotations or ServiceMonitor)    ▼                               │
              │      │                                         existing Qwen server (namespace labelled   │
              │      ▼                                         foodcare.io/llm-server=true). NOT shipped   │
              │  Grafana ◄── deploy/k8s/monitoring/grafana-dashboard.json   here, never downloaded.       │
              │                                                                                           │
              │  Flux ◄── watches git ──► deploy/k8s/overlays/<cloud>                                     │
              └───────────────────────────────────────────────────────────────────────────────────────────┘
```

| Platform piece (as advertised) | What this repo provides | File |
|---|---|---|
| Docker | Multi-stage image. Non-root (uid 10001). A `WITH_TORCH=0` lean build. An optional corporate CA passed as a BuildKit secret. | `Dockerfile` |
| Kubernetes (GKE preferred) | A Kustomize base, plus a GKE overlay (`standard-rwo` disks) | `deploy/k8s/base`, `deploy/k8s/overlays/gke` |
| Azure | An AKS overlay (`managed-csi` disks) | `deploy/k8s/overlays/aks` |
| Helm | **Not shipped yet.** Kustomize was chosen because it needs no extra tool (`kubectl apply -k`). Wrapping the base in a chart is straightforward if the platform team requires Helm. | — |
| Flux GitOps | A `GitRepository` and `Kustomization` example with a health check | `deploy/flux/foodcare-copilot.yaml` |
| Prometheus | `/metrics` in Prometheus text format, scrape annotations, and an optional `ServiceMonitor` component | `backend/app/observability.py`, `deploy/k8s/components/servicemonitor` |
| Grafana | A dashboard: tokens, LLM calls, p95 latency, 5xx, CPU, vision queue, agent runs, DB size | `deploy/k8s/monitoring/grafana-dashboard.json` |
| Security (DevSecOps) | runAsNonRoot, seccomp `RuntimeDefault`, all capabilities dropped, read-only root filesystem, no service-account token, and a NetworkPolicy whose egress allows DNS and the model namespace only. The namespace enforces Pod Security `restricted`. | `deploy/k8s/base/*` |
| SAP / Databricks / Power BI | **Not integrated.** The app's data sources are pluggable (see the Data Sources page); these would be future adapters, read-only first. | — |

### Deploying it

```bash
# 1. build and push the image to the cluster's registry
docker build -t <registry>/foodcare-copilot:0.1.0 .
docker push <registry>/foodcare-copilot:0.1.0

# 2. point the base at that registry (deploy/k8s/base/kustomization.yaml → images.newName)
#    and at the existing Qwen server (deploy/k8s/base/configmap.yaml → FOODCARE_LLM_BASE_URL / _MODEL)

# 3. label the namespaces the NetworkPolicy trusts
kubectl label namespace <ingress-ns>    foodcare.io/allow-ingress=true
kubectl label namespace <monitoring-ns> foodcare.io/monitoring=true
kubectl label namespace <qwen-ns>       foodcare.io/llm-server=true

# 4. apply (or let Flux do it)
kubectl apply -k deploy/k8s/overlays/gke      # or overlays/aks
```

If the model gateway needs a key:
`kubectl -n foodcare create secret generic foodcare-llm --from-literal=api-key=…`.
The Deployment marks it `optional`.

---

## 4. System metrics: what `/metrics` exposes

All metric names start with `foodcare_`. **Labels never contain usernames, prompts or answers.**
The test suite checks this.

| Metric | Type | Meaning |
|---|---|---|
| `foodcare_up`, `foodcare_uptime_seconds` | gauge | The backend is alive, and for how long |
| `foodcare_http_requests_total{method,route,status}` | counter | Requests per **route template** (e.g. `/api/inspections/{id}`), so cardinality stays bounded |
| `foodcare_http_request_duration_seconds` | histogram | Latency; feeds the p95 panel |
| `foodcare_process_cpu_percent`, `foodcare_process_resident_memory_bytes` | gauge | Backend process resources (psutil) |
| `foodcare_machine_cpu_percent`, `foodcare_machine_memory_percent` | gauge | Node-level view, as the container sees it |
| `foodcare_agent_runs_total{agent,status}`, `foodcare_tool_calls_total{tool,status}` | counter | Agent work, from the audit trail |
| `foodcare_vision_jobs_running/queued`, `foodcare_vision_jobs_rejected_total` | gauge / counter | Image inspection back-pressure |
| `foodcare_memory_db_bytes`, `foodcare_conversations` | gauge | Memory database growth |

Set `FOODCARE_METRICS_ENABLED=0` to turn the endpoint off (it then returns 404).

---

## 5. Token usage: how it is counted, and how it is not

Every call to the local model is written to the `llm_usage` table (migration 6). Each row holds
the time, model, purpose (`copilot.answer`, `delivery.brief_analysis`, `delivery.requirements`),
status (`ok`, `error`, `cancelled`, `invalid_output`), whether the call was a cache hit, the
latency, and the **prompt and completion token counts reported by the model server**.

- **Where the counts come from.** The request asks the server for them with
  `stream_options: {"include_usage": true}`. This is part of the OpenAI-compatible API, and vLLM,
  llama.cpp server, LM Studio and recent Ollama all support it. If a server does not report usage,
  the counts stay **empty**. The call is then counted under
  `foodcare_llm_calls_without_token_counts_total`. **We never estimate tokens from characters.**
  An estimate would look precise and be wrong.
- **Cache hits cost zero tokens.** They are recorded with `cached = 1` and no token counts.
- **There is no money column.** A self-hosted model has no per-token price, and inventing a
  "cost" figure would break this project's no-fabrication rule. To charge back, multiply the
  tokens by the platform team's own internal rate in Grafana.
- **Exported metrics:** `foodcare_llm_requests_total{model,purpose,status}`,
  `foodcare_llm_tokens_total{model,purpose,type=prompt|completion}`,
  `foodcare_llm_cache_hits_total`, `foodcare_llm_queue_depth`, `foodcare_llm_in_flight` and
  `foodcare_llm_configured`.
- **API:** `GET /api/llm/usage?days=30` returns totals, p50/p95 latency, usage per day and per
  purpose. Add `&mine=true` for the signed-in user's own calls. The Observability page in the UI
  draws this as a panel.
- **Turn off the usage request** with `FOODCARE_LLM_STREAM_USAGE=0`, for an old server that
  rejects `stream_options`.

---

## 6. Limits, and questions for the platform team

1. **It runs as a single replica, by design.** Memory and audit data live in SQLite on a
   ReadWriteOnce volume, so the Deployment uses `replicas: 1` and the `Recreate` strategy (two
   pods never write the same file). Scaling out needs a shared database such as Cloud SQL or Azure
   Database for PostgreSQL. That is a code change, not just a configuration change.
2. **Which model gateway is approved?** The app speaks plain OpenAI-compatible HTTP to an
   *existing* Qwen server. It does not ship, start or download a model.
3. **GKE, AKS or both, and which ingress?** Both overlays exist. TLS, the hostname and SSO (for
   example Entra ID via an auth proxy) belong to the cluster's ingress layer and are not
   configured here.
4. **Is Helm mandatory?** If yes, wrap `deploy/k8s/base` in a chart; the values map 1:1 to the
   ConfigMap.
5. **Do logs go to ELK or Splunk?** The app logs to stdout, so any cluster log shipper collects
   them. Structured JSON logging is not yet implemented.
6. **SAP and Databricks.** Read-only adapters would be the next step, each one behind the same
   approval gates the app already uses for consequential decisions.

The test `backend/tests/test_k8s_manifests.py` keeps all of this honest. It checks:

- the single-writer settings;
- the probes and the non-root security settings;
- that the NetworkPolicy has no `ipBlock` egress;
- the storage classes per cloud;
- that the ConfigMap only sets variables the app actually reads;
- that **every metric the Grafana dashboard queries is actually exported by `/metrics`**.
