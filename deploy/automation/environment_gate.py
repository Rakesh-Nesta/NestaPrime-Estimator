"""No manual fallback: unknown/missing protections are deployment blockers."""
from eligibility import api

def validate_environment(env, rules):
    review = [rule for rule in env["protection_rules"] if rule["type"] == "required_reviewers"]
    assert len(review) == 1 and review[0]["reviewers"] and review[0]["prevent_self_review"]
    assert env.get("can_admins_bypass") is False, "Unverifiable/allowed bypass blocks deployment"
    policy = env["deployment_branch_policy"]
    assert policy and policy["custom_branch_policies"] and not policy["protected_branches"]
    assert len(rules) == 1 and rules[0]["name"] == "main" and rules[0]["type"] == "branch"
    assert all(item["type"] == "User" for item in review[0]["reviewers"]), "Only explicitly pinned individual reviewers are supported"
    return {item["reviewer"]["id"] for item in review[0]["reviewers"]}


def validate_approval(reviews, env_id, actor_id, permitted_reviewers):
    assert permitted_reviewers, "Explicit independent individual reviewers required"
    matching = [review for review in reviews if any(env["id"] == env_id for env in review["environments"])]
    assert len(matching) == 1 and matching[0]["state"] == "approved", "Missing/ambiguous production approval history"
    reviewer = matching[-1]["user"]["id"]
    assert reviewer != actor_id and reviewer in permitted_reviewers, "Self-review or unauthorized/bypass reviewer"


if __name__ == "__main__":
    validate_environment(api("/environments/production"), api("/environments/production/deployment-branch-policies")["branch_policies"])
