import { useEffect, useMemo, useState } from "react";
import { getAdminOverview } from "./api";
import {
  BriefcaseIcon,
  ClockIcon,
  CrownIcon,
  GridIcon,
  LockIcon,
  ReceiptIcon,
  SearchIcon,
  ShieldIcon,
  TruckIcon,
  UsersIcon,
  WrenchIcon,
} from "./Icons";

// Amendment 59 (Section 62): the Overview an Admin sees instead of the business dashboard. An Admin has no
// business records, so nothing here is a count of clients, projects, quotations or money -- only people and the
// recent activity log (cost and margin values arrive already hidden from the server for this role).
//
// Redesign (2026-09-27, Director's request): same screen, same data and the same server call (getAdminOverview) --
// a page-shell header with a "Manage team" shortcut, colour-coded tiles and role badges, and a searchable/filterable/
// paginated activity table instead of a flat list. Sidebar and header are untouched; only this screen's own content
// changed. Nothing here grants an Admin any value they couldn't already see -- the server still hides cost, margin
// and price fields for this role (mask_for_role on the backend).
const ROLE_LABELS = {
  admin: "Admin",
  director: "Director",
  pm: "PM",
  sales: "Sales",
  procurement: "Procurement",
  site_engineer: "Site Engineer",
  ca_tax: "CA / Tax",
};

const ROLE_STYLE = {
  admin: { icon: ShieldIcon, bg: "bg-purple-500/15", text: "text-purple-400" },
  director: { icon: CrownIcon, bg: "bg-gold/15", text: "text-gold" },
  pm: { icon: BriefcaseIcon, bg: "bg-blue-500/15", text: "text-blue-400" },
  sales: { icon: UsersIcon, bg: "bg-green-500/15", text: "text-green-400" },
  procurement: { icon: TruckIcon, bg: "bg-amber-500/15", text: "text-amber-400" },
  site_engineer: { icon: WrenchIcon, bg: "bg-slate-500/15", text: "text-slate-400" },
  ca_tax: { icon: ReceiptIcon, bg: "bg-teal-500/15", text: "text-teal-400" },
};

const TILE_STYLE = {
  active: { icon: UsersIcon, bg: "bg-gold/15", text: "text-gold" },
  inactive: { icon: UsersIcon, bg: "bg-slate-500/15", text: "text-slate-400" },
  locked: { icon: LockIcon, bg: "bg-red-500/15", text: "text-red-400" },
  pending: { icon: ClockIcon, bg: "bg-amber-500/15", text: "text-amber-400" },
};

const PAGE_SIZE = 8;

// Dashboard fix (2026-09-29 correction plan): these tiles and the role cards below used to be plain,
// non-interactive divs -- no missing handler was hiding behind them, there simply was no interaction at
// all. onClick (when given) opens Team & Access -> People, pre-filtered to exactly what the tile or card
// represents (AdminPeoplePanel's own roleFilter/statusFilter), the same "click a count, land on the
// matching filtered records" pattern the business Dashboard uses for its own tiles.
function Tile({ tone, label, value, hint, onClick }) {
  const style = TILE_STYLE[tone];
  const TileIcon = style.icon;
  const content = (
    <>
      <span className={`shrink-0 w-9 h-9 rounded-full flex items-center justify-center ${style.bg} ${style.text}`}>
        <TileIcon className="w-4 h-4" />
      </span>
      <div className="min-w-0">
        <p className="text-[11px] uppercase tracking-wider text-text-secondary">{label}</p>
        <p className="text-2xl font-semibold text-text-primary mt-0.5 tabular-nums">{value}</p>
        {hint && <p className="text-xs text-text-secondary mt-0.5">{hint}</p>}
      </div>
    </>
  );
  return onClick ? (
    <button
      onClick={onClick}
      className="text-left bg-surface-raised border border-border-dark rounded-lg px-4 py-3 flex items-start gap-3 hover:border-gold hover:-translate-y-0.5 transition-all duration-250 ease-out"
    >
      {content}
    </button>
  ) : (
    <div className="bg-surface-raised border border-border-dark rounded-lg px-4 py-3 flex items-start gap-3">{content}</div>
  );
}

