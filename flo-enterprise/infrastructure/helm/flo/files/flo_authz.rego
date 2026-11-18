# FLO authorization policy (Rego v1). Mirrors governance/policy.py exactly; data comes from the YAML bundle
# (exported to data.json by `python -m governance.opa export`). Parity is verified by tests/security/test_opa_parity.py.
package flo.authz

levels := data.flo.abac.classification_levels

default allow := false

prohibited if input.action in data.flo.rbac.prohibited

perms contains p if {
	some r in input.principal.roles
	some p in data.flo.rbac.roles[r]
}

action_matches(pattern, _) if pattern == "*"

action_matches(pattern, action) if pattern == action

action_matches(pattern, action) if {
	endswith(pattern, ":*")
	split(action, ":")[0] == trim_suffix(pattern, ":*")
}

rbac_granted if {
	some p in perms
	action_matches(p, input.action)
}

has_resource if {
	is_object(input.resource)
	count(input.resource) > 0
}

tenant_mismatch if {
	has_resource
	input.resource.tenant_id != null
	input.resource.tenant_id != input.principal.tenant_id
}

# attribute lookup; undefined when missing or null (missing attributes fail closed)
attr(path) := v if {
	v := object.get(input, split(path, "."), null)
	v != null
}

rhs(c) := attr(c.ref) if c.ref

rhs(c) := c.value if not c.ref

leaf(c) if {
	c.op == "present"
	attr(c.attr)
}

leaf(c) if {
	c.op == "eq"
	attr(c.attr) == rhs(c)
}

leaf(c) if {
	c.op == "neq"
	l := attr(c.attr)
	r := rhs(c)
	l != r
}

leaf(c) if {
	c.op == "in"
	l := attr(c.attr)
	some x in rhs(c)
	x == l
}

leaf(c) if {
	c.op == "contains_any"
	some x in attr(c.attr)
	some y in rhs(c)
	x == y
}

leaf(c) if {
	c.op == "lte_level"
	levels[attr(c.attr)] <= levels[rhs(c)]
}

l1(c) if {
	c.op
	leaf(c)
}

l1(c) if {
	some x in c.any
	leaf(x)
}

l1(c) if {
	c.all
	every x in c.all {
		leaf(x)
	}
}

l2(c) if l1(c)

l2(c) if {
	some x in c.any
	l1(x)
}

l2(c) if {
	c.all
	every x in c.all {
		l1(x)
	}
}

applicable(rule) if {
	some a in rule.actions
	action_matches(a, input.action)
	not rule.resource_types
}

applicable(rule) if {
	some a in rule.actions
	action_matches(a, input.action)
	input.resource.type in rule.resource_types
}

abac_failures contains rule.id if {
	has_resource
	some rule in data.flo.abac.rules
	applicable(rule)
	not l2(rule.require)
}

denials := {"AUTHN-REQUIRED"} if {
	not input.principal
} else := {"PROHIBITED-ACTION"} if {
	prohibited
} else := {"RBAC-DENY-DEFAULT"} if {
	not rbac_granted
} else := {"TENANT-ISOLATION"} if {
	tenant_mismatch
} else := abac_failures

allow if count(denials) == 0

obligations contains "approval_required" if {
	allow
	data.flo.approvals.actions[input.action]
}

decision := {
	"allow": allow,
	"denials": denials,
	"obligations": obligations,
	"policy_version": data.flo.version,
}
