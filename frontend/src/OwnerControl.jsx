import { useEffect, useState } from "react";
import { assignOwner, getOwnershipOverview } from "./api";

// Amendment 60 (Section 63): who owns a client, project or enquiry, and (for a PM or Director) changing it.
// Everyone else sees nothing here -- the API answers only PM and Director, so the screens ask only for them.
export const CAN_ASSIGN_OWNERS = ["pm", "director"];

// Two people can share a name, so an owner is always offered with their role beside it.
const ROLE_LABEL = { sales: "Sales", pm: "PM", director: "Director" };
export const ownerLabel = (o) => `${o.name} (${ROLE_LABEL[o.role] || o.role})`;

// The people a record may be given to, and a name for any owner id a row carries (including someone since
// deactivated, who is no longer offered but still has records until they are moved).
export function useOwners(token, role) {
  const [state, setState] = useState({ options: [], names: {} });
  useEffect(() => {
    if (!CAN_ASSIGN_OWNERS.includes(role)) return;
    getOwnershipOverview(token)
      .then((overview) => {
        const names = {};
        overview.by_owner.forEach((o) => {
          names[o.user_id] = o.name;
        });
        overview.owners.forEach((o) => {
          names[o.user_id] = o.name;
        });
        setState({ options: overview.owners, names });
      })
      .catch(() => setState({ options: [], names: {} }));
  }, [token, role]);
  return state;
}

// `kind` is "client", "project" or "opportunity". A client's own projects and enquiries move with it, which the
// title says, because that is the one surprise in this control.
export default function OwnerControl({ token, kind, recordId, ownerId, owners, onChanged }) {
  const [value, setValue] = useState(ownerId || "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => setValue(ownerId || ""), [ownerId]);

  async function change(next) {
    setBusy(true);
    setError("");
    try {
      await assignOwner(token, kind, recordId, next || null);
      setValue(next);
      if (onChanged) onChanged(next || null);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  const known = owners.options.some((o) => o.user_id === value);
  return (
    <span className="inline-flex flex-col items-start gap-0.5 text-xs">
      <label className="flex items-center gap-1.5 text-text-secondary">
        <span>Owner</span>
        <select
          aria-label="Owner"
          value={value}
          disabled={busy}
          onChange={(e) => change(e.target.value)}
          title={kind === "client" ? "Its projects and enquiries that were the old owner's move with it." : undefined}
          className={`rounded border bg-surface-raised px-1.5 py-1 text-xs max-w-[11rem] ${
            value ? "border-border-dark text-text-primary" : "border-amber-500/60 text-amber-400"
          }`}
        >
          <option value="">Unassigned</option>
          {!known && value && <option value={value}>{owners.names[value] || "Former user"} (inactive)</option>}
          {owners.options.map((o) => (
            <option key={o.user_id} value={o.user_id}>
              {ownerLabel(o)}
            </option>
          ))}
        </select>
      </label>
      {error && <span className="text-red-400">{error}</span>}
    </span>
  );
}
