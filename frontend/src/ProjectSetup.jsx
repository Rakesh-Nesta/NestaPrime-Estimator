import { useEffect, useRef, useState } from "react";
import {
  addProjectSport,
  createClient,
  createProject,
  getClientTypeDefaults,
  listClients,
  listFieldSettings,
  listHubs,
  listRegionalMultipliers,
  listSports,
} from "./api";
import SelectWithOther from "./SelectWithOther";

const PROJECT_TYPES = [
  ["new_build", "New Build"],
  ["resurfacing", "Resurfacing"],
  ["repair", "Repair"],
  ["supply_only", "Supply only"],
];

const CLIENT_TYPES = [
  ["school", "School"],
  ["college", "College"],
  ["housing_society", "Housing Society"],
  ["corporate", "Corporate"],
  ["club", "Club"],
  ["government", "Government (Tender)"],
  ["individual", "Individual"],
];

// Section 22: no trailing "Other" entry -- SelectWithOther supplies its own
// "Others…" option and reveals a real text input, replacing the old inert
// literal-string "Other" value that meant nothing to the backend.
const CITIES = [
  "Mumbai", "Delhi NCR", "Bengaluru", "Hyderabad", "Chennai",
  "Pune", "Kolkata", "Ahmedabad", "Jaipur", "Lucknow",
];

const SITE_CONDITIONS = [["level", "Level"], ["sloped", "Sloped"], ["water_logged", "Water-logged"]];
const SOIL_TYPES = [
  ["normal", "Normal"], ["rocky", "Rocky"], ["black_cotton", "Black cotton"],
  ["sandy", "Sandy"], ["filled", "Filled (loose)"],
];
const BUILDING_STATUSES = [
  ["existing_building", "Existing building"], ["new_peb_building", "New PEB building"],
  ["open_air", "Open air"], ["covered_shed", "Covered shed"],
];
const SITE_ACCESS_OPTIONS = [
  ["good", "Good"], ["narrow_road", "Narrow road (< 4 m)"], ["no_crane_access", "No crane access"],
];
const POWER_OPTIONS = [["yes", "Yes"], ["no", "No"], ["partial", "Partial"]];
const WATER_OPTIONS = [["yes", "Yes"], ["no", "No"]];
const PACKAGES = [["budget", "Budget"], ["standard", "Standard"], ["premium", "Premium"]];

const emptyForm = {
  projectType: "new_build",
  clientMode: "new", // "new" | "existing"
  existingClientId: "",
  clientName: "",
  clientType: "school",
  paymentTerms: "",
  quickSportId: "",
  city: "Mumbai",
  siteAddress: "",
  hubId: "",
  distanceKm: "",
  siteCondition: "level",
  soilType: "normal",
  buildingStatus: "open_air",
  siteAccess: "good",
  powerAvailable: "yes",
  waterAvailable: "yes",
  numberOfCourts: 1,
  unitSystem: "feet",
  package: "standard",
  safeBearingCapacity: "",
  existingBuildingClearHeightFt: "",
};

