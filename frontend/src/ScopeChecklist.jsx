import { useEffect, useState } from "react";
import { addProjectScopeItem, listProjectScopeItems, listScopeItems, removeProjectScopeItem } from "./api";

const GROUP_LABELS = {
  civil: "Civil",
  electrical: "Electrical",
  water: "Water",
  external: "External",
  services: "Services",
  maintenance: "Maintenance",
};

const GROUP_ORDER = ["civil", "electrical", "water", "external", "services", "maintenance"];

export default function ScopeChecklist({ token, project, onBack, onNext, onDocuments, onSiteSurvey }) {
  const [items, setItems] = useState([]);
  const [selections, setSelections] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    Promise.all([listScopeItems(token), listProjectScopeItems(token, project.id)])
      .then(([itemsRes, selectionsRes]) => {
        setItems(itemsRes);
        setSelections(selectionsRes);
      })
      .finally(() => setLoading(false));
  }, [token, project.id]);

  const selectedItemIds = new Set(selections.map((s) => s.scope_item_id));

  async function handleToggle(item, checked) {
    setError("");
    try {
      if (checked) {
        const created = await addProjectScopeItem(token, project.id, { scope_item_id: item.id });
        setSelections((s) => [...s, created]);
      } else {
        const selection = selections.find((s) => s.scope_item_id === item.id);
        await removeProjectScopeItem(token, project.id, selection.id);
        setSelections((s) => s.filter((sel) => sel.id !== selection.id));
      }
    } catch (err) {
      setError(err.message);
    }
  }

  // Amendment 39 (Section 45): "Select all" / "Clear all" for ONE group. It
  // makes the same add/remove calls handleToggle already makes, once per item
  // that actually needs changing -- no new endpoint and no new "reviewed" state.
  // Each call is saved independently, so the list on screen only ever shows what
  // really saved: if some fail, the successes stay and the error says how many
  // did not, rather than pretending the whole group changed.
  async function handleBulk(groupItems, select) {
    setError("");
    setBusy(true);
    const targets = groupItems.filter((item) => selectedItemIds.has(item.id) !== select);
    const results = await Promise.allSettled(
      targets.map((item) =>
        select
          ? addProjectScopeItem(token, project.id, { scope_item_id: item.id })
          : removeProjectScopeItem(token, project.id, selections.find((s) => s.scope_item_id === item.id).id)
      )
    );
    const failed = results.filter((r) => r.status === "rejected");
    if (select) {
      const created = results.filter((r) => r.status === "fulfilled").map((r) => r.value);
      setSelections((s) => [...s, ...created]);
    } else {
      const removedIds = new Set(
        targets
          .filter((_, i) => results[i].status === "fulfilled")
          .map((item) => selections.find((s) => s.scope_item_id === item.id).id)
      );
      setSelections((s) => s.filter((sel) => !removedIds.has(sel.id)));
    }
    if (failed.length > 0) {
      setError(
        `${failed.length} of ${targets.length} items could not be saved (${failed[0].reason?.message || "error"}). ` +
          "The list shows what was saved."
      );
    }
    setBusy(false);
  }

  if (loading) {
    return <p className="text-center text-text-secondary mt-10">Loading scope checklist…</p>;
  }

  const byGroup = GROUP_ORDER.map((group) => ({
    group,
    items: items.filter((i) => i.group === group),
  }));

  return (
    <div className="max-w-2xl mx-auto mt-8 mb-10 space-y-6">
      <div className="bg-surface shadow rounded-lg p-6">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-text-primary">Additional Scope Checklist</h2>
            <p className="text-sm text-text-secondary">
              Project <span className="font-mono">{project.project_no}</span>
            </p>
          </div>
          <div className="flex items-center gap-4">
            <button onClick={onBack} className="text-sm text-gold hover:underline">
              &larr; Back to Sport Selection
            </button>
            {project.tender_mode && (
              <button onClick={onNext} className="text-sm text-gold hover:underline">
                Tender Mode &rarr;
              </button>
            )}
            <button onClick={onSiteSurvey} className="text-sm text-gold hover:underline">
              Site Survey &rarr;
            </button>
            <button onClick={onDocuments} className="text-sm text-gold hover:underline">
              Documents &rarr;
            </button>
          </div>
        </div>
        <p className="text-xs text-text-secondary mt-2">
          Unchecked items are excluded and listed under Exclusions (Part I). {selections.length} of{" "}
          {items.length} included.
        </p>
        {error && <p className="text-sm text-red-400 mt-2">{error}</p>}
      </div>

      {byGroup.map(({ group, items: groupItems }) => {
        const includedCount = groupItems.filter((i) => selectedItemIds.has(i.id)).length;
        return (
        <div key={group} className="bg-surface shadow rounded-lg p-6">
          <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
            <h3 className="text-sm font-semibold text-text-secondary">
              {GROUP_LABELS[group]}{" "}
              <span className="font-normal text-xs">
                ({includedCount} of {groupItems.length})
              </span>
            </h3>
            <span className="flex items-center gap-4 text-xs">
              <button
                onClick={() => handleBulk(groupItems, true)}
                disabled={busy || includedCount === groupItems.length}
                className="text-gold hover:underline disabled:opacity-40 disabled:no-underline"
              >
                Select all
              </button>
              <button
                onClick={() => handleBulk(groupItems, false)}
                disabled={busy || includedCount === 0}
                className="text-gold hover:underline disabled:opacity-40 disabled:no-underline"
              >
                Clear all
              </button>
            </span>
          </div>
          <div className="space-y-2">
            {groupItems.map((item) => (
              <label key={item.id} className="flex items-center gap-2 text-sm text-text-secondary">
                <input
                  type="checkbox"
                  checked={selectedItemIds.has(item.id)}
                  disabled={busy}
                  onChange={(e) => handleToggle(item, e.target.checked)}
                />
                {item.name}
              </label>
            ))}
          </div>
        </div>
        );
      })}
    </div>
  );
}
