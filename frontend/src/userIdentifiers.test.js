// Run with:  node --test src/userIdentifiers.test.js   (Node's built-in runner; no framework added)
//
// Amendment 61 Part B (Section 64 items 9-10): the pure rules behind the sign-in identifier and the People create/edit forms.
// The SERVER stays authoritative for what a mobile number or email IS (normalisation, uniqueness, malformed values); these
// tests pin only what the screens decide: at least one non-blank identifier, which fields go in the request (PATCH omission
// versus explicit clearing), and how identifiers are shown and searched safely -- including mobile-only accounts.
import assert from "node:assert/strict";
import { test } from "node:test";
import {
  AT_LEAST_ONE_IDENTIFIER_MESSAGE,
  buildCreateUserPayload,
  buildIdentifierPatch,
  identifierLines,
  userMatchesSearch,
  MOBILE_HINT,
  userSearchText,
} from "./userIdentifiers.js";

const FORM = { name: "  Asha Rao ", role: "sales", password: "TempPass!1234" };

// ---- create -------------------------------------------------------------------------------------------------------------------

test("create with an email only sends the email and omits the mobile key entirely", () => {
  const result = buildCreateUserPayload({ ...FORM, email: " asha@example.com ", mobile: "" });
  assert.equal(result.ok, true);
  assert.deepEqual(result.payload, { name: "Asha Rao", role: "sales", password: "TempPass!1234", email: "asha@example.com" });
  assert.equal("mobile" in result.payload, false);
});

test("create with a mobile only sends the mobile exactly as typed and omits the email (the server rejects an empty email string)", () => {
  const result = buildCreateUserPayload({ ...FORM, email: "", mobile: "98765 43210" });
  assert.equal(result.ok, true);
  assert.deepEqual(result.payload, { name: "Asha Rao", role: "sales", password: "TempPass!1234", mobile: "98765 43210" });
  assert.equal("email" in result.payload, false);
});

test("create with both sends both; the mobile is NOT reformatted by the screen (the server normalises)", () => {
  const typed = "(+91) 98765.43210";
  const result = buildCreateUserPayload({ ...FORM, email: "a@b.co", mobile: typed });
  assert.equal(result.payload.mobile, typed);
  assert.equal(result.payload.email, "a@b.co");
});

test("create with neither identifier, or only whitespace, is refused with the same wording as the server", () => {
  for (const [email, mobile] of [["", ""], ["   ", "\t"], [undefined, undefined], [null, null]]) {
    const result = buildCreateUserPayload({ ...FORM, email, mobile });
    assert.equal(result.ok, false);
    assert.equal(result.error, AT_LEAST_ONE_IDENTIFIER_MESSAGE);
  }
  assert.equal(AT_LEAST_ONE_IDENTIFIER_MESSAGE, "Enter an email, a mobile number, or both");
});

test("create does not apply a frontend format policy: odd mobile text is passed through for the server to refuse", () => {
  for (const odd of ["abc9876543210", "98765/43210", "+91९12345678"]) {
    const result = buildCreateUserPayload({ ...FORM, email: "", mobile: odd });
    assert.equal(result.ok, true);
    assert.equal(result.payload.mobile, odd);
  }
});

// ---- edit: PATCH omission versus explicit clearing ----------------------------------------------------------------------------

const BOTH = { email: "asha@example.com", mobile: "+919876543210" };

test("editing nothing sends nothing and says so", () => {
  const result = buildIdentifierPatch(BOTH, { email: "asha@example.com", mobile: "+919876543210" });
  assert.equal(result.ok, true);
  assert.equal(result.unchanged, true);
  assert.deepEqual(result.payload, {});
});

test("changing only the mobile OMITS the email key (omitted = leave alone)", () => {
  const result = buildIdentifierPatch(BOTH, { email: "asha@example.com", mobile: "98765 43211" });
  assert.equal(result.ok, true);
  assert.deepEqual(result.payload, { mobile: "98765 43211" });
  assert.equal("email" in result.payload, false);
});

test("changing only the email OMITS the mobile key", () => {
  const result = buildIdentifierPatch(BOTH, { email: "asha.rao@example.com", mobile: "+919876543210" });
  assert.deepEqual(result.payload, { email: "asha.rao@example.com" });
});

