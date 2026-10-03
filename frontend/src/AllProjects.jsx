import { useEffect, useState } from "react";
import { listProjects } from "./api";
import { FolderIcon, SearchIcon } from "./Icons";
import OwnerControl, { CAN_ASSIGN_OWNERS, useOwners } from "./OwnerControl";

const STATUS_OPTIONS = [
  { value: "", label: "All projects" },
  { value: "open", label: "Open" },
  { value: "won", label: "Won" },
  { value: "lost", label: "Lost" },
];

const STATUS_PILL_STYLE = {
  open: "bg-gold/10 text-gold",
  won: "bg-green-500/10 text-green-400",
  lost: "bg-red-500/10 text-red-400",
};
const TILE_STYLE = {
  total: "bg-surface-raised text-text-secondary",
  open: "bg-gold/10 text-gold",
  won: "bg-green-500/10 text-green-400",
  lost: "bg-red-500/10 text-red-400",
};

function StatusPill({ status }) {
  return (
    <span className={`text-[10px] uppercase tracking-wide px-2 py-0.5 rounded-full inline-flex items-center gap-1 ${STATUS_PILL_STYLE[status] || ""}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${status === "open" ? "bg-gold" : status === "won" ? "bg-green-400" : "bg-red-400"}`} />
      {status}
    </span>
  );
}

function SortHeader({ label, sortKey, sort, onSort, align }) {
  const active = sort.key === sortKey;
  return (
    <th className={`px-3 py-2 ${align === "right" ? "text-right" : "text-left"}`}>
      <button
        onClick={() => onSort(sortKey)}
        className={`inline-flex items-center gap-1 hover:text-text-primary ${active ? "text-text-primary" : ""}`}
      >
        {label}
        <span className="text-[10px]">{active ? (sort.dir === "asc" ? "▲" : "▼") : "⇅"}</span>
      </button>
    </th>
  );
}

