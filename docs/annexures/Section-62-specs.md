# Section 62 — Amendment No. 59 Spec

## Amendment No. 59 — Sign-in and User Creation with a Mobile Number or an Email

### Registered scope
The Director's instruction (26 September 2026), in full: **"login benchmark admin-manager/PM- Users create with
mobile no or email both"**. It is terse, so this spec states how it was read, and the Director confirms or
corrects that reading when approving:

1. **A person's account can be created with a mobile number, an email, or both** -- at least one.
2. **They sign in with whichever they have** -- one box that accepts either.
3. **"admin-manager/PM" can create users.** The app has six roles and no "admin" or "manager": the proposal is
   **Director = admin** and **PM = manager**, with no new role. Today only the Director can create users.
4. **"Benchmark"** is read as "the way the reference product behaves" (the app has followed a CRM reference
   elsewhere), not a performance test. **If a specific screen or product was meant, name it and the spec is
   adjusted before anything is built.**

Evidence is in `docs/annexures/Annexure-2.md`, Amendment No. 59. In short: an account today is a name, a required
unique **email**, a password and a role; sign-in takes the email only; the sign-in token carries the email; only the
Director may create users. There is nowhere to hold a mobile number, and an account with no email cannot exist.

### Governing principles
- **A mobile number is a second way to identify a person, not a second way to prove who they are.** Sign-in stays
  password-based. One-time codes by SMS or WhatsApp need a messaging provider and are a separate amendment (with
  two-factor sign-in).
- **Nothing gets easier to guess.** Every failure to sign in still gives the same message; a locked account stays
  locked whichever identifier is typed; the per-address throttle from Amendment 58 is unchanged.
- **A PM may not grant power they do not hold.** A PM can create accounts only for the roles below them; they can
  never create a Director or another PM.
- **Existing accounts and existing sessions keep working**, apart from one sign-in after the deploy (item 4).
- **Nothing shows a cost or margin to a role that could not already see it (K.3).**

### Proposed spec

**Part A -- Backend (one migration)**
1. **Data.** `users.mobile` (text, nullable, unique) is added and `users.email` becomes nullable, with a database
   check that **at least one of the two is present**. Existing rows are untouched (all have an email).
2. **One way to write a mobile number.** Whatever is typed -- `98765 43210`, `098765-43210`, `+91 98765 43210`,
   `91 9876543210` -- is stored as `+919876543210`. An Indian mobile is 10 digits starting 6-9, with an optional `0`,
   `91` or `+91` in front; a number from another country must start with `+` and its country code (8-15 digits in
   all). Anything else is refused with a plain message. The same routine is used to create, to edit and to sign in,
   so a number can never be stored one way and typed another.
3. **Sign-in accepts either.** The existing `username` field takes an email (it contains `@`) or a mobile number
   (it does not). Email matching is unchanged. An unrecognised or badly formed value gives the same "Incorrect email
   or password" as any other failure, and counts toward the same lockout for a real account.
4. **The sign-in token identifies the person by id, not by email**, since some accounts will have no email. Tokens
   issued before the deploy name an email, no longer match, and end: **everyone signs in once after the deploy**
   (as after Amendment 58). Nothing else about the token changes.
5. **Create user** takes `email` and `mobile`, both optional, at least one required; each must be unique
   (409 "A user with this mobile number already exists" / "...email..."). The password rule "may not equal the
   email" also covers the mobile number typed as a password. A created account still gets the Director-or-PM-chosen
   temporary password and `must_change_password`.
6. **Who may create.** The **Director** may create any role. A **PM** may create **sales, procurement, site_engineer
   and ca_tax** accounts only -- a request for `director` or `pm` is refused 403 with a plain reason. Sales,
   Procurement, Site Engineer and CA/Tax cannot create users (unchanged). The PM may also list users (the screen
   needs it to avoid duplicates); resetting a password, deactivating, changing a role and editing an identifier stay
   **Director-only** (decision 4).
7. **Edit an identifier.** `PATCH /users/{id}` (Director) may add, change or clear `mobile` and `email`; an account
   may never be left with neither, and uniqueness holds. Both are recorded in the audit log (old and new value; never
   a password).
8. **Everything that assumed an email is made safe for its absence:** the "internal email domains" default derived
   from users' addresses skips users with none, the notification recipients for Sales skip users with none, and
   `GET /auth/me` returns `mobile` beside `email`.
