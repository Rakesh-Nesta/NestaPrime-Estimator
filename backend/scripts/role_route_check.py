"""Amendment 58 (Section 61) item 11: check every gated route against every role.

Reads the Director's "who can do what" table (`GET /role-permissions`, generated from the live route table)
and then calls each route as each of the six roles. A role the table admits must NOT be answered 401 or 403
(anything else -- 200, 400, 404, 422 -- means the gate let it through to the route's own logic); a role the
table does not admit must be answered exactly 403. It also checks that anonymous calls to every route answer
401 and that a route needing only a sign-in admits all six roles.

RUN THIS ONLY AGAINST A LOCAL OR TEST COPY. Routes are called with a nil UUID in place of every id and an
empty JSON body, which is harmless on a real database in practice, but a checker that calls every write route
as every role has no business near production data.

    python scripts/role_route_check.py --base http://127.0.0.1:8000 --director director@nestaprime.local \
        --user pm=pm@nestaprime.local --user sales=sales@nestaprime.local ... --password 'TestPass!1'

Exit status 0 = the table and the server agree everywhere; 1 = mismatches (listed); 2 = could not run.
"""

import argparse
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

NIL_UUID = "00000000-0000-0000-0000-000000000000"


def call(base: str, method: str, path: str, token: str | None) -> int:
    url = base.rstrip("/") + re.sub(r"\{[^}]+\}", NIL_UUID, path)
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = b"{}" if method in ("POST", "PUT", "PATCH") else None
    request = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            response.read()
            return response.status
    except urllib.error.HTTPError as error:
        error.read()
        return error.code


def sign_in(base: str, email: str, password: str) -> str:
    body = urllib.parse.urlencode({"username": email, "password": password}).encode()
    request = urllib.request.Request(base.rstrip("/") + "/auth/login", data=body, method="POST")
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)["access_token"]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:8000")
    parser.add_argument("--director", required=True, help="a Director's email (reads the role table)")
    parser.add_argument("--user", action="append", default=[], help="role=email, one per role to check")
    parser.add_argument("--password", required=True, help="the password all these test accounts share")
    args = parser.parse_args()

    try:
        director_token = sign_in(args.base, args.director, args.password)
        tokens = {"director": director_token}
        for pair in args.user:
            role, email = pair.split("=", 1)
            tokens[role] = sign_in(args.base, email, args.password)
        request = urllib.request.Request(
            args.base.rstrip("/") + "/role-permissions", headers={"Authorization": f"Bearer {director_token}"}
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            table = json.load(response)
    except Exception as error:  # noqa: BLE001 -- a script: say what failed and stop
        print(f"Could not run: {error}")
        return 2

    roles = [r for r in table["roles"] if r in tokens]
    missing = [r for r in table["roles"] if r not in tokens]
    mismatches: list[str] = []
    checked = {"admitted": 0, "refused": 0, "anonymous": 0, "signed_in_only": 0}

    for area in table["areas"]:
        for group in area["groups"]:
            for item in group["items"]:
                method, path = item["method"], item["path"]
                anonymous = call(args.base, method, path, None)
                checked["anonymous"] += 1
                if anonymous != 401:
                    mismatches.append(f"anonymous {method} {path}: expected 401, got {anonymous}")
                for role in roles:
                    status = call(args.base, method, path, tokens[role])
                    if role in group["roles"]:
                        checked["admitted"] += 1
                        if status in (401, 403):
                            mismatches.append(f"{role} {method} {path}: table admits it, server answered {status}")
                    else:
                        checked["refused"] += 1
                        if status != 403:
                            mismatches.append(f"{role} {method} {path}: table refuses it, server answered {status}")

    for item in table["ungated"]:
        if item["access"] != "any_signed_in":
            continue
        for role in roles:
            status = call(args.base, item["method"], item["path"], tokens[role])
            checked["signed_in_only"] += 1
            if status in (401, 403):
                mismatches.append(f"{role} {item['method']} {item['path']}: needs only a sign-in, server answered {status}")

    total_routes = table["gated_route_count"]
    print(f"Roles checked: {', '.join(roles)}" + (f" (not checked, no account given: {', '.join(missing)})" if missing else ""))
    print(f"Gated routes in the table: {total_routes}")
    print(
        f"Calls: {checked['admitted']} admitted, {checked['refused']} refused, "
        f"{checked['anonymous']} anonymous, {checked['signed_in_only']} sign-in-only"
    )
    if mismatches:
        print(f"\n{len(mismatches)} MISMATCH(ES):")
        for line in mismatches:
            print(" -", line)
        return 1
    print("\nThe role table and the server agree on every route.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
