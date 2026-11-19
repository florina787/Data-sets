# Open-source security research and technology selection

**Method.** Repository facts (license, last push, archived, stars, language) come from the GitHub search API on 2026-11-19. Licences were double-checked against the LICENSE file where GitHub's label was ambiguous. "Ran here" means the tool was actually executed in this environment against a test input.

| Repository | Licence | Last push | Stars | Ran here | Decision |
|---|---|---|---|---|---|
| knostic/OpenAnt | Apache-2.0 | 2026-11-18 | 813 | No | Evaluate later: LLM-driven, needs a hosted model key |
| 0sec-labs/0security | Apache-2.0 | 2026-11-18 | 1,505 | No | Evaluate later (TypeScript, LLM-driven) |
| protectai/vulnhuntr | **AGPL-3.0** | 2025-02-06 (stale) | 2,826 | No | **Rejected:** AGPL obligations and no activity in 21 months |
| PanshiAgent/Panshi-Security-Agent | **none** | 2026-09-17 | 1 | No | **Rejected:** no licence means no right to use |
| opengrep/opengrep | LGPL-2.1 | 2026-11-18 | 3,357 | **Yes, v1.33.1** | **Adopted** as the primary pattern engine, run as a separate process with Florome-authored rules |
| semgrep/semgrep | LGPL-2.1 | 2026-11-19 | 17,812 | Yes (1.79) | Not adopted: Opengrep is the open fork without registry/login coupling |
| github/codeql | MIT (queries) | 2026-11-18 | 10,384 | No | **Not adopted:** the CodeQL CLI's own licence restricts use on non-open-source code |
| tree-sitter/tree-sitter | MIT | 2026-11-18 | 27,505 | **Yes, py 0.26.1** | **Adopted** for parsing (Python and JavaScript grammars) |
| PyCQA Bandit (added) | Apache-2.0 | n/a | n/a | **Yes, 1.9.4** | **Adopted:** Python AST security checks |
| google/oss-fuzz | Apache-2.0 | 2026-11-18 | 12,974 | No | Later: Docker infrastructure for C/C++ projects |
| AFLplusplus/AFLplusplus | **AGPL-3.0** (verified in LICENSE) | 2026-11-17 | 6,891 | No | Not adopted now: C/C++ targets, AGPL; would run isolated if added |
| google/clusterfuzz | Apache-2.0 | 2026-11-18 | 5,639 | No | Later (GCP-oriented infrastructure) |
| langchain-ai/langgraph | MIT | 2026-11-19 | 45,133 | Yes (Project B) | Not needed: Shield's supervisor is deterministic code |
| OpenHands/OpenHands (moved from All-Hands-AI) | MIT | 2026-11-19 | 93,778 | No | Later, for LLM patch agents |
| microsoft/PyRIT | MIT | 2026-11-19 | 4,941 | No | Its attack categories informed Shield's adversarial corpus. It targets LLM endpoints, and Florome's controls are deterministic |
| NVIDIA/garak | Apache-2.0 | 2026-11-18 | 10,093 | No | Same as PyRIT |
| promptfoo/promptfoo | MIT | 2026-11-18 | 27,434 | No | Same as PyRIT |
| ethz-spylab/agentdojo (moved from agentdojo/agentdojo) | MIT | 2026-06-02 | 1,054 | No | Same as PyRIT; its injection-task design inspired the corpus |
| wazuh/wazuh | Dual: GPLv2 and AGPL-3.0 engine (per LICENSE) | 2026-11-19 | 17,818 | No | Later, as an event source over its API (no code import) |
| falcosecurity/falco | Apache-2.0 | 2026-11-09 | 9,590 | No | Later: needs a kernel driver/eBPF, unavailable in this container |
| aquasecurity/trivy | Apache-2.0 | 2026-11-18 | 39,513 | **Yes, v0.76.2** | **Adopted** for dependency CVEs and secrets |
| open-policy-agent/opa | Apache-2.0 | 2026-11-18 | 12,492 | **Yes, v1.22.4** | **Adopted** as a second, independent policy engine for Shield actions |
| sunblaze-ucb/cybergym | Apache-2.0 | 2026-08-28 | 1,049 | No | Later: large Docker-based dataset; Shield ships its own labelled corpus first |

## Integration pattern

Every external tool runs as a **separate process** behind an adapter, with a timeout, its output parsed into Shield's normalised finding schema, and its version recorded on every finding. No GPL/AGPL/LGPL code is copied or linked into Florome. Binaries are not committed: `scripts/fetch_shield_tools.sh` downloads them, and adapters fail closed with a clear error when a binary is missing.

## Milestone plan

| # | Milestone | Scope delivered in this round |
|---|---|---|
| 1 | Control plane | Scope authorization (target allow-list), signed plans (HMAC), deny-by-default policy plus OPA cross-check, rate limits, quotas, emergency revocation |
| 2 | Code intelligence | Tree-sitter ingestion, symbols, imports, calls, routes, auth boundaries, sinks, with commit/file/line provenance |
| 3 | Vulnerability research | Opengrep/Bandit/Trivy adapters, normalised and deduplicated findings, graph-driven hypotheses |
| 4 | Cyber Range | Namespace-isolated verification runner with rlimits, empty env, no network, temporary copy |
| 5 | Adjudication and patching | Reproducibility-based adjudication, template patches, regression tests |
| 6 | AI/MCP security | Agent containment supervisor (audit hooks), MCP server manifest pin, revocation, adversarial corpus |
| 7 | Incident integration | Confirmed findings become Florome incidents |
| 8 | UI | Shield workspaces |
| 9 | Evaluation | Labelled-corpus benchmark comparing a scanner-only and a hybrid pipeline |
