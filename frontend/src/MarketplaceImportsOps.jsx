import { useEffect, useState } from "react";
import {
  getMarketplaceConnectionHealth,
  getMarketplaceImportsSummary,
  listMarketplaceImports,
  retryMarketplaceImport,
  runMarketplaceBackfill,
  verifyMarketplaceKey,
} from "./api";

// P3 contract (revision 4), Section 8: the operational screen -- PM/Director only. Connection
// health, Backlog/Quarantined/Failures/Expired counts, "Verify key now" (through the shared rate
// gate, Section 3), per-row "Retry" (synchronous, revision 4 fix), and a chunked backfill form.

const STATUS_LABELS = {
  pending: "Pending",
  quarantined: "Quarantined",
  converted: "Converted",
  duplicate_delivery: "Duplicate delivery",
  rejected: "Rejected",
  expired: "Expired",
};

function StatCard({ label, value, tone = "" }) {
  return (
    <div className={`bg-surface-raised border border-border-dark rounded-lg px-4 py-3 ${tone}`}>
      <p className="text-[10px] uppercase tracking-wider text-text-secondary/70">{label}</p>
      <p className="text-xl font-heading font-semibold text-text-primary mt-1">{value}</p>
    </div>
  );
}

export default function MarketplaceImportsOps({ token }) {
  const [health, setHealth] = useState(null);
  const [summary, setSummary] = useState(null);
  const [rows, setRows] = useState([]);
  const [statusFilter, setStatusFilter] = useState("rejected");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [verifying, setVerifying] = useState(false);
  const [verifyResult, setVerifyResult] = useState(null);
  const [retryingId, setRetryingId] = useState(null);
  const [backfillStart, setBackfillStart] = useState("");
  const [backfillEnd, setBackfillEnd] = useState("");
  const [backfillRunning, setBackfillRunning] = useState(false);
  const [backfillResult, setBackfillResult] = useState(null);

  function load() {
    setLoading(true);
    setError("");
    Promise.all([
      getMarketplaceConnectionHealth(token),
      getMarketplaceImportsSummary(token),
      listMarketplaceImports(token, statusFilter),
    ])
      .then(([h, s, r]) => {
        setHealth(h);
        setSummary(s);
        setRows(r);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, statusFilter]);

  async function handleVerify() {
    setVerifying(true);
    setVerifyResult(null);
    try {
      const result = await verifyMarketplaceKey(token);
      setVerifyResult(result);
      load();
    } catch (err) {
      setError(err.message);
    } finally {
      setVerifying(false);
    }
  }

  async function handleRetry(rowId) {
    setRetryingId(rowId);
    try {
      const outcome = await retryMarketplaceImport(token, rowId);
      load();
      return outcome;
    } catch (err) {
      setError(err.message);
    } finally {
      setRetryingId(null);
    }
  }

  async function handleBackfill() {
    if (!backfillStart || !backfillEnd) return;
    setBackfillRunning(true);
    setBackfillResult(null);
    try {
      const chunks = await runMarketplaceBackfill(token, { rangeStart: backfillStart, rangeEnd: backfillEnd });
      setBackfillResult(chunks);
      // The shared rate gate (Section 3) means a wide range can genuinely only complete one
      // chunk per real 5-minute window -- a stopped-early result is not a failure, it's a
      // resumable pause. Advance "From" to exactly where this run left off, so the same
      // "Run backfill" click resumes correctly a few minutes later without the operator having
      // to read the chunk list and do the date math themselves.
      const lastRan = [...chunks].reverse().find((c) => c.ran);
      const stoppedEarly = chunks.length > 0 && !chunks[chunks.length - 1].ran;
      if (stoppedEarly && lastRan) {
        setBackfillStart(lastRan.window_end.slice(0, 16));
      }
      load();
    } catch (err) {
      setError(err.message);
    } finally {
      setBackfillRunning(false);
    }
  }

  return (
    <div className="max-w-4xl mx-auto mt-8 mb-10 space-y-6">
      <div className="bg-surface shadow rounded-lg p-6">
        <h2 className="text-lg font-semibold text-text-primary">IndiaMART lead imports</h2>
        <p className="text-sm text-text-secondary">
          Connection health, backlog, and failures for the Pull import ledger.
        </p>
        {error && <p className="text-sm text-red-400 mt-2">{error}</p>}
      </div>

      <div className="bg-surface shadow rounded-lg p-6 space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h3 className="text-sm font-semibold text-text-primary">Connection health</h3>
          <button
            onClick={handleVerify}
            disabled={verifying}
            className="text-xs rounded px-3 py-1.5 bg-gold text-base font-medium hover:bg-gold/90 disabled:opacity-40"
          >
            {verifying ? "Verifying…" : "Verify key now"}
          </button>
        </div>
        {health && (
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 text-sm">
            <div>
              <p className="text-text-secondary text-xs">Status</p>
              <p className="text-text-primary">{health.configured ? "Configured" : "Not configured"}</p>
            </div>
            <div>
              <p className="text-text-secondary text-xs">Key</p>
              <p className="text-text-primary font-mono">{health.masked_key || "—"}</p>
            </div>
            <div>
              <p className="text-text-secondary text-xs">Checkpoint</p>
              <p className="text-text-primary">{health.checkpoint ? new Date(health.checkpoint).toLocaleString() : "never"}</p>
            </div>
          </div>
        )}
        {verifyResult && (
          <p className={`text-xs ${verifyResult.ok ? "text-emerald-400" : "text-red-400"}`}>
            {verifyResult.ok ? "Verified successfully." : `Not verified: ${verifyResult.reason}`}
          </p>
        )}
      </div>

      {summary && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <StatCard label="Backlog" value={summary.backlog_count} />
          <StatCard label="Quarantined" value={summary.quarantined_count} tone="border-amber-500/30" />
          <StatCard label="Failures" value={summary.failures_count} tone="border-red-500/30" />
          <StatCard label="Expired" value={summary.expired_count} />
        </div>
      )}

      <div className="bg-surface shadow rounded-lg p-6 space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h3 className="text-sm font-semibold text-text-primary">Ledger rows</h3>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="text-xs bg-surface-raised border border-border-dark rounded px-2 py-1"
          >
            {Object.entries(STATUS_LABELS).map(([value, label]) => (
              <option key={value} value={value}>{label}</option>
            ))}
          </select>
        </div>
        {loading && <p className="text-sm text-text-secondary">Loading…</p>}
        {!loading && rows.length === 0 && <p className="text-sm text-text-secondary">Nothing in this status.</p>}
        <div className="space-y-1.5">
          {rows.map((row) => (
            <div key={row.id} className="border border-border-dark rounded px-3 py-2 text-sm flex items-center justify-between gap-3">
              <div className="min-w-0">
                <p className="text-text-primary truncate">{row.external_id || "(no identity)"}</p>
                <p className="text-xs text-text-secondary truncate">
                  {new Date(row.received_at).toLocaleString()}
                  {row.rejection_reason ? ` · ${row.rejection_reason}` : ""}
                  {row.retry_count ? ` · ${row.retry_count} automatic ${row.retry_count === 1 ? "attempt" : "attempts"}` : ""}
                </p>
              </div>
              {row.status === "rejected" && (
                <button
                  onClick={() => handleRetry(row.id)}
                  disabled={retryingId === row.id}
                  className="text-xs text-gold hover:underline disabled:opacity-40 shrink-0"
                >
                  {retryingId === row.id ? "Retrying…" : "Retry"}
                </button>
              )}
            </div>
          ))}
        </div>
      </div>

      <div className="bg-surface shadow rounded-lg p-6 space-y-3">
        <h3 className="text-sm font-semibold text-text-primary">Backfill</h3>
        <p className="text-xs text-text-secondary">
          A multi-day backfill respects the same 5-minute rate limit every other call does, so a wide range may
          only complete one chunk per click -- run it again to continue where it left off.
        </p>
        <div className="flex flex-wrap items-end gap-3">
          <label className="text-xs text-text-secondary">
            From
            <input
              type="datetime-local"
              value={backfillStart}
              onChange={(e) => setBackfillStart(e.target.value)}
              className="block mt-1 bg-surface-raised border border-border-dark rounded px-2 py-1 text-sm"
            />
          </label>
          <label className="text-xs text-text-secondary">
            To
            <input
              type="datetime-local"
              value={backfillEnd}
              onChange={(e) => setBackfillEnd(e.target.value)}
              className="block mt-1 bg-surface-raised border border-border-dark rounded px-2 py-1 text-sm"
            />
          </label>
          <button
            onClick={handleBackfill}
            disabled={backfillRunning || !backfillStart || !backfillEnd}
            className="text-xs rounded px-3 py-1.5 bg-gold text-base font-medium hover:bg-gold/90 disabled:opacity-40"
          >
            {backfillRunning ? "Running…" : "Run backfill"}
          </button>
        </div>
        {backfillResult && (
          <div className="space-y-1 text-xs text-text-secondary">
            {backfillResult.map((chunk, i) => (
              <p key={i}>
                {new Date(chunk.window_start).toLocaleDateString()}–{new Date(chunk.window_end).toLocaleDateString()}:{" "}
                {chunk.ran ? `${chunk.captured} captured, ${chunk.quarantined} quarantined, ${chunk.duplicates} duplicate` : `stopped (${chunk.reason})`}
              </p>
            ))}
            {!backfillResult[backfillResult.length - 1]?.ran && (
              <p className="text-amber-400">
                Rate-limited for now -- "From" has been advanced to where this run left off. Click "Run backfill"
                again in a few minutes to continue.
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
