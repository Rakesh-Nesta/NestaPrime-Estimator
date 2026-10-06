# Dependency audit exceptions

`pip-audit` and `npm audit --omit=dev` run on every PR (`.github/workflows/backend-ci.yml`, job
`dependency-audit`; Amendment 58, Section 61). An advisory may be ignored **only** when there is no fix and
the flaw is not reachable in this app, and it is written down here first.

## Current exceptions: none

No advisory is ignored. `pip-audit -r requirements.txt` runs with no `--ignore-vuln`.

## Retired: PYSEC-2026-1325 -- `ecdsa` 0.19.2 (found 26 September 2026, retired with the JWT migration)

- **What it was:** a Minerva timing side channel in python-ecdsa's ECDSA **signing**. `ecdsa` was only present as a
  dependency of `python-jose`, which this app used for the sign-in token (HS256 only, so the flaw was never reachable).
- **Why it is gone:** the token library is now `PyJWT[crypto]` (`backend/requirements.txt`), which does not depend on
  `ecdsa`, `rsa` or `pyasn1`; python-jose was removed. Verified on a fresh Python 3.12 environment and a fresh image: those
  packages are absent and an unsuppressed `pip-audit` of the installed graph and of `requirements.txt` is clean.
- **Do not re-add** an ignore for it. A new exception needs the same bar as before: no fix, not reachable here, written down
  here first.