// Amendment 12 (Section 11): the Dashboard's "Open Projects" tile had no
// screen behind it -- only a 5-row "Recent projects" list. This is that
// screen: every project, filterable by open/won/lost (matching
// dashboard.py's own status vocabulary), with a client-side search on top
// of the backend's own project_no/client_name search.
//
// Redesign (2026-09-27, Director's request): same screen, same data and the same server calls -- a
// sortable, selectable table with a client filter and a summary bar for the selected row, instead of a
// flat list of buttons. Sidebar and header are untouched; only this screen's own content changed.
export default function AllProjects({ token, role, initialStatus = "", onOpenProject, onBack }) {
  const owners = useOwners(token, role);
  const canAssign = CAN_ASSIGN_OWNERS.includes(role);
  const [rows, setRows] = useState([]);
  const [status, setStatus] = useState(initialStatus);
  // P1 acceptance fix (correction plan, 2026-09-30): see Opportunities.jsx's own comment on this
  // same pattern -- useState's initial value only applies on first mount, so landing here twice
  // without an intervening remount (App.jsx's screen key unchanged) needs this to actually reset.
  useEffect(() => {
    setStatus(initialStatus);
  }, [initialStatus]);
  const [search, setSearch] = useState("");
  const [clientFilter, setClientFilter] = useState("");
  // Calibration/test projects are never counted on the Dashboard (Amendment 28 Part B). They stay in the data and one
  // click away here, but are hidden by default so the counts below match the Dashboard tile that opens this screen.
  const [showCalibration, setShowCalibration] = useState(false);
  const [selectedId, setSelectedId] = useState(null);
  const [autoSelectDone, setAutoSelectDone] = useState(false);
  const [sort, setSort] = useState({ key: "project_no", dir: "asc" });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    setLoading(true);
    // The whole list is fetched once; the status tabs filter it client-side. Fetching per status (as before) made every
    // tab/tile count reflect only the current filter -- "Open (3)" turned into "Open (0)" after choosing Lost.
    listProjects(token)
      .then(setRows)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [token]);

  // The "Selected project" summary bar reads as part of the page -- so the first row is selected by
  // default as soon as there is one, the same as the mockup shows it. Once, not on every load.
  useEffect(() => {
    if (!autoSelectDone && selectedId === null && rows.length > 0) {
      setSelectedId(rows[0].id);
      setAutoSelectDone(true);
    }
  }, [rows, autoSelectDone, selectedId]);

  function onSort(key) {
    setSort((s) => (s.key === key ? { key, dir: s.dir === "asc" ? "desc" : "asc" } : { key, dir: "asc" }));
  }

  if (loading) {
    return <p className="text-center text-text-secondary mt-10">Loading projects…</p>;
  }

  const needle = search.trim().toLowerCase();
  const population = showCalibration ? rows : rows.filter((r) => !r.is_calibration);
  const clientNames = [...new Set(population.map((r) => r.client_name))].sort();
  const calibrationCount = rows.filter((r) => r.is_calibration).length;
  const visibleRows = population
    .filter((r) => !status || r.status === status)
    .filter((r) => (!needle || r.project_no.toLowerCase().includes(needle) || r.client_name.toLowerCase().includes(needle)))
    .filter((r) => !clientFilter || r.client_name === clientFilter)
    .slice()
    .sort((a, b) => {
      const av = a[sort.key] ?? "";
      const bv = b[sort.key] ?? "";
      const cmp = String(av).localeCompare(String(bv));
      return sort.dir === "asc" ? cmp : -cmp;
    });
  const selected = population.find((r) => r.id === selectedId) || null;
  const tabCounts = {
    "": population.length,
    open: population.filter((r) => r.status === "open").length,
    won: population.filter((r) => r.status === "won").length,
    lost: population.filter((r) => r.status === "lost").length,
  };
  const tiles = [
    { key: "", label: "Total projects", value: tabCounts[""], icon: FolderIcon },
    { key: "open", label: "Open", value: tabCounts.open, icon: FolderIcon },
    { key: "lost", label: "Lost", value: tabCounts.lost, icon: FolderIcon },
  ];

  return (
    <div className="max-w-[1400px] mx-auto mt-6 mb-10 px-4 sm:px-6 space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs uppercase tracking-wide text-text-secondary">Workspace / Projects</p>
          <h2 className="font-heading font-bold text-text-primary text-2xl sm:text-3xl mt-1 flex items-center gap-2">
            <FolderIcon className="w-6 h-6 text-gold" /> All Projects
          </h2>
          <p className="text-sm text-text-secondary mt-1">Find and manage your client projects.</p>
        </div>
        {onBack && (
          <button onClick={onBack} className="text-xs uppercase tracking-wider text-gold hover:text-gold-hover shrink-0">
            ← Back
          </button>
        )}
      </div>

      {error && <p className="text-sm text-red-400">{error}</p>}

      <div className="grid grid-cols-3 gap-4">
        {tiles.map((tile) => (
          <button
            key={tile.label}
            onClick={() => setStatus(tile.key)}
            className={`text-left bg-surface border rounded-lg p-4 flex items-center gap-3 hover:-translate-y-0.5 transition-all duration-250 ease-out ${
              status === tile.key ? "border-gold" : "border-border-dark"
            }`}
          >
            <span className={`w-10 h-10 rounded-full flex items-center justify-center shrink-0 ${TILE_STYLE[tile.key || "total"]}`}>
              <tile.icon className="w-4 h-4" />
            </span>
            <div className="min-w-0">
              <p className="text-xs uppercase tracking-wide text-text-secondary truncate">{tile.label}</p>
              <p className="text-xl font-heading font-bold text-text-primary">{tile.value}</p>
            </div>
          </button>
        ))}
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border-dark">
        <div className="flex items-center gap-5 overflow-x-auto">
          {STATUS_OPTIONS.map((s) => (
            <button
              key={s.value}
              onClick={() => setStatus(s.value)}
              className={`text-sm pb-2.5 border-b-2 whitespace-nowrap transition-colors duration-200 ${
                status === s.value
                  ? "text-gold border-gold font-medium"
                  : "text-text-secondary border-transparent hover:text-text-primary"
              }`}
            >
              {s.label} <span className="text-xs text-text-secondary">({tabCounts[s.value]})</span>
            </button>
          ))}
        </div>
        <div className="flex items-center gap-2 pb-2 shrink-0">
          <div className="relative">
            <SearchIcon className="w-3.5 h-3.5 text-text-secondary absolute left-2.5 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search project or client…"
              className="rounded border border-border-dark bg-surface-raised text-text-primary pl-7 pr-2 py-1.5 text-xs w-48"
            />
          </div>
          {calibrationCount > 0 && (
            <label className="flex items-center gap-1.5 text-xs text-text-secondary whitespace-nowrap cursor-pointer">
              <input type="checkbox" checked={showCalibration} onChange={(e) => setShowCalibration(e.target.checked)} />
              Show calibration/test ({calibrationCount})
            </label>
          )}
          <select
            value={clientFilter}
            onChange={(e) => setClientFilter(e.target.value)}
            className="rounded border border-border-dark bg-surface-raised text-text-primary px-2 py-1.5 text-xs max-w-[10rem]"
            aria-label="Client"
          >
            <option value="">All clients</option>
            {clientNames.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="bg-surface border border-border-dark rounded-lg overflow-x-auto">
        <table className="w-full text-xs">
          <thead className="text-text-secondary border-b border-border-dark">
            <tr>
              <SortHeader label="Project ID" sortKey="project_no" sort={sort} onSort={onSort} />
              <SortHeader label="Client" sortKey="client_name" sort={sort} onSort={onSort} />
              <SortHeader label="Location" sortKey="city" sort={sort} onSort={onSort} />
              <th className="text-left px-3 py-2">Status</th>
              {canAssign && <th className="text-left px-3 py-2">Owner</th>}
              <th className="text-left px-3 py-2">Action</th>
            </tr>
          </thead>
          <tbody>
            {visibleRows.map((p) => (
              <tr
                key={p.id}
                onClick={() => setSelectedId(p.id)}
                className={`border-t cursor-pointer align-middle hover:bg-surface-raised transition-colors duration-150 ${
                  selectedId === p.id ? "border-gold bg-gold/5" : "border-border-dark"
                }`}
              >
                <td className="px-3 py-2.5 font-mono text-text-primary whitespace-nowrap">
                  <span className="inline-flex items-center gap-1.5">
                    <FolderIcon className="w-3.5 h-3.5 text-gold" /> {p.project_no}
                    {p.is_calibration && (
                      <span className="text-[10px] uppercase tracking-wide px-1.5 py-0.5 rounded bg-surface-raised text-text-secondary">
                        calibration
                      </span>
                    )}
                  </span>
                </td>
                <td className="px-3 py-2.5 text-text-primary">{p.client_name}</td>
                <td className="px-3 py-2.5 text-text-secondary">{p.city}</td>
                <td className="px-3 py-2.5">
                  <StatusPill status={p.status} />
                </td>
                {canAssign && (
                  <td className="px-3 py-2.5" onClick={(e) => e.stopPropagation()}>
                    <OwnerControl
                      token={token}
                      kind="project"
                      recordId={p.id}
                      ownerId={p.owner_id}
                      owners={owners}
                      onChanged={(next) => setRows((rs) => rs.map((r) => (r.id === p.id ? { ...r, owner_id: next } : r)))}
                    />
                  </td>
                )}
                <td className="px-3 py-2.5 whitespace-nowrap">
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      onOpenProject(p.id);
                    }}
                    className="text-gold hover:underline"
                  >
                    Open project →
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {visibleRows.length === 0 && (
          <p className="text-sm text-text-secondary text-center py-6">No projects match these filters.</p>
        )}
      </div>

      {selected && (
        <div className="flex flex-wrap items-center justify-between gap-3 bg-surface border border-gold rounded-lg px-4 py-3">
          <div className="flex items-center gap-4 min-w-0">
            <span className="text-xs uppercase tracking-wide text-text-secondary shrink-0">Selected project</span>
            <span className="inline-flex items-center gap-1.5 font-mono text-text-primary shrink-0">
              <FolderIcon className="w-4 h-4 text-gold" /> {selected.project_no}
            </span>
            <span className="text-text-primary truncate">{selected.client_name}</span>
            <span className="text-text-secondary truncate hidden sm:inline">{selected.city}</span>
            {canAssign && selected.owner_id && (
              <span className="text-xs text-text-secondary hidden md:inline">
                Owner: {owners.names[selected.owner_id] || "—"}
              </span>
            )}
          </div>
          <button
            onClick={() => onOpenProject(selected.id)}
            className="bg-gold text-base text-sm rounded px-4 py-2 font-semibold hover:bg-gold-hover shrink-0"
          >
            Open project →
          </button>
        </div>
      )}
    </div>
  );
}
