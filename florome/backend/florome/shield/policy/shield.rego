# Florome Shield authorization policy, evaluated by OPA as a second, independent engine.
# Deny by default. Both this policy and the built-in table must allow an action.
package florome.shield

import rego.v1

default allow := false

permission := {
	"repository.register": "shield:manage",
	"repository.ingest": "shield:research",
	"repository.scan": "shield:research",
	"hypothesis.verify": "shield:verify",
	"patch.generate": "shield:research",
	"patch.review": "shield:review",
	"containment.run": "shield:verify",
	"mcp.pin": "mcp:manage",
	"mcp.revoke": "mcp:manage",
	"evaluation.run": "shield:verify",
}

# Actions that execute code or change state are blocked by the tenant emergency stop.
executing := {"hypothesis.verify", "containment.run", "evaluation.run", "patch.generate"}

allow if {
	required := permission[input.action]
	required in input.principal.permissions
	not blocked_by_emergency_stop
	not out_of_scope
	not self_review
}

blocked_by_emergency_stop if {
	input.action in executing
	input.tenant.emergency_stop
}

out_of_scope if {
	input.resource.requires_scope
	not input.resource.in_authorized_scope
}

self_review if {
	input.action == "patch.review"
	input.resource.requested_by == input.principal.user_id
}
