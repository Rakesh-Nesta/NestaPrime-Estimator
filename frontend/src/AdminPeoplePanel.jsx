import { Fragment, useEffect, useMemo, useState } from "react";
import { createUser, listUsers, resetUserPassword, updateUser } from "./api";
import { rolesThatMayBeCreated } from "./UserManagement";
import MiniField from "./MiniField";
import { IdentifierEditor, IdentifierFields, IdentifierText } from "./UserIdentifierFields";
import { IDENTIFIER_RULE, buildCreateUserPayload, userMatchesSearch } from "./userIdentifiers";
import { ClockIcon, LockIcon, SearchIcon, ShieldIcon, UsersIcon } from "./Icons";

// Team & Access (Admin view) redesign (2026-09-27, Director's request): the People tab, restyled to match the
// Admin-account mockup -- same data and the same server calls as UserManagement.jsx (createUser, listUsers,
// resetUserPassword, updateUser), and the same create/manage rule: an Admin may create any role and manage
// anyone. Director and PM keep the existing UserManagement.jsx screen unchanged (that pass was explicitly
// parked) -- TeamAccess.jsx only renders this panel when the signed-in user is an Admin.
const ROLE_LABELS = {
  sales: "Sales",
  pm: "PM",
  director: "Director",
  procurement: "Procurement",
  site_engineer: "Site Engineer",
  ca_tax: "CA / Tax",
  admin: "Admin",
};
const ALL_ROLES = Object.keys(ROLE_LABELS);

function emptyUserForm(role = "sales") {
  return { name: "", email: "", mobile: "", role, password: "" };
}

function Tile({ icon: TileIcon, tone, label, value }) {
  return (
    <div className="bg-surface-raised border border-border-dark rounded-lg px-3 py-2.5 flex items-center gap-2.5">
      <span className={`shrink-0 w-8 h-8 rounded-full flex items-center justify-center ${tone.bg} ${tone.text}`}>
        <TileIcon className="w-4 h-4" />
      </span>
      <div className="min-w-0">
        <p className="text-[10px] uppercase tracking-wider text-text-secondary truncate">{label}</p>
        <p className="text-lg font-semibold text-text-primary tabular-nums">{value}</p>
      </div>
    </div>
  );
}

