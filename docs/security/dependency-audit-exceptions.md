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
  `ecdsa`, `rsa` or `pyasn1`; python-jose was removed.
- **Do not re-add** an ignore for it. A new exception needs the same bar as before: no fix, not reachable here, written down
  here first.

### What was verified, kept separate (2026-10-06)

1. **Clean requirements audit.** `pip-audit -r backend/requirements.txt` with **no** `--ignore-vuln` (a fresh Python 3.12
   resolution) reports no known vulnerabilities. CI's `dependency-audit` job runs the same command with no ignore.
2. **Confirmed absence.** `python-jose`, `ecdsa`, `rsa` and `pyasn1` are not installed in a fresh Python 3.12 virtual
   environment built from `requirements.txt`, nor in the image built from the repository `Dockerfile`.
3. **The as-built image does NOT audit clean.** Auditing the image's installed packages without any ignore reports the base
   image's bundled **`pip 25.0.1`** (the Python base image's installer; it is not in `requirements.txt`): 12 reported
   entries covering **6 unique advisories** (PYSEC-2026-196, -1795, -1796, -2875, -2876, -3721; fixed in pip 25.3 to
   26.2; the repeats are the same advisory listed more than once, one with two fix-version spellings). The image is not
   clean. **Image remediation (the `Dockerfile` / pip) is outstanding and was not part of this change**; CI does not audit
   the image.
4. **Clean only after upgrading pip in the verification environment.** In a fresh virtual environment, after
   `pip install --upgrade pip` (to 26.2.1, which CI also does before auditing), the audit of the installed environment is
   clean, and all 51 other installed distributions audit clean. This describes that verification environment, **not** the
   image.

The retirement of the `ecdsa` exception rests on items 1 and 2: `ecdsa` is absent from the dependency graph and the
requirements audit is clean without an ignore. Items 3 and 4 do not change that; they are a separate, still-open image
tooling finding.
