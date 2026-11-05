package flo.authz_test

import data.flo.authz

advisor := {"user_id": "u-advisor", "tenant_id": "t-flo", "roles": ["wealth_advisor"], "advisor_id": "A-001", "clearance": "confidential", "business_unit": "private_wealth"}

test_advisor_reads_assigned_client if {
	authz.allow with input as {"principal": advisor, "action": "client:read", "resource": {"type": "client", "id": "C-1", "tenant_id": "t-flo", "advisor_id": "A-001", "classification": "confidential"}, "context": {}}
}

test_advisor_denied_unassigned_client if {
	d := authz.decision with input as {"principal": advisor, "action": "client:read", "resource": {"type": "client", "id": "C-2", "tenant_id": "t-flo", "advisor_id": "A-009", "classification": "confidential"}, "context": {}}
	not d.allow
	"ABAC-CLIENT-ASSIGNMENT" in d.denials
}

test_cross_tenant_denied if {
	d := authz.decision with input as {"principal": advisor, "action": "client:read", "resource": {"type": "client", "id": "C-3", "tenant_id": "t-nw", "advisor_id": "A-001", "classification": "confidential"}, "context": {}}
	d.denials == {"TENANT-ISOLATION"}
}

test_trading_prohibited if {
	d := authz.decision with input as {"principal": advisor, "action": "trade:execute", "resource": null, "context": {}}
	d.denials == {"PROHIBITED-ACTION"}
}

test_default_deny if {
	d := authz.decision with input as {"principal": advisor, "action": "aiops:manage", "resource": null, "context": {}}
	d.denials == {"RBAC-DENY-DEFAULT"}
}

test_send_requires_approval if {
	d := authz.decision with input as {"principal": advisor, "action": "comms:send", "resource": {"type": "client", "id": "C-1", "tenant_id": "t-flo", "advisor_id": "A-001", "classification": "confidential"}, "context": {}}
	d.allow
	"approval_required" in d.obligations
}

test_advisor_denied_restricted_classification if {
	d := authz.decision with input as {"principal": advisor, "action": "client:read", "resource": {"type": "client", "id": "C-1", "tenant_id": "t-flo", "advisor_id": "A-001", "classification": "restricted"}, "context": {}}
	d.denials == {"ABAC-CLASSIFICATION"}
}
