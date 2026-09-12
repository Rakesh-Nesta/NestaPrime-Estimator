import { useEffect, useState } from "react";
import AttachmentsPanel from "./AttachmentsPanel";
import { completeSiteSurvey, createSiteSurvey, listSiteSurveys, updateSiteSurvey } from "./api";

const FIELD_ROWS = [
  { key: "sports_and_count", label: "Sport(s) & count", type: "text" },
  { key: "available_area_length", label: "Available area -- length", type: "number" },
  { key: "available_area_width", label: "Available area -- width", type: "number" },
  { key: "area_unit", label: "Area unit", type: "select", options: ["feet", "metres"] },
  { key: "slope_or_level", label: "Slope / level", type: "select", options: ["level", "sloped", "water_logged"] },
  { key: "soil_observed", label: "Soil observed", type: "select", options: ["normal", "rocky", "black_cotton", "sandy", "filled"] },
  { key: "water_logging_observed", label: "Water-logging observed", type: "bool" },
  { key: "access_road_width_m", label: "Access road width (m)", type: "number" },
  { key: "crane_access", label: "Crane access", type: "bool" },
  { key: "power_phase", label: "Power phase", type: "text" },
  { key: "power_load_kw", label: "Power load (kW)", type: "number" },
  { key: "water_source", label: "Water source", type: "text" },
  { key: "existing_structures_trees", label: "Existing structures / trees", type: "text" },
  { key: "neighbour_constraints", label: "Neighbour constraints", type: "text" },
  { key: "orientation", label: "Orientation (N-S preferred for courts)", type: "text" },
];

function FieldInput({ row, value, onChange, disabled }) {
  if (row.type === "select") {
    return (
      <select
        value={value ?? ""}
        onChange={(e) => onChange(e.target.value || null)}
        disabled={disabled}
        className="rounded border border-border-dark bg-surface-raised text-text-primary px-2 py-1 text-sm w-full disabled:bg-surface-raised"
      >
        <option value="">--</option>
        {row.options.map((o) => (
          <option key={o} value={o}>{o}</option>
        ))}
      </select>
    );
  }
  if (row.type === "bool") {
    return (
      <select
        value={value === true ? "yes" : value === false ? "no" : ""}
        onChange={(e) => onChange(e.target.value === "" ? null : e.target.value === "yes")}
        disabled={disabled}
        className="rounded border border-border-dark bg-surface-raised text-text-primary px-2 py-1 text-sm w-full disabled:bg-surface-raised"
      >
        <option value="">--</option>
        <option value="yes">Yes</option>
        <option value="no">No</option>
      </select>
    );
  }
  return (
    <input
      type={row.type}
      value={value ?? ""}
      onChange={(e) => onChange(row.type === "number" ? (e.target.value === "" ? null : Number(e.target.value)) : e.target.value)}
      disabled={disabled}
      className="rounded border border-border-dark bg-surface-raised text-text-primary px-2 py-1 text-sm w-full disabled:bg-surface-raised"
    />
  );
}

