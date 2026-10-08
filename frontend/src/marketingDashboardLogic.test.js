// Run with:  node --test src/marketingDashboardLogic.test.js   (Node's built-in runner; no framework added)
import assert from "node:assert/strict";
import { test } from "node:test";
import { createDashboardLoader, hasUnappliedFilters, validatePeriod } from "./marketingDashboardLogic.js";

const OK = { periodStart: "2026-09-01", periodEnd: "2026-09-30", basis: "enquiry_time", bucket: "day" };

function deferred() {
  let resolve, reject;
  const promise = new Promise((res, rej) => ((resolve = res), (reject = rej)));
  return { promise, resolve, reject };
}

// A loader whose requests the test completes by hand, and a state object assembled the way the component does.
function harness() {
  const state = { data: undefined, loading: undefined, error: undefined, changes: 0 };
  const pending = [];
  const loader = createDashboardLoader({
    fetchDashboard: (params, signal) => {
      const d = deferred();
      pending.push({ params, signal, ...d });
      return d.promise;
    },
    onChange: (u) => {
      state.changes += 1;
      Object.assign(state, u);
    },
  });
  return { state, pending, loader };
}

const result = (bucket) => ({ period_start: "2026-09-01", period_end: "2026-09-30", cohort_basis: "enquiry_time", bucket });
const tick = () => new Promise((r) => setImmediate(r));

test("validatePeriod refuses empty, malformed and reversed dates and accepts a valid or single-day period", () => {
  assert.match(validatePeriod("", "2026-09-30"), /both/i);
  assert.match(validatePeriod("2026-09-01", ""), /both/i);
  assert.match(validatePeriod("2026-9-1", "2026-09-30"), /valid calendar/i);
  assert.match(validatePeriod("2026-09-30", "2026-09-01"), /end date must not be before/i);
  assert.equal(validatePeriod("2026-09-01", "2026-09-30"), null);
  assert.equal(validatePeriod("2026-09-15", "2026-09-15"), null);
});

test("hasUnappliedFilters compares the controls with the applied response, never with older controls", () => {
  const applied = result("day");
  assert.equal(hasUnappliedFilters(OK, applied), false);
  assert.equal(hasUnappliedFilters({ ...OK, bucket: "week" }, applied), true);
  assert.equal(hasUnappliedFilters({ ...OK, basis: "received_at" }, applied), true);
  assert.equal(hasUnappliedFilters({ ...OK, periodEnd: "2026-09-29" }, applied), true);
  assert.equal(hasUnappliedFilters(OK, null), false);
});

test("an invalid period after a successful result clears the results and makes no request", async () => {
  const { state, pending, loader } = harness();
  loader.load(OK);
  pending[0].resolve(result("day"));
  await tick();
  assert.equal(state.data.bucket, "day");
  loader.load({ ...OK, periodStart: "2026-10-05", periodEnd: "2026-09-01" });
  assert.equal(state.data, null);
  assert.match(state.error, /end date must not be before/i);
  assert.equal(state.loading, false);
  assert.equal(pending.length, 1); // no request for the invalid selection
});

test("an empty date clears the results and makes no request", async () => {
  const { state, pending, loader } = harness();
  loader.load(OK);
  pending[0].resolve(result("day"));
  await tick();
  loader.load({ ...OK, periodStart: "" });
  assert.equal(state.data, null);
  assert.match(state.error, /both a start date and an end date/i);
  assert.equal(pending.length, 1);
});

test("an invalid period supersedes a request still in flight: its late success cannot repopulate the results", async () => {
  const { state, pending, loader } = harness();
  loader.load(OK);
  loader.load({ ...OK, periodEnd: "" });
  pending[0].resolve(result("day")); // arrives after the invalid selection
  await tick();
  assert.equal(state.data, null);
  assert.match(state.error, /both/i);
  assert.equal(state.loading, false);
});

test("two successes completing in reverse order: the newer request wins", async () => {
  const { state, pending, loader } = harness();
  loader.load({ ...OK, bucket: "week" });
  loader.load({ ...OK, bucket: "month" });
  assert.equal(pending[0].signal.aborted, true); // the older request was cancelled
  pending[1].resolve(result("month"));
  await tick();
  pending[0].resolve(result("week")); // late, and cancellation did not stop it
  await tick();
  assert.equal(state.data.bucket, "month");
  assert.equal(state.error, "");
  assert.equal(state.loading, false);
});

test("an older request that FAILS after a newer success does not overwrite it with an error", async () => {
  const { state, pending, loader } = harness();
  loader.load({ ...OK, bucket: "week" });
  loader.load({ ...OK, bucket: "month" });
  pending[1].resolve(result("month"));
  await tick();
  pending[0].reject(new Error("server exploded")); // stale error arrives later
  await tick();
  assert.equal(state.data.bucket, "month");
  assert.equal(state.error, "");
  assert.equal(state.loading, false);
});

test("an older request that SUCCEEDS after a newer failure does not replace the error with old results", async () => {
  const { state, pending, loader } = harness();
  loader.load({ ...OK, bucket: "week" });
  loader.load({ ...OK, bucket: "month" });
  pending[1].reject(new Error("newer failed"));
  await tick();
  pending[0].resolve(result("week"));
  await tick();
  assert.equal(state.data, null);
  assert.equal(state.error, "newer failed");
  assert.equal(state.loading, false);
});

test("a stale abort rejection is ignored and the current request still completes normally", async () => {
  const { state, pending, loader } = harness();
  loader.load({ ...OK, bucket: "week" });
  loader.load({ ...OK, bucket: "month" });
  const abort = new Error("aborted");
  abort.name = "AbortError";
  pending[0].reject(abort);
  await tick();
  assert.equal(state.loading, true); // the newer request is still pending, untouched by the stale abort
  pending[1].resolve(result("month"));
  await tick();
  assert.equal(state.data.bucket, "month");
  assert.equal(state.loading, false);
});

test("cancel (unmount) stops any later response from changing state", async () => {
  const { state, pending, loader } = harness();
  loader.load(OK);
  const before = state.changes;
  loader.cancel();
  pending[0].resolve(result("day"));
  await tick();
  assert.equal(state.changes, before);
  assert.equal(pending[0].signal.aborted, true);
});
