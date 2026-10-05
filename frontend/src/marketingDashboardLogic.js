// Marketing dashboard (M4): the load/validation/"latest request wins" logic, kept free of React so it can be
// unit-tested with Node's built-in runner (`node --test src/marketingDashboardLogic.test.js`).

const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;

// A message when the selected period cannot be requested, otherwise null. Empty or malformed dates (a cleared date
// input yields "") are refused here, before any request, instead of being sent to the server.
export function validatePeriod(periodStart, periodEnd) {
  if (!periodStart || !periodEnd) return "Choose both a start date and an end date.";
  if (!ISO_DATE.test(periodStart) || !ISO_DATE.test(periodEnd)) return "Enter the dates as valid calendar dates.";
  if (periodEnd < periodStart) return "The end date must not be before the start date.";
  return null;
}

// True while the controls differ from what the results on screen were produced with. The results are always
// described by the RESPONSE (data.*); this only decides whether to warn that the controls have moved on.
export function hasUnappliedFilters(controls, data) {
  if (!data) return false;
  return (
    controls.periodStart !== data.period_start ||
    controls.periodEnd !== data.period_end ||
    controls.basis !== data.cohort_basis ||
    controls.bucket !== data.bucket
  );
}

// Only the LATEST request may change data, error or loading. Each load takes a sequence number and aborts the
// previous request; a success, failure or abort from any older request is ignored even if it arrives later and
// cancellation did not stop it. An invalid period also supersedes whatever is in flight and clears the results,
// so earlier results are never shown as results for the invalid selection.
export function createDashboardLoader({ fetchDashboard, onChange }) {
  let seq = 0;
  let controller = null;

  function supersede() {
    seq += 1;
    controller?.abort();
    controller = null;
    return seq;
  }

  return {
    load(params) {
      const problem = validatePeriod(params.periodStart, params.periodEnd);
      const mine = supersede();
      if (problem) {
        onChange({ data: null, loading: false, error: problem });
        return;
      }
      controller = new AbortController();
      onChange({ loading: true, error: "" });
      fetchDashboard(params, controller.signal)
        .then((result) => {
          if (mine === seq) onChange({ data: result, loading: false, error: "" });
        })
        .catch((err) => {
          if (mine !== seq) return; // superseded: neither its error nor its abort may touch the current state
          onChange({ data: null, loading: false, error: err?.message || "Request failed" });
        });
    },
    cancel() {
      supersede();
    },
  };
}
