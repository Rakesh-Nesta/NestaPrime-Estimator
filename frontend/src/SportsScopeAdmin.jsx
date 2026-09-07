import { useEffect, useState } from "react";
import {
  createScopeItem,
  createSport,
  listScopeItems,
  listSports,
  updateScopeItem,
  updateSport,
} from "./api";

const SPORT_CATEGORIES = ["indoor", "outdoor"];
const SCOPE_GROUPS = ["civil", "electrical", "water", "external", "services", "maintenance"];

function emptySportForm() {
  return {
    key: "", display_order: "", name: "", category: "outdoor", playing_dims: "", build_dims: "",
    playing_l_ft: "", playing_w_ft: "", build_l_ft: "", build_w_ft: "", min_clear_height_ft: "",
    governing_body: "", source_citation: "",
  };
}

function emptyScopeItemForm() {
  return { key: "", display_order: "", group: "civil", name: "" };
}

function num(v) {
  if (v === "" || v === null || v === undefined) return null;
  const n = Number(v);
  return Number.isNaN(n) ? null : n;
}

export default function SportsScopeAdmin({ token, onBack }) {
  const [tab, setTab] = useState("sports"); // "sports" | "scope"
  const [sports, setSports] = useState([]);
  const [scopeItems, setScopeItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  function load() {
    return Promise.all([listSports(token, true), listScopeItems(token, true)]).then(([s, i]) => {
      setSports(s);
      setScopeItems(i);
    });
  }

  useEffect(() => {
    setLoading(true);
    load()
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  function withErrorHandling(fn) {
    return async (...args) => {
      setError("");
      try {
        await fn(...args);
        await load();
      } catch (err) {
        setError(err.message);
      }
    };
  }

  if (loading) {
    return <p className="text-center text-gray-500 mt-10">Loading Sports &amp; Scope admin…</p>;
  }

  return (
    <div className="max-w-3xl mx-auto mt-8 mb-10 space-y-6">
      <div className="bg-white shadow rounded-lg p-6">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-900">Sports &amp; Scope master admin</h2>
          {onBack && (
            <button onClick={onBack} className="text-sm text-blue-600 hover:underline">
              &larr; Back
            </button>
          )}
        </div>
        <p className="text-xs text-gray-400 mt-1">
          Part C (Sport master list) and Part I (Additional Scope Checklist) were seeded once and read-only in
          Phase 1b -- this screen closes that gap. Director-only; deactivating retires an item without breaking
          existing projects that already reference it. A sport's key can't be changed once created -- every
          recommendation formula elsewhere in the app matches on it.
        </p>
        {error && <p className="text-sm text-red-600 mt-2">{error}</p>}
        <div className="flex gap-2 mt-4">
          <button
            onClick={() => setTab("sports")}
            className={`text-sm rounded px-3 py-1 ${tab === "sports" ? "bg-blue-600 text-white" : "bg-gray-100 text-gray-700"}`}
          >
            Sports ({sports.length})
          </button>
          <button
            onClick={() => setTab("scope")}
            className={`text-sm rounded px-3 py-1 ${tab === "scope" ? "bg-blue-600 text-white" : "bg-gray-100 text-gray-700"}`}
          >
            Scope items ({scopeItems.length})
          </button>
        </div>
      </div>

      {tab === "sports" && <SportsTab token={token} sports={sports} onAction={withErrorHandling} />}
      {tab === "scope" && <ScopeItemsTab token={token} scopeItems={scopeItems} onAction={withErrorHandling} />}
    </div>
  );
}

function SportsTab({ token, sports, onAction }) {
  const [editingId, setEditingId] = useState(null);
  const [editForm, setEditForm] = useState(null);
  const [creating, setCreating] = useState(false);
  const [createForm, setCreateForm] = useState(emptySportForm());

  const handleCreate = onAction(async (e) => {
    e.preventDefault();
    await createSport(token, {
      key: createForm.key,
      display_order: Number(createForm.display_order),
      name: createForm.name,
      category: createForm.category,
      playing_dims: createForm.playing_dims,
      build_dims: createForm.build_dims,
      playing_l_ft: num(createForm.playing_l_ft),
      playing_w_ft: num(createForm.playing_w_ft),
      build_l_ft: num(createForm.build_l_ft),
      build_w_ft: num(createForm.build_w_ft),
      min_clear_height_ft: num(createForm.min_clear_height_ft),
      governing_body: createForm.governing_body,
      source_citation: createForm.source_citation || null,
    });
    setCreateForm(emptySportForm());
    setCreating(false);
  });

  function startEdit(sport) {
    setEditingId(sport.id);
    setEditForm({ ...sport });
  }

  const handleSaveEdit = onAction(async () => {
    await updateSport(token, editingId, {
      display_order: Number(editForm.display_order),
      name: editForm.name,
      category: editForm.category,
      playing_dims: editForm.playing_dims,
      build_dims: editForm.build_dims,
      playing_l_ft: num(editForm.playing_l_ft),
      playing_w_ft: num(editForm.playing_w_ft),
      build_l_ft: num(editForm.build_l_ft),
      build_w_ft: num(editForm.build_w_ft),
      min_clear_height_ft: num(editForm.min_clear_height_ft),
      governing_body: editForm.governing_body,
      source_citation: editForm.source_citation || null,
    });
    setEditingId(null);
  });

  const toggleActive = onAction(async (sport) => updateSport(token, sport.id, { is_active: !sport.is_active }));

  return (
    <div className="bg-white shadow rounded-lg p-6 space-y-3">
      {sports.map((s) =>
        editingId === s.id ? (
          <div key={s.id} className="border border-blue-300 rounded p-3 space-y-2 text-sm bg-blue-50">
            <div className="grid grid-cols-3 gap-2">
              <LabeledInput label="Name" value={editForm.name} onChange={(v) => setEditForm((f) => ({ ...f, name: v }))} />
              <LabeledInput
                label="Order"
                type="number"
                value={editForm.display_order}
                onChange={(v) => setEditForm((f) => ({ ...f, display_order: v }))}
              />
              <LabeledSelect
                label="Category"
                value={editForm.category}
                options={SPORT_CATEGORIES}
                onChange={(v) => setEditForm((f) => ({ ...f, category: v }))}
              />
            </div>
            <div className="grid grid-cols-2 gap-2">
              <LabeledInput
                label="Playing dims"
                value={editForm.playing_dims}
                onChange={(v) => setEditForm((f) => ({ ...f, playing_dims: v }))}
              />
              <LabeledInput
                label="Build dims"
                value={editForm.build_dims}
                onChange={(v) => setEditForm((f) => ({ ...f, build_dims: v }))}
              />
            </div>
            <div className="grid grid-cols-4 gap-2">
              <LabeledInput
                label="Playing L (ft)"
                type="number"
                value={editForm.playing_l_ft ?? ""}
                onChange={(v) => setEditForm((f) => ({ ...f, playing_l_ft: v }))}
              />
              <LabeledInput
                label="Playing W (ft)"
                type="number"
                value={editForm.playing_w_ft ?? ""}
                onChange={(v) => setEditForm((f) => ({ ...f, playing_w_ft: v }))}
              />
              <LabeledInput
                label="Build L (ft)"
                type="number"
                value={editForm.build_l_ft ?? ""}
                onChange={(v) => setEditForm((f) => ({ ...f, build_l_ft: v }))}
              />
              <LabeledInput
                label="Build W (ft)"
                type="number"
                value={editForm.build_w_ft ?? ""}
                onChange={(v) => setEditForm((f) => ({ ...f, build_w_ft: v }))}
              />
            </div>
            <div className="grid grid-cols-3 gap-2">
              <LabeledInput
                label="Min clear height (ft)"
                type="number"
                value={editForm.min_clear_height_ft ?? ""}
                onChange={(v) => setEditForm((f) => ({ ...f, min_clear_height_ft: v }))}
              />
              <LabeledInput
                label="Governing body"
                value={editForm.governing_body}
                onChange={(v) => setEditForm((f) => ({ ...f, governing_body: v }))}
              />
              <LabeledInput
                label="Source citation"
                value={editForm.source_citation ?? ""}
                onChange={(v) => setEditForm((f) => ({ ...f, source_citation: v }))}
              />
            </div>
            <div className="flex gap-2">
              <button onClick={handleSaveEdit} className="bg-blue-600 text-white text-xs rounded px-3 py-1 hover:bg-blue-700">
                Save
              </button>
              <button onClick={() => setEditingId(null)} className="text-xs text-gray-500 hover:underline">
                Cancel
              </button>
            </div>
          </div>
        ) : (
          <div
            key={s.id}
            className={`flex flex-wrap items-center justify-between gap-2 text-sm border rounded px-3 py-2 ${
              s.is_active ? "border-gray-200" : "border-gray-200 bg-gray-50 opacity-60"
            }`}
          >
            <span>
              <span className="text-gray-400 font-mono text-xs">#{s.display_order}</span>{" "}
              <span className="font-medium">{s.name}</span>{" "}
              <span className="text-gray-400 text-xs">({s.key})</span> · {s.category} · {s.governing_body}
              {!s.is_active && <span className="text-gray-400"> · inactive</span>}
            </span>
            <div className="flex items-center gap-3">
              <button onClick={() => startEdit(s)} className="text-blue-600 hover:underline text-xs">
                Edit
              </button>
              <button onClick={() => toggleActive(s)} className="text-gray-500 hover:underline text-xs">
                {s.is_active ? "Deactivate" : "Reactivate"}
              </button>
            </div>
          </div>
        )
      )}

      {creating ? (
        <form onSubmit={handleCreate} className="border border-green-300 rounded p-3 space-y-2 text-sm bg-green-50">
          <div className="grid grid-cols-3 gap-2">
            <LabeledInput label="Key (unique, immutable)" value={createForm.key} onChange={(v) => setCreateForm((f) => ({ ...f, key: v }))} required />
            <LabeledInput label="Order" type="number" value={createForm.display_order} onChange={(v) => setCreateForm((f) => ({ ...f, display_order: v }))} required />
            <LabeledSelect label="Category" value={createForm.category} options={SPORT_CATEGORIES} onChange={(v) => setCreateForm((f) => ({ ...f, category: v }))} />
          </div>
          <LabeledInput label="Name" value={createForm.name} onChange={(v) => setCreateForm((f) => ({ ...f, name: v }))} required />
          <div className="grid grid-cols-2 gap-2">
            <LabeledInput label="Playing dims" value={createForm.playing_dims} onChange={(v) => setCreateForm((f) => ({ ...f, playing_dims: v }))} required />
            <LabeledInput label="Build dims" value={createForm.build_dims} onChange={(v) => setCreateForm((f) => ({ ...f, build_dims: v }))} required />
          </div>
          <div className="grid grid-cols-4 gap-2">
            <LabeledInput label="Playing L (ft)" type="number" value={createForm.playing_l_ft} onChange={(v) => setCreateForm((f) => ({ ...f, playing_l_ft: v }))} />
            <LabeledInput label="Playing W (ft)" type="number" value={createForm.playing_w_ft} onChange={(v) => setCreateForm((f) => ({ ...f, playing_w_ft: v }))} />
            <LabeledInput label="Build L (ft)" type="number" value={createForm.build_l_ft} onChange={(v) => setCreateForm((f) => ({ ...f, build_l_ft: v }))} />
            <LabeledInput label="Build W (ft)" type="number" value={createForm.build_w_ft} onChange={(v) => setCreateForm((f) => ({ ...f, build_w_ft: v }))} />
          </div>
          <div className="grid grid-cols-3 gap-2">
            <LabeledInput label="Min clear height (ft)" type="number" value={createForm.min_clear_height_ft} onChange={(v) => setCreateForm((f) => ({ ...f, min_clear_height_ft: v }))} />
            <LabeledInput label="Governing body" value={createForm.governing_body} onChange={(v) => setCreateForm((f) => ({ ...f, governing_body: v }))} required />
            <LabeledInput label="Source citation" value={createForm.source_citation} onChange={(v) => setCreateForm((f) => ({ ...f, source_citation: v }))} />
          </div>
          <div className="flex gap-2">
            <button type="submit" className="bg-green-600 text-white text-xs rounded px-3 py-1 hover:bg-green-700">
              Add sport
            </button>
            <button type="button" onClick={() => setCreating(false)} className="text-xs text-gray-500 hover:underline">
              Cancel
            </button>
          </div>
          <p className="text-[11px] text-gray-400">
            A brand-new sport gets no Base/Structure/Flooring/Lighting recommendation until this app's
            recommendation tables are extended for its key -- same as any of the 30 seeded sports not covered by
            a given table today.
          </p>
        </form>
      ) : (
        <button onClick={() => setCreating(true)} className="text-sm text-blue-600 hover:underline">
          + Add sport
        </button>
      )}
    </div>
  );
}

function ScopeItemsTab({ token, scopeItems, onAction }) {
  const [editingId, setEditingId] = useState(null);
  const [editForm, setEditForm] = useState(null);
  const [creating, setCreating] = useState(false);
  const [createForm, setCreateForm] = useState(emptyScopeItemForm());

  const handleCreate = onAction(async (e) => {
    e.preventDefault();
    await createScopeItem(token, {
      key: createForm.key,
      display_order: Number(createForm.display_order),
      group: createForm.group,
      name: createForm.name,
    });
    setCreateForm(emptyScopeItemForm());
    setCreating(false);
  });

  function startEdit(item) {
    setEditingId(item.id);
    setEditForm({ ...item });
  }

  const handleSaveEdit = onAction(async () => {
    await updateScopeItem(token, editingId, {
      display_order: Number(editForm.display_order),
      group: editForm.group,
      name: editForm.name,
    });
    setEditingId(null);
  });

  const toggleActive = onAction(async (item) => updateScopeItem(token, item.id, { is_active: !item.is_active }));

  return (
    <div className="bg-white shadow rounded-lg p-6 space-y-3">
      {scopeItems.map((i) =>
        editingId === i.id ? (
          <div key={i.id} className="border border-blue-300 rounded p-3 space-y-2 text-sm bg-blue-50">
            <div className="grid grid-cols-3 gap-2">
              <LabeledInput label="Name" value={editForm.name} onChange={(v) => setEditForm((f) => ({ ...f, name: v }))} />
              <LabeledInput
                label="Order"
                type="number"
                value={editForm.display_order}
                onChange={(v) => setEditForm((f) => ({ ...f, display_order: v }))}
              />
              <LabeledSelect
                label="Group"
                value={editForm.group}
                options={SCOPE_GROUPS}
                onChange={(v) => setEditForm((f) => ({ ...f, group: v }))}
              />
            </div>
            <div className="flex gap-2">
              <button onClick={handleSaveEdit} className="bg-blue-600 text-white text-xs rounded px-3 py-1 hover:bg-blue-700">
                Save
              </button>
              <button onClick={() => setEditingId(null)} className="text-xs text-gray-500 hover:underline">
                Cancel
              </button>
            </div>
          </div>
        ) : (
          <div
            key={i.id}
            className={`flex flex-wrap items-center justify-between gap-2 text-sm border rounded px-3 py-2 ${
              i.is_active ? "border-gray-200" : "border-gray-200 bg-gray-50 opacity-60"
            }`}
          >
            <span>
              <span className="text-gray-400 font-mono text-xs">#{i.display_order}</span>{" "}
              <span className="font-medium">{i.name}</span>{" "}
              <span className="text-gray-400 text-xs">({i.key})</span> · {i.group}
              {!i.is_active && <span className="text-gray-400"> · inactive</span>}
            </span>
            <div className="flex items-center gap-3">
              <button onClick={() => startEdit(i)} className="text-blue-600 hover:underline text-xs">
                Edit
              </button>
              <button onClick={() => toggleActive(i)} className="text-gray-500 hover:underline text-xs">
                {i.is_active ? "Deactivate" : "Reactivate"}
              </button>
            </div>
          </div>
        )
      )}

      {creating ? (
        <form onSubmit={handleCreate} className="border border-green-300 rounded p-3 space-y-2 text-sm bg-green-50">
          <div className="grid grid-cols-3 gap-2">
            <LabeledInput label="Key (unique, immutable)" value={createForm.key} onChange={(v) => setCreateForm((f) => ({ ...f, key: v }))} required />
            <LabeledInput label="Order" type="number" value={createForm.display_order} onChange={(v) => setCreateForm((f) => ({ ...f, display_order: v }))} required />
            <LabeledSelect label="Group" value={createForm.group} options={SCOPE_GROUPS} onChange={(v) => setCreateForm((f) => ({ ...f, group: v }))} />
          </div>
          <LabeledInput label="Name" value={createForm.name} onChange={(v) => setCreateForm((f) => ({ ...f, name: v }))} required />
          <div className="flex gap-2">
            <button type="submit" className="bg-green-600 text-white text-xs rounded px-3 py-1 hover:bg-green-700">
              Add scope item
            </button>
            <button type="button" onClick={() => setCreating(false)} className="text-xs text-gray-500 hover:underline">
              Cancel
            </button>
          </div>
        </form>
      ) : (
        <button onClick={() => setCreating(true)} className="text-sm text-blue-600 hover:underline">
          + Add scope item
        </button>
      )}
    </div>
  );
}

function LabeledInput({ label, value, onChange, type = "text", required = false }) {
  return (
    <label className="text-xs text-gray-500 space-y-0.5 block">
      {label}
      <input
        type={type}
        value={value}
        required={required}
        onChange={(e) => onChange(e.target.value)}
        className="mt-0.5 w-full rounded border border-gray-300 px-2 py-1 text-sm"
      />
    </label>
  );
}

function LabeledSelect({ label, value, options, onChange }) {
  return (
    <label className="text-xs text-gray-500 space-y-0.5 block">
      {label}
      <select value={value} onChange={(e) => onChange(e.target.value)} className="mt-0.5 w-full rounded border border-gray-300 px-2 py-1 text-sm">
        {options.map((o) => (
          <option key={o} value={o}>
            {o}
          </option>
        ))}
      </select>
    </label>
  );
}
