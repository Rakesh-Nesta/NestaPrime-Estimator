import { useEffect, useState } from "react";
import {
  createAccessoryCatalogItem,
  createHub,
  createNettingGrade,
  createScopeItem,
  createSport,
  createVehicleClass,
  deleteSportMarginPolicy,
  deleteSportPoleCount,
  listAccessoryCatalog,
  listFlooringGuides,
  listHubs,
  listLightingLuxStandards,
  listNettingGrades,
  listPackageContents,
  listScopeItems,
  listSportMarginPolicies,
  listSportPoleCounts,
  listSports,
  listVehicleClasses,
  updateAccessoryCatalogItem,
  updateHub,
  updateNettingGrade,
  updateScopeItem,
  updateSport,
  updateVehicleClass,
  upsertFlooringGuide,
  upsertLightingLuxStandard,
  upsertPackageContent,
  upsertSportMarginPolicy,
  upsertSportPoleCount,
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

function emptyNettingGradeForm() {
  return { key: "", name: "", material: "", twine: "", mesh: "", uv_stabilized: "", typical_use: "", rate_per_sqm: "" };
}

function emptyVehicleClassForm() {
  return { key: "", name: "", truck_capacity_tonnes: "", rate_per_km: "" };
}

function emptyFlooringGuideForm() {
  return { primary_spec: "", secondary_spec: "", budget_spec: "", rationale: "" };
}

function emptyLuxStandardForm() {
  return { lux_practice: "", lux_match: "", lux_tournament: "" };
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
  const [nettingGrades, setNettingGrades] = useState([]);
  const [vehicleClasses, setVehicleClasses] = useState([]);
  const [flooringGuides, setFlooringGuides] = useState([]);
  const [luxStandards, setLuxStandards] = useState([]);
  const [poleCounts, setPoleCounts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  function load() {
    return Promise.all([
      listSports(token, true), listScopeItems(token, true), listSportMarginPolicies(token),
      listPackageContents(token), listHubs(token, true), listAccessoryCatalog(token, undefined, true),
      listNettingGrades(token, true), listVehicleClasses(token, true),
      listFlooringGuides(token), listLightingLuxStandards(token), listSportPoleCounts(token),
    ]).then(([s, i, m, p, h, a, n, v, fg, lux, pole]) => {
      setSports(s);
      setScopeItems(i);
      setSportMarginPolicies(m);
      setPackageContents(p);
      setHubs(h);
      setAccessoryCatalog(a);
      setNettingGrades(n);
      setVehicleClasses(v);
      setFlooringGuides(fg);
      setLuxStandards(lux);
      setPoleCounts(pole);
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
    return <p className="text-center text-text-secondary mt-10">Loading Sports &amp; Scope admin…</p>;
  }

  return (
    <div className="max-w-3xl mx-auto mt-8 mb-10 space-y-6">
      <div className="bg-surface shadow rounded-lg p-6">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-text-primary">Sports &amp; Scope master admin</h2>
          {onBack && (
            <button onClick={onBack} className="text-sm text-gold hover:underline">
              &larr; Back
            </button>
          )}
        </div>
        <p className="text-xs text-text-secondary mt-1">
          Part C (Sport master list) and Part I (Additional Scope Checklist) were seeded once and read-only in
          Phase 1b -- this screen closes that gap. Director-only; deactivating retires an item without breaking
          existing projects that already reference it. A sport's key can't be changed once created -- every
          recommendation formula elsewhere in the app matches on it.
        </p>
        {error && <p className="text-sm text-red-400 mt-2">{error}</p>}
        <div className="flex gap-2 mt-4">
          <button
            onClick={() => setTab("sports")}
            className={`text-sm rounded px-3 py-1 ${tab === "sports" ? "bg-gold text-base" : "bg-surface-raised text-text-secondary"}`}
          >
            Sports ({sports.length})
          </button>
          <button
            onClick={() => setTab("scope")}
            className={`text-sm rounded px-3 py-1 ${tab === "scope" ? "bg-gold text-base" : "bg-surface-raised text-text-secondary"}`}
          >
            Scope items ({scopeItems.length})
          </button>
          <button
            onClick={() => setTab("margins")}
            className={`text-sm rounded px-3 py-1 ${tab === "margins" ? "bg-gold text-base" : "bg-surface-raised text-text-secondary"}`}
          >
            Margin floor overrides ({sportMarginPolicies.length})
          </button>
          <button
            onClick={() => setTab("packages")}
            className={`text-sm rounded px-3 py-1 ${tab === "packages" ? "bg-gold text-base" : "bg-surface-raised text-text-secondary"}`}
          >
            Package content ({packageContents.length})
          </button>
          <button
            onClick={() => setTab("hubs")}
            className={`text-sm rounded px-3 py-1 ${tab === "hubs" ? "bg-gold text-base" : "bg-surface-raised text-text-secondary"}`}
          >
            Hubs ({hubs.length})
          </button>
          <button
            onClick={() => setTab("accessories")}
            className={`text-sm rounded px-3 py-1 ${tab === "accessories" ? "bg-gold text-base" : "bg-surface-raised text-text-secondary"}`}
          >
            Accessory catalog ({accessoryCatalog.length})
          </button>
          <button
            onClick={() => setTab("netting")}
            className={`text-sm rounded px-3 py-1 ${tab === "netting" ? "bg-gold text-base" : "bg-surface-raised text-text-secondary"}`}
          >
            Netting grades ({nettingGrades.length})
          </button>
          <button
            onClick={() => setTab("vehicles")}
            className={`text-sm rounded px-3 py-1 ${tab === "vehicles" ? "bg-gold text-base" : "bg-surface-raised text-text-secondary"}`}
          >
            Vehicle classes ({vehicleClasses.length})
          </button>
          <button
            onClick={() => setTab("flooring_guides")}
            className={`text-sm rounded px-3 py-1 ${tab === "flooring_guides" ? "bg-gold text-base" : "bg-surface-raised text-text-secondary"}`}
          >
            Flooring guides ({flooringGuides.length})
          </button>
          <button
            onClick={() => setTab("lighting_standards")}
            className={`text-sm rounded px-3 py-1 ${tab === "lighting_standards" ? "bg-gold text-base" : "bg-surface-raised text-text-secondary"}`}
          >
            Lighting standards ({luxStandards.length + poleCounts.length})
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
      {tab === "netting" && <NettingGradesTab token={token} nettingGrades={nettingGrades} onAction={withErrorHandling} />}
      {tab === "vehicles" && <VehicleClassesTab token={token} vehicleClasses={vehicleClasses} onAction={withErrorHandling} />}
      {tab === "flooring_guides" && (
        <FlooringGuidesTab token={token} sports={sports} flooringGuides={flooringGuides} onAction={withErrorHandling} />
      )}
      {tab === "lighting_standards" && (
        <LightingStandardsTab
          token={token}
          sports={sports}
          luxStandards={luxStandards}
          poleCounts={poleCounts}
          onAction={withErrorHandling}
        />
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
    <div className="bg-surface shadow rounded-lg p-6 space-y-3">
      {sports.map((s) =>
        editingId === s.id ? (
          <div key={s.id} className="border border-gold rounded p-3 space-y-2 text-sm bg-gold-muted">
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
              <button onClick={handleSaveEdit} className="bg-gold text-base text-xs rounded px-3 py-1 hover:bg-gold-hover">
                Save
              </button>
              <button onClick={() => setEditingId(null)} className="text-xs text-text-secondary hover:underline">
                Cancel
              </button>
            </div>
          </div>
        ) : (
          <div
            key={s.id}
            className={`flex flex-wrap items-center justify-between gap-2 text-sm border rounded px-3 py-2 ${
              s.is_active ? "border-border-dark" : "border-border-dark bg-surface-raised opacity-60"
            }`}
          >
            <span>
              <span className="text-text-secondary font-mono text-xs">#{s.display_order}</span>{" "}
              <span className="font-medium">{s.name}</span>{" "}
              <span className="text-text-secondary text-xs">({s.key})</span> · {s.category} · {s.governing_body}
              {!s.is_active && <span className="text-text-secondary"> · inactive</span>}
            </span>
            <div className="flex items-center gap-3">
              <button onClick={() => startEdit(s)} className="text-gold hover:underline text-xs">
                Edit
              </button>
              <button onClick={() => toggleActive(s)} className="text-text-secondary hover:underline text-xs">
                {s.is_active ? "Deactivate" : "Reactivate"}
              </button>
            </div>
          </div>
        )
      )}

      {creating ? (
        <form onSubmit={handleCreate} className="border border-green-500/30 rounded p-3 space-y-2 text-sm bg-green-500/10">
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
            <button type="button" onClick={() => setCreating(false)} className="text-xs text-text-secondary hover:underline">
              Cancel
            </button>
          </div>
          <p className="text-[11px] text-text-secondary">
            A brand-new sport gets no Base/Structure/Flooring/Lighting recommendation until this app's
            recommendation tables are extended for its key -- same as any of the 30 seeded sports not covered by
            a given table today.
          </p>
        </form>
      ) : (
        <button onClick={() => setCreating(true)} className="text-sm text-gold hover:underline">
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
    <div className="bg-surface shadow rounded-lg p-6 space-y-3">
      {scopeItems.map((i) =>
        editingId === i.id ? (
          <div key={i.id} className="border border-gold rounded p-3 space-y-2 text-sm bg-gold-muted">
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
              <button onClick={handleSaveEdit} className="bg-gold text-base text-xs rounded px-3 py-1 hover:bg-gold-hover">
                Save
              </button>
              <button onClick={() => setEditingId(null)} className="text-xs text-text-secondary hover:underline">
                Cancel
              </button>
            </div>
          </div>
        ) : (
          <div
            key={i.id}
            className={`flex flex-wrap items-center justify-between gap-2 text-sm border rounded px-3 py-2 ${
              i.is_active ? "border-border-dark" : "border-border-dark bg-surface-raised opacity-60"
            }`}
          >
            <span>
              <span className="text-text-secondary font-mono text-xs">#{i.display_order}</span>{" "}
              <span className="font-medium">{i.name}</span>{" "}
              <span className="text-text-secondary text-xs">({i.key})</span> · {i.group}
              {!i.is_active && <span className="text-text-secondary"> · inactive</span>}
            </span>
            <div className="flex items-center gap-3">
              <button onClick={() => startEdit(i)} className="text-gold hover:underline text-xs">
                Edit
              </button>
              <button onClick={() => toggleActive(i)} className="text-text-secondary hover:underline text-xs">
                {i.is_active ? "Deactivate" : "Reactivate"}
              </button>
            </div>
          </div>
        )
      )}

      {creating ? (
        <form onSubmit={handleCreate} className="border border-green-500/30 rounded p-3 space-y-2 text-sm bg-green-500/10">
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
            <button type="button" onClick={() => setCreating(false)} className="text-xs text-text-secondary hover:underline">
              Cancel
            </button>
          </div>
        </form>
      ) : (
        <button onClick={() => setCreating(true)} className="text-sm text-gold hover:underline">
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
    <div className="bg-surface shadow rounded-lg p-6 space-y-3">
      <p className="text-xs text-text-secondary">
        K.2: "A sport-type floor (e.g. Pool 15%, PEB 14%) replaces the client floor for that sport when the
        Director has defined one." A sport with no override here simply uses its project's client-type floor.
        A multi-sport Quotation blends each included sport's own effective floor as a cost-weighted average.
      </p>
      {sports.map((s) => {
        const override = bySportId[s.id];
        return editingSportId === s.id ? (
          <div key={s.id} className="flex items-center gap-2 text-sm border border-gold bg-gold-muted rounded px-3 py-2">
            <span className="flex-1">
              <span className="font-medium">{s.name}</span>{" "}
              <span className="text-text-secondary text-xs">({s.key})</span>
            </span>
            <input
              type="number"
              step="0.01"
              min="0"
              max="99.99"
              value={editValue}
              onChange={(e) => setEditValue(e.target.value)}
              className="w-24 rounded border border-border-dark bg-surface-raised text-text-primary px-2 py-1 text-sm"
            />
            <span className="text-xs text-text-secondary">%</span>
            <button onClick={() => handleSave(s.id)} className="bg-gold text-base text-xs rounded px-3 py-1 hover:bg-gold-hover">
              Save
            </button>
            <button onClick={() => setEditingSportId(null)} className="text-xs text-text-secondary hover:underline">
              Cancel
            </button>
          </div>
        ) : (
          <div key={s.id} className="flex items-center justify-between gap-2 text-sm border border-border-dark rounded px-3 py-2">
            <span>
              <span className="font-medium">{s.name}</span>{" "}
              <span className="text-text-secondary text-xs">({s.key})</span>
              {override ? (
                <span className="ml-2 text-gold-hover font-medium">{override.floor_margin_percent}% floor override</span>
              ) : (
                <span className="ml-2 text-text-secondary">uses client-type floor</span>
              )}
            </span>
            <div className="flex items-center gap-3">
              <button onClick={() => startEdit(s)} className="text-gold hover:underline text-xs">
                {override ? "Edit" : "Set override"}
              </button>
              {override && (
                <button onClick={() => handleRemove(s.id)} className="text-text-secondary hover:underline text-xs">
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
    <div className="bg-surface shadow rounded-lg p-6 space-y-3">
      <p className="text-xs text-text-secondary -mt-1 mb-2">
        Part I / Module 9: which accessory (and how many per court/lane) is auto-added for a sport's take-off --
        formerly a hardcoded Python/JS dict, now Director-editable here. A sport with no rows below still works via
        the "custom items" fallback on the Cost Sheet's Accessories form.
      </p>
      {sports.map((sport) => {
        const items = bySportId[sport.id] ?? [];
        return (
          <div key={sport.id} className="border border-border-dark rounded p-3 space-y-2">
            <p className="text-sm font-medium">
              {sport.name} <span className="text-text-secondary text-xs font-normal">({sport.key})</span>
            </p>
            {items.length === 0 && <p className="text-xs text-text-secondary">No catalog items yet.</p>}
            {items.map((item) =>
              editingId === item.id ? (
                <div key={item.id} className="border border-gold bg-gold-muted rounded p-2 space-y-2 text-sm">
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
                    <button onClick={handleSaveEdit} className="bg-gold text-base text-xs rounded px-3 py-1 hover:bg-gold-hover">
                      Save
                    </button>
                    <button onClick={() => setEditingId(null)} className="text-xs text-text-secondary hover:underline">
                      Cancel
                    </button>
                  </div>
                </div>
              ) : (
                <div
                  key={item.id}
                  className={`flex items-center justify-between gap-2 text-sm border rounded px-3 py-1.5 ${
                    item.is_active ? "border-border-dark" : "border-border-dark bg-surface-raised opacity-60"
                  }`}
                >
                  <span>
                    {item.item_name} <span className="text-text-secondary text-xs">({item.quantity_per_court} {item.unit}/court)</span>
                    {!item.is_active && <span className="text-text-secondary"> · inactive</span>}
                  </span>
                  <div className="flex items-center gap-3">
                    <button onClick={() => startEdit(item)} className="text-gold hover:underline text-xs">
                      Edit
                    </button>
                    <button onClick={() => toggleActive(item)} className="text-text-secondary hover:underline text-xs">
                      {item.is_active ? "Deactivate" : "Reactivate"}
                    </button>
                  </div>
                </div>
              )
            )}

            {addingForSportId === sport.id ? (
              <div className="border border-green-500/30 bg-green-500/10 rounded p-2 space-y-2 text-sm">
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
                    className="text-xs text-text-secondary hover:underline"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            ) : (
              <button onClick={() => setAddingForSportId(sport.id)} className="text-xs text-gold hover:underline">
                + Add item
              </button>
            )}
          </div>
        );
      })}
    </div>
  );
}

function NettingGradesTab({ token, nettingGrades, onAction }) {
  const [adding, setAdding] = useState(false);
  const [addForm, setAddForm] = useState(emptyNettingGradeForm());
  const [editingId, setEditingId] = useState(null);
  const [editForm, setEditForm] = useState(null);

  const uvOption = (v) => (v === "" ? null : v === "true");

  const handleCreate = onAction(async () => {
    await createNettingGrade(token, {
      key: addForm.key,
      name: addForm.name,
      material: addForm.material,
      twine: addForm.twine || null,
      mesh: addForm.mesh,
      uv_stabilized: uvOption(addForm.uv_stabilized),
      typical_use: addForm.typical_use,
      rate_per_sqm: Number(addForm.rate_per_sqm),
    });
    setAddForm(emptyNettingGradeForm());
    setAdding(false);
  });

  function startEdit(grade) {
    setEditingId(grade.id);
    setEditForm({
      name: grade.name, material: grade.material, twine: grade.twine || "", mesh: grade.mesh,
      uv_stabilized: grade.uv_stabilized === null ? "" : String(grade.uv_stabilized),
      typical_use: grade.typical_use, rate_per_sqm: String(grade.rate_per_sqm),
    });
  }

  const handleSaveEdit = onAction(async () => {
    await updateNettingGrade(token, editingId, {
      name: editForm.name,
      material: editForm.material,
      twine: editForm.twine || null,
      mesh: editForm.mesh,
      uv_stabilized: uvOption(editForm.uv_stabilized),
      typical_use: editForm.typical_use,
      rate_per_sqm: Number(editForm.rate_per_sqm),
    });
    setEditingId(null);
  });

  const toggleActive = onAction(async (grade) => updateNettingGrade(token, grade.id, { is_active: !grade.is_active }));

  return (
    <div className="bg-surface shadow rounded-lg p-6 space-y-3">
      <p className="text-xs text-text-secondary -mt-1 mb-2">
        E.3: the netting grades a structure's Cost Sheet take-off can select instead of a bare Rs/sqm figure --
        N1 Budget through N4 Welded mesh, each with its own material/twine/mesh/UV spec. A PM can still enter a bare
        rate directly for a one-off spec these four don't cover.
      </p>
      <div className="space-y-2">
        {nettingGrades.map((grade) =>
          editingId === grade.id ? (
            <div key={grade.id} className="border border-gold bg-gold-muted rounded p-2 space-y-2 text-sm">
              <div className="grid grid-cols-3 gap-2">
                <LabeledInput label="Name" value={editForm.name} onChange={(v) => setEditForm((f) => ({ ...f, name: v }))} />
                <LabeledInput label="Material" value={editForm.material} onChange={(v) => setEditForm((f) => ({ ...f, material: v }))} />
                <LabeledInput label="Twine" value={editForm.twine} onChange={(v) => setEditForm((f) => ({ ...f, twine: v }))} />
                <LabeledInput label="Mesh" value={editForm.mesh} onChange={(v) => setEditForm((f) => ({ ...f, mesh: v }))} />
                <div>
                  <label className="block text-xs text-text-secondary">UV stabilized</label>
                  <select
                    value={editForm.uv_stabilized}
                    onChange={(e) => setEditForm((f) => ({ ...f, uv_stabilized: e.target.value }))}
                    className="mt-1 w-full rounded border border-border-dark bg-surface-raised text-text-primary px-2 py-1 text-sm"
                  >
                    <option value="">-- (n/a)</option>
                    <option value="true">Yes</option>
                    <option value="false">No</option>
                  </select>
                </div>
                <LabeledInput
                  label="Rate Rs/sqm" type="number"
                  value={editForm.rate_per_sqm} onChange={(v) => setEditForm((f) => ({ ...f, rate_per_sqm: v }))}
                />
                <div className="col-span-3">
                  <LabeledInput label="Typical use" value={editForm.typical_use} onChange={(v) => setEditForm((f) => ({ ...f, typical_use: v }))} />
                </div>
              </div>
              <div className="flex gap-2">
                <button onClick={handleSaveEdit} className="bg-gold text-base text-xs rounded px-3 py-1 hover:bg-gold-hover">
                  Save
                </button>
                <button onClick={() => setEditingId(null)} className="text-xs text-text-secondary hover:underline">
                  Cancel
                </button>
              </div>
            </div>
          ) : (
            <div
              key={grade.id}
              className={`flex items-center justify-between gap-2 text-sm border rounded px-3 py-2 ${
                grade.is_active ? "border-border-dark" : "border-border-dark bg-surface-raised opacity-60"
              }`}
            >
              <div>
                <span className="font-medium">{grade.name}</span>{" "}
                <span className="text-text-secondary text-xs">
                  ({grade.material}
                  {grade.twine && `, ${grade.twine} twine`}, {grade.mesh} mesh
                  {grade.uv_stabilized !== null && `, UV ${grade.uv_stabilized ? "yes" : "no"}`}) -- {grade.typical_use}
                </span>
                {!grade.is_active && <span className="text-text-secondary"> · inactive</span>}
              </div>
              <div className="flex items-center gap-3 shrink-0">
                <span className="text-text-secondary">Rs {grade.rate_per_sqm}/sqm</span>
                <button onClick={() => startEdit(grade)} className="text-gold hover:underline text-xs">
                  Edit
                </button>
                <button onClick={() => toggleActive(grade)} className="text-text-secondary hover:underline text-xs">
                  {grade.is_active ? "Deactivate" : "Reactivate"}
                </button>
              </div>
            </div>
          )
        )}
      </div>

      {adding ? (
        <div className="border border-green-500/30 bg-green-500/10 rounded p-2 space-y-2 text-sm">
          <div className="grid grid-cols-3 gap-2">
            <LabeledInput label="Key" value={addForm.key} onChange={(v) => setAddForm((f) => ({ ...f, key: v }))} />
            <LabeledInput label="Name" value={addForm.name} onChange={(v) => setAddForm((f) => ({ ...f, name: v }))} />
            <LabeledInput label="Material" value={addForm.material} onChange={(v) => setAddForm((f) => ({ ...f, material: v }))} />
            <LabeledInput label="Twine" value={addForm.twine} onChange={(v) => setAddForm((f) => ({ ...f, twine: v }))} />
            <LabeledInput label="Mesh" value={addForm.mesh} onChange={(v) => setAddForm((f) => ({ ...f, mesh: v }))} />
            <div>
              <label className="block text-xs text-text-secondary">UV stabilized</label>
              <select
                value={addForm.uv_stabilized}
                onChange={(e) => setAddForm((f) => ({ ...f, uv_stabilized: e.target.value }))}
                className="mt-1 w-full rounded border border-border-dark bg-surface-raised text-text-primary px-2 py-1 text-sm"
              >
                <option value="">-- (n/a)</option>
                <option value="true">Yes</option>
                <option value="false">No</option>
              </select>
            </div>
            <LabeledInput
              label="Rate Rs/sqm" type="number"
              value={addForm.rate_per_sqm} onChange={(v) => setAddForm((f) => ({ ...f, rate_per_sqm: v }))}
            />
            <div className="col-span-2">
              <LabeledInput label="Typical use" value={addForm.typical_use} onChange={(v) => setAddForm((f) => ({ ...f, typical_use: v }))} />
            </div>
          </div>
          <div className="flex gap-2">
            <button onClick={handleCreate} className="bg-green-600 text-white text-xs rounded px-3 py-1 hover:bg-green-700">
              Add grade
            </button>
            <button
              onClick={() => {
                setAdding(false);
                setAddForm(emptyNettingGradeForm());
              }}
              className="text-xs text-text-secondary hover:underline"
            >
              Cancel
            </button>
          </div>
        </div>
      ) : (
        <button onClick={() => setAdding(true)} className="text-xs text-gold hover:underline">
          + Add grade
        </button>
      )}
    </div>
  );
}

function VehicleClassesTab({ token, vehicleClasses, onAction }) {
  const [adding, setAdding] = useState(false);
  const [addForm, setAddForm] = useState(emptyVehicleClassForm());
  const [editingId, setEditingId] = useState(null);
  const [editForm, setEditForm] = useState(null);

  const handleCreate = onAction(async () => {
    await createVehicleClass(token, {
      key: addForm.key,
      name: addForm.name,
      truck_capacity_tonnes: Number(addForm.truck_capacity_tonnes),
      rate_per_km: Number(addForm.rate_per_km),
    });
    setAddForm(emptyVehicleClassForm());
    setAdding(false);
  });

  function startEdit(vc) {
    setEditingId(vc.id);
    setEditForm({
      name: vc.name, truck_capacity_tonnes: String(vc.truck_capacity_tonnes), rate_per_km: String(vc.rate_per_km),
    });
  }

  const handleSaveEdit = onAction(async () => {
    await updateVehicleClass(token, editingId, {
      name: editForm.name,
      truck_capacity_tonnes: Number(editForm.truck_capacity_tonnes),
      rate_per_km: Number(editForm.rate_per_km),
    });
    setEditingId(null);
  });

  const toggleActive = onAction(async (vc) => updateVehicleClass(token, vc.id, { is_active: !vc.is_active }));

  return (
    <div className="bg-surface shadow rounded-lg p-6 space-y-3">
      <p className="text-xs text-text-secondary -mt-1 mb-2">
        Q.1: "Freight & crane | Rs/km by vehicle class, truck capacity t, crane day rate." No worked example exists
        for this row -- NestaPrime adds its own actual fleet/vendor vehicle classes here, so the catalog starts
        empty. Selecting one on a freight take-off both supplies Rs/km and lets trips = ceil(tonnes / capacity) be
        computed automatically from a PM-entered total tonnage (B.1).
      </p>
      <div className="space-y-2">
        {vehicleClasses.map((vc) =>
          editingId === vc.id ? (
            <div key={vc.id} className="border border-gold bg-gold-muted rounded p-2 space-y-2 text-sm">
              <div className="grid grid-cols-3 gap-2">
                <LabeledInput label="Name" value={editForm.name} onChange={(v) => setEditForm((f) => ({ ...f, name: v }))} />
                <LabeledInput
                  label="Capacity (t)" type="number"
                  value={editForm.truck_capacity_tonnes} onChange={(v) => setEditForm((f) => ({ ...f, truck_capacity_tonnes: v }))}
                />
                <LabeledInput
                  label="Rate Rs/km" type="number"
                  value={editForm.rate_per_km} onChange={(v) => setEditForm((f) => ({ ...f, rate_per_km: v }))}
                />
              </div>
              <div className="flex gap-2">
                <button onClick={handleSaveEdit} className="bg-gold text-base text-xs rounded px-3 py-1 hover:bg-gold-hover">
                  Save
                </button>
                <button onClick={() => setEditingId(null)} className="text-xs text-text-secondary hover:underline">
                  Cancel
                </button>
              </div>
            </div>
          ) : (
            <div
              key={vc.id}
              className={`flex items-center justify-between gap-2 text-sm border rounded px-3 py-2 ${
                vc.is_active ? "border-border-dark" : "border-border-dark bg-surface-raised opacity-60"
              }`}
            >
              <span>
                {vc.name} <span className="text-text-secondary text-xs">({vc.truck_capacity_tonnes} t capacity)</span>
                {!vc.is_active && <span className="text-text-secondary"> · inactive</span>}
              </span>
              <div className="flex items-center gap-3 shrink-0">
                <span className="text-text-secondary">Rs {vc.rate_per_km}/km</span>
                <button onClick={() => startEdit(vc)} className="text-gold hover:underline text-xs">
                  Edit
                </button>
                <button onClick={() => toggleActive(vc)} className="text-text-secondary hover:underline text-xs">
                  {vc.is_active ? "Deactivate" : "Reactivate"}
                </button>
              </div>
            </div>
          )
        )}
        {vehicleClasses.length === 0 && !adding && (
          <p className="text-sm text-text-secondary">No vehicle classes yet -- add your own fleet/vendor classes below.</p>
        )}
      </div>

      {adding ? (
        <div className="border border-green-500/30 bg-green-500/10 rounded p-2 space-y-2 text-sm">
          <div className="grid grid-cols-3 gap-2">
            <LabeledInput label="Key" value={addForm.key} onChange={(v) => setAddForm((f) => ({ ...f, key: v }))} />
            <LabeledInput label="Name" value={addForm.name} onChange={(v) => setAddForm((f) => ({ ...f, name: v }))} />
            <LabeledInput
              label="Capacity (t)" type="number"
              value={addForm.truck_capacity_tonnes} onChange={(v) => setAddForm((f) => ({ ...f, truck_capacity_tonnes: v }))}
            />
            <LabeledInput
              label="Rate Rs/km" type="number"
              value={addForm.rate_per_km} onChange={(v) => setAddForm((f) => ({ ...f, rate_per_km: v }))}
            />
          </div>
          <div className="flex gap-2">
            <button onClick={handleCreate} className="bg-green-600 text-white text-xs rounded px-3 py-1 hover:bg-green-700">
              Add vehicle class
            </button>
            <button
              onClick={() => {
                setAdding(false);
                setAddForm(emptyVehicleClassForm());
              }}
              className="text-xs text-text-secondary hover:underline"
            >
              Cancel
            </button>
          </div>
        </div>
      ) : (
        <button onClick={() => setAdding(true)} className="text-xs text-gold hover:underline">
          + Add vehicle class
        </button>
      )}
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
    <div className="bg-surface shadow rounded-lg p-6 space-y-3">
      <p className="text-xs text-text-secondary -mt-1 mb-2">
        Part O HUBS / B.1 field #4: NestaPrime's own dispatch/depot locations -- the PM picks one when setting up a
        project and enters the km distance from it (Phase 1 is manual km; PIN-code auto-lookup is a Phase 7
        integration).
      </p>
      {hubs.map((h) =>
        editingId === h.id ? (
          <div key={h.id} className="border border-gold rounded p-3 space-y-2 text-sm bg-gold-muted">
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
              <button onClick={handleSaveEdit} className="bg-gold text-base text-xs rounded px-3 py-1 hover:bg-gold-hover">
                Save
              </button>
              <button onClick={() => setEditingId(null)} className="text-xs text-text-secondary hover:underline">
                Cancel
              </button>
            </div>
          </div>
        ) : (
          <div
            key={h.id}
            className={`flex flex-wrap items-center justify-between gap-2 text-sm border rounded px-3 py-2 ${
              h.is_active ? "border-border-dark" : "border-border-dark bg-surface-raised opacity-60"
            }`}
          >
            <span>
              <span className="font-medium">{h.name}</span>{" "}
              <span className="text-text-secondary text-xs">
                ({h.city}, {h.state_code})
              </span>
              {!h.is_active && <span className="text-text-secondary"> · inactive</span>}
            </span>
            <div className="flex items-center gap-3">
              <button onClick={() => startEdit(h)} className="text-gold hover:underline text-xs">
                Edit
              </button>
              <button onClick={() => toggleActive(h)} className="text-text-secondary hover:underline text-xs">
                {h.is_active ? "Deactivate" : "Reactivate"}
              </button>
            </div>
          </div>
        )
      )}

      {creating ? (
        <form onSubmit={handleCreate} className="border border-green-500/30 rounded p-3 space-y-2 text-sm bg-green-500/10">
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
            <button type="button" onClick={() => setCreating(false)} className="text-xs text-text-secondary hover:underline">
              Cancel
            </button>
          </div>
        </form>
      ) : (
        <button onClick={() => setCreating(true)} className="text-sm text-gold hover:underline">
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
    <div className="bg-surface shadow rounded-lg p-6 space-y-4">
      <p className="text-xs text-text-secondary">
        Part O PACKAGES / Q.1: "Packages | Budget/Standard/Premium contents | Per sport | Director." This is the
        content the Estimate PDF's "Package content" section prints for each option -- flooring, structure,
        lighting, what's included (one line per bullet), and warranty duration. Sales still customises items on the
        actual Estimate; this is only the Director-set default per sport and tier.
      </p>
      {sports.map((sport) => (
        <div key={sport.id} className="border border-border-dark rounded p-3 space-y-2">
          <p className="text-sm font-medium">
            {sport.name} <span className="text-text-secondary text-xs font-normal">({sport.key})</span>
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
                    configured ? "border-gold bg-gold-muted text-gold-hover" : "border-border-dark text-text-secondary"
                  }`}
                >
                  {tier.charAt(0).toUpperCase() + tier.slice(1)} {configured ? "✓" : "(not set)"}
                </button>
              );
            })}
          </div>
          {editingKey?.startsWith(`${sport.id}:`) && (
            <div className="border border-gold bg-gold-muted rounded p-3 space-y-2 text-sm">
              <p className="text-xs font-medium text-gold">
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
              <label className="text-xs text-text-secondary space-y-0.5 block">
                Scope (one item per line)
                <textarea
                  value={editForm.scope_description}
                  onChange={(e) => setEditForm((f) => ({ ...f, scope_description: e.target.value }))}
                  rows={3}
                  className="mt-0.5 w-full rounded border border-border-dark bg-surface-raised text-text-primary px-2 py-1 text-sm"
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
                  className="bg-gold text-base text-xs rounded px-3 py-1 hover:bg-gold-hover"
                >
                  Save
                </button>
                <button onClick={() => setEditingKey(null)} className="text-xs text-text-secondary hover:underline">
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

function FlooringGuidesTab({ token, sports, flooringGuides, onAction }) {
  const [editingId, setEditingId] = useState(null); // sport_id
  const [editForm, setEditForm] = useState(emptyFlooringGuideForm());

  const bySportId = Object.fromEntries(flooringGuides.map((g) => [g.sport_id, g]));

  function startEdit(sportId) {
    const existing = bySportId[sportId];
    setEditingId(sportId);
    setEditForm(
      existing
        ? {
            primary_spec: existing.primary_spec,
            secondary_spec: existing.secondary_spec ?? "",
            budget_spec: existing.budget_spec ?? "",
            rationale: existing.rationale,
          }
        : emptyFlooringGuideForm()
    );
  }

  const handleSave = onAction(async (sportId) => {
    await upsertFlooringGuide(token, sportId, {
      primary_spec: editForm.primary_spec,
      secondary_spec: editForm.secondary_spec || null,
      budget_spec: editForm.budget_spec || null,
      rationale: editForm.rationale,
    });
    setEditingId(null);
  });

  return (
    <div className="bg-surface shadow rounded-lg p-6 space-y-4">
      <p className="text-xs text-text-secondary">
        Parts F.1 (indoor) / F.2 (outdoor): the per-sport flooring recommendation -- primary spec (Premium
        package), an optional secondary spec (Standard, falling back to primary if unset), an optional budget spec
        (Budget package, falling back to secondary then primary), and the rationale shown alongside it. A sport with
        no row here gets no flooring recommendation at all, rather than a guess -- e.g. shooting_range_10m and
        archery_range have none, on purpose.
      </p>
      {sports.map((sport) => {
        const guide = bySportId[sport.id];
        return (
          <div key={sport.id} className="border border-border-dark rounded p-3 space-y-2">
            <div className="flex items-center justify-between">
              <p className="text-sm font-medium">
                {sport.name} <span className="text-text-secondary text-xs font-normal">({sport.key})</span>
              </p>
              <button
                onClick={() => startEdit(sport.id)}
                className={`text-xs rounded px-3 py-1 border ${
                  guide ? "border-gold bg-gold-muted text-gold-hover" : "border-border-dark text-text-secondary"
                }`}
              >
                {guide ? "Edit" : "Not set"}
              </button>
            </div>
            {guide && editingId !== sport.id && (
              <p className="text-xs text-text-secondary">
                Primary: {guide.primary_spec}
                {guide.secondary_spec && <> · Secondary: {guide.secondary_spec}</>}
                {guide.budget_spec && <> · Budget: {guide.budget_spec}</>}
              </p>
            )}
            {editingId === sport.id && (
              <div className="border border-gold bg-gold-muted rounded p-3 space-y-2 text-sm">
                <LabeledInput
                  label="Primary spec (Premium)"
                  value={editForm.primary_spec}
                  onChange={(v) => setEditForm((f) => ({ ...f, primary_spec: v }))}
                  required
                />
                <LabeledInput
                  label="Secondary spec (Standard, optional)"
                  value={editForm.secondary_spec}
                  onChange={(v) => setEditForm((f) => ({ ...f, secondary_spec: v }))}
                />
                <LabeledInput
                  label="Budget spec (optional)"
                  value={editForm.budget_spec}
                  onChange={(v) => setEditForm((f) => ({ ...f, budget_spec: v }))}
                />
                <LabeledInput
                  label="Rationale"
                  value={editForm.rationale}
                  onChange={(v) => setEditForm((f) => ({ ...f, rationale: v }))}
                  required
                />
                <div className="flex gap-2">
                  <button
                    onClick={() => handleSave(sport.id)}
                    className="bg-gold text-base text-xs rounded px-3 py-1 hover:bg-gold-hover"
                  >
                    Save
                  </button>
                  <button onClick={() => setEditingId(null)} className="text-xs text-text-secondary hover:underline">
                    Cancel
                  </button>
                </div>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

const LUX_CATEGORIES = ["court", "football_cricket", "pool", "gym"];

function LightingStandardsTab({ token, sports, luxStandards, poleCounts, onAction }) {
  const [editingCategory, setEditingCategory] = useState(null);
  const [luxForm, setLuxForm] = useState(emptyLuxStandardForm());
  const [poleSportId, setPoleSportId] = useState("");
  const [poleCountValue, setPoleCountValue] = useState("");

  const luxByCategory = Object.fromEntries(luxStandards.map((s) => [s.category, s]));
  const sportsById = Object.fromEntries(sports.map((s) => [s.id, s]));

  function startEditLux(category) {
    const existing = luxByCategory[category];
    setEditingCategory(category);
    setLuxForm(
      existing
        ? {
            lux_practice: existing.lux_practice ?? "",
            lux_match: existing.lux_match ?? "",
            lux_tournament: existing.lux_tournament ?? "",
          }
        : emptyLuxStandardForm()
    );
  }

  const handleSaveLux = onAction(async (category) => {
    await upsertLightingLuxStandard(token, category, {
      lux_practice: num(luxForm.lux_practice),
      lux_match: num(luxForm.lux_match),
      lux_tournament: num(luxForm.lux_tournament),
    });
    setEditingCategory(null);
  });

  const handleSetPoleCount = onAction(async (e) => {
    e.preventDefault();
    await upsertSportPoleCount(token, poleSportId, { pole_count: Number(poleCountValue) });
    setPoleSportId("");
    setPoleCountValue("");
  });

  const handleRemovePoleCount = onAction(async (sportId) => deleteSportPoleCount(token, sportId));

  return (
    <div className="space-y-4">
      <div className="bg-surface shadow rounded-lg p-6 space-y-3">
        <p className="text-xs text-text-secondary">
          Part H's lux table, by sport group -- "court", "football_cricket", "pool" and "gym" are a fixed code-level
          grouping (which sports behave alike), not editable here; only the lux figures for each group are.
        </p>
        {LUX_CATEGORIES.map((category) => {
          const standard = luxByCategory[category];
          return (
            <div key={category} className="border border-border-dark rounded p-3 space-y-2">
              <div className="flex items-center justify-between">
                <p className="text-sm font-medium">{category}</p>
                <button
                  onClick={() => startEditLux(category)}
                  className="text-xs rounded px-3 py-1 border border-gold bg-gold-muted text-gold-hover"
                >
                  Edit
                </button>
              </div>
              {standard && editingCategory !== category && (
                <p className="text-xs text-text-secondary">
                  Practice: {standard.lux_practice ?? "--"} · Match: {standard.lux_match ?? "--"} · Tournament:{" "}
                  {standard.lux_tournament ?? "--"}
                </p>
              )}
              {editingCategory === category && (
                <div className="border border-gold bg-gold-muted rounded p-3 space-y-2 text-sm">
                  <div className="grid grid-cols-3 gap-2">
                    <LabeledInput
                      label="Practice lux"
                      type="number"
                      value={luxForm.lux_practice}
                      onChange={(v) => setLuxForm((f) => ({ ...f, lux_practice: v }))}
                    />
                    <LabeledInput
                      label="Match lux"
                      type="number"
                      value={luxForm.lux_match}
                      onChange={(v) => setLuxForm((f) => ({ ...f, lux_match: v }))}
                    />
                    <LabeledInput
                      label="Tournament lux"
                      type="number"
                      value={luxForm.lux_tournament}
                      onChange={(v) => setLuxForm((f) => ({ ...f, lux_tournament: v }))}
                    />
                  </div>
                  <div className="flex gap-2">
                    <button
                      onClick={() => handleSaveLux(category)}
                      className="bg-gold text-base text-xs rounded px-3 py-1 hover:bg-gold-hover"
                    >
                      Save
                    </button>
                    <button onClick={() => setEditingCategory(null)} className="text-xs text-text-secondary hover:underline">
                      Cancel
                    </button>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>

      <div className="bg-surface shadow rounded-lg p-6 space-y-3">
        <p className="text-xs text-text-secondary">
          Part H's pole table (open-air only): the fixture-count floor once a sport mounts lighting on poles rather
          than structure. Most sports have no row -- that's a real state (no pole-count floor applies), not a gap.
        </p>
        {poleCounts.map((row) => (
          <div key={row.sport_id} className="flex items-center justify-between border border-border-dark rounded p-2 text-sm">
            <span>
              {sportsById[row.sport_id]?.name ?? row.sport_id} · {row.pole_count} poles
            </span>
            <button onClick={() => handleRemovePoleCount(row.sport_id)} className="text-xs text-red-400 hover:underline">
              Remove
            </button>
          </div>
        ))}
        <form onSubmit={handleSetPoleCount} className="flex items-center gap-2">
          <select
            value={poleSportId}
            onChange={(e) => setPoleSportId(e.target.value)}
            required
            className="rounded border border-border-dark bg-surface-raised text-text-primary px-2 py-1 text-sm"
          >
            <option value="">Select sport…</option>
            {sports.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>
          <input
            type="number"
            min="1"
            placeholder="Pole count"
            value={poleCountValue}
            onChange={(e) => setPoleCountValue(e.target.value)}
            required
            className="w-28 rounded border border-border-dark bg-surface-raised text-text-primary px-2 py-1 text-sm"
          />
          <button type="submit" className="bg-gold text-base text-xs rounded px-3 py-1 hover:bg-gold-hover">
            Set
          </button>
        </form>
      </div>
    </div>
  );
}

function LabeledInput({ label, value, onChange, type = "text", required = false }) {
  return (
    <label className="text-xs text-text-secondary space-y-0.5 block">
      {label}
      <input
        type={type}
        value={value}
        required={required}
        onChange={(e) => onChange(e.target.value)}
        className="mt-0.5 w-full rounded border border-border-dark bg-surface-raised text-text-primary px-2 py-1 text-sm"
      />
    </label>
  );
}

function LabeledSelect({ label, value, options, onChange }) {
  return (
    <label className="text-xs text-text-secondary space-y-0.5 block">
      {label}
      <select value={value} onChange={(e) => onChange(e.target.value)} className="mt-0.5 w-full rounded border border-border-dark bg-surface-raised text-text-primary px-2 py-1 text-sm">
        {options.map((o) => (
          <option key={o} value={o}>
            {o}
          </option>
        ))}
      </select>
    </label>
  );
}
