import { useEffect, useState } from "react";
import { addProjectSport, listProjectSports, listSports, removeProjectSport } from "./api";

const BUILDING_STATUSES = [
  ["existing_building", "Existing building"],
  ["new_peb_building", "New PEB building"],
  ["open_air", "Open air"],
  ["covered_shed", "Covered shed"],
];

export default function SportSelection({ token, project, onBack, onNext }) {
  const [sports, setSports] = useState([]);
  const [selections, setSelections] = useState([]);
  const [drafts, setDrafts] = useState({}); // sportId -> { building_status, number_of_courts }
  const [cardErrors, setCardErrors] = useState({}); // sportId -> message
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([listSports(token), listProjectSports(token, project.id)])
      .then(([sportsRes, selectionsRes]) => {
        setSports(sportsRes);
        setSelections(selectionsRes);
        const initialDrafts = {};
        for (const sport of sportsRes) {
          initialDrafts[sport.id] = {
            building_status: project.building_status,
            number_of_courts: 1,
          };
        }
        setDrafts(initialDrafts);
      })
      .finally(() => setLoading(false));
  }, [token, project.id, project.building_status]);

  function setDraft(sportId, field, value) {
    setDrafts((d) => ({ ...d, [sportId]: { ...d[sportId], [field]: value } }));
  }

  async function handleAdd(sport) {
    setCardErrors((e) => ({ ...e, [sport.id]: "" }));
    const draft = drafts[sport.id];
    try {
      const created = await addProjectSport(token, project.id, {
        sport_id: sport.id,
        building_status: draft.building_status,
        number_of_courts: Number(draft.number_of_courts),
      });
      setSelections((s) => [...s, created]);
    } catch (err) {
      setCardErrors((e) => ({ ...e, [sport.id]: err.message }));
    }
  }

  async function handleRemove(selectionId) {
    await removeProjectSport(token, project.id, selectionId);
    setSelections((s) => s.filter((sel) => sel.id !== selectionId));
  }

  if (loading) {
    return <p className="text-center text-gray-500 mt-10">Loading sports…</p>;
  }

  const sportsById = Object.fromEntries(sports.map((s) => [s.id, s]));
  const indoor = sports.filter((s) => s.category === "indoor");
  const outdoor = sports.filter((s) => s.category === "outdoor");

  return (
    <div className="max-w-3xl mx-auto mt-8 mb-10 space-y-6">
      <div className="bg-white shadow rounded-lg p-6">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-gray-900">Select Sports</h2>
            <p className="text-sm text-gray-500">
              Project <span className="font-mono">{project.project_no}</span>
            </p>
          </div>
          <div className="flex items-center gap-4">
            <button onClick={onBack} className="text-sm text-blue-600 hover:underline">
              &larr; Back to Project Setup
            </button>
            <button onClick={onNext} className="text-sm text-blue-600 hover:underline">
              Additional Scope &rarr;
            </button>
          </div>
        </div>

        {selections.length > 0 && (
          <div className="mt-4 space-y-2">
            <h3 className="text-sm font-medium text-gray-700">Selected ({selections.length})</h3>
            {selections.map((sel) => {
              const sport = sportsById[sel.sport_id];
              return (
                <div
                  key={sel.id}
                  className="flex items-start justify-between bg-blue-50 rounded px-3 py-2 text-sm"
                >
                  <span>
                    <span className="font-medium">{sport?.name ?? sel.sport_id}</span>
                    {" · "}
                    {sel.building_status.replaceAll("_", " ")}
                    {" · "}
                    {sel.number_of_courts} court{sel.number_of_courts > 1 ? "s" : ""}
                    {sel.recommended_base ? (
                      <span className="block text-xs text-gray-500 mt-0.5">
                        Base (D.2): {sel.recommended_base.recommended}
                        {sel.recommended_base.alternative && ` (alt: ${sel.recommended_base.alternative})`}
                      </span>
                    ) : (
                      <span className="block text-xs text-gray-400 mt-0.5">
                        Base: not yet in D.2 matrix — pending Director confirmation
                      </span>
                    )}
                    {sel.recommended_structure ? (
                      <span className="block text-xs text-gray-500 mt-0.5">
                        Structure (E.4): Type {sel.recommended_structure.structure_type} ·{" "}
                        {sel.recommended_structure.section} · {sel.recommended_structure.height}
                      </span>
                    ) : (
                      <span className="block text-xs text-gray-400 mt-0.5">
                        Structure: none recommended (fit-out or not yet in E.4 matrix)
                      </span>
                    )}
                    {sel.structural_signoff_required && (
                      <span className="block text-xs text-amber-700 bg-amber-50 rounded px-1.5 py-0.5 mt-1">
                        Structural engineer sign-off required (E.5): {sel.structural_signoff_reasons.join(", ")}
                      </span>
                    )}
                    {sel.recommended_flooring ? (
                      <span className="block text-xs text-gray-500 mt-0.5">
                        Flooring (F.1/F.2, {sel.recommended_flooring.selected_tier}): {sel.recommended_flooring.selected}
                      </span>
                    ) : (
                      <span className="block text-xs text-gray-400 mt-0.5">
                        Flooring: not yet in F.1/F.2 matrix — pending Director confirmation
                      </span>
                    )}
                    {sel.recommended_lighting ? (
                      <span className="block text-xs text-gray-500 mt-0.5">
                        Lighting (H): {sel.recommended_lighting.fixtures} x {sel.recommended_lighting.fixture_spec}
                        {" "}({sel.recommended_lighting.mounting_mode}
                        {sel.recommended_lighting.pole_count ? `, ${sel.recommended_lighting.pole_count} poles` : ""})
                      </span>
                    ) : (
                      <span className="block text-xs text-gray-400 mt-0.5">
                        Lighting: not enough data (no numeric playing area or lux row) — pending Director confirmation
                      </span>
                    )}
                  </span>
                  <button
                    onClick={() => handleRemove(sel.id)}
                    className="text-red-600 hover:underline shrink-0 ml-2"
                  >
                    Remove
                  </button>
                </div>
              );
            })}
          </div>
        )}
      </div>

      <SportGroup
        title="Indoor sports (C.1)"
        sports={indoor}
        drafts={drafts}
        setDraft={setDraft}
        cardErrors={cardErrors}
        onAdd={handleAdd}
      />
      <SportGroup
        title="Outdoor sports (C.2)"
        sports={outdoor}
        drafts={drafts}
        setDraft={setDraft}
        cardErrors={cardErrors}
        onAdd={handleAdd}
      />
    </div>
  );
}