// Amendment 44 Phase C: startFrom = { opportunityId, clientId, clientName,
// leadName } when reached via "Start Project" on a Won Opportunity -- the
// client is pre-selected and locked (the backend rejects a mismatch anyway),
// and opportunity_id rides along on createProject so the new Project records
// where it came from.
export default function ProjectSetup({ token, onProjectCreated, onQuickSetupComplete, startFrom = null }) {
  const [form, setForm] = useState(
    startFrom ? { ...emptyForm, clientMode: "existing", existingClientId: startFrom.clientId } : emptyForm
  );
  const opportunityField = startFrom ? { opportunity_id: startFrom.opportunityId } : {};
  const [clients, setClients] = useState([]);
  const [multipliers, setMultipliers] = useState([]);
  const [hubs, setHubs] = useState([]);
  const [sports, setSports] = useState([]);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState(null);
  // Amendment 2: Quick is the default -- 5 fields, blind-quoting defaults
  // for everything else. Detailed is today's full form, unchanged.
  const [mode, setMode] = useState("quick"); // "quick" | "detailed"
  // Amendment 5 Phase 2: field_key -> "compulsory" | "optional" | "hidden".
  // A field with no entry yet (still loading, or the Director never set
  // it) is treated as compulsory -- today's real behavior.
  const [fieldSettings, setFieldSettings] = useState({});

  useEffect(() => {
    listClients(token).then(setClients).catch(() => {});
    listRegionalMultipliers(token).then(setMultipliers).catch(() => {});
    listHubs(token).then(setHubs).catch(() => {});
    listSports(token).then(setSports).catch(() => {});
    listFieldSettings(token)
      .then((rows) => setFieldSettings(Object.fromEntries(rows.map((r) => [r.field_key, r.state]))))
      .catch(() => {});
  }, [token]);

  function fieldState(key) {
    return fieldSettings[key] || "compulsory";
  }

  function set(field, value) {
    setForm((f) => ({ ...f, [field]: value }));
  }

  const cityInfo = multipliers.find((m) => m.city === form.city);
  const isExistingBuilding = form.buildingStatus === "existing_building";
  const isGovernment = form.clientMode === "new" && form.clientType === "government";

  const selectedExistingClient = clients.find((c) => c.id === form.existingClientId);
  const effectiveClientType = form.clientMode === "new" ? form.clientType : selectedExistingClient?.type;

  // Amendment 37 (Section 43): choosing an existing client pre-fills the
  // project's city from that client's own record -- but ONLY when the client has
  // one. A client with no city on record leaves whatever the user already had;
  // it never forces the field back to "Mumbai" or blank. It only changes what
  // the form starts with (like package/payment terms), never an existing project.
  // Its own effect, applied once per selected client: the type-defaults effect
  // below only re-runs when the client TYPE changes, so two clients of the same
  // type would never re-trigger it.
  const cityFilledFor = useRef(null);
  // SelectWithOther decides whether to show its "Others" text box once, when it
  // first appears. A client's free-text city (e.g. "Nagpur") is not in the
  // dropdown's list, so bumping this key remounts the field with the new value
  // and it shows the real city instead of a blank "Select...".
  const [cityFieldKey, setCityFieldKey] = useState(0);
  useEffect(() => {
    if (form.clientMode !== "existing" || !selectedExistingClient) return;
    if (cityFilledFor.current === selectedExistingClient.id) return;
    cityFilledFor.current = selectedExistingClient.id;
    if (selectedExistingClient.city) {
      setForm((f) => ({ ...f, city: selectedExistingClient.city }));
      setCityFieldKey((k) => k + 1);
    }
  }, [form.clientMode, selectedExistingClient]);

  // B.2: "Client = School -> Package Standard . Payment 40/40/20" -- both
  // prefilled here as a starting suggestion whenever the effective client
  // type changes; Sales can still type over either before submitting.
  const [typeDefaults, setTypeDefaults] = useState(null);
  useEffect(() => {
    if (!effectiveClientType) {
      setTypeDefaults(null);
      return;
    }
    let cancelled = false;
    getClientTypeDefaults(token, effectiveClientType)
      .then((d) => {
        if (cancelled) return;
        setTypeDefaults(d);
        setForm((f) => ({
          ...f,
          package: d.package || f.package,
          paymentTerms: f.clientMode === "new" && d.payment_terms ? d.payment_terms : f.paymentTerms,
        }));
      })
      .catch(() => setTypeDefaults(null));
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, effectiveClientType]);

  // Amendment 2 spec: Government/Tender clients and any client type with no
  // B.2 package default get routed to Detailed mode automatically -- Quick
  // mode's own package field relies on that default existing to auto-resolve
  // silently, and Tender Mode's extra fields aren't part of the 5-field flow.
  const forcesDetailed = effectiveClientType === "government" || (typeDefaults !== null && !typeDefaults?.package);
  useEffect(() => {
    if (forcesDetailed && mode === "quick") {
      setMode("detailed");
    }
  }, [forcesDetailed, mode]);

  const quickSport = sports.find((s) => s.id === form.quickSportId);

  async function handleQuickSubmit(e) {
    e.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      let clientId = form.existingClientId;
      if (form.clientMode === "new") {
        const client = await createClient(token, {
          name: form.clientName,
          type: form.clientType,
          payment_terms: form.paymentTerms || null,
        });
        clientId = client.id;
      }

      const project = await createProject(token, {
        client_id: clientId,
        project_type: form.projectType,
        city: form.city,
        site_condition: "level",
        soil_type: "normal",
        building_status: "open_air",
        site_access: "good",
        power_available: "yes",
        water_available: true,
        number_of_courts: 1,
        unit_system: "feet",
        quick_setup: true,
        ...opportunityField,
      });

      await addProjectSport(token, project.id, {
        sport_id: form.quickSportId,
        building_status: "open_air",
        number_of_courts: 1,
      });

      onQuickSetupComplete(project);
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      let clientId = form.existingClientId;
      if (form.clientMode === "new") {
        const client = await createClient(token, {
          name: form.clientName,
          type: form.clientType,
          payment_terms: form.paymentTerms || null,
        });
        clientId = client.id;
      }

      const project = await createProject(token, {
        client_id: clientId,
        project_type: form.projectType,
        city: form.city,
        site_address: form.siteAddress || null,
        hub_id: form.hubId || null,
        distance_km: form.distanceKm ? Number(form.distanceKm) : null,
        site_condition: form.siteCondition,
        soil_type: form.soilType || null,
        building_status: form.buildingStatus,
        site_access: form.siteAccess || null,
        power_available: form.powerAvailable || null,
        // Unlike power_available (a string enum backend-side),
        // water_available is a real boolean column -- convert the
        // Select's "yes"/"no"/"" string state to true/false/null.
        water_available: form.waterAvailable === "" ? null : form.waterAvailable === "yes",
        number_of_courts: Number(form.numberOfCourts),
        unit_system: form.unitSystem,
        package: form.package,
        safe_bearing_capacity: form.safeBearingCapacity ? Number(form.safeBearingCapacity) : null,
        existing_building_clear_height_ft: isExistingBuilding && form.existingBuildingClearHeightFt
          ? Number(form.existingBuildingClearHeightFt)
          : null,
        ...opportunityField,
      });

      setResult(project);
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  }

  if (result) {
    return (
      <div className="max-w-lg mx-auto mt-10 bg-surface shadow rounded-lg p-8">
        <h2 className="text-lg font-semibold text-text-primary">Project created</h2>
        <p className="text-2xl font-mono mt-2 text-gold-hover">{result.project_no}</p>

        <div className="mt-4 space-y-2 text-sm">
          <p className="text-text-secondary">
            <span className="font-medium">Project type:</span>{" "}
            {PROJECT_TYPES.find(([v]) => v === result.project_type)?.[1] ?? result.project_type}
          </p>
          <Flag label="Tender Mode" active={result.tender_mode} onText="ON — Government client (B.2)" offText="Off" />
          <Flag
            label="Soil test"
            active={result.soil_test_required}
            onText="Required before foundation design (D.4)"
            offText="Not required"
          />
          <Flag
            label="Rock breaking"
            active={result.rock_breaking_required}
            onText="Required — rocky soil (D.4)"
            offText="Not required"
          />
          <Flag
            label="Sand + CNS layer"
            active={result.sand_cns_layer_required}
            onText="Required — black cotton soil (D.4)"
            offText="Not required"
          />
          <Flag
            label="Dewatering"
            active={result.dewatering_required}
            onText="Required — water-logged site (D.4)"
            offText="Not required"
          />
        </div>

        <button
          onClick={() => onProjectCreated(result)}
          className="mt-6 w-full bg-gold text-base rounded py-2 font-medium hover:bg-gold-hover"
        >
          Select sports for this project &rarr;
        </button>
        {!startFrom && (
        <button
          onClick={() => { setResult(null); setForm(emptyForm); }}
          className="mt-2 w-full bg-surface text-text-secondary border border-border-dark bg-surface-raised text-text-primary rounded py-2 font-medium hover:bg-surface-raised"
        >
          Start another project
        </button>
        )}
      </div>
    );
  }

  if (mode === "quick") {
    return (
      <form onSubmit={handleQuickSubmit} className="max-w-lg mx-auto mt-10 mb-10 bg-surface shadow rounded-lg p-8 space-y-5">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-text-primary">New Project — Quick setup</h2>
          <button type="button" onClick={() => setMode("detailed")} className="text-sm text-gold hover:underline">
            Need more detail? Switch to Detailed setup
          </button>
        </div>
        <p className="text-xs text-text-secondary -mt-3">
          Five fields, everything else assumed (printed as T&amp;C on the Quotation) -- Amendment 2.
        </p>

        <fieldset className="space-y-3 border-t pt-4">
          <legend className="text-sm font-medium text-text-secondary -mt-7 bg-surface pr-2">Client</legend>
          {startFrom && (
          <p className="text-xs text-gold bg-gold-muted rounded px-2 py-1.5">
            Starting from Opportunity "{startFrom.leadName}" -- client is fixed to {startFrom.clientName}.
          </p>
          )}
          <div className={`flex gap-4 text-sm ${startFrom ? "hidden" : ""}`}>
            <label className="flex items-center gap-1">
              <input type="radio" checked={form.clientMode === "new"} onChange={() => set("clientMode", "new")} />
              New client
            </label>
            <label className="flex items-center gap-1">
              <input type="radio" checked={form.clientMode === "existing"} onChange={() => set("clientMode", "existing")} />
              Existing client
            </label>
          </div>

          {startFrom ? null : form.clientMode === "new" ? (
            <>
              <Text label="Client name" value={form.clientName} onChange={(v) => set("clientName", v)} required />
              <Select label="Client type" value={form.clientType} onChange={(v) => set("clientType", v)} options={CLIENT_TYPES} />
              {isGovernment && (
                <p className="text-xs text-amber-400 bg-amber-500/10 rounded px-2 py-1">
                  Government clients need Detailed setup (Tender Mode fields) -- switching automatically.
                </p>
              )}
            </>
          ) : (
            <Select
              label="Client"
              value={form.existingClientId}
              onChange={(v) => set("existingClientId", v)}
              options={clients.map((c) => [c.id, `${c.name} (${c.type})`])}
              placeholder="Select a client…"
              required
            />
          )}
        </fieldset>

        <Select
          label="Sport"
          value={form.quickSportId}
          onChange={(v) => set("quickSportId", v)}
          options={sports.map((s) => [s.id, s.name])}
          placeholder="Select a sport…"
          required
        />
        {quickSport && (
          <p className="text-xs text-text-secondary -mt-3">
            Dimensions: standard build {quickSport.build_dims} ft (customize on the next screen)
          </p>
        )}

        <SelectWithOther key={cityFieldKey} label="City / district" value={form.city} onChange={(v) => set("city", v)} options={CITIES} required />
        {cityInfo && !cityInfo.is_confirmed && (
          <p className="text-xs text-amber-400 bg-amber-500/10 rounded px-2 py-1">
            Regional multipliers for {form.city} are seeded placeholders, not yet Director-confirmed.
          </p>
        )}

        <Select label="Base scope / status" value={form.projectType} onChange={(v) => set("projectType", v)} options={PROJECT_TYPES} />

        {error && <p className="text-sm text-red-400">{error}</p>}

        <button
          type="submit"
          disabled={submitting || !form.quickSportId}
          className="w-full bg-gold text-base rounded py-2 font-medium hover:bg-gold-hover disabled:opacity-50"
        >
          {submitting ? "Creating…" : "Create project"}
        </button>
      </form>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="max-w-lg mx-auto mt-10 mb-10 bg-surface shadow rounded-lg p-8 space-y-5">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-text-primary">New Project — Detailed setup</h2>
        {!forcesDetailed && (
          <button type="button" onClick={() => setMode("quick")} className="text-sm text-gold hover:underline">
            Switch to Quick setup
          </button>
        )}
      </div>
      {forcesDetailed && (
        <p className="text-xs text-amber-400 bg-amber-500/10 rounded px-2 py-1 -mt-3">
          {effectiveClientType === "government"
            ? "Government clients need Detailed setup (Tender Mode fields)."
            : "No B.2 default package configured for this client type -- Quick setup needs one to auto-resolve Package."}
        </p>
      )}

      <Select label="Project type" value={form.projectType} onChange={(v) => set("projectType", v)} options={PROJECT_TYPES} />
      {form.projectType === "resurfacing" && (
        <p className="text-xs text-amber-400 bg-amber-500/10 rounded px-2 py-1">
          Resurfacing hides Site Prep, Base and Structure in the Cost Sheet builder — only Flooring, Line marking
          and Accessories apply (B.1).
        </p>
      )}
      {form.projectType === "supply_only" && (
        <p className="text-xs text-amber-400 bg-amber-500/10 rounded px-2 py-1">
          Supply only: goods delivered without installation (no labour, no site prep). Priced the same as a
          turnkey project — one blended rate including GST, not itemized per good (K.1b).
        </p>
      )}

      <fieldset className="space-y-3 border-t pt-4">
        <legend className="text-sm font-medium text-text-secondary -mt-7 bg-surface pr-2">Client</legend>
        {startFrom && (
        <p className="text-xs text-gold bg-gold-muted rounded px-2 py-1.5">
          Starting from Opportunity "{startFrom.leadName}" -- client is fixed to {startFrom.clientName}.
        </p>
        )}
        <div className={`flex gap-4 text-sm ${startFrom ? "hidden" : ""}`}>
          <label className="flex items-center gap-1">
            <input type="radio" checked={form.clientMode === "new"} onChange={() => set("clientMode", "new")} />
            New client
          </label>
          <label className="flex items-center gap-1">
            <input type="radio" checked={form.clientMode === "existing"} onChange={() => set("clientMode", "existing")} />
            Existing client
          </label>
        </div>

        {startFrom ? null : form.clientMode === "new" ? (
          <>
            <Text label="Client name" value={form.clientName} onChange={(v) => set("clientName", v)} required />
            <Select label="Client type" value={form.clientType} onChange={(v) => set("clientType", v)} options={CLIENT_TYPES} />
            {isGovernment && (
              <p className="text-xs text-amber-400 bg-amber-500/10 rounded px-2 py-1">
                Tender Mode will switch on automatically for this project (B.2).
              </p>
            )}
            <Text
              label="Payment terms"
              value={form.paymentTerms}
              onChange={(v) => set("paymentTerms", v)}
            />
            {typeDefaults?.package || typeDefaults?.payment_terms ? (
              <p className="text-xs text-gold-hover bg-gold-muted rounded px-2 py-1">
                B.2 recommends{typeDefaults.package && ` package ${typeDefaults.package}`}
                {typeDefaults.package && typeDefaults.payment_terms && " and"}
                {typeDefaults.payment_terms && ` payment terms ${typeDefaults.payment_terms}`} for this client
                type -- both prefilled below, editable.
              </p>
            ) : (
              <p className="text-xs text-text-secondary">
                No B.2 default package/payment terms configured for this client type yet -- pick a package below.
              </p>
            )}
          </>
        ) : (
          <Select
            label="Client"
            value={form.existingClientId}
            onChange={(v) => set("existingClientId", v)}
            options={clients.map((c) => [c.id, `${c.name} (${c.type})`])}
            placeholder="Select a client…"
            required
          />
        )}
      </fieldset>

      <fieldset className="space-y-3 border-t pt-4">
        <legend className="text-sm font-medium text-text-secondary -mt-7 bg-surface pr-2">Site</legend>
        <SelectWithOther key={cityFieldKey} label="City / district" value={form.city} onChange={(v) => set("city", v)} options={CITIES} required />
        {cityInfo && !cityInfo.is_confirmed && (
          <p className="text-xs text-amber-400 bg-amber-500/10 rounded px-2 py-1">
            Regional multipliers for {form.city} are seeded placeholders, not yet Director-confirmed.
          </p>
        )}
        <Text label="Site address" value={form.siteAddress} onChange={(v) => set("siteAddress", v)} />
        <Select
          label="Nearest NestaPrime hub"
          value={form.hubId}
          onChange={(v) => set("hubId", v)}
          options={hubs.map((h) => [h.id, `${h.name} (${h.city}, ${h.state_code})`])}
          placeholder={hubs.length ? "Select a hub…" : "No hubs configured yet (Q.1)"}
        />
        {fieldState("distance_km") !== "hidden" && (
          <NumberField
            label="Distance from hub (km)"
            value={form.distanceKm}
            onChange={(v) => set("distanceKm", v)}
            hint="Phase 1: manual entry from the selected hub -- PIN-code lookup is a later integration"
          />
        )}
        <Select label="Site condition" value={form.siteCondition} onChange={(v) => set("siteCondition", v)} options={SITE_CONDITIONS} />
        {fieldState("soil_type") !== "hidden" && (
          <Select
            label="Soil type"
            value={form.soilType}
            onChange={(v) => set("soilType", v)}
            options={SOIL_TYPES}
            placeholder={fieldState("soil_type") === "optional" ? "None" : undefined}
          />
        )}
        <Select label="Building status" value={form.buildingStatus} onChange={(v) => set("buildingStatus", v)} options={BUILDING_STATUSES} />
        {isExistingBuilding && (
          <NumberField
            label="Existing building clear height (ft)"
            value={form.existingBuildingClearHeightFt}
            onChange={(v) => set("existingBuildingClearHeightFt", v)}
          />
        )}
        {fieldState("site_access") !== "hidden" && (
          <Select
            label="Site access"
            value={form.siteAccess}
            onChange={(v) => set("siteAccess", v)}
            options={SITE_ACCESS_OPTIONS}
            placeholder={fieldState("site_access") === "optional" ? "None" : undefined}
          />
        )}
      </fieldset>

      <fieldset className="space-y-3 border-t pt-4">
        <legend className="text-sm font-medium text-text-secondary -mt-7 bg-surface pr-2">Services & scope</legend>
        {fieldState("power_available") !== "hidden" && (
          <Select
            label="Power available"
            value={form.powerAvailable}
            onChange={(v) => set("powerAvailable", v)}
            options={POWER_OPTIONS}
            placeholder={fieldState("power_available") === "optional" ? "None" : undefined}
          />
        )}
        {fieldState("water_available") !== "hidden" && (
          <Select
            label="Water available"
            value={form.waterAvailable}
            onChange={(v) => set("waterAvailable", v)}
            options={WATER_OPTIONS}
            placeholder={fieldState("water_available") === "optional" ? "None" : undefined}
          />
        )}
        {fieldState("number_of_courts") !== "hidden" && (
          <NumberField label="Number of courts" value={form.numberOfCourts} onChange={(v) => set("numberOfCourts", v)} min={1} />
        )}
        <Select label="Unit system" value={form.unitSystem} onChange={(v) => set("unitSystem", v)} options={[["feet", "Feet"], ["metres", "Metres"]]} />
        <Select label="Package" value={form.package} onChange={(v) => set("package", v)} options={PACKAGES} />
        {form.clientMode === "existing" && typeDefaults?.package && (
          <p className="text-xs text-gold-hover bg-gold-muted rounded px-2 py-1">
            B.2 recommends package {typeDefaults.package} for {selectedExistingClient?.type} clients -- prefilled
            above, editable.
          </p>
        )}
        <NumberField
          label="Safe bearing capacity (kN/sqm)"
          value={form.safeBearingCapacity}
          onChange={(v) => set("safeBearingCapacity", v)}
          hint="Blank until a soil report exists"
        />
      </fieldset>

      {error && <p className="text-sm text-red-400">{error}</p>}

      <button
        type="submit"
        disabled={submitting}
        className="w-full bg-gold text-base rounded py-2 font-medium hover:bg-gold-hover disabled:opacity-50"
      >
        {submitting ? "Creating…" : "Create project"}
      </button>
    </form>
  );
}

function Flag({ label, active, onText, offText }) {
  return (
    <div className={`rounded px-3 py-2 ${active ? "bg-amber-500/10 text-amber-400" : "bg-surface-raised text-text-secondary"}`}>
      <span className="font-medium">{label}:</span> {active ? onText : offText}
    </div>
  );
}

function Text({ label, value, onChange, required }) {
  return (
    <div>
      <label className="block text-sm font-medium text-text-secondary">{label}</label>
      <input
        type="text"
        required={required}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="mt-1 w-full rounded border border-border-dark bg-surface-raised text-text-primary px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-gold"
      />
    </div>
  );
}

function NumberField({ label, value, onChange, min, hint }) {
  return (
    <div>
      <label className="block text-sm font-medium text-text-secondary">{label}</label>
      <input
        type="number"
        min={min}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="mt-1 w-full rounded border border-border-dark bg-surface-raised text-text-primary px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-gold"
      />
      {hint && <p className="text-xs text-text-secondary mt-0.5">{hint}</p>}
    </div>
  );
}

function Select({ label, value, onChange, options, placeholder, required }) {
  return (
    <div>
      <label className="block text-sm font-medium text-text-secondary">{label}</label>
      <select
        required={required}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="mt-1 w-full rounded border border-border-dark bg-surface-raised text-text-primary px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-gold"
      >
        {placeholder && <option value="">{placeholder}</option>}
        {options.map(([val, label]) => (
          <option key={val} value={val}>{label}</option>
        ))}
      </select>
    </div>
  );
}
