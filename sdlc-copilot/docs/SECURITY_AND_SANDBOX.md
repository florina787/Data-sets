# Security and sandbox

## Execution isolation

**No container runtime is used.** The build environment had a Docker client but no daemon. The honest fallback is:

* Only **trusted, seeded fixture patches** (`fixtures/patches/*.patch`) are ever applied and executed. Live-generated patches are never executed; LIVE runs stop before implementation.
* Tool processes run through `tools/runner.py`:
  * a fixed argv, with only the platform's Python interpreter and `git` allowed;
  * a working directory that must resolve inside `var/`;
  * a scrubbed environment (PATH, locale, PYTHONHASHSEED) with HOME set to a per-run directory, so the developer's home directory is never used;
  * names containing KEY, TOKEN or SECRET are refused;
  * a new session or process group, killed on timeout (default 180 s);
  * `RLIMIT_CPU` 300 s and `RLIMIT_FSIZE` 200 MB on POSIX;
  * output capped at 200 kB.
* Tests run against an exported copy of the commit (`git archive`, with members validated against path escape and links), never against the live worktree.
* The protected acceptance tests are copied from the platform's fixture store and hash-checked against the plan frozen at requirement approval. Patches cannot touch tests: only `storefront/` is editable.

For arbitrary generated code, run each test execution in a container with no network, a read-only root, resource limits and only the run directory mounted. This is listed in [PRODUCTION_GAPS.md](PRODUCTION_GAPS.md).

## Authentication and authorization

* Five local demo accounts with PBKDF2-SHA256 password hashes (120k iterations) and random bearer tokens, stored hashed with a 12 h expiry. **This is not enterprise SSO.**
* Every mutating endpoint checks the role server-side (`auth.PERMISSIONS`). Rejected attempts are audited with `outcome = rejected`. The UI only disables buttons as a hint and lets you try an action, so you can see the server reject it.
* Separation of duties: engineers cannot approve releases, and only release approvers can approve, deploy or roll back.
* Approvals bind to the exact revision and manifest SHA-256. They are unique per release, and a new commit invalidates them.

## Data handling

* All data is synthetic. Customer identities are fixtures (`cust-*-demo` tokens). The payment processor is a mock (`tok_demo_ok` / `tok_demo_decline`).
* Audit and evidence tables are only ever appended to through the application. SQLite is not tamper-proof, and no cryptographic integrity is claimed.
* `ANTHROPIC_API_KEY` is read only by the backend (LIVE mode) and is never passed to tool or storefront processes.

## Prompt-injection posture

Briefs, documents and code comments are untrusted data. Retrieval quotes them as evidence. LIVE prompts wrap them in `<untrusted_*>` tags with an instruction not to follow embedded instructions. Model output only becomes records after schema validation, and is never executed.
