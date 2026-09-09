import { useEffect, useState } from "react";
import {
  createAccessoryCatalogItem,
  createHub,
  createScopeItem,
  createSport,
  deleteSportMarginPolicy,
  listAccessoryCatalog,
  listHubs,
  listPackageContents,
  listScopeItems,
  listSportMarginPolicies,
  listSports,
  updateAccessoryCatalogItem,
  updateHub,
  updateScopeItem,
  updateSport,
  upsertPackageContent,
  upsertSportMarginPolicy,
} from "./api";

const SPORT_CATEGORIES = ["indoor", "outdoor"];
const SCOPE_GROUPS = ["civil", "electrical", "water", "external", "services", "maintenance"];
const PACKAGE_TIERS = ["budget", "standard", "premium"];

function emptyPackageContentForm() {
  return { flooring_description: "", structure_description: "", lighting_description: "", scope_description: "", warranty_years: "" };
}

function emptyAccessoryItemForm() {
  return { item_name: "", unit: "nos", quantity_per_court: "1" };
}

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

function emptyHubForm() {
  return { name: "", city: "", state_code: "" };
}

function num(v) {
  if (v === "" || v === null || v === undefined) return null;
  const n = Number(v);
  return Number.isNaN(n) ? null : n;
}

export default function SportsScopeAdmin({ token, onBack }) {
  const [tab, setTab] = useState("sports"); // "sports" | "scope" | "margins" | "packages" | "hubs" | "accessories"
  const [sports, setSports] = useState([]);
  const [scopeItems, setScopeItems] = useState([]);
  const [sportMarginPolicies, setSportMarginPolicies] = useState([]);
  const [packageContents, setPackageContents] = useState([]);
  const [hubs, setHubs] = useState([]);
  const [accessoryCatalog, setAccessoryCatalog] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  function load() {
    return Promise.all([
      listSports(token, true), listScopeItems(token, true), listSportMarginPolicies(token),
      listPackageContents(token), listHubs(token, true), listAccessoryCatalog(token, undefined, true),
    ]).then(([s, i, m, p, h, a]) => {
      setSports(s);
      setScopeItems(i);
      setSportMarginPolicies(m);
      setPackageContents(p);
      setHubs(h);
      setAccessoryCatalog(a);
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
          <button
            onClick={() => setTab("margins")}
            className={`text-sm rounded px-3 py-1 ${tab === "margins" ? "bg-blue-600 text-white" : "bg-gray-100 text-gray-700"}`}
          >
            Margin floor overrides ({sportMarginPolicies.length})
          </button>
          <button
            onClick={() => setTab("packages")}
            className={`text-sm rounded px-3 py-1 ${tab === "packages" ? "bg-blue-600 text-white" : "bg-gray-100 text-gray-700"}`}
          >
            Package content ({packageContents.length})
          </button>
          <button
            onClick={() => setTab("hubs")}
            className={`text-sm rounded px-3 py-1 ${tab === "hubs" ? "bg-blue-600 text-white" : "bg-gray-100 text-gray-700"}`}
          >
            Hubs ({hubs.length})
          </button>
          <button
            onClick={() => setTab("accessories")}
            className={`text-sm rounded px-3 py-1 ${tab === "accessories" ? "bg-blue-600 text-white" : "bg-gray-100 text-gray-700"}`}
          >
            Accessory catalog ({accessoryCatalog.length})
          </button>
        </div>
      </div>

      {tab === "sports" && <SportsTab token={token} sports={sports} onAction={withErrorHandling} />}
      {tab === "scope" && <ScopeItemsTab token={token} scopeItems={scopeItems} onAction={withErrorHandling} />}
      {tab === "margins" && (
        <MarginFloorsTab
          token={token}
          sports={sports}
          sportMarginPolicies={sportMarginPolicies}
          onAction={withErrorHandling}
        />
      )}
      {tab === "packages" && (
        <PackageContentsTab token={token} sports={sports} packageContents={packageContents} onAction={withErrorHandling} />
      )}
      {tab === "hubs" && <HubsTab token={token} hubs={hubs} onAction={withErrorHandling} />}
      {tab === "accessories" && (
        <AccessoryCatalogTab token={token} sports={sports} accessoryCatalog={accessoryCatalog} onAction={withErrorHandling} />
      )}
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

function MarginFloorsTab({ token, sports, sportMarginPolicies, onAction }) {
  const [editingSportId, setEditingSportId] = useState(null);
  const [editValue, setEditValue] = useState("");

  const bySportId = Object.fromEntries(sportMarginPolicies.map((p) => [p.sport_id, p]));

  function startEdit(sport) {
    setEditingSportId(sport.id);
    setEditValue(bySportId[sport.id] ? String(bySportId[sport.id].floor_margin_percent) : "");
  }

  const handleSave = onAction(async (sportId) => {
    await upsertSportMarginPolicy(token, sportId, { floor_margin_percent: Number(editValue) });
    setEditingSportId(null);
  });

  const handleRemove = onAction(async (sportId) => deleteSportMarginPolicy(token, sportId));

  return (
    <div className="bg-white shadow rounded-lg p-6 space-y-3">
      <p className="text-xs text-gray-400">
        K.2: "A sport-type floor (e.g. Pool 15%, PEB 14%) replaces the client floor for that sport when the
        Director has defined one." A sport with no override here simply uses its project's client-type floor.
        A multi-sport Quotation blends each included sport's own effective floor as a cost-weighted average.
      </p>
      {sports.map((s) => {
        const override = bySportId[s.id];
        return editingSportId === s.id ? (
          <div key={s.id} className="flex items-center gap-2 text-sm border border-blue-300 bg-blue-50 rounded px-3 py-2">
            <span className="flex-1">
              <span className="font-medium">{s.name}</span>{" "}
              <span className="text-gray-400 text-xs">({s.key})</span>
            </span>
            <input
              type="number"
              step="0.01"
              min="0"
              max="99.99"
              value={editValue}
              onChange={(e) => setEditValue(e.target.value)}
              className="w-24 rounded border border-gray-300 px-2 py-1 text-sm"
            />
            <span className="text-xs text-gray-400">%</span>
            <button onClick={() => handleSave(s.id)} className="bg-blue-600 text-white text-xs rounded px-3 py-1 hover:bg-blue-700">
              Save
            </button>
            <button onClick={() => setEditingSportId(null)} className="text-xs text-gray-500 hover:underline">
              Cancel
            </button>
          </div>
        ) : (
          <div key={s.id} className="flex items-center justify-between gap-2 text-sm border border-gray-200 rounded px-3 py-2">
            <span>
              <span className="font-medium">{s.name}</span>{" "}
              <span className="text-gray-400 text-xs">({s.key})</span>
              {override ? (
                <span className="ml-2 text-blue-700 font-medium">{override.floor_margin_percent}% floor override</span>
              ) : (
                <span className="ml-2 text-gray-400">uses client-type floor</span>
              )}
            </span>
            <div className="flex items-center gap-3">
              <button onClick={() => startEdit(s)} className="text-blue-600 hover:underline text-xs">
                {override ? "Edit" : "Set override"}
              </button>
              {override && (
                <button onClick={() => handleRemove(s.id)} className="text-gray-500 hover:underline text-xs">
                  Remove
                </button>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function AccessoryCatalogTab({ token, sports, accessoryCatalog, onAction }) {
  const [addingForSportId, setAddingForSportId] = useState(null);
  const [addForm, setAddForm] = useState(emptyAccessoryItemForm());
  const [editingId, setEditingId] = useState(null);
  const [editForm, setEditForm] = useState(null);

  const bySportId = {};
  for (const item of accessoryCatalog) {
    (bySportId[item.sport_id] ??= []).push(item);
  }

  const handleCreate = onAction(async (sportId) => {
    await createAccessoryCatalogItem(token, {
      sport_id: sportId,
      item_name: addForm.item_name,
      unit: addForm.unit,
      quantity_per_court: Number(addForm.quantity_per_court),
    });
    setAddForm(emptyAccessoryItemForm());
    setAddingForSportId(null);
  });

  function startEdit(item) {
    setEditingId(item.id);
    setEditForm({ item_name: item.item_name, unit: item.unit, quantity_per_court: String(item.quantity_per_court) });
  }

  const handleSaveEdit = onAction(async () => {
    await updateAccessoryCatalogItem(token, editingId, {
      item_name: editForm.item_name,
      unit: editForm.unit,
      quantity_per_court: Number(editForm.quantity_per_court),
    });
    setEditingId(null);
  });

  const toggleActive = onAction(async (item) => updateAccessoryCatalogItem(token, item.id, { is_active: !item.is_active }));

  return (
    <div className="bg-white shadow rounded-lg p-6 space-y-3">
      <p className="text-xs text-gray-400 -mt-1 mb-2">
        Part I / Module 9: which accessory (and how many per court/lane) is auto-added for a sport's take-off --
        formerly a hardcoded Python/JS dict, now Director-editable here. A sport with no rows below still works via
        the "custom items" fallback on the Cost Sheet's Accessories form.
      </p>
      {sports.map((sport) => {
        const items = bySportId[sport.id] ?? [];
        return (
          <div key={sport.id} className="border border-gray-200 rounded p-3 space-y-2">
            <p className="text-sm font-medium">
              {sport.name} <span className="text-gray-400 text-xs font-normal">({sport.key})</span>
            </p>
            {items.length === 0 && <p className="text-xs text-gray-400">No catalog items yet.</p>}
            {items.map((item) =>
              editingId === item.id ? (
                <div key={item.id} className="border border-blue-300 bg-blue-50 rounded p-2 space-y-2 text-sm">
                  <div className="grid grid-cols-3 gap-2">
                    <LabeledInput label="Item name" value={editForm.item_name} onChange={(v) => setEditForm((f) => ({ ...f, item_name: v }))} />
                    <LabeledInput label="Unit" value={editForm.unit} onChange={(v) => setEditForm((f) => ({ ...f, unit: v }))} />
                    <LabeledInput
                      label="Qty per court"
                      type="number"
                      value={editForm.quantity_per_court}
                      onChange={(v) => setEditForm((f) => ({ ...f, quantity_per_court: v }))}
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
                  key={item.id}
                  className={`flex items-center justify-between gap-2 text-sm border rounded px-3 py-1.5 ${
                    item.is_active ? "border-gray-200" : "border-gray-200 bg-gray-50 opacity-60"
                  }`}
                >
                  <span>
                    {item.item_name} <span className="text-gray-400 text-xs">({item.quantity_per_court} {item.unit}/court)</span>
                    {!item.is_active && <span className="text-gray-400"> · inactive</span>}
                  </span>
                  <div className="flex items-center gap-3">
                    <button onClick={() => startEdit(item)} className="text-blue-600 hover:underline text-xs">
                      Edit
                    </button>
                    <button onClick={() => toggleActive(item)} className="text-gray-500 hover:underline text-xs">
                      {item.is_active ? "Deactivate" : "Reactivate"}
                    </button>
                  </div>
                </div>
              )
            )}

            {addingForSportId === sport.id ? (
              <div className="border border-green-300 bg-green-50 rounded p-2 space-y-2 text-sm">
                <div className="grid grid-cols-3 gap-2">
                  <LabeledInput label="Item name" value={addForm.item_name} onChange={(v) => setAddForm((f) => ({ ...f, item_name: v }))} />
                  <LabeledInput label="Unit" value={addForm.unit} onChange={(v) => setAddForm((f) => ({ ...f, unit: v }))} />
                  <LabeledInput
                    label="Qty per court"
                    type="number"
                    value={addForm.quantity_per_court}
                    onChange={(v) => setAddForm((f) => ({ ...f, quantity_per_court: v }))}
                  />
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={() => handleCreate(sport.id)}
                    className="bg-green-600 text-white text-xs rounded px-3 py-1 hover:bg-green-700"
                  >
                    Add item
                  </button>
                  <button
                    onClick={() => {
                      setAddingForSportId(null);
                      setAddForm(emptyAccessoryItemForm());
                    }}
                    className="text-xs text-gray-500 hover:underline"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            ) : (
              <button onClick={() => setAddingForSportId(sport.id)} className="text-xs text-blue-600 hover:underline">
                + Add item
              </button>
            )}
          </div>
        );
      })}
    </div>
  );
}

function HubsTab({ token, hubs, onAction }) {
  const [editingId, setEditingId] = useState(null);
  const [editForm, setEditForm] = useState(null);
  const [creating, setCreating] = useState(false);
  const [createForm, setCreateForm] = useState(emptyHubForm());

  const handleCreate = onAction(async (e) => {
    e.preventDefault();
    await createHub(token, createForm);
    setCreateForm(emptyHubForm());
    setCreating(false);
  });

  function startEdit(hub) {
    setEditingId(hub.id);
    setEditForm({ ...hub });
  }

  const handleSaveEdit = onAction(async () => {
    await updateHub(token, editingId, { name: editForm.name, city: editForm.city, state_code: editForm.state_code });
    setEditingId(null);
  });

  const toggleActive = onAction(async (hub) => updateHub(token, hub.id, { is_active: !hub.is_active }));

  return (
    <div className="bg-white shadow rounded-lg p-6 space-y-3">
      <p className="text-xs text-gray-400 -mt-1 mb-2">
        Part O HUBS / B.1 field #4: NestaPrime's own dispatch/depot locations -- the PM picks one when setting up a
        project and enters the km distance from it (Phase 1 is manual km; PIN-code auto-lookup is a Phase 7
        integration).
      </p>
      {hubs.map((h) =>
        editingId === h.id ? (
          <div key={h.id} className="border border-blue-300 rounded p-3 space-y-2 text-sm bg-blue-50">
            <div className="grid grid-cols-3 gap-2">
              <LabeledInput label="Name" value={editForm.name} onChange={(v) => setEditForm((f) => ({ ...f, name: v }))} />
              <LabeledInput label="City" value={editForm.city} onChange={(v) => setEditForm((f) => ({ ...f, city: v }))} />
              <LabeledInput
                label="State code"
                value={editForm.state_code}
                onChange={(v) => setEditForm((f) => ({ ...f, state_code: v }))}
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
            key={h.id}
            className={`flex flex-wrap items-center justify-between gap-2 text-sm border rounded px-3 py-2 ${
              h.is_active ? "border-gray-200" : "border-gray-200 bg-gray-50 opacity-60"
            }`}
          >
            <span>
              <span className="font-medium">{h.name}</span>{" "}
              <span className="text-gray-400 text-xs">
                ({h.city}, {h.state_code})
              </span>
              {!h.is_active && <span className="text-gray-400"> · inactive</span>}
            </span>
            <div className="flex items-center gap-3">
              <button onClick={() => startEdit(h)} className="text-blue-600 hover:underline text-xs">
                Edit
              </button>
              <button onClick={() => toggleActive(h)} className="text-gray-500 hover:underline text-xs">
                {h.is_active ? "Deactivate" : "Reactivate"}
              </button>
            </div>
          </div>
        )
      )}

      {creating ? (
        <form onSubmit={handleCreate} className="border border-green-300 rounded p-3 space-y-2 text-sm bg-green-50">
          <div className="grid grid-cols-3 gap-2">
            <LabeledInput label="Name" value={createForm.name} onChange={(v) => setCreateForm((f) => ({ ...f, name: v }))} required />
            <LabeledInput label="City" value={createForm.city} onChange={(v) => setCreateForm((f) => ({ ...f, city: v }))} required />
            <LabeledInput
              label="State code"
              value={createForm.state_code}
              onChange={(v) => setCreateForm((f) => ({ ...f, state_code: v }))}
              required
            />
          </div>
          <div className="flex gap-2">
            <button type="submit" className="bg-green-600 text-white text-xs rounded px-3 py-1 hover:bg-green-700">
              Add hub
            </button>
            <button type="button" onClick={() => setCreating(false)} className="text-xs text-gray-500 hover:underline">
              Cancel
            </button>
          </div>
        </form>
      ) : (
        <button onClick={() => setCreating(true)} className="text-sm text-blue-600 hover:underline">
          + Add hub
        </button>
      )}
    </div>
  );
}

function PackageContentsTab({ token, sports, packageContents, onAction }) {
  const [editingKey, setEditingKey] = useState(null); // `${sportId}:${tier}`
  const [editForm, setEditForm] = useState(emptyPackageContentForm());

  const byKey = Object.fromEntries(packageContents.map((p) => [`${p.sport_id}:${p.tier}`, p]));

  function startEdit(sportId, tier) {
    const key = `${sportId}:${tier}`;
    const existing = byKey[key];
    setEditingKey(key);
    setEditForm(
      existing
        ? {
            flooring_description: existing.flooring_description,
            structure_description: existing.structure_description,
            lighting_description: existing.lighting_description,
            scope_description: existing.scope_description,
            warranty_years: existing.warranty_years ?? "",
          }
        : emptyPackageContentForm()
    );
  }

  const handleSave = onAction(async (sportId, tier) => {
    await upsertPackageContent(token, sportId, tier, {
      flooring_description: editForm.flooring_description,
      structure_description: editForm.structure_description,
      lighting_description: editForm.lighting_description,
      scope_description: editForm.scope_description,
      warranty_years: editForm.warranty_years === "" ? null : Number(editForm.warranty_years),
    });
    setEditingKey(null);
  });

  return (
    <div className="bg-white shadow rounded-lg p-6 space-y-4">
      <p className="text-xs text-gray-400">
        Part O PACKAGES / Q.1: "Packages | Budget/Standard/Premium contents | Per sport | Director." This is the
        content the Estimate PDF's "Package content" section prints for each option -- flooring, structure,
        lighting, what's included (one line per bullet), and warranty duration. Sales still customises items on the
        actual Estimate; this is only the Director-set default per sport and tier.
      </p>
      {sports.map((sport) => (
        <div key={sport.id} className="border border-gray-200 rounded p-3 space-y-2">
          <p className="text-sm font-medium">
            {sport.name} <span className="text-gray-400 text-xs font-normal">({sport.key})</span>
          </p>
          <div className="flex flex-wrap gap-2">
            {PACKAGE_TIERS.map((tier) => {
              const key = `${sport.id}:${tier}`;
              const configured = Boolean(byKey[key]);
              return (
                <button
                  key={tier}
                  onClick={() => startEdit(sport.id, tier)}
                  className={`text-xs rounded px-3 py-1 border ${
                    configured ? "border-blue-300 bg-blue-50 text-blue-700" : "border-gray-200 text-gray-500"
                  }`}
                >
                  {tier.charAt(0).toUpperCase() + tier.slice(1)} {configured ? "✓" : "(not set)"}
                </button>
              );
            })}
          </div>
          {editingKey?.startsWith(`${sport.id}:`) && (
            <div className="border border-blue-300 bg-blue-50 rounded p-3 space-y-2 text-sm">
              <p className="text-xs font-medium text-blue-800">
                Editing {editingKey.split(":")[1]} tier
              </p>
              <LabeledInput
                label="Flooring"
                value={editForm.flooring_description}
                onChange={(v) => setEditForm((f) => ({ ...f, flooring_description: v }))}
              />
              <LabeledInput
                label="Structure"
                value={editForm.structure_description}
                onChange={(v) => setEditForm((f) => ({ ...f, structure_description: v }))}
              />
              <LabeledInput
                label="Lighting"
                value={editForm.lighting_description}
                onChange={(v) => setEditForm((f) => ({ ...f, lighting_description: v }))}
              />
              <label className="text-xs text-gray-500 space-y-0.5 block">
                Scope (one item per line)
                <textarea
                  value={editForm.scope_description}
                  onChange={(e) => setEditForm((f) => ({ ...f, scope_description: e.target.value }))}
                  rows={3}
                  className="mt-0.5 w-full rounded border border-gray-300 px-2 py-1 text-sm"
                />
              </label>
              <div className="w-32">
                <LabeledInput
                  label="Warranty (years)"
                  type="number"
                  value={editForm.warranty_years}
                  onChange={(v) => setEditForm((f) => ({ ...f, warranty_years: v }))}
                />
              </div>
              <div className="flex gap-2">
                <button
                  onClick={() => handleSave(sport.id, editingKey.split(":")[1])}
                  className="bg-blue-600 text-white text-xs rounded px-3 py-1 hover:bg-blue-700"
                >
                  Save
                </button>
                <button onClick={() => setEditingKey(null)} className="text-xs text-gray-500 hover:underline">
                  Cancel
                </button>
              </div>
            </div>
          )}
        </div>
      ))}
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