9. **Tests**, including: each way of writing one mobile number stores identically; sign in by email and by mobile
   (both formats of the same number); a wrong password by mobile counts toward the same lockout as by email; a mobile
   number cannot be created twice; an account with neither is refused; a PM can create Sales but not Director or PM
   (403) and Sales cannot create anyone; an account with only a mobile number signs in, calls `/auth/me`, changes its
   password and keeps working on the fresh token; a token naming an email is refused; the all-routes test and the
   role table still pass. Each guard is removed once to see a test fail.

**Part B -- Screens (after Part A is live)**
10. **Sign-in page:** the box reads "Email or mobile number" (a text field with the username hint for password
    managers, not an email-only field).
11. **Team & Access -> People:** the create form has **Email** and **Mobile number** ("at least one -- either can be
    used to sign in") and the role list offers a PM only the four roles it may create; the list shows both. **A PM
    sees the People tab and nothing else on that screen** (no role table, no reset or deactivate buttons), through
    the same single role table the sidebar uses. Director's screen is unchanged apart from the new field.
12. **Handbook:** the sign-in, Team & Access and "how do I add someone" entries -- checked by name and by wording.
13. **Phone layout** at 375, 414 and 768px, and a real-Chrome pass per role (zero refused calls; the PM's reduced
    screen; a mobile-only account signing in and being forced to change its password).

**Sequencing (one Amendment number, two ordered PRs):** PR 1 = Part A (backend, migration, tests); PR 2 = Part B
(frontend). Part A is safe under the old frontend (it still sends an email and the create form still works). Each
is deployed and verified from outside before the close-out. The migration runs by itself when the backend starts.

### Explicitly out of scope
- **One-time passcodes or two-factor sign-in** by SMS, WhatsApp or an authenticator app (separate amendment).
- **Sending the temporary password or the sign-in details** to the new person by WhatsApp or email -- the creator
  still tells them (a natural next step: the app already has a WhatsApp gateway).
- **Verifying that a mobile number is real or belongs to the person.**
- **A new "admin" or "manager" role**, self-registration, "forgot password", editing a person's name, importing
  many users at once.
- Any pricing rule, K.3 gate, or role other than the user-creation change above.

### Acceptance criteria
- As Director: create a user with only a mobile number, only an email, and both; each signs in with what they
  have, and the one with both signs in with either. The same number typed four ways is one number.
- A mobile-only user is forced to change the temporary password, lands in the app on the fresh token with no
  refused calls, and cannot be created a second time (409).
- As PM: the People tab shows the create form and the list and nothing else; creating a Sales user works; asking for
  a Director or PM is refused 403 in the API and is not offered in the screen; Sales, Procurement, Site Engineer and
  CA/Tax cannot create users (403) and do not see the screen.
- Five wrong passwords by mobile lock the account (one audit entry); the email then also fails until the lockout
  ends; an unknown mobile gives the same message and locks nothing.
- Every existing account still signs in by email; existing tokens end once at the deploy; the all-routes test, the
  role table check and the existing backend suite pass.
- At 375px and 414px the sign-in box and the People form need no more width than the phone has.

### Open decisions (proposed defaults)
1. **Reading of the instruction** as set out above (either identifier; sign in with either; Director and PM create
   users). Proposed: **yes** -- correct it if not.
2. **No new roles: Director = admin, PM = manager.** Proposed: **yes.**
3. **A PM may create only Sales, Procurement, Site Engineer and CA/Tax accounts**, never a Director or another PM.
   Proposed: **yes.** (Alternative: PMs create nobody, only the Director does -- as today.)
4. **A PM may create and list users, but reset, deactivate, change role and edit identifiers stay Director-only.**
   Proposed: **yes.**
5. **Mobile numbers: Indian numbers in any common format, and other countries only with an explicit `+` and
   country code.** Proposed: **yes.**
6. **Mobile numbers are unverified identifiers; sign-in stays password-only.** Proposed: **yes** (codes are a
   separate amendment).
7. **Everyone signs in once after the backend deploy**, because the token now names the person by id. Proposed:
   **yes**, at a quiet time.
8. **Two ordered PRs** (backend and migration, then screens). Proposed: **yes.**

### Approval
☐ Approved as proposed
☐ Approved with changes (noted above)
☐ Not approved

**Prepared by:** R. Patni (with AI development assistance)
**Date:** 26 September 2026
