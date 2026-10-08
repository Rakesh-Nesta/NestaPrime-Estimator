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
3. **The image as built BEFORE the image remediation did NOT audit clean.** Auditing its installed packages without any
   ignore reported the base image's bundled **`pip 25.0.1`** (the Python base image's installer; not in
   `requirements.txt`): 12 reported entries covering **6 unique advisories** (PYSEC-2026-196, -1795, -1796, -2875, -2876,
   -3721; fixed in pip 25.3 to 26.2; the repeats are the same advisory listed more than once, one with two fix-version
   spellings). That evidence is preserved and unchanged.
4. **Clean after upgrading pip in a verification environment.** In a fresh virtual environment, after
   `pip install --upgrade pip` (to 26.2.1), the audit of the installed environment is clean, and all 51 other installed
   distributions audit clean. This described that environment, **not** the image.
5. **Image remediation (this change).** The `Dockerfile` now installs the explicitly pinned **`pip==26.2.1`** *before* the
   application dependencies. Every advisory in item 3 is fixed in pip >= 26.2.0 (OSV and the GitHub Advisory Database agree;
   the highest fixed version is 26.2.0 for PYSEC-2026-3721 / CVE-2026-13346); 26.2.1 is the newest release (2026-08-04, not
   yanked, Python >= 3.10) and only fixes a keyring regression on top of 26.2. A fresh image built with `--no-cache` from
   that source was verified as a whole: pip 26.2.1 is the only pip distribution, `pip check` is clean, PyJWT and cryptography
   are present, the obsolete packages are absent, and the **complete installed inventory (52 distributions, including pip)
   audits clean with no ignore flags by two methods that leave the audited image unchanged** (the image's own site-packages
   audited by a read-only mounted external tool, and the frozen inventory audited in a separate container). The exact image
   ID, build command, inventory and raw results are recorded with the review evidence for the PR, not here.

**Limits of that audit:** it covers Python distributions only. Operating-system packages in the image (Debian base,
`clamdscan`) are not covered by `pip-audit`. CI's `dependency-audit` job audits `requirements.txt`, not the built image, so
this image result is a point-in-time verification; running the same inventory audit on each image build in CI would be a
separate, proposed follow-up (not part of this change).

The retirement of the `ecdsa` exception rests on items 1 and 2.