function SurveyCard({ token, survey, onChanged }) {
  const [draft, setDraft] = useState(survey);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const locked = survey.status === "completed";

  useEffect(() => setDraft(survey), [survey]);

  async function handleSave() {
    setError("");
    setSaving(true);
    try {
      const payload = {};
      for (const row of FIELD_ROWS) payload[row.key] = draft[row.key];
      await updateSiteSurvey(token, survey.id, payload);
      await onChanged();
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  async function handleComplete() {
    setError("");
    try {
      await completeSiteSurvey(token, survey.id);
      await onChanged();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <div className="bg-surface shadow rounded-lg p-4 sm:p-6 space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="text-sm">
          <span className="font-medium">{survey.client_name || "(unnamed)"}</span>{" "}
          <span className="text-xs text-text-secondary">{survey.site_address}</span>
        </span>
        <span className={`text-xs rounded px-2 py-0.5 ${locked ? "bg-green-500/10 text-green-400" : "bg-surface-raised text-text-secondary"}`}>
          {survey.status}
        </span>
      </div>
      {error && <p className="text-xs text-red-400">{error}</p>}

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-sm">
        {FIELD_ROWS.map((row) => (
          <label key={row.key} className="space-y-1">
            <span className="text-xs text-text-secondary">{row.label}</span>
            <FieldInput
              row={row}
              value={draft[row.key]}
              onChange={(v) => setDraft((d) => ({ ...d, [row.key]: v }))}
              disabled={locked}
            />
          </label>
        ))}
      </div>

      {!locked && (
        <button
          onClick={handleSave}
          disabled={saving}
          className="w-full sm:w-auto bg-gold text-base text-xs rounded px-3 py-2 sm:py-1.5 hover:bg-gold-hover disabled:opacity-50"
        >
          {saving ? "Saving…" : "Save"}
        </button>
      )}

      <AttachmentsPanel token={token} docType="site_survey" docId={survey.id} />

      <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-text-secondary">
        <span>
          {survey.photo_count} photo(s) attached (min 4 required to complete)
          {survey.surveyed_by_id && ` · surveyed ${survey.surveyed_at}`}
        </span>
        {!locked && (
          <button
            onClick={handleComplete}
            disabled={survey.photo_count < 4}
            className="w-full sm:w-auto bg-green-600 text-white rounded px-3 py-2 sm:py-1.5 hover:bg-green-700 disabled:opacity-50"
          >
            Mark Completed
          </button>
        )}
      </div>
    </div>
  );
}

export default function SiteSurvey({ token, project, role, onBack }) {
  const [surveys, setSurveys] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [newForm, setNewForm] = useState({ client_name: "", site_address: "", pin_code: "", contact_name: "", contact_phone: "" });
  const canWrite = role === "site_engineer" || role === "pm" || role === "director";

  function load() {
    return listSiteSurveys(token, project.id).then(setSurveys);
  }

  useEffect(() => {
    setLoading(true);
    load().catch((err) => setError(err.message)).finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, project.id]);

  async function handleCreate() {
    setError("");
    try {
      await createSiteSurvey(token, project.id, newForm);
      setNewForm({ client_name: "", site_address: "", pin_code: "", contact_name: "", contact_phone: "" });
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  if (loading) return <p className="text-center text-text-secondary mt-10">Loading site surveys…</p>;

  return (
    <div className="max-w-3xl mx-auto mt-4 sm:mt-8 mb-10 px-3 sm:px-4 space-y-4 sm:space-y-6">
      <div className="bg-surface shadow rounded-lg p-4 sm:p-6">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-lg font-semibold text-text-primary">Site Survey (Appendix C)</h2>
          {onBack && (
            <button onClick={onBack} className="text-sm text-gold hover:underline">
              &larr; Back
            </button>
          )}
        </div>
        <p className="text-xs text-text-secondary mt-1">
          A.3: "Site Engineer: Site survey form, actuals entry." Starts blank, filled in during the site visit, and
          completed once the surveyor, date and at least 4 photos are recorded.
        </p>
        {error && <p className="text-sm text-red-400 mt-2">{error}</p>}
      </div>

      {surveys.map((s) => (
        <SurveyCard key={s.id} token={token} survey={s} onChanged={load} />
      ))}

      {canWrite && (
        <div className="bg-surface shadow rounded-lg p-4 sm:p-6 space-y-2">
          <h3 className="text-sm font-semibold text-text-secondary">Start a new survey</h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            <input
              placeholder="Client" value={newForm.client_name}
              onChange={(e) => setNewForm((f) => ({ ...f, client_name: e.target.value }))}
              className="rounded border border-border-dark bg-surface-raised text-text-primary px-2 py-2 sm:py-1 text-sm"
            />
            <input
              placeholder="Site address" value={newForm.site_address}
              onChange={(e) => setNewForm((f) => ({ ...f, site_address: e.target.value }))}
              className="rounded border border-border-dark bg-surface-raised text-text-primary px-2 py-2 sm:py-1 text-sm"
            />
            <input
              placeholder="PIN code" value={newForm.pin_code}
              onChange={(e) => setNewForm((f) => ({ ...f, pin_code: e.target.value }))}
              className="rounded border border-border-dark bg-surface-raised text-text-primary px-2 py-2 sm:py-1 text-sm"
            />
            <input
              placeholder="Contact name" value={newForm.contact_name}
              onChange={(e) => setNewForm((f) => ({ ...f, contact_name: e.target.value }))}
              className="rounded border border-border-dark bg-surface-raised text-text-primary px-2 py-2 sm:py-1 text-sm"
            />
            <input
              placeholder="Contact phone" value={newForm.contact_phone}
              onChange={(e) => setNewForm((f) => ({ ...f, contact_phone: e.target.value }))}
              className="rounded border border-border-dark bg-surface-raised text-text-primary px-2 py-2 sm:py-1 text-sm"
            />
          </div>
          <button
            onClick={handleCreate}
            className="w-full sm:w-auto bg-gold text-base text-sm rounded px-4 py-2 hover:bg-gold-hover"
          >
            Start survey
          </button>
        </div>
      )}
    </div>
  );
}