export default function AdminOverview({ token, onManageTeam, onOpenTeam }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [actorFilter, setActorFilter] = useState("all");
  const [eventFilter, setEventFilter] = useState("all");
  const [page, setPage] = useState(1);

  useEffect(() => {
    getAdminOverview(token)
      .then(setData)
      .catch((err) => setError(err.message));
  }, [token]);

  const roles = data ? Object.keys(ROLE_LABELS).filter((r) => r in data.active_users_by_role) : [];
  const active = roles.reduce((sum, r) => sum + data.active_users_by_role[r], 0) || 0;

  const eventTypes = useMemo(
    () => (data ? [...new Set(data.recent_activity.map((e) => e.document_type))].sort() : []),
    [data]
  );
  const actorRoles = useMemo(
    () => (data ? [...new Set(data.recent_activity.map((e) => e.role))].sort() : []),
    [data]
  );

  const needle = search.trim().toLowerCase();
  const filtered = useMemo(() => {
    if (!data) return [];
    return data.recent_activity.filter((e) => {
      if (actorFilter !== "all" && e.role !== actorFilter) return false;
      if (eventFilter !== "all" && e.document_type !== eventFilter) return false;
      if (!needle) return true;
      const haystack = `${e.document_type} ${e.field} ${ROLE_LABELS[e.role] || e.role}`.toLowerCase();
      return haystack.includes(needle);
    });
  }, [data, actorFilter, eventFilter, needle]);

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const pageSafe = Math.min(page, totalPages);
  const visible = filtered.slice((pageSafe - 1) * PAGE_SIZE, pageSafe * PAGE_SIZE);

  function updateFilter(setter, value) {
    setter(value);
    setPage(1);
  }

  if (error) return <p className="max-w-4xl mx-auto mt-8 px-4 text-sm text-red-400">{error}</p>;
  if (!data) return <p className="text-center text-text-secondary mt-10">Loading…</p>;

  return (
    <div className="max-w-[1400px] mx-auto mt-6 mb-10 px-4 sm:px-6 space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          {/* P1 (Master Plan Reconciliation Section 5, Director-approved header table, 2026-09-30):
              Admin's own role header, re-skin only -- same screen, same data, same permissions. */}
          <p className="text-xs uppercase tracking-wide text-text-secondary">NestaPrime / People & Access</p>
          <div className="flex flex-wrap items-center gap-2 mt-1">
            <GridIcon className="w-5 h-5 text-gold shrink-0" />
            <h2 className="font-heading font-bold text-text-primary text-2xl sm:text-3xl">Admin overview</h2>
            <span className="inline-flex items-center gap-1 text-[10px] uppercase tracking-wider rounded-full px-2 py-0.5 bg-purple-500/15 text-purple-400">
              <ShieldIcon className="w-3 h-3" /> Admin view
            </span>
          </div>
          <p className="text-sm text-text-secondary mt-1">The state of the system: who has access, and what changed lately.</p>
        </div>
        {onManageTeam && (
          <button
            onClick={onManageTeam}
            className="bg-gold text-base text-sm rounded px-4 py-2 font-semibold hover:bg-gold-hover shrink-0"
          >
            Manage team
          </button>
        )}
      </div>

      <div className="flex items-start gap-2 bg-gold/5 border border-gold/20 rounded-lg px-4 py-3 text-sm text-text-secondary">
        <span className="text-gold shrink-0">ℹ</span>
        <span>Business figures are not available in this view. An Admin sees people, access and the audit trail only.</span>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <Tile tone="active" label="Active people" value={active} onClick={onOpenTeam && (() => onOpenTeam({ status: "active" }))} />
        <Tile tone="inactive" label="Inactive" value={data.inactive_users} onClick={onOpenTeam && (() => onOpenTeam({ status: "inactive" }))} />
        <Tile
          tone="locked"
          label="Locked out"
          value={data.locked_accounts}
          hint="Too many wrong passwords"
          onClick={onOpenTeam && (() => onOpenTeam({ status: "locked" }))}
        />
        <Tile
          tone="pending"
          label="Awaiting new password"
          value={data.awaiting_password_change}
          hint="Temporary password not yet changed"
          onClick={onOpenTeam && (() => onOpenTeam({ status: "pending" }))}
        />
      </div>

      <div className="bg-surface border border-border-dark rounded-lg p-5">
        <h3 className="text-sm font-semibold text-text-primary flex items-center gap-2 mb-3">
          <UsersIcon className="w-4 h-4 text-gold" /> Active people by role
        </h3>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
          {roles.map((r) => {
            const style = ROLE_STYLE[r];
            const RoleIcon = style.icon;
            const cardContent = (
              <>
                <span className={`w-7 h-7 rounded-full flex items-center justify-center shrink-0 ${style.bg} ${style.text}`}>
                  <RoleIcon className="w-3.5 h-3.5" />
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block text-xs text-text-secondary truncate">{ROLE_LABELS[r]}</span>
                  <span className="block font-medium tabular-nums">{data.active_users_by_role[r]}</span>
                </span>
              </>
            );
            return onOpenTeam ? (
              <button
                key={r}
                onClick={() => onOpenTeam({ role: r, status: "active" })}
                className="flex items-center gap-2.5 border border-border-dark rounded px-3 py-2 text-sm text-left hover:border-gold hover:-translate-y-0.5 transition-all duration-250 ease-out"
              >
                {cardContent}
              </button>
            ) : (
              <div key={r} className="flex items-center gap-2.5 border border-border-dark rounded px-3 py-2 text-sm">
                {cardContent}
              </div>
            );
          })}
        </div>
      </div>

      <div className="bg-surface border border-border-dark rounded-lg p-5">
        <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
          <h3 className="text-sm font-semibold text-text-primary flex items-center gap-2">
            <ClockIcon className="w-4 h-4 text-gold" /> Recent activity
            <span className="text-[10px] bg-surface-raised text-text-secondary rounded-full w-5 h-5 flex items-center justify-center">
              {filtered.length}
            </span>
          </h3>
          <div className="flex flex-wrap items-center gap-2">
            <select
              value={eventFilter}
              onChange={(e) => updateFilter(setEventFilter, e.target.value)}
              className="text-xs rounded border border-border-dark bg-surface-raised text-text-primary px-2 py-1.5"
            >
              <option value="all">All events</option>
              {eventTypes.map((t) => (
                <option key={t} value={t}>{t.replace(/_/g, " ")}</option>
              ))}
            </select>
            <select
              value={actorFilter}
              onChange={(e) => updateFilter(setActorFilter, e.target.value)}
              className="text-xs rounded border border-border-dark bg-surface-raised text-text-primary px-2 py-1.5"
            >
              <option value="all">All actors</option>
              {actorRoles.map((r) => (
                <option key={r} value={r}>{ROLE_LABELS[r] || r}</option>
              ))}
            </select>
            <div className="relative">
              <SearchIcon className="w-3.5 h-3.5 text-text-secondary absolute left-2.5 top-1/2 -translate-y-1/2" />
              <input
                type="search"
                value={search}
                onChange={(e) => updateFilter(setSearch, e.target.value)}
                placeholder="Search activity"
                className="rounded border border-border-dark bg-surface-raised text-text-primary pl-7 pr-2 py-1.5 text-xs w-40"
              />
            </div>
          </div>
        </div>

        {data.recent_activity.length === 0 ? (
          <p className="text-sm text-text-secondary">Nothing recorded yet.</p>
        ) : filtered.length === 0 ? (
          <p className="text-sm text-text-secondary text-center py-4">No activity matches these filters.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead className="text-text-secondary border-b border-border-dark">
                <tr>
                  <th className="text-left px-3 py-2">Event</th>
                  <th className="text-left px-3 py-2">Change</th>
                  <th className="text-left px-3 py-2">Actor</th>
                  <th className="text-left px-3 py-2">Date &amp; time</th>
                </tr>
              </thead>
              <tbody>
                {visible.map((e) => (
                  <tr key={e.id} className="border-t border-border-dark align-top">
                    <td className="px-3 py-2.5 text-text-primary whitespace-nowrap capitalize">
                      {e.document_type.replace(/_/g, " ")} · {e.field}
                    </td>
                    <td className="px-3 py-2.5 text-text-secondary break-words">
                      {(e.old_value != null || e.new_value != null) ? `${e.old_value ?? "—"} → ${e.new_value ?? "—"}` : "—"}
                    </td>
                    <td className="px-3 py-2.5 text-text-secondary whitespace-nowrap">{ROLE_LABELS[e.role] || e.role}</td>
                    <td className="px-3 py-2.5 text-text-secondary whitespace-nowrap">{new Date(e.timestamp).toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {filtered.length > PAGE_SIZE && (
          <div className="flex items-center justify-between mt-3 text-xs text-text-secondary">
            <span>
              Page {pageSafe} of {totalPages}
            </span>
            <div className="flex gap-1">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={pageSafe === 1}
                className="rounded border border-border-dark px-2 py-1 disabled:opacity-40"
              >
                ← Prev
              </button>
              <button
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={pageSafe === totalPages}
                className="rounded border border-border-dark px-2 py-1 disabled:opacity-40"
              >
                Next →
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
