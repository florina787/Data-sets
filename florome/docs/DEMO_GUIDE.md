# Demo guide (about 5 minutes)

The tenant is **Meridian Freight**, a fictional company; everything is synthetic. A second tenant, **Halcyon Retail**, exists to demonstrate isolation.

1. **Overview.** One open incident, one verified (simulated) connection. The copilot layer reports Project B live or unavailable based on a real call.
2. **Nervous System.** Every node is red. Note that customer-portal is unaffected.
3. **RCA** (acting as operator). Run the investigation and read the conclusion: H3 is confirmed, and the red herrings H1, H2, H4 and H5 are disproven. Click an evidence node to see the raw payload and "hash verified".
4. **Actions.** Generate the plan. The 5 steps show operation, risk, rollback and permission.
   * Try **Approve** as the operator: a policy error is shown.
   * Switch to **demo approver**, then approve.
   * Switch back to **demo operator**, then execute.
   * Validation lists every metric back within threshold, plus "report generated".
5. **Nervous System** again: everything is healthy and the incident overlay is cleared.
6. **Integrations** (acting as admin). Discover `sandbox-ops`, then invoke `get_service_status`. The platform tiles show exactly what is built and what is planned.
7. **Governance.** The audit chain is verified. Activate the emergency stop and try to execute a new approved plan: it is refused (HTTP 423).

To reset, restart the API (demo tenants are re-seeded) or call `POST /api/v1/demo/reset` as an admin.
