import { useEffect, useState } from "react";
import { createUser, listUsers, resetUserPassword, updateUser } from "./api";
import MiniField from "./MiniField";

// Amendment 51 (Section 55): moved here unchanged from MasterSettings.jsx, where it
// was a tab under "Team & Access" -- which opened Master Settings. It is now the
// People tab of the real Team & Access screen (TeamAccess.jsx).
const USER_ROLES = ["sales", "pm", "director", "procurement", "site_engineer", "ca_tax"];

function emptyUserForm() {
  return { name: "", email: "", role: "sales", password: "" };
}

export default function UserManagementTab({ token, currentUser }) {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [creating, setCreating] = useState(false);
  const [createForm, setCreateForm] = useState(emptyUserForm());

  const [resettingId, setResettingId] = useState(null);
  const [resetPassword, setResetPassword] = useState("");

  function load() {
    return listUsers(token).then(setUsers);
  }

  useEffect(() => {
    setLoading(true);
    load()
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  async function handleCreate(e) {
    e.preventDefault();
    setError("");
    try {
      await createUser(token, createForm);
      setCreateForm(emptyUserForm());
      setCreating(false);
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleRoleChange(u, role) {
    if (role === u.role) return;
    setError("");
    try {
      await updateUser(token, u.id, { role });
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleToggleActive(u) {
    setError("");
    try {
      await updateUser(token, u.id, { is_active: !u.is_active });
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleResetPassword(u) {
    setError("");
    try {
      await resetUserPassword(token, u.id, resetPassword);
      setResettingId(null);
      setResetPassword("");
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  if (loading) return null;

  return (
    <div className="bg-surface shadow rounded-lg p-6 space-y-4">
      <div>
        <h3 className="text-sm font-semibold text-text-secondary mb-1">User management</h3>
        <p className="text-xs text-text-secondary">
          Director-only. A newly created or reset account must change its password on first login --
          enforced on the backend, not just hidden in this screen. Two guardrails apply server-side too:
          you can't deactivate your own account, and you can't demote or deactivate the last active Director.
        </p>
      </div>
      {error && <p className="text-sm text-red-400">{error}</p>}

      <div className="space-y-2">
        {users.map((u) => {
          const isSelf = u.id === currentUser?.id;
          return (
            <div key={u.id} className={`border rounded px-3 py-2 text-sm ${u.is_active ? "border-border-dark" : "border-border-dark bg-surface-raised opacity-60"}`}>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <span className="font-medium">{u.name}</span>{" "}
                  <span className="text-xs text-text-secondary">
                    ({u.email}){isSelf && " · you"}
                  </span>
                  {u.must_change_password && (
                    <span className="ml-2 text-[10px] uppercase rounded px-1.5 py-0.5 bg-amber-500/15 text-amber-400">
                      Password change pending
                    </span>
                  )}
                  {!u.is_active && <span className="ml-2 text-xs text-text-secondary">· inactive</span>}
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <select
                    value={u.role}
                    onChange={(e) => handleRoleChange(u, e.target.value)}
                    className="text-xs rounded border border-border-dark bg-surface-raised text-text-primary px-2 py-1"
                  >
                    {USER_ROLES.map((r) => (
                      <option key={r} value={r}>{r}</option>
                    ))}
                  </select>
                  <button
                    onClick={() => handleToggleActive(u)}
                    disabled={isSelf && u.is_active}
                    title={isSelf && u.is_active ? "You cannot deactivate your own account" : undefined}
                    className="text-xs text-text-secondary hover:underline disabled:text-text-secondary disabled:cursor-not-allowed disabled:hover:no-underline"
                  >
                    {u.is_active ? "Deactivate" : "Reactivate"}
                  </button>
                  {resettingId === u.id ? (
                    <div className="flex items-center gap-1">
                      <input
                        type="password"
                        placeholder="New password"
                        value={resetPassword}
                        onChange={(e) => setResetPassword(e.target.value)}
                        className="text-xs rounded border border-border-dark bg-surface-raised text-text-primary px-2 py-1 w-32"
                      />
                      <button
                        onClick={() => handleResetPassword(u)}
                        className="text-xs bg-gold text-base rounded px-2 py-1 hover:bg-gold-hover"
                      >
                        Save
                      </button>
                      <button
                        onClick={() => { setResettingId(null); setResetPassword(""); }}
                        className="text-xs text-text-secondary hover:underline"
                      >
                        Cancel
                      </button>
                    </div>
                  ) : (
                    <button
                      onClick={() => { setResettingId(u.id); setResetPassword(""); }}
                      className="text-xs text-gold hover:underline"
                    >
                      Reset password
                    </button>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {creating ? (
        <form onSubmit={handleCreate} className="border border-green-500/30 bg-green-500/10 rounded p-3 space-y-2">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            <MiniField label="Name" value={createForm.name} onChange={(v) => setCreateForm((f) => ({ ...f, name: v }))} required />
            <MiniField label="Email" value={createForm.email} onChange={(v) => setCreateForm((f) => ({ ...f, email: v }))} required />
            <div>
              <label className="block text-xs text-text-secondary">Role</label>
              <select
                value={createForm.role}
                onChange={(e) => setCreateForm((f) => ({ ...f, role: e.target.value }))}
                className="mt-1 w-full rounded border border-border-dark bg-surface-raised text-text-primary px-2 py-1 text-sm"
              >
                {USER_ROLES.map((r) => (
                  <option key={r} value={r}>{r}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs text-text-secondary">Initial password</label>
              <input
                type="password"
                required
                minLength={8}
                value={createForm.password}
                onChange={(e) => setCreateForm((f) => ({ ...f, password: e.target.value }))}
                className="mt-1 w-full rounded border border-border-dark bg-surface-raised text-text-primary px-2 py-1 text-sm"
              />
            </div>
          </div>
          <p className="text-xs text-text-secondary">
            The new user must change this password before they can use the app.
          </p>
          <div className="flex gap-2">
            <button type="submit" className="bg-green-600 text-white text-xs rounded px-3 py-1 hover:bg-green-700">
              Create user
            </button>
            <button
              type="button"
              onClick={() => { setCreating(false); setCreateForm(emptyUserForm()); }}
              className="text-xs text-text-secondary hover:underline"
            >
              Cancel
            </button>
          </div>
        </form>
      ) : (
        <button onClick={() => setCreating(true)} className="text-xs text-gold hover:underline">
          + Create a user
        </button>
      )}
    </div>
  );
}
