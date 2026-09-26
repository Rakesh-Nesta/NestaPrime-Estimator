# Dependency audit exceptions

`pip-audit` and `npm audit --omit=dev` run on every PR (`.github/workflows/backend-ci.yml`, job
`dependency-audit`; Amendment 58, Section 61). An advisory may be ignored **only** when there is no fix and
the flaw is not reachable in this app, and it is written down here first.

## PYSEC-2026-1325 -- `ecdsa` 0.19.2 (found 26 September 2026)

- **What it is:** a Minerva timing side channel in python-ecdsa's ECDSA **signing** (P-256): timing many
  signatures can leak the private key. Verification is unaffected. The project treats side channels as out
  of scope and plans no fix.
- **Why it is here:** `python-jose` (used for the sign-in token) lists `ecdsa` as a dependency.
- **Why it is not reachable:** this app signs and verifies its tokens with **HS256** (a shared-secret HMAC,
  `backend/app/core/security.py`, `ALGORITHM = "HS256"`). No ECDSA key exists and nothing calls ECDSA signing.
- **What would remove it:** replacing `python-jose` with PyJWT, which does not depend on `ecdsa`. Not done
  here (it changes the token library); worth doing in a later dependency pass.
- **Review:** revisit when `ecdsa` publishes a fix, or if the token algorithm ever changes from HS256.
