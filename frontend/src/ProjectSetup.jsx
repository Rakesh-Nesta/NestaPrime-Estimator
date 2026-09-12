import { useEffect, useState } from "react";
import {
  addProjectSport,
  createClient,
  createProject,
  getClientTypeDefaults,
  listClients,
  listHubs,
  listRegionalMultipliers,
  listSports,
} from "./api";

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

const CITIES = [
  "Mumbai", "Delhi NCR", "Bengaluru", "Hyderabad", "Chennai",
  "Pune", "Kolkata", "Ahmedabad", "Jaipur", "Lucknow", "Other",
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
  waterAvailable: true,
  numberOfCourts: 1,
  unitSystem: "feet",
  package: "standard",
  safeBearingCapacity: "",
  existingBuildingClearHeightFt: "",
};

export default function ProjectSetup({ token, onProjectCreated, onQuickSetupComplete }) {
  const [form, setForm] = useState(emptyForm);
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

  useEffect(() => {
    listClients(token).then(setClients).catch(() => {});
    listRegionalMultipliers(token).then(setMultipliers).catch(() => {});
    listHubs(token).then(setHubs).catch(() => {});
    listSports(token).then(setSports).catch(() => {});
  }, [token]);

  function set(field, value) {
    setForm((f) => ({ ...f, [field]: value }));
  }

  const cityInfo = multipliers.find((m) => m.city === form.city);
  const isExistingBuilding = form.buildingStatus === "existing_building";
  const isGovernment = form.clientMode === "new" && form.clientType === "government";

  const selectedExistingClient = clients.find((c) => c.id === form.existingClientId);
  const effectiveClientType = form.clientMode === "new" ? form.clientType : selectedExistingClient?.type;

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
        soil_type: form.soilType,
        building_status: form.buildingStatus,
        site_access: form.siteAccess,
        power_available: form.powerAvailable,
        water_available: form.waterAvailable,
        number_of_courts: Number(form.numberOfCourts),
        unit_system: form.unitSystem,
        package: form.package,
        safe_bearing_capacity: form.safeBearingCapacity ? Number(form.safeBearingCapacity) : null,
        existing_building_clear_height_ft: isExistingBuilding && form.existingBuildingClearHeightFt
          ? Number(form.existingBuildingClearHeightFt)
          : null,
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
      <div className="max-w-lg mx-auto mt-10 bg-white shadow rounded-lg p-8">
        <h2 className="text-lg font-semibold text-gray-900">Project created</h2>
        <p className="text-2xl font-mono mt-2 text-blue-700">{result.project_no}</p>

        <div className="mt-4 space-y-2 text-sm">
          <p className="text-gray-600">
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
          className="mt-6 w-full bg-blue-600 text-white rounded py-2 font-medium hover:bg-blue-700"
        >
          Select sports for this project &rarr;
        </button>
        <button
          onClick={() => { setResult(null); setForm(emptyForm); }}
          className="mt-2 w-full bg-white text-gray-600 border border-gray-300 rounded py-2 font-medium hover:bg-gray-50"
        >
          Start another project
        </button>
      </div>
    );
  }

  if (mode === "quick") {
    return (
      <form onSubmit={handleQuickSubmit} className="max-w-lg mx-auto mt-10 mb-10 bg-white shadow rounded-lg p-8 space-y-5">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-900">New Project — Quick setup</h2>
          <button type="button" onClick={() => setMode("detailed")} className="text-sm text-blue-600 hover:underline">
            Need more detail? Switch to Detailed setup
          </button>
        </div>
        <p className="text-xs text-gray-500 -mt-3">
          Five fields, everything else assumed (printed as T&amp;C on the Quotation) -- Amendment 2.
        </p>

        <fieldset className="space-y-3 border-t pt-4">
          <legend className="text-sm font-medium text-gray-700 -mt-7 bg-white pr-2">Client</legend>
          <div className="flex gap-4 text-sm">
            <label className="flex items-center gap-1">
              <input type="radio" checked={form.clientMode === "new"} onChange={() => set("clientMode", "new")} />
              New client
            </label>
            <label className="flex items-center gap-1">
              <input type="radio" checked={form.clientMode === "existing"} onChange={() => set("clientMode", "existing")} />
              Existing client
            </label>
          </div>

          {form.clientMode === "new" ? (
            <>
              <Text label="Client name" value={form.clientName} onChange={(v) => set("clientName", v)} required />
              <Select label="Client type" value={form.clientType} onChange={(v) => set("clientType", v)} options={CLIENT_TYPES} />
              {isGovernment && (
                <p className="text-xs text-amber-700 bg-amber-50 rounded px-2 py-1">
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
          <p className="text-xs text-gray-500 -mt-3">
            Dimensions: standard build {quickSport.build_dims} ft (customizable once Amendment 9 ships)
          </p>
        )}

        <Select label="City / district" value={form.city} onChange={(v) => set("city", v)} options={CITIES.map((c) => [c, c])} />
        {cityInfo && !cityInfo.is_confirmed && (
          <p className="text-xs text-amber-700 bg-amber-50 rounded px-2 py-1">
            Regional multipliers for {form.city} are seeded placeholders, not yet Director-confirmed.
          </p>
        )}

        <Select label="Base scope / status" value={form.projectType} onChange={(v) => set("projectType", v)} options={PROJECT_TYPES} />

        {error && <p className="text-sm text-red-600">{error}</p>}

        <button
          type="submit"
          disabled={submitting || !form.quickSportId}
          className="w-full bg-blue-600 text-white rounded py-2 font-medium hover:bg-blue-700 disabled:opacity-50"
        >
          {submitting ? "Creating…" : "Create project"}
        </button>
      </form>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="max-w-lg mx-auto mt-10 mb-10 bg-white shadow rounded-lg p-8 space-y-5">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-gray-900">New Project — Detailed setup</h2>
        {!forcesDetailed && (
          <button type="button" onClick={() => setMode("quick")} className="text-sm text-blue-600 hover:underline">
            Switch to Quick setup
          </button>
        )}
      </div>
      {forcesDetailed && (
        <p className="text-xs text-amber-700 bg-amber-50 rounded px-2 py-1 -mt-3">
          {effectiveClientType === "government"
            ? "Government clients need Detailed setup (Tender Mode fields)."
            : "No B.2 default package configured for this client type -- Quick setup needs one to auto-resolve Package."}
        </p>
      )}

      <Select label="Project type" value={form.projectType} onChange={(v) => set("projectType", v)} options={PROJECT_TYPES} />
      {form.projectType === "resurfacing" && (
        <p className="text-xs text-amber-700 bg-amber-50 rounded px-2 py-1">
          Resurfacing hides Site Prep, Base and Structure in the Cost Sheet builder — only Flooring, Line marking
          and Accessories apply (B.1).
        </p>
      )}
      {form.projectType === "supply_only" && (
        <p className="text-xs text-amber-700 bg-amber-50 rounded px-2 py-1">
          Supply only: goods delivered without installation (no labour, no site prep). Priced the same as a
          turnkey project — one blended rate including GST, not itemized per good (K.1b).
        </p>
      )}

      <fieldset className="space-y-3 border-t pt-4">
        <legend className="text-sm font-medium text-gray-700 -mt-7 bg-white pr-2">Client</legend>
        <div className="flex gap-4 text-sm">
          <label className="flex items-center gap-1">
            <input type="radio" checked={form.clientMode === "new"} onChange={() => set("clientMode", "new")} />
            New client
          </label>
          <label className="flex items-center gap-1">
            <input type="radio" checked={form.clientMode === "existing"} onChange={() => set("clientMode", "existing")} />
            Existing client
          </label>
        </div>

        {form.clientMode === "new" ? (
          <>
            <Text label="Client name" value={form.clientName} onChange={(v) => set("clientName", v)} required />
            <Select label="Client type" value={form.clientType} onChange={(v) => set("clientType", v)} options={CLIENT_TYPES} />
            {isGovernment && (
              <p className="text-xs text-amber-700 bg-amber-50 rounded px-2 py-1">
                Tender Mode will switch on automatically for this project (B.2).
              </p>
            )}
            <Text
              label="Payment terms"
              value={form.paymentTerms}
              onChange={(v) => set("paymentTerms", v)}
            />
            {typeDefaults?.package || typeDefaults?.payment_terms ? (
              <p className="text-xs text-blue-700 bg-blue-50 rounded px-2 py-1">
                B.2 recommends{typeDefaults.package && ` package ${typeDefaults.package}`}
                {typeDefaults.package && typeDefaults.payment_terms && " and"}
                {typeDefaults.payment_terms && ` payment terms ${typeDefaults.payment_terms}`} for this client
                type -- both prefilled below, editable.
              </p>
            ) : (
              <p className="text-xs text-gray-400">
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
        <legend className="text-sm font-medium text-gray-700 -mt-7 bg-white pr-2">Site</legend>
        <Select label="City / district" value={form.city} onChange={(v) => set("city", v)} options={CITIES.map((c) => [c, c])} />
        {cityInfo && !cityInfo.is_confirmed && (
          <p className="text-xs text-amber-700 bg-amber-50 rounded px-2 py-1">
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
        <NumberField
          label="Distance from hub (km)"
          value={form.distanceKm}
          onChange={(v) => set("distanceKm", v)}
          hint="Phase 1: manual entry from the selected hub -- PIN-code lookup is a later integration"
        />
        <Select label="Site condition" value={form.siteCondition} onChange={(v) => set("siteCondition", v)} options={SITE_CONDITIONS} />
        <Select label="Soil type" value={form.soilType} onChange={(v) => set("soilType", v)} options={SOIL_TYPES} />
        <Select label="Building status" value={form.buildingStatus} onChange={(v) => set("buildingStatus", v)} options={BUILDING_STATUSES} />
        {isExistingBuilding && (
          <NumberField
            label="Existing building clear height (ft)"
            value={form.existingBuildingClearHeightFt}
            onChange={(v) => set("existingBuildingClearHeightFt", v)}
          />
        )}
        <Select label="Site access" value={form.siteAccess} onChange={(v) => set("siteAccess", v)} options={SITE_ACCESS_OPTIONS} />
      </fieldset>

      <fieldset className="space-y-3 border-t pt-4">
        <legend className="text-sm font-medium text-gray-700 -mt-7 bg-white pr-2">Services & scope</legend>
        <Select label="Power available" value={form.powerAvailable} onChange={(v) => set("powerAvailable", v)} options={POWER_OPTIONS} />
        <label className="flex items-center gap-2 text-sm text-gray-700">
          <input type="checkbox" checked={form.waterAvailable} onChange={(e) => set("waterAvailable", e.target.checked)} />
          Water available
        </label>
        <NumberField label="Number of courts" value={form.numberOfCourts} onChange={(v) => set("numberOfCourts", v)} min={1} />
        <Select label="Unit system" value={form.unitSystem} onChange={(v) => set("unitSystem", v)} options={[["feet", "Feet"], ["metres", "Metres"]]} />
        <Select label="Package" value={form.package} onChange={(v) => set("package", v)} options={PACKAGES} />
        {form.clientMode === "existing" && typeDefaults?.package && (
          <p className="text-xs text-blue-700 bg-blue-50 rounded px-2 py-1">
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

      {error && <p className="text-sm text-red-600">{error}</p>}

      <button
        type="submit"
        disabled={submitting}
        className="w-full bg-blue-600 text-white rounded py-2 font-medium hover:bg-blue-700 disabled:opacity-50"
      >
        {submitting ? "Creating…" : "Create project"}
      </button>
    </form>
  );
}

function Flag({ label, active, onText, offText }) {
  return (
    <div className={`rounded px-3 py-2 ${active ? "bg-amber-50 text-amber-800" : "bg-gray-50 text-gray-500"}`}>
      <span className="font-medium">{label}:</span> {active ? onText : offText}
    </div>
  );
}

function Text({ label, value, onChange, required }) {
  return (
    <div>
      <label className="block text-sm font-medium text-gray-700">{label}</label>
      <input
        type="text"
        required={required}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="mt-1 w-full rounded border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
      />
    </div>
  );
}

function NumberField({ label, value, onChange, min, hint }) {
  return (
    <div>
      <label className="block text-sm font-medium text-gray-700">{label}</label>
      <input
        type="number"
        min={min}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="mt-1 w-full rounded border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
      />
      {hint && <p className="text-xs text-gray-400 mt-0.5">{hint}</p>}
    </div>
  );
}

function Select({ label, value, onChange, options, placeholder, required }) {
  return (
    <div>
      <label className="block text-sm font-medium text-gray-700">{label}</label>
      <select
        required={required}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="mt-1 w-full rounded border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
      >
        {placeholder && <option value="">{placeholder}</option>}
        {options.map(([val, label]) => (
          <option key={val} value={val}>{label}</option>
        ))}
      </select>
    </div>
  );
}