export default function AdminPeoplePanel({ token, currentUser, initialRoleFilter, initialStatusFilter }) {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [ownerNote, setOwnerNote] = useState("");

  const [search, setSearch] = useState("");
  const [roleFilter, setRoleFilter] = useState(initialRoleFilter && ALL_ROLES.includes(initialRoleFilter) ? initialRoleFilter : "all");
  const [statusFilter, setStatusFilter] = useState(
    initialStatusFilter && ["active", "inactive", "pending", "locked"].includes(initialStatusFilter) ? initialStatusFilter : "all"
  );
  // P1 acceptance fix (correction plan, 2026-09-30): see Opportunities.jsx's own comment on this
  // same pattern -- useState's initial value only applies on first mount, so landing here twice
  // without an intervening remount (App.jsx's screen key unchanged) needs this to actually reset.
  useEffect(() => {
    setRoleFilter(initialRoleFilter && ALL_ROLES.includes(initialRoleFilter) ? initialRoleFilter : "all");
    setStatusFilter(
      initialStatusFilter && ["active", "inactive", "pending", "locked"].includes(initialStatusFilter) ? initialStatusFilter : "all"
    );
  }, [initialRoleFilter, initialStatusFilter]);

  const [creating, setCreating] = useState(false);
  const [createForm, setCreateForm] = useState(emptyUserForm());

  const [resettingId, setResettingId] = useState(null);
  const [resetPassword, setResetPassword] = useState("");

  // Amendment 61 Part B: which account's sign-in details (email / mobile number) are being edited, and what the server said.
  const [editingId, setEditingId] = useState(null);
  const [identifierError, setIdentifierError] = useState("");

  const createRoles = rolesThatMayBeCreated("admin", users);

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
    const built = buildCreateUserPayload(createForm);
    if (!built.ok) {
      setError(built.error);
      return;
    }
    try {
      await createUser(token, built.payload);
      setCreateForm(emptyUserForm(createRoles[0]));
      setCreating(false);
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  // Never throws: a refusal (malformed number, duplicate, would-leave-neither) is shown inside the editor.
  async function handleSaveIdentifiers(u, payload) {
    setIdentifierError("");
    try {
      await updateUser(token, u.id, payload);
      setEditingId(null);
      await load();
    } catch (err) {
      setIdentifierError(err.message);
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
    setOwnerNote("");
    try {
      await updateUser(token, u.id, { is_active: !u.is_active });
      if (u.is_active && ["sales", "pm", "director"].includes(u.role)) {
        setOwnerNote(
          `${u.name} still owns any clients, projects and enquiries they held. A PM or the Director can move them in Team & Access, under Record owners.`
        );
      }
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

  const totals = useMemo(
    () => ({
      total: users.length,
      active: users.filter((u) => u.is_active).length,
      inactive: users.filter((u) => !u.is_active).length,
      pending: users.filter((u) => u.is_active && u.must_change_password).length,
      locked: users.filter((u) => u.is_locked).length,
    }),
    [users]
  );

  const visible = users.filter((u) => {
    if (roleFilter !== "all" && u.role !== roleFilter) return false;
    if (statusFilter === "active" && !u.is_active) return false;
    if (statusFilter === "inactive" && u.is_active) return false;
    if (statusFilter === "pending" && !(u.is_active && u.must_change_password)) return false;
    if (statusFilter === "locked" && !u.is_locked) return false;
    return userMatchesSearch(u, search); // name, email or mobile; a blank search matches everyone
  });

  if (loading) return null;

  return (
    <div className="bg-surface shadow rounded-lg p-6 space-y-4">
      <h3 className="text-sm font-semibold text-text-secondary">People</h3>

      <div className="grid grid-cols-2 sm:grid-cols-3 gap-2.5">
        <Tile icon={UsersIcon} tone={{ bg: "bg-gold/15", text: "text-gold" }} label="Total users" value={totals.total} />
        <Tile icon={ShieldIcon} tone={{ bg: "bg-green-500/15", text: "text-green-400" }} label="Active" value={totals.active} />
        <Tile icon={UsersIcon} tone={{ bg: "bg-slate-500/15", text: "text-slate-400" }} label="Inactive" value={totals.inactive} />
        <Tile icon={LockIcon} tone={{ bg: "bg-red-500/15", text: "text-red-400" }} label="Locked out" value={totals.locked} />
        <Tile icon={ClockIcon} tone={{ bg: "bg-amber-500/15", text: "text-amber-400" }} label="Password change pending" value={totals.pending} />
      </div>

      <div className="flex items-start gap-2 bg-gold/5 border border-gold/20 rounded-lg px-3 py-2.5 text-xs text-text-secondary">
        <span className="text-gold shrink-0">ℹ</span>
        <span>As Admin you can add, change, deactivate and reset anyone, including other Admins. A person signs in with their email or their mobile number; an account needs at least one.</span>
      </div>

      {error && <p className="text-sm text-red-400">{error}</p>}
      {ownerNote && <p className="text-sm text-amber-400">{ownerNote}</p>}

      <div className="flex flex-wrap items-center gap-2">
        <div className="relative flex-1 min-w-[10rem]">
          <SearchIcon className="w-3.5 h-3.5 text-text-secondary absolute left-2.5 top-1/2 -translate-y-1/2" />
          <input
            type="search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by name, email or mobile"
            className="w-full rounded border border-border-dark bg-surface-raised text-text-primary pl-7 pr-2 py-1.5 text-xs"
          />
        </div>
        <select
          value={roleFilter}
          onChange={(e) => setRoleFilter(e.target.value)}
          className="text-xs rounded border border-border-dark bg-surface-raised text-text-primary px-2 py-1.5"
        >
          <option value="all">All roles</option>
          {ALL_ROLES.map((r) => (
            <option key={r} value={r}>{ROLE_LABELS[r]}</option>
          ))}
        </select>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="text-xs rounded border border-border-dark bg-surface-raised text-text-primary px-2 py-1.5"
        >
          <option value="all">All statuses</option>
          <option value="active">Active</option>
          <option value="inactive">Inactive</option>
          <option value="locked">Locked out</option>
          <option value="pending">Password change pending</option>
        </select>
      </div>

      <div className="overflow-x-auto -mx-1">
        <table className="w-full text-xs min-w-[32rem]">
          <thead className="text-text-secondary border-b border-border-dark">
            <tr>
              <th className="text-left px-1 py-2">Person</th>
              <th className="text-left px-1 py-2">Role</th>
              <th className="text-left px-1 py-2">Account status</th>
              <th className="text-left px-1 py-2">Password status</th>
              <th className="text-left px-1 py-2">Actions</th>
            </tr>
          </thead>
          <tbody>
            {visible.map((u) => {
              const isSelf = u.id === currentUser?.id;
              return (
                <Fragment key={u.id}>
                <tr className="border-t border-border-dark align-top">
                  <td className="px-1 py-2.5">
                    <span className="block font-medium text-text-primary">{u.name}</span>
                    <span className="block text-[11px] text-text-secondary">
                      <IdentifierText user={u} stacked />
                      {isSelf && <span className="block">you</span>}
                    </span>
                  </td>
                  <td className="px-1 py-2.5">
                    <select
                      value={u.role}
                      onChange={(e) => handleRoleChange(u, e.target.value)}
                      disabled={isSelf}
                      title={isSelf ? "You cannot change your own role" : undefined}
                      aria-label={`Role of ${u.name}`}
                      className="text-xs rounded border border-border-dark bg-surface-raised text-text-primary px-1.5 py-1 disabled:opacity-60"
                    >
                      {[...new Set([...ALL_ROLES, u.role])].map((r) => (
                        <option key={r} value={r}>{ROLE_LABELS[r] || r}</option>
                      ))}
                    </select>
                  </td>
                  <td className="px-1 py-2.5 whitespace-nowrap">
                    <span
                      className={`inline-flex items-center gap-1 text-[10px] uppercase tracking-wider rounded-full px-2 py-0.5 ${
                        u.is_active ? "bg-green-500/15 text-green-400" : "bg-slate-500/15 text-slate-400"
                      }`}
                    >
                      {u.is_active ? "Active" : "Inactive"}
                    </span>
                    {u.is_locked && (
                      <span className="ml-1 inline-flex items-center gap-1 text-[10px] uppercase tracking-wider rounded-full px-2 py-0.5 bg-red-500/15 text-red-400">
                        <LockIcon className="w-3 h-3" /> Locked
                      </span>
                    )}
                  </td>
                  <td className="px-1 py-2.5 whitespace-nowrap">
                    {u.must_change_password ? (
                      <span className="inline-flex items-center gap-1 text-[10px] uppercase tracking-wider rounded-full px-2 py-0.5 bg-amber-500/15 text-amber-400">
                        <LockIcon className="w-3 h-3" /> Pending
                      </span>
                    ) : (
                      <span className="text-[10px] uppercase tracking-wider text-text-secondary">OK</span>
                    )}
                  </td>
                  <td className="px-1 py-2.5">
                    <div className="flex flex-wrap items-center gap-2">
                      <button
                        onClick={() => { setIdentifierError(""); setEditingId(editingId === u.id ? null : u.id); }}
                        className="text-gold hover:underline"
                      >
                        Edit sign-in
                      </button>
                      <button
                        onClick={() => handleToggleActive(u)}
                        disabled={isSelf && u.is_active}
                        title={isSelf && u.is_active ? "You cannot deactivate your own account" : undefined}
                        className="text-text-secondary hover:underline disabled:text-text-secondary disabled:cursor-not-allowed disabled:hover:no-underline"
                      >
                        {u.is_active ? "Deactivate" : "Reactivate"}
                      </button>
                      {resettingId === u.id ? (
                        <div className="flex items-center gap-1">
                          <input
                            type="password"
                            placeholder="New password (10+ chars)"
                            aria-label={`New password for ${u.name}`}
                            value={resetPassword}
                            onChange={(e) => setResetPassword(e.target.value)}
                            className="rounded border border-border-dark bg-surface-raised text-text-primary px-1.5 py-1 w-32"
                          />
                          <button
                            onClick={() => handleResetPassword(u)}
                            className="bg-gold text-base rounded px-2 py-1 hover:bg-gold-hover"
                          >
                            Save
                          </button>
                          <button
                            onClick={() => { setResettingId(null); setResetPassword(""); }}
                            className="text-text-secondary hover:underline"
                          >
                            Cancel
                          </button>
                        </div>
                      ) : (
                        <button
                          onClick={() => { setResettingId(u.id); setResetPassword(""); }}
                          className="text-gold hover:underline"
                        >
                          Reset password
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
                {editingId === u.id && (
                  <tr>
                    <td colSpan={5} className="px-1 pb-3">
                      {/* A full-width row (not inside the narrow Person cell), pinned to the left edge so it stays in view while the table scrolls on a phone. */}
                      <div className="sticky left-0 w-[min(100%,24rem)] max-w-[calc(100vw-4rem)]">
                        <IdentifierEditor
                          user={u}
                          serverError={identifierError}
                          onSave={(payload) => handleSaveIdentifiers(u, payload)}
                          onCancel={() => { setEditingId(null); setIdentifierError(""); }}
                        />
                      </div>
                    </td>
                  </tr>
                )}
                </Fragment>
              );
            })}
          </tbody>
        </table>
        {users.length > 0 && visible.length === 0 && (
          <p className="text-sm text-text-secondary text-center py-4">No one matches these filters.</p>
        )}
      </div>

      {createRoles.length > 0 &&
        (creating ? (
          <form onSubmit={handleCreate} className="border border-green-500/30 bg-green-500/10 rounded p-3 space-y-2">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              <MiniField label="Name" value={createForm.name} onChange={(v) => setCreateForm((f) => ({ ...f, name: v }))} required />
              <IdentifierFields
                idPrefix="admin-new-user"
                email={createForm.email}
                mobile={createForm.mobile}
                onChange={(field, value) => setCreateForm((f) => ({ ...f, [field]: value }))}
              />
              <div>
                <label htmlFor="admin-new-user-role" className="block text-xs text-text-secondary">Role</label>
                <select
                  id="admin-new-user-role"
                  value={createRoles.includes(createForm.role) ? createForm.role : createRoles[0]}
                  onChange={(e) => setCreateForm((f) => ({ ...f, role: e.target.value }))}
                  className="mt-1 w-full rounded border border-border-dark bg-surface-raised text-text-primary px-2 py-1 text-sm"
                >
                  {createRoles.map((r) => (
                    <option key={r} value={r}>{ROLE_LABELS[r] || r}</option>
                  ))}
                </select>
              </div>
              <div>
                <label htmlFor="admin-new-user-password" className="block text-xs text-text-secondary">Initial password (10+ characters)</label>
                <input
                  id="admin-new-user-password"
                  type="password"
                  required
                  minLength={10}
                  value={createForm.password}
                  onChange={(e) => setCreateForm((f) => ({ ...f, password: e.target.value }))}
                  className="mt-1 w-full rounded border border-border-dark bg-surface-raised text-text-primary px-2 py-1 text-sm"
                />
              </div>
            </div>
            <p className="text-xs text-text-secondary">{IDENTIFIER_RULE}</p>
            <p className="text-xs text-text-secondary">The new user must change this password before they can use the app.</p>
            <div className="flex gap-2">
              <button type="submit" className="bg-green-600 text-white text-xs rounded px-3 py-1.5 hover:bg-green-700">
                Create user
              </button>
              <button
                type="button"
                onClick={() => { setCreating(false); setCreateForm(emptyUserForm(createRoles[0])); }}
                className="text-xs text-text-secondary hover:underline"
              >
                Cancel
              </button>
            </div>
          </form>
        ) : (
          <button
            onClick={() => { setCreateForm((f) => ({ ...f, role: createRoles.includes(f.role) ? f.role : createRoles[0] })); setCreating(true); }}
            className="bg-gold text-base text-sm rounded px-4 py-2 font-semibold hover:bg-gold-hover"
          >
            + Create user
          </button>
        ))}

      <p className="text-[11px] text-text-secondary border-t border-border-dark pt-3">
        Nobody can deactivate or change the role of their own account. The last active Director and the last active
        Admin cannot be demoted or deactivated.
      </p>
    </div>
  );
}