test("clearing a field sends an explicit empty string (clear), not an omission, when another identifier remains", () => {
  const clearMobile = buildIdentifierPatch(BOTH, { email: "asha@example.com", mobile: "   " });
  assert.equal(clearMobile.ok, true);
  assert.deepEqual(clearMobile.payload, { mobile: "" });
  const clearEmail = buildIdentifierPatch(BOTH, { email: "", mobile: "+919876543210" });
  assert.deepEqual(clearEmail.payload, { email: "" });
});

test("adding an identifier to an account that had only one", () => {
  const mobileOnly = { email: null, mobile: "+919876543210" };
  const result = buildIdentifierPatch(mobileOnly, { email: " new@example.com ", mobile: "+919876543210" });
  assert.deepEqual(result.payload, { email: "new@example.com" });
  const emailOnly = { email: "a@b.co", mobile: null };
  assert.deepEqual(buildIdentifierPatch(emailOnly, { email: "a@b.co", mobile: "9876543210" }).payload, { mobile: "9876543210" });
});

test("an edit that would leave neither identifier is refused before any request", () => {
  const bothCleared = buildIdentifierPatch(BOTH, { email: "", mobile: "" });
  assert.equal(bothCleared.ok, false);
  assert.equal(bothCleared.error, AT_LEAST_ONE_IDENTIFIER_MESSAGE);
  const lastOneCleared = buildIdentifierPatch({ email: null, mobile: "+919876543210" }, { email: "", mobile: "" });
  assert.equal(lastOneCleared.ok, false);
  const swapped = buildIdentifierPatch({ email: null, mobile: "+919876543210" }, { email: "x@y.co", mobile: "" });
  assert.equal(swapped.ok, true);
  assert.deepEqual(swapped.payload, { email: "x@y.co", mobile: "" });
});

test("retyping a stored mobile in another format is sent as a change; the server decides that it is the same number", () => {
  const result = buildIdentifierPatch(BOTH, { email: "asha@example.com", mobile: "98765 43210" });
  assert.deepEqual(result.payload, { mobile: "98765 43210" });
});

// ---- display and search -----------------------------------------------------------------------------------------------------------

test("a mobile-only account is shown by its mobile, with no 'null' or empty email line", () => {
  const lines = identifierLines({ name: "M", email: null, mobile: "+919876543210" });
  assert.deepEqual(lines, [{ kind: "mobile", label: "Mobile", value: "+919876543210" }]);
});

test("an email-only account is shown by its email; a dual account shows both, email first", () => {
  assert.deepEqual(identifierLines({ email: "a@b.co", mobile: null }), [{ kind: "email", label: "Email", value: "a@b.co" }]);
  assert.deepEqual(identifierLines({ email: "a@b.co", mobile: "+919876543210" }).map((l) => l.kind), ["email", "mobile"]);
});

test("blank or missing identifiers are never rendered (the screens show their own wording when none is present)", () => {
  assert.deepEqual(identifierLines({ email: "  ", mobile: "" }), []);
  assert.deepEqual(identifierLines({}), []);
  assert.deepEqual(identifierLines(null), []);
});

test("search text never contains the word 'null' or 'undefined' for a mobile-only account, and finds by mobile in any spacing", () => {
  const mobileOnly = { name: "Mobile Only", email: null, mobile: "+919876543210" };
  const text = userSearchText(mobileOnly);
  assert.equal(text.includes("null"), false);
  assert.equal(text.includes("undefined"), false);
  assert.equal(text.includes("mobile only"), true);
  assert.equal(text.includes("+919876543210"), true);
  const emailOnly = { name: "Email Only", email: "e@x.co", mobile: null };
  assert.equal(userSearchText(emailOnly).includes("null"), false);
  assert.equal(userSearchText(emailOnly).includes("e@x.co"), true);
});

test("search matches a mobile typed with spaces or without the country code", () => {
  const user = { name: "A", email: null, mobile: "+919876543210" };
  assert.equal(userMatchesSearch(user, "98765 43210"), true);
  assert.equal(userMatchesSearch(user, "9876543210"), true);
  assert.equal(userMatchesSearch(user, "+91 98765"), true);
  assert.equal(userMatchesSearch(user, "98765 99999"), false);
  assert.equal(userMatchesSearch(user, "null"), false);
});

// ---- wording --------------------------------------------------------------------------------------------------------------------

test("the mobile hint names parentheses (square brackets are refused by the server) and does not say 'brackets'", () => {
  assert.match(MOBILE_HINT, /parentheses/);
  assert.doesNotMatch(MOBILE_HINT, /brackets/);
});
