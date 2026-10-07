// Amendment 61 Part B (Section 64 items 9-10): the pure rules behind the sign-in identifier and the People create/edit forms.
//
// An account is identified by an email, a mobile number, or both -- at least one. The SERVER is authoritative for what a
// mobile number or an email is: it normalises the mobile (`98765 43210`, `098765-43210`, `+91 98765 43210` and `91 9876543210`
// are one number), checks uniqueness and refuses malformed values with a plain message. This module therefore adds NO format
// policy of its own: it never reformats, validates or "fixes" a typed mobile number. It decides only
//   * that at least one identifier is non-blank (the same rule and wording as the server),
//   * which identifier fields go in a request -- omitted means "leave alone", an explicit "" means "clear" (the PATCH
//     convention of PATCH /users/{id}), and a blank on create is simply left out (the server rejects an empty email string),
//   * how identifiers are shown and searched without ever rendering "null" -- including for a mobile-only account.

export const AT_LEAST_ONE_IDENTIFIER_MESSAGE = "Enter an email, a mobile number, or both";
export const IDENTIFIER_RULE = "At least one -- either can be used to sign in.";
// What the server accepts, in words (it stays authoritative; see the header comment). Shown under the Mobile number box.
export const MOBILE_HINT =
  "An Indian number in any common format (98765 43210, 098765-43210, +91 98765 43210); another country needs + and its country code. " +
  "Spaces, hyphens, dots and brackets are fine; letters and other symbols are refused.";

function text(value) {
  return typeof value === "string" ? value.trim() : "";
}

/** The POST /users body: name, role and password always; email and mobile only when non-blank (as typed, trimmed). */
export function buildCreateUserPayload(form) {
  const email = text(form?.email);
  const mobile = text(form?.mobile);
  if (!email && !mobile) return { ok: false, error: AT_LEAST_ONE_IDENTIFIER_MESSAGE };
  const payload = { name: text(form?.name), role: form?.role, password: form?.password };
  if (email) payload.email = email;
  if (mobile) payload.mobile = mobile;
  return { ok: true, payload };
}

/**
 * The PATCH /users/{id} body for an identifier edit. `user` is the stored account, `edited` the form's `{ email, mobile }`.
 * A field that was not changed is OMITTED (leave alone); a field changed to something is sent as typed; a field changed to
 * blank is sent as an explicit "" (clear). An edit that would leave neither identifier is refused here, before any request
 * (the server refuses it too). `unchanged: true` with an empty payload means there is nothing to send.
 */
export function buildIdentifierPatch(user, edited) {
  const was = { email: text(user?.email), mobile: text(user?.mobile) };
  const now = { email: text(edited?.email), mobile: text(edited?.mobile) };
  const payload = {};
  if (now.email !== was.email) payload.email = now.email; // "" clears
  if (now.mobile !== was.mobile) payload.mobile = now.mobile; // "" clears
  if (!now.email && !now.mobile) return { ok: false, error: AT_LEAST_ONE_IDENTIFIER_MESSAGE };
  return { ok: true, payload, unchanged: Object.keys(payload).length === 0 };
}

/** What to show for an account's identifiers: only the ones present, email first. Never an empty or "null" line. */
export function identifierLines(user) {
  const lines = [];
  const email = text(user?.email);
  const mobile = text(user?.mobile);
  if (email) lines.push({ kind: "email", label: "Email", value: email });
  if (mobile) lines.push({ kind: "mobile", label: "Mobile", value: mobile });
  return lines;
}

/** Lower-cased text a People search runs over: name, email and mobile, with absent identifiers left out. */
export function userSearchText(user) {
  return [text(user?.name), text(user?.email), text(user?.mobile)].filter(Boolean).join(" ").toLowerCase();
}

function digits(value) {
  return String(value ?? "").replace(/\D/g, "");
}

/**
 * Whether a typed search matches a person: a plain substring of the name/email/mobile text, or -- so a number can be
 * found however it is typed -- a match on the digits alone (`98765 43210` finds `+919876543210`). A blank search matches
 * everyone. This is a search convenience, not an identifier format policy.
 */
export function userMatchesSearch(user, needle) {
  const query = text(needle).toLowerCase();
  if (!query) return true;
  if (userSearchText(user).includes(query)) return true;
  const queryDigits = digits(query);
  return queryDigits.length > 0 && digits(user?.mobile).includes(queryDigits);
}