function SportGroup({ title, sports, drafts, setDraft, cardErrors, onAdd }) {
  return (
    <div className="bg-white shadow rounded-lg p-6">
      <h3 className="text-sm font-semibold text-gray-700 mb-3">{title}</h3>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {sports.map((sport) => (
          <SportCard
            key={sport.id}
            sport={sport}
            draft={drafts[sport.id] ?? { building_status: "open_air", number_of_courts: 1 }}
            setDraft={setDraft}
            error={cardErrors[sport.id]}
            onAdd={onAdd}
          />
        ))}
      </div>
    </div>
  );
}

function SportCard({ sport, draft, setDraft, error, onAdd }) {
  return (
    <div className="border border-gray-200 rounded-lg p-3">
      <div className="flex items-baseline justify-between">
        <h4 className="font-medium text-gray-900">{sport.name}</h4>
        <span className="text-xs text-gray-400">{sport.governing_body}</span>
      </div>
      <p className="text-xs text-gray-500 mt-1">Playing: {sport.playing_dims} ft</p>
      <p className="text-xs text-gray-500">Build: {sport.build_dims} ft</p>
      {sport.min_clear_height_ft != null && (
        <p className="text-xs text-gray-500">Min clear height: {sport.min_clear_height_ft} ft</p>
      )}

      <div className="mt-2 flex items-center gap-2">
        <select
          value={draft.building_status}
          onChange={(e) => setDraft(sport.id, "building_status", e.target.value)}
          className="flex-1 rounded border border-gray-300 px-2 py-1 text-xs"
        >
          {BUILDING_STATUSES.map(([val, label]) => (
            <option key={val} value={val}>{label}</option>
          ))}
        </select>
        <input
          type="number"
          min={1}
          value={draft.number_of_courts}
          onChange={(e) => setDraft(sport.id, "number_of_courts", e.target.value)}
          className="w-14 rounded border border-gray-300 px-2 py-1 text-xs"
        />
        <button
          onClick={() => onAdd(sport)}
          className="bg-blue-600 text-white text-xs rounded px-3 py-1 hover:bg-blue-700"
        >
          Add
        </button>
      </div>

      {error && <p className="text-xs text-red-600 mt-1">{error}</p>}
    </div>
  );
}
