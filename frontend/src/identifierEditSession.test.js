// Run with:  node --test src/identifierEditSession.test.js   (Node's built-in runner; no framework added)
//
// Amendment 61 Part B editor race: a save started in one "Edit sign-in" session must not affect a LATER session -- not when the
// user switched to another person, nor when they cancelled and reopened the same person (so the person's ID alone cannot
// identify the session). These tests drive the shared session logic with deferred (manually settled) requests.
//
// Scope: the pure logic that BOTH People screens use. The screens' wiring and the real-browser behaviour with a delayed server
// are covered separately (see the structural test at the end and the Chrome evidence).
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { editorReducer, initialEditorState, runIdentifierSave } from "./identifierEditSession.js";

function deferred() {
  let resolve, reject;
  const promise = new Promise((res, rej) => { resolve = res; reject = rej; });
  return { promise, resolve, reject };
}

// A tiny store: dispatch applies the reducer; reload() records that the list was refreshed.
function makeStore() {
  const store = { state: initialEditorState, reloads: 0, history: [] };
  store.dispatch = (action) => { store.state = editorReducer(store.state, action); store.history.push(action.type); };
  store.reload = async () => { store.reloads += 1; };
  store.toggle = (userId) => store.dispatch({ type: "toggle", userId });
  store.close = () => store.dispatch({ type: "close" });
  // Starts a save from the CURRENT session; returns its deferred request and the save promise.
  store.startSave = (payload = { email: "" }) => {
    const { key, userId } = store.state.active;
    const request = deferred();
    const done = runIdentifierSave({ key, userId, payload, update: () => request.promise, dispatch: store.dispatch, reload: store.reload });
    return { request, done, key, userId };
  };
  return store;
}

const flush = () => new Promise((resolve) => setImmediate(resolve));

test("a late SUCCESS for person A does not close the editor the user has since opened for person B", async () => {
  const s = makeStore();
  s.toggle("A");
  const save = s.startSave();
  s.toggle("B"); // user moves on while A's request is in flight
  const keyB = s.state.active.key;
  save.request.resolve({});
  await save.done;
  assert.deepEqual(s.state.active, { key: keyB, userId: "B" }, "B's editor must stay open");
  assert.equal(s.reloads, 1, "the saved data is still refreshed");
});

test("a late FAILURE for person A is not shown in person B's editor", async () => {
  const s = makeStore();
  s.toggle("A");
  const save = s.startSave();
  s.toggle("B");
  save.request.reject(new Error("A user with this mobile number already exists"));
  await save.done;
  assert.equal(s.state.error, "", "B's editor must show no error from A's request");
  assert.equal(s.state.active.userId, "B");
  assert.equal(s.reloads, 0, "a failed save refreshes nothing");
});

test("cancel then reopen the SAME person: the earlier request's success must not close the new editor", async () => {
  const s = makeStore();
  s.toggle("A");
  const first = s.startSave();
  s.close(); // cancel
  s.toggle("A"); // reopen: a new session for the same person
  const reopened = s.state.active;
  assert.notEqual(reopened.key, first.key, "a reopened editor is a new session");
  first.request.resolve({});
  await first.done;
  assert.equal(s.state.active, reopened, "the reopened editor stays open, untouched (same object: no re-render, no draft reset)");
  assert.equal(s.reloads, 1);
});

test("cancel then reopen the SAME person: the earlier request's failure must not appear in the new editor", async () => {
  const s = makeStore();
  s.toggle("A");
  const first = s.startSave();
  s.close();
  s.toggle("A");
  first.request.reject(new Error("Enter a 10-digit Indian mobile number"));
  await first.done;
  assert.equal(s.state.error, "");
  assert.equal(s.state.active.userId, "A");
});

test("a stale outcome neither changes the session object nor its key (so the new editor's draft is not remounted)", async () => {
  const s = makeStore();
  s.toggle("A");
  const first = s.startSave();
  s.close();
  s.toggle("A");
  const before = s.state;
  first.request.reject(new Error("late"));
  await first.done;
  assert.equal(s.state.active, before.active);
  assert.equal(s.state.counter, before.counter);
});

test("the CURRENT session still closes on its own success, and shows its own failure", async () => {
  const s = makeStore();
  s.toggle("A");
  const ok = s.startSave();
  ok.request.resolve({});
  await ok.done;
  assert.equal(s.state.active, null);
  assert.equal(s.reloads, 1);

  s.toggle("A");
  const bad = s.startSave();
  bad.request.reject(new Error("A user with this email already exists"));
  await bad.done;
  assert.equal(s.state.error, "A user with this email already exists");
  assert.equal(s.state.active.userId, "A", "a refused save leaves the editor open for correction");
});

test("a new save in the current session clears that session's earlier error", async () => {
  const s = makeStore();
  s.toggle("A");
  const bad = s.startSave();
  bad.request.reject(new Error("first refusal"));
  await bad.done;
  assert.equal(s.state.error, "first refusal");
  const retry = s.startSave();
  await flush();
  assert.equal(s.state.error, "");
  retry.request.resolve({});
  await retry.done;
  assert.equal(s.state.active, null);
});

test("two overlapping saves from two different sessions of the same person settle independently", async () => {
  const s = makeStore();
  s.toggle("A");
  const first = s.startSave({ email: "" });
  s.close();
  s.toggle("A");
  const second = s.startSave({ mobile: "" });
  second.request.reject(new Error("second failed"));
  await second.done;
  assert.equal(s.state.error, "second failed");
  first.request.resolve({}); // the first (stale) save succeeds afterwards
  await first.done;
  assert.equal(s.state.error, "second failed", "the stale success must not erase the current session's error");
  assert.equal(s.state.active.userId, "A", "...nor close its editor");
  assert.equal(s.reloads, 1);
});

test("a stale outcome after the editor was closed leaves it closed and shows nothing", async () => {
  const s = makeStore();
  s.toggle("A");
  const save = s.startSave();
  s.close();
  save.request.reject(new Error("late failure"));
  await save.done;
  assert.equal(s.state.active, null);
  assert.equal(s.state.error, "");
});

// Both People screens must use the one shared session logic and key the editor by session, not by person.
test("both People implementations use the shared editor session (structural check)", () => {
  for (const file of ["UserManagement.jsx", "AdminPeoplePanel.jsx"]) {
    const source = readFileSync(new URL(`./${file}`, import.meta.url), "utf8");
    assert.match(source, /useIdentifierEditor/, `${file} uses the shared hook`);
    assert.match(source, /<IdentifierEditor[\s\S]*?key=\{editor\.key\}/, `${file} keys the editor by its session`);
    assert.doesNotMatch(source, /setEditingId|setIdentifierError/, `${file} keeps no private editor state`);
  }
});
