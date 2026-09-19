# Section 24 — Draft Specifications for Director Approval

**Date: 19 September 2026 | Status: DRAFT — specification only, per Annexure 2's Change
Process (Part 1): "Director approves → complete amended specification prepared. Only
then implement." Implementation starts once approved below.**

Scope note: self-identified during the same 19 September proactive gap audit as Section
23 — a real authentication gap, spot-verified against the live code before being
registered as Amendment No. 18.

---

## Amendment No. 18 — Login Rate Limiting / Lockout

**Registered scope (Annexure 2, §Amendment 18):** `POST /auth/login` has no attempt
counter, delay, or lockout on repeated failed password checks — unlimited guesses are
possible against any known email address.

### Current state (verified against `backend/app/api/auth.py`, full file read)

```python
@router.post("/login", response_model=TokenOut)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == form_data.username).first()
    if (
        user is None
        or not user.is_active
        or not verify_password(form_data.password, user.hashed_password)
    ):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    token = create_access_token(subject=user.email, role=user.role.value)
    return TokenOut(access_token=token)
```

No counter, no delay, no lockout anywhere in this function or elsewhere in the repo —
confirmed by reading the whole file (67 lines) and checking `requirements.txt` for any
rate-limiting package (`slowapi`, or similar): none present. Production runs two
gunicorn/uvicorn workers (`Dockerfile`: `--workers 2`), so any fix that only tracks state
in one process's memory would miss roughly half of a real attacker's requests — the
existing `User` model (`backend/app/models/user.py`) is the only place in this app that
already persists per-user state visible to every worker (`is_active`,
`must_change_password`), which this should follow rather than introducing a new
dependency (Redis, an in-memory limiter) for a single small self-hosted deployment.

### Proposed spec

1. **Two new columns on `User`:** `failed_login_attempts: int` (default 0) and
   `locked_until: datetime | None` (default `None`) — same persistence pattern as
   `must_change_password`, a normal Alembic migration.
2. **On a failed login** (wrong password, or unknown email — see Decision 1 below):
   increment `failed_login_attempts`; once it reaches a threshold (proposed: 5), set
   `locked_until = now + 15 minutes` and reset the counter to 0. Every failed attempt
   still returns the same generic `401 "Incorrect email or password"` — no different
   error message that would let an attacker distinguish "wrong password" from "account
   locked," which would itself leak which emails are valid accounts.
3. **On a login attempt while `locked_until` is in the future:** same generic 401,
   regardless of whether the password supplied is actually correct — a locked account
   stays locked for the full window even if the real owner tries again immediately with
   the right password, which is the whole point of a lockout.
4. **On a successful login:** reset `failed_login_attempts` to 0 and `locked_until` to
   `None`.
5. **No change to `/auth/change-password` or any other endpoint** — this is scoped to
   `/auth/login` only, where the actual credential-guessing surface is.
6. **No new dependency** — plain SQLAlchemy columns and a `datetime` comparison, same
   toolkit already used everywhere else in this file.

**Acceptance criteria:** 5 consecutive failed logins against one email lock that account
for 15 minutes, during which even the correct password is rejected with the same generic
401; a 6th distinct email is unaffected (lockout is per-account, not global); after the
window elapses, a correct password succeeds normally and the counters reset; a successful
login at any point before the threshold resets the counter; existing auth tests
(`backend/tests/test_auth.py` or equivalent) continue to pass unchanged for the
already-covered success/failure paths.

### Open decisions — need Director input before implementation

1. **Does an unknown email count toward lockout?** Proposed: no — only count failed
   attempts against a real, existing account (looked up by email first; if `user is
   None`, return the generic 401 without touching any counter). Counting unknown emails
   would let an attacker lock out arbitrary real accounts just by guessing emails paired
   with an already-locked one's timing; scoping to real accounts only avoids that
   denial-of-service angle. Confirm or specify otherwise.
2. **Threshold and lockout duration** — proposed: 5 attempts, 15-minute lockout. Confirm
   or supply different numbers.
3. **Should a lockout be visible/reversible by a Director** (e.g. an admin "unlock"
   action on the Users screen), or does the 15-minute window alone suffice? Proposed:
   out of scope for this pass — the timed lockout alone closes the gap; a manual-unlock
   admin control can be a future small addition if it turns out to matter in practice.

---

## Approval

Amendment 18 (login rate limiting / lockout): ☑ Approved — "approve as proposed, all
decisions" (19 September 2026)

Decision 1 (unknown emails don't count toward lockout): ☑ Resolved as proposed.
Decision 2 (5 attempts / 15-minute lockout): ☑ Resolved as proposed.
Decision 3 (no admin-unlock control in this pass): ☑ Resolved as proposed.

Director Name: ______________________ Signature: ______________________ Date: ____________

Prepared by: R. Patni (with AI development assistance) | Date: 19 September 2026
