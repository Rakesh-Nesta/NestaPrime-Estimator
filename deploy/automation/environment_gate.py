"""Refuse an absent or unprotected environment; never auto-create one."""
from eligibility import api

env = api("/environments/production")
review = [rule for rule in env["protection_rules"] if rule["type"] == "required_reviewers"]
assert len(review) == 1 and review[0]["reviewers"] and review[0]["prevent_self_review"]
# Administrator bypass is a mandatory UI setup check; the public REST
# environment schema does not expose that setting reliably.
policy = env["deployment_branch_policy"]
assert policy and policy["custom_branch_policies"]
rules = api("/environments/production/deployment-branch-policies")["branch_policies"]
assert len(rules) == 1 and rules[0]["name"] == "main" and rules[0]["type"] == "branch"
