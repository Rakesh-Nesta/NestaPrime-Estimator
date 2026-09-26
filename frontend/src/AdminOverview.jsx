import { useEffect, useState } from "react";
import { getAdminOverview } from "./api";

// Amendment 59 (Section 62): the Overview an Admin sees instead of the business dashboard. An Admin has no
// business records, so nothing here is a count of clients, projects, quotations or money -- only people and the
// recent activity log (cost and margin values arrive already hidden from the server for this role).
const ROLE_LABELS = {
  admin: "Admin",
  director: "Director",
  pm: "PM",
  sales: "Sales",
  procurement: "Procurement",
  site_engineer: "Site Engineer",
  ca_tax: "CA / Tax",
};

function Tile({ label, value, hint }) {
  return (
    <div className="bg-surface-raised border border-border-dark rounded-lg px-4 py-3">
      <p className="text-[11px] uppercase tracking-wider text-text-secondary">{label}</p>
      <p className="text-2xl font-semibold text-text-primary mt-1 tabular-nums">{value}</p>
      {hint && <p className="text-xs text-text-secondary mt-1">{hint}</p>}
    </div>
  );
}

export default function AdminOverview({ token }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    getAdminOverview(token)
      .then(setData)
      .catch((err) => setError(err.message));
  }, [token]);

  if (error) return <p className="max-w-4xl mx-auto mt-8 px-4 text-sm text-red-400">{error}</p>;
  if (!data) return <p className="text-center text-text-secondary mt-10">Loading…</p>;

  const roles = Object.keys(ROLE_LABELS).filter((r) => r in data.active_users_by_role);
  const active = roles.reduce((sum, r) => sum + data.active_users_by_role[r], 0);

  return (
    <div className="max-w-4xl mx-auto mt-8 mb-10 px-4 space-y-6">
      <div className="bg-surface shadow rounded-lg p-6">
        <h2 className="text-lg font-semibold text-text-primary">Overview</h2>
        <p className="text-xs text-text-secondary mt-1">
          The state of the system: who has access, and what changed lately. Business figures are not shown to an Admin.
        </p>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-4">
          <Tile label="Active people" value={active} />
          <Tile label="Inactive" value={data.inactive_users} />
          <Tile label="Locked out" value={data.locked_accounts} hint="Too many wrong passwords" />
          <Tile label="Awaiting a new password" value={data.awaiting_password_change} hint="Temporary password not yet changed" />
        </div>
      </div>

      <div className="bg-surface shadow rounded-lg p-6">
        <h3 className="text-sm font-semibold text-text-secondary mb-3">Active people by role</h3>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
          {roles.map((r) => (
            <div key={r} className="flex items-center justify-between border border-border-dark rounded px-3 py-2 text-sm">
              <span className="text-text-secondary">{ROLE_LABELS[r]}</span>
              <span className="font-medium tabular-nums">{data.active_users_by_role[r]}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="bg-surface shadow rounded-lg p-6">
        <h3 className="text-sm font-semibold text-text-secondary mb-3">Recent activity</h3>
        {data.recent_activity.length === 0 ? (
          <p className="text-sm text-text-secondary">Nothing recorded yet.</p>
        ) : (
          <ul className="space-y-2">
            {data.recent_activity.map((e) => (
              <li key={e.id} className="border border-border-dark rounded px-3 py-2 text-xs">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="text-text-primary">
                    {e.document_type} · {e.field}
                  </span>
                  <span className="text-text-secondary">
                    {ROLE_LABELS[e.role] || e.role} · {new Date(e.timestamp).toLocaleString()}
                  </span>
                </div>
                {(e.old_value != null || e.new_value != null) && (
                  <p className="text-text-secondary mt-1 break-words">
                    {e.old_value ?? "—"} → {e.new_value ?? "—"}
                  </p>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
