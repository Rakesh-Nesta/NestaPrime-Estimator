# Section 64 — Amendment No. 61 Spec

## Amendment No. 61 — Sign-in and User Creation with a Mobile Number or an Email

### Registered scope
The Director's instruction (26 September 2026): **"login benchmark ... users create with mobile no or email, both."**
Read as: (1) an account can be created with a mobile number, an email, or both -- at least one; (2) the person signs in
with whichever they have; (3) "benchmark" means "as the reference product does it". Who may create users is decided by
Amendment 59 (Admin: any role; Director: any role except Admin; PM: Sales, Procurement, Site Engineer and CA/Tax);
this amendment does not change it. Evidence is in `docs/annexures/Annexure-2.md`, Amendment No. 61: today an account
is a required unique **email**, sign-in and the token are email-only, and there is nowhere to hold a mobile number.

### Governing principles
- **A mobile number is a second way to identify a person, not a second way to prove who they are.** Sign-in stays
  password-based. One-time codes by SMS or WhatsApp need a messaging provider and are a separate amendment (with
  two-factor sign-in).
- **Nothing gets easier to guess.** Every failure to sign in gives the same message; a locked account stays locked
  whichever identifier is typed; the per-address throttle from Amendment 58 is unchanged.
- **Existing accounts and sessions keep working**, apart from one sign-in after the deploy (item 4).
- **Nothing shows a cost or margin to a role that could not already see it (K.3).**

### Proposed spec

**Part A -- Backend (one migration)**
1. **Data.** `users.mobile` (text, nullable, unique) is added and `users.email` becomes nullable, with a database
   check that **at least one of the two is present**. Existing rows are untouched (all have an email).
2. **One way to write a mobile number.** `98765 43210`, `098765-43210`, `+91 98765 43210` and `91 9876543210` are all
   stored as `+919876543210`. An Indian mobile is 10 digits starting 6-9, with an optional `0`, `91` or `+91`; a
   number from another country must start with `+` and its country code (8-15 digits in all). Anything else is
   refused with a plain message. The same routine serves create, edit and sign-in.
3. **Sign-in accepts either.** The `username` field takes an email (it contains `@`) or a mobile number (it does not).
   An unrecognised or malformed value gives the same "Incorrect email or password" as any failure, and counts toward
   the same lockout for a real account.
4. **The sign-in token names the person by id, not by email.** Tokens issued before the deploy name an email and end:
   **everyone signs in once after the deploy** (as after Amendment 58).
5. **Create user** takes `email` and `mobile`, both optional, at least one; each unique (409 "A user with this mobile
   number already exists"). The password rule "may not equal the email" also covers the mobile number. A created
   account keeps the temporary password and `must_change_password`.
6. **Edit an identifier.** `PATCH /users/{id}` (Admin, and Director for non-Admin users) may add, change or clear
   `mobile` and `email`; an account is never left with neither; uniqueness holds; audited (old and new value).
7. **Everything that assumed an email is made safe for its absence:** the "internal email domains" default, the Sales
   recipients notified on a structural-design rebase, `GET /auth/me` (returns `mobile` beside `email`), and the People
   list.
8. **Tests**, including: each way of writing one number stores identically; sign in by email and by mobile (both
   formats); wrong passwords by mobile count toward the same lockout as by email; a number cannot be created twice;
   an account with neither is refused; a mobile-only account signs in, changes its password and keeps working on the
   fresh token; a token naming an email is refused; the all-routes test and the role table pass; each guard removed
   once to see a test fail.

**Part B -- Screens**
9. **Sign-in page:** "Email or mobile number" (a text field with the username hint for password managers).
10. **Team & Access -> People:** the create and edit forms have **Email** and **Mobile number** ("at least one --
    either can be used to sign in"); the list shows both.
11. **Handbook:** the sign-in, Team & Access and "how do I add someone" entries -- by name and by wording.
12. **Phone layout** at 375, 414 and 768px and a real-Chrome pass per role, including a mobile-only account being
    forced to change its password and landing in the app.

**Sequencing (one Amendment number, two ordered PRs):** Part A (backend, migration, tests), then Part B (frontend).
Part A is safe under the old frontend. Each is verified from outside before the close-out.

### Explicitly out of scope
- One-time passcodes or two-factor sign-in; sending the temporary password by WhatsApp or email; verifying a number is
  real; "forgot password"; self-registration; bulk import; new roles.

### Acceptance criteria
- Create a user with only a mobile number, only an email, and both; each signs in with what they have, and the one
  with both with either. The same number typed four ways is one number.
- A mobile-only user is forced to change the temporary password, lands in the app on the fresh token with no refused
  calls, and cannot be created a second time (409).
- Five wrong passwords by mobile lock the account (one audit entry) and the email also fails until the lockout ends;
  an unknown mobile gives the same message and locks nothing.
- Every existing account still signs in by email; existing tokens end once; the all-routes test, the role-table check
  and the existing suite pass; at 375px and 414px the sign-in box and People form fit.

### Open decisions (proposed defaults)
1. **Reading of the instruction** as above. Proposed: **yes.**
2. **Mobile numbers: Indian numbers in any common format; other countries only with `+` and country code.**
   Proposed: **yes.**
3. **Mobile numbers are unverified identifiers; sign-in stays password-only.** Proposed: **yes.**
4. **Everyone signs in once after the backend deploy.** Proposed: **yes**, at a quiet time.
5. **Two ordered PRs.** Proposed: **yes.**

### Approval
☑ Approved — "approve as proposed, all decisions" (26 September 2026), covering the eight decisions of the earlier
version of this spec (whose decision on who may create users is now Amendment 59) and the order of the three
amendments.
☐ Approved with changes (noted above)
☐ Not approved

**Prepared by:** R. Patni (with AI development assistance)
**Date:** 26 September 2026
