import { useEffect, useState } from "react";
import {
  addProjectSport,
  getSchedule,
  listProjectSports,
  listSports,
  removeProjectSport,
  updateActualDimensions,
  updateBuildSize,
} from "./api";

const DEVIATION_COLOR = {
  green: "text-green-400 bg-green-500/10",
  amber: "text-amber-400 bg-amber-500/10",
  red: "text-red-400 bg-red-500/10",
};

const BUILDING_STATUSES = [
  ["existing_building", "Existing building"],
  ["new_peb_building", "New PEB building"],
  ["open_air", "Open air"],
  ["covered_shed", "Covered shed"],
];

export default function SportSelection({ token, project, role, onBack, onNext }) {
  const [sports, setSports] = useState([]);
  const [selections, setSelections] = useState([]);
  const [drafts, setDrafts] = useState({}); // sportId -> { building_status, number_of_courts }
  const [cardErrors, setCardErrors] = useState({}); // sportId -> message
  const [loading, setLoading] = useState(true);
  const [schedules, setSchedules] = useState({}); // selectionId -> schedule | "loading"
  const [dimDrafts, setDimDrafts] = useState({}); // selectionId -> { actual_l_ft, actual_w_ft }
  const [sizeDrafts, setSizeDrafts] = useState({}); // selectionId -> { custom_build_l_ft, custom_build_w_ft }
  const [sizeErrors, setSizeErrors] = useState({}); // selectionId -> message
  const [customizingSize, setCustomizingSize] = useState({}); // selectionId -> bool
  const canRecordActuals = role === "site_engineer" || role === "pm" || role === "director";

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

  function setDimDraft(selectionId, field, value) {
    setDimDrafts((d) => ({ ...d, [selectionId]: { ...d[selectionId], [field]: value } }));
  }

  async function handleSaveActualDimensions(selectionId) {
    const draft = dimDrafts[selectionId] || {};
    const updated = await updateActualDimensions(token, project.id, selectionId, {
      actual_l_ft: draft.actual_l_ft === "" || draft.actual_l_ft == null ? null : Number(draft.actual_l_ft),
      actual_w_ft: draft.actual_w_ft === "" || draft.actual_w_ft == null ? null : Number(draft.actual_w_ft),
    });
    setSelections((s) => s.map((sel) => (sel.id === selectionId ? updated : sel)));
  }

  function setSizeDraft(selectionId, field, value) {
    setSizeDrafts((d) => ({ ...d, [selectionId]: { ...d[selectionId], [field]: value } }));
  }

  async function handleSaveBuildSize(selectionId) {
    setSizeErrors((e) => ({ ...e, [selectionId]: "" }));
    const draft = sizeDrafts[selectionId] || {};
    try {
      const updated = await updateBuildSize(token, project.id, selectionId, {
        custom_build_l_ft: draft.custom_build_l_ft === "" || draft.custom_build_l_ft == null ? null : Number(draft.custom_build_l_ft),
        custom_build_w_ft: draft.custom_build_w_ft === "" || draft.custom_build_w_ft == null ? null : Number(draft.custom_build_w_ft),
      });
      setSelections((s) => s.map((sel) => (sel.id === selectionId ? updated : sel)));
      setCustomizingSize((c) => ({ ...c, [selectionId]: false }));
    } catch (err) {
      setSizeErrors((e) => ({ ...e, [selectionId]: err.message }));
    }
  }

  async function handleRemove(selectionId) {
    await removeProjectSport(token, project.id, selectionId);
    setSelections((s) => s.filter((sel) => sel.id !== selectionId));
  }

  async function handleToggleSchedule(selectionId) {
    if (schedules[selectionId]) {
      setSchedules((s) => { const next = { ...s }; delete next[selectionId]; return next; });
      return;
    }
    setSchedules((s) => ({ ...s, [selectionId]: "loading" }));
    try {
      const schedule = await getSchedule(token, selectionId);
      setSchedules((s) => ({ ...s, [selectionId]: schedule }));
    } catch (err) {
      setSchedules((s) => ({ ...s, [selectionId]: { error: err.message } }));
    }
  }

  if (loading) {
    return <p className="text-center text-text-secondary mt-10">Loading sports…</p>;
  }

  const sportsById = Object.fromEntries(sports.map((s) => [s.id, s]));
  const indoor = sports.filter((s) => s.category === "indoor");
  const outdoor = sports.filter((s) => s.category === "outdoor");

  return (
    <div className="max-w-3xl mx-auto mt-8 mb-10 space-y-6">
      <div className="bg-surface shadow rounded-lg p-6">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-text-primary">Select Sports</h2>
            <p className="text-sm text-text-secondary">
              Project <span className="font-mono">{project.project_no}</span>
            </p>
          </div>
          <div className="flex items-center gap-4">
            <button onClick={onBack} className="text-sm text-gold hover:underline">
              &larr; Back to Project Setup
            </button>
            <button onClick={onNext} className="text-sm text-gold hover:underline">
              Additional Scope &rarr;
            </button>
          </div>
        </div>

        {selections.length > 0 && (
          <div className="mt-4 space-y-2">
            <h3 className="text-sm font-medium text-text-secondary">Selected ({selections.length})</h3>
            {selections.map((sel) => {
              const sport = sportsById[sel.sport_id];
              return (
                <div
                  key={sel.id}
                  className="bg-gold-muted rounded px-3 py-2 text-sm"
                >
                <div className="flex items-start justify-between">
                  <span>
                    <span className="font-medium">{sport?.name ?? sel.sport_id}</span>
                    {" · "}
                    {sel.building_status.replaceAll("_", " ")}
                    {" · "}
                    {sel.number_of_courts} court{sel.number_of_courts > 1 ? "s" : ""}
                    <CourtSize
                      sel={sel}
                      sport={sport}
                      customizing={customizingSize[sel.id] ?? false}
                      setCustomizing={(v) => setCustomizingSize((c) => ({ ...c, [sel.id]: v }))}
                      draft={sizeDrafts[sel.id]}
                      setDraft={(field, value) => setSizeDraft(sel.id, field, value)}
                      onSave={() => handleSaveBuildSize(sel.id)}
                      error={sizeErrors[sel.id]}
                    />
                    {sel.recommended_base ? (
                      <span className="block text-xs text-text-secondary mt-0.5">
                        Base (D.2): {sel.recommended_base.recommended}
                        {sel.recommended_base.alternative && ` (alt: ${sel.recommended_base.alternative})`}
                      </span>
                    ) : (
                      <span className="block text-xs text-text-secondary mt-0.5">
                        Base: not yet in D.2 matrix — pending Director confirmation
                      </span>
                    )}
                    {sel.recommended_structure ? (
                      <span className="block text-xs text-text-secondary mt-0.5">
                        Structure (E.4): Type {sel.recommended_structure.structure_type} ·{" "}
                        {sel.recommended_structure.section} · {sel.recommended_structure.height}
                      </span>
                    ) : (
                      <span className="block text-xs text-text-secondary mt-0.5">
                        Structure: none recommended (fit-out or not yet in E.4 matrix)
                      </span>
                    )}
                    {sel.structural_signoff_required && (
                      <span className="block text-xs text-amber-400 bg-amber-500/10 rounded px-1.5 py-0.5 mt-1">
                        Structural engineer sign-off required (E.5): {sel.structural_signoff_reasons.join(", ")}
                      </span>
                    )}
                    {sel.recommended_flooring ? (
                      <span className="block text-xs text-text-secondary mt-0.5">
                        Flooring (F.1/F.2, {sel.recommended_flooring.selected_tier}): {sel.recommended_flooring.selected}
                      </span>
                    ) : (
                      <span className="block text-xs text-text-secondary mt-0.5">
                        Flooring: not yet in F.1/F.2 matrix — pending Director confirmation
                      </span>
                    )}
                    {sel.recommended_lighting ? (
                      <span className="block text-xs text-text-secondary mt-0.5">
                        Lighting (H): {sel.recommended_lighting.fixtures} x {sel.recommended_lighting.fixture_spec}
                        {" "}({sel.recommended_lighting.mounting_mode}
                        {sel.recommended_lighting.pole_count ? `, ${sel.recommended_lighting.pole_count} poles` : ""})
                      </span>
                    ) : (
                      <span className="block text-xs text-text-secondary mt-0.5">
                        Lighting: not enough data (no numeric playing area or lux row) — pending Director confirmation
                      </span>
                    )}
                    <ActualDimensions
                      sel={sel}
                      canEdit={canRecordActuals}
                      draft={dimDrafts[sel.id]}
                      setDraft={(field, value) => setDimDraft(sel.id, field, value)}
                      onSave={() => handleSaveActualDimensions(sel.id)}
                    />
                  </span>
                  <div className="flex flex-col items-end gap-1 shrink-0 ml-2">
                    <button
                      onClick={() => handleToggleSchedule(sel.id)}
                      className="text-gold hover:underline"
                    >
                      {schedules[sel.id] ? "Hide schedule" : "Schedule (N)"}
                    </button>
                    <button
                      onClick={() => handleRemove(sel.id)}
                      className="text-red-400 hover:underline"
                    >
                      Remove
                    </button>
                  </div>
                </div>
                {schedules[sel.id] && <ScheduleDetails schedule={schedules[sel.id]} />}
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
    <div className="bg-surface shadow rounded-lg p-6">
      <h3 className="text-sm font-semibold text-text-secondary mb-3">{title}</h3>
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
    <div className="border border-border-dark rounded-lg p-3">
      <div className="flex items-baseline justify-between">
        <h4 className="font-medium text-text-primary">{sport.name}</h4>
        <span className="text-xs text-text-secondary">{sport.governing_body}</span>
      </div>
      <p className="text-xs text-text-secondary mt-1">Playing: {sport.playing_dims} ft</p>
      <p className="text-xs text-text-secondary">Build: {sport.build_dims} ft</p>
      {sport.min_clear_height_ft != null && (
        <p className="text-xs text-text-secondary">Min clear height: {sport.min_clear_height_ft} ft</p>
      )}

      <div className="mt-2 flex items-center gap-2">
        <select
          value={draft.building_status}
          onChange={(e) => setDraft(sport.id, "building_status", e.target.value)}
          className="flex-1 rounded border border-border-dark bg-surface-raised text-text-primary px-2 py-1 text-xs"
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
          className="w-14 rounded border border-border-dark bg-surface-raised text-text-primary px-2 py-1 text-xs"
        />
        <button
          onClick={() => onAdd(sport)}
          className="bg-gold text-white text-xs rounded px-3 py-1 hover:bg-gold-hover"
        >
          Add
        </button>
      </div>

      {error && <p className="text-xs text-red-400 mt-1">{error}</p>}
    </div>
  );
}

// Amendment 9 (Annexure 2): Court size step. Standard is accepted with a
// click; "Customize" reveals L/W, floored at the sport's own federation
// playing dimensions (server-enforced too -- the message that comes back
// on a rejected value is shown as-is, not re-derived here).
function CourtSize({ sel, sport, customizing, setCustomizing, draft, setDraft, onSave, error }) {
  const hasCustom = sel.custom_build_l_ft != null || sel.custom_build_w_ft != null;
  const standard = sport?.build_dims;

  if (!customizing && !hasCustom) {
    return (
      <span className="block text-xs text-text-secondary mt-0.5">
        Court size: standard build {standard ?? "—"} ft{" "}
        <button onClick={() => setCustomizing(true)} className="text-gold hover:underline">
          Customize size
        </button>
      </span>
    );
  }

  if (!customizing && hasCustom) {
    return (
      <span className="block text-xs mt-0.5">
        <span className="text-text-secondary">
          Court size: custom build {sel.custom_build_l_ft} x {sel.custom_build_w_ft} ft
        </span>{" "}
        <button onClick={() => setCustomizing(true)} className="text-gold hover:underline">
          Change
        </button>
      </span>
    );
  }

  return (
    <span className="block text-xs mt-0.5">
      <span className="text-text-secondary">Court size (standard build {standard ?? "—"} ft):</span>
      <span className="inline-flex items-center gap-1 ml-2">
        <input
          type="number"
          placeholder="L (ft)"
          value={draft?.custom_build_l_ft ?? sel.custom_build_l_ft ?? ""}
          onChange={(e) => setDraft("custom_build_l_ft", e.target.value)}
          className="w-16 rounded border border-border-dark bg-surface-raised text-text-primary px-1 py-0.5 text-xs"
        />
        <input
          type="number"
          placeholder="W (ft)"
          value={draft?.custom_build_w_ft ?? sel.custom_build_w_ft ?? ""}
          onChange={(e) => setDraft("custom_build_w_ft", e.target.value)}
          className="w-16 rounded border border-border-dark bg-surface-raised text-text-primary px-1 py-0.5 text-xs"
        />
        <button onClick={onSave} className="text-gold hover:underline">
          Save
        </button>
        <button onClick={() => setCustomizing(false)} className="text-text-secondary hover:underline">
          Cancel
        </button>
      </span>
      {error && <span className="block text-red-400 mt-0.5">{error}</span>}
    </span>
  );
}

function ActualDimensions({ sel, canEdit, draft, setDraft, onSave }) {
  const hasActual = sel.actual_l_ft != null || sel.actual_w_ft != null;

  if (!hasActual && !canEdit) {
    return (
      <span className="block text-xs text-text-secondary mt-0.5">
        Actual dimensions (C.3): not yet recorded
      </span>
    );
  }

  return (
    <span className="block text-xs mt-0.5">
      {hasActual ? (
        <span className="text-text-secondary">
          Actual (C.3): {sel.actual_l_ft ?? "-"} x {sel.actual_w_ft ?? "-"} ft
          {sel.dimension_deviation_status && (
            <span
              className={`ml-1 rounded px-1 py-0.5 ${DEVIATION_COLOR[sel.dimension_deviation_status]}`}
            >
              {sel.dimension_deviation_status.toUpperCase()}
              {" "}
              ({Math.max(...sel.dimension_deviations.map((d) => d.deviation_percent))}% deviation)
            </span>
          )}
        </span>
      ) : (
        <span className="text-text-secondary">Actual dimensions (C.3): not yet recorded</span>
      )}
      {canEdit && (
        <span className="inline-flex items-center gap-1 ml-2">
          <input
            type="number"
            placeholder="L (ft)"
            value={draft?.actual_l_ft ?? sel.actual_l_ft ?? ""}
            onChange={(e) => setDraft("actual_l_ft", e.target.value)}
            className="w-16 rounded border border-border-dark bg-surface-raised text-text-primary px-1 py-0.5 text-xs"
          />
          <input
            type="number"
            placeholder="W (ft)"
            value={draft?.actual_w_ft ?? sel.actual_w_ft ?? ""}
            onChange={(e) => setDraft("actual_w_ft", e.target.value)}
            className="w-16 rounded border border-border-dark bg-surface-raised text-text-primary px-1 py-0.5 text-xs"
          />
          <button onClick={onSave} className="text-gold hover:underline">
            Save
          </button>
        </span>
      )}
    </span>
  );
}

function ScheduleDetails({ schedule }) {
  if (schedule === "loading") {
    return <p className="text-xs text-text-secondary mt-2">Loading schedule…</p>;
  }
  if (schedule.error) {
    return <p className="text-xs text-red-400 mt-2">{schedule.error}</p>;
  }
  return (
    <div className="mt-2 bg-surface rounded border border-border-dark p-2 text-xs space-y-2">
      <p className="font-medium text-text-secondary">
        Total: {schedule.total_days} days ({schedule.total_weeks} weeks)
      </p>
      <table className="w-full text-left">
        <tbody>
          {schedule.activities.map((a, i) => (
            <tr key={i} className={a.parallel ? "text-text-secondary" : "text-text-secondary"}>
              <td className="pr-2 py-0.5">
                {a.name}
                {a.parallel && " (parallel)"}
              </td>
              <td className="pr-2 py-0.5">{a.duration_days}d</td>
              <td className="py-0.5">{a.start_date} &rarr; {a.end_date}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="font-medium text-text-secondary mt-1">Payment schedule (N)</p>
      <table className="w-full text-left">
        <tbody>
          {schedule.payment_schedule.map((p, i) => (
            <tr key={i} className="text-text-secondary">
              <td className="pr-2 py-0.5">{p.name}</td>
              <td className="pr-2 py-0.5">{p.percent}%</td>
              <td className="py-0.5">{p.date}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
