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

export default function ScopeChecklist({ token, project, onBack, onNext }) {
  const [items, setItems] = useState([]);
  const [selections, setSelections] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

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

  if (loading) {
    return <p className="text-center text-gray-500 mt-10">Loading scope checklist…</p>;
  }

  const byGroup = GROUP_ORDER.map((group) => ({
    group,
    items: items.filter((i) => i.group === group),
  }));

  return (
    <div className="max-w-2xl mx-auto mt-8 mb-10 space-y-6">
      <div className="bg-white shadow rounded-lg p-6">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-gray-900">Additional Scope Checklist</h2>
            <p className="text-sm text-gray-500">
              Project <span className="font-mono">{project.project_no}</span>
            </p>
          </div>
          <div className="flex items-center gap-4">
            <button onClick={onBack} className="text-sm text-blue-600 hover:underline">
              &larr; Back to Sport Selection
            </button>
            {project.tender_mode && (
              <button onClick={onNext} className="text-sm text-blue-600 hover:underline">
                Tender Mode &rarr;
              </button>
            )}
          </div>
        </div>
        <p className="text-xs text-gray-400 mt-2">
          Unchecked items are excluded and listed under Exclusions (Part I). {selections.length} of{" "}
          {items.length} included.
        </p>
        {error && <p className="text-sm text-red-600 mt-2">{error}</p>}
      </div>

      {byGroup.map(({ group, items: groupItems }) => (
        <div key={group} className="bg-white shadow rounded-lg p-6">
          <h3 className="text-sm font-semibold text-gray-700 mb-3">{GROUP_LABELS[group]}</h3>
          <div className="space-y-2">
            {groupItems.map((item) => (
              <label key={item.id} className="flex items-center gap-2 text-sm text-gray-700">
                <input
                  type="checkbox"
                  checked={selectedItemIds.has(item.id)}
                  onChange={(e) => handleToggle(item, e.target.checked)}
                />
                {item.name}
              </label>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
