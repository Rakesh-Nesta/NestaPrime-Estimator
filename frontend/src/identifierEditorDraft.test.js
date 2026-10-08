// Run with:  node --test src/identifierEditorDraft.test.js   (Node's built-in runner; no framework added)
//
// Refresh-then-submit defect in the shared "Edit sign-in" editor: the editor used to snapshot both boxes when it opened and, on
// submit, compare BOTH with the account as it is by then. After an earlier (delayed) save and a list refresh, an untouched box
// still held the old snapshot, so submitting reverted the field the earlier save had changed. The editor must send only the
// fields the person INTENTIONALLY edited in this session, and judge "at least one identifier" using the refreshed values for
// the fields they did not touch. These tests replay the sequences with a small fake server.
import assert from "node:assert/strict";
import { test } from "node:test";
import { draftValue, editDraft, newDraft, submitDraft } from "./identifierEditorDraft.js";
import { AT_LEAST_ONE_IDENTIFIER_MESSAGE } from "./userIdentifiers.js";

// A fake server holding one account, applying PATCH bodies with the real convention (omitted = leave, "" = clear).
function makeServer(account) {
  const server = { account: { ...account }, patches: [] };
  server.patch = (payload) => {
    server.patches.push(payload);
    for (const field of ["email", "mobile"]) {
      if (field in payload) server.account[field] = payload[field] === "" ? null : payload[field];
    }
  };
  server.list = () => ({ id: "A", name: "Asha", ...server.account }); // what a refreshed People list shows
  return server;
}

// The editor as the screen drives it: opens on the list's current row, takes edits, submits against the list's current row.
function makeEditor(rowAtOpen) {
  const editor = { draft: newDraft(rowAtOpen), row: rowAtOpen };
  editor.type = (field, value) => { editor.draft = editDraft(editor.draft, field, value); };
  editor.shown = (field) => draftValue(editor.draft, editor.row, field);
  editor.refresh = (row) => { editor.row = row; }; // the list refreshed under the open editor
  editor.submit = () => submitDraft(editor.draft, editor.row);
  return editor;
}

const START = { email: "asha@old.example.org", mobile: "+919876543210" };

test("EXACT SEQUENCE: save email, delay, cancel/reopen, edit only mobile, release + refresh, submit -> second PATCH is only the mobile; email is not reverted", () => {
  const server = makeServer(START);

  const first = makeEditor(server.list());
  first.type("email", "asha@new.example.org");
  const firstSubmit = first.submit();
  assert.deepEqual(firstSubmit.payload, { email: "asha@new.example.org" });
  server.patch(firstSubmit.payload); // the server has applied it; the browser has not heard back yet

  // user cancels and reopens A while that save is still in flight: the list row is still the OLD one
  const second = makeEditor({ id: "A", name: "Asha", ...START });
  second.type("mobile", "98765 43211");

  // the earlier save completes and the list refreshes under the open editor
  second.refresh(server.list());
  assert.equal(second.shown("email"), "asha@new.example.org", "an untouched box shows the refreshed value, not the open-time snapshot");
  assert.equal(second.shown("mobile"), "98765 43211", "the current draft is preserved");

  const secondSubmit = second.submit();
  assert.equal(secondSubmit.ok, true);
  assert.deepEqual(secondSubmit.payload, { mobile: "98765 43211" }, "only the intentionally edited field is sent");
  assert.equal("email" in secondSubmit.payload, false);
  server.patch(secondSubmit.payload);
  assert.equal(server.account.email, "asha@new.example.org", "the earlier save's email survives");
  assert.equal(server.account.mobile, "98765 43211");
});

test("RECIPROCAL: save mobile, delay, cancel/reopen, edit only email, release + refresh, submit -> second PATCH is only the email; mobile is not reverted", () => {
  const server = makeServer(START);

  const first = makeEditor(server.list());
  first.type("mobile", "98765 43211");
  server.patch(first.submit().payload);

  const second = makeEditor({ id: "A", name: "Asha", ...START });
  second.type("email", "asha@new.example.org");
  second.refresh(server.list());
  assert.equal(second.shown("mobile"), "98765 43211");

  const result = second.submit();
  assert.deepEqual(result.payload, { email: "asha@new.example.org" });
  assert.equal("mobile" in result.payload, false);
  server.patch(result.payload);
  assert.equal(server.account.mobile, "98765 43211");
  assert.equal(server.account.email, "asha@new.example.org");
});

test("an intentionally CLEARED field is still sent as an explicit empty string (omission versus clearing is preserved)", () => {
  const server = makeServer(START);
  const editor = makeEditor(server.list());
  editor.type("email", "   ");
  const result = editor.submit();
  assert.equal(result.ok, true);
  assert.deepEqual(result.payload, { email: "" });
  assert.equal("mobile" in result.payload, false);
});

test("a touched box retyped back to the account's current value sends nothing (and says so)", () => {
  const editor = makeEditor({ id: "A", ...START });
  editor.type("email", "other@x.example.org");
  editor.type("email", START.email);
  const result = editor.submit();
  assert.equal(result.ok, true);
  assert.equal(result.unchanged, true);
  assert.deepEqual(result.payload, {});
});

test("CLEARING VALIDATION uses refreshed values: an earlier save removed the mobile, so clearing the email now would leave neither", () => {
  const server = makeServer(START);
  const first = makeEditor(server.list());
  first.type("mobile", "");
  server.patch(first.submit().payload); // server: email only

  const second = makeEditor({ id: "A", name: "Asha", ...START }); // opened on the stale row (both identifiers shown)
  second.type("email", "");
  second.refresh(server.list()); // refreshed: the mobile is gone
  const result = second.submit();
  assert.equal(result.ok, false, "refused locally; the stale snapshot would have let this reach the server");
  assert.equal(result.error, AT_LEAST_ONE_IDENTIFIER_MESSAGE);
});

test("CLEARING VALIDATION the other way: an earlier save added a mobile, so clearing the email is now allowed", () => {
  const server = makeServer({ email: "asha@old.example.org", mobile: null });
  const first = makeEditor(server.list());
  first.type("mobile", "98765 43211");
  server.patch(first.submit().payload); // server: email + mobile

  const second = makeEditor({ id: "A", name: "Asha", email: "asha@old.example.org", mobile: null }); // stale: email only
  second.type("email", "");
  second.refresh(server.list());
  const result = second.submit();
  assert.equal(result.ok, true);
  assert.deepEqual(result.payload, { email: "" });
});

test("clearing BOTH boxes in one session is refused whatever the refresh did", () => {
  const server = makeServer(START);
  const editor = makeEditor(server.list());
  editor.type("email", "");
  editor.type("mobile", "");
  assert.equal(editor.submit().ok, false);
});

test("an untouched editor submits nothing, and follows the refreshed row for display", () => {
  const server = makeServer(START);
  const editor = makeEditor(server.list());
  server.patch({ email: "asha@new.example.org" });
  editor.refresh(server.list());
  assert.equal(editor.shown("email"), "asha@new.example.org");
  const result = editor.submit();
  assert.equal(result.ok, true);
  assert.equal(result.unchanged, true);
});
