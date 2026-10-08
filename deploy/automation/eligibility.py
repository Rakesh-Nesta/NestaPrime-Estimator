"""Fail closed: exact latest main push CI run, all three required jobs successful."""
import json
import os
import re
import urllib.request

REQUIRED = {"test", "docker-build", "dependency-audit"}


def validate(run, jobs, sha, repo):
    assert re.fullmatch(r"[0-9a-f]{40}", sha), "Use a full commit SHA"
    assert run["head_sha"] == sha and run["head_branch"] == "main"
    assert run["event"] == "push" and run["head_repository"]["full_name"] == repo
    assert run["status"] == "completed" and run["conclusion"] == "success"
    found = {j["name"]: j for j in jobs}
    assert REQUIRED <= found.keys(), "Required CI jobs missing"
    assert all(found[n]["status"] == "completed" and found[n]["conclusion"] == "success" for n in REQUIRED)


def api(path):
    request = urllib.request.Request("https://api.github.com/repos/" + os.environ["GITHUB_REPOSITORY"] + path,
        headers={"Authorization": "Bearer " + os.environ["GH_TOKEN"], "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def eligible(sha, get=api):
    assert re.fullmatch(r"[0-9a-f]{40}", sha)
    assert get("/git/ref/heads/main")["object"]["sha"] == sha, "Release must be the current main tip"
    runs = get("/actions/workflows/backend-ci.yml/runs?event=push&branch=main&head_sha=" + sha)["workflow_runs"]
    assert runs, "No main push CI run for commit"
    run = max(runs, key=lambda r: r["id"])
    jobs = get(f'/actions/runs/{run["id"]}/attempts/{run["run_attempt"]}/jobs?per_page=100')["jobs"]
    validate(run, jobs, sha, os.environ["GITHUB_REPOSITORY"])
    return {"commit": sha, "ci_run": run["id"], "ci_attempt": run["run_attempt"], "required_jobs": sorted(REQUIRED)}


if __name__ == "__main__":
    sha = os.environ["RELEASE_SHA"]
    assert sha == os.environ["GITHUB_SHA"], "Dispatch workflow must execute at the selected main tip"
    print(json.dumps(eligible(sha)))
