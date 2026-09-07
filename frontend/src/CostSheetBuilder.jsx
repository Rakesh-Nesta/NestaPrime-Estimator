import { useEffect, useState } from "react";
import PurchaseOrdersPanel from "./PurchaseOrdersPanel";
import {
  addAccessoriesTakeoff,
  addAcrylicPuTakeoff,
  addBaseTakeoff,
  addCostSheetLine,
  addDrainageTakeoff,
  addHvacTakeoff,
  addLightingTakeoff,
  addLineMarkingTakeoff,
  addStructureTakeoff,
  addTurfTakeoff,
  addWoodenFlooringTakeoff,
  deleteCostSheetLine,
  getConsumptionSheet,
  getLabourWarnings,
  listCostSheetLines,
  listLabourCategories,
  recomputeCostSheet,
  verifyCostSheet,
} from "./api";

const TABS = [
  { key: "structure", label: "Structures (E)" },
  { key: "base", label: "Base (D.1)" },
  { key: "drainage", label: "Drainage (D.3)" },
  { key: "turf", label: "Turf (F.5)" },
  { key: "wooden", label: "Wooden floor (F.3)" },
  { key: "acrylic_pu", label: "Acrylic/PU (F.2)" },
  { key: "line_marking", label: "Line marking (F.6)" },
  { key: "lighting", label: "Lighting (H)" },
  { key: "hvac", label: "HVAC (G.5)" },
  { key: "accessories", label: "Accessories (I)" },
  { key: "manual", label: "Manual line" },
];

// Mirrors the backend's ACCESSORY_CATALOG (app/api/accessories.py) --
// purely to render one rate input per known item; the backend stays the
// source of truth and rejects the request if a rate is missing, so a
// stale/incomplete list here only means a plainer form, not a silent gap.
const ACCESSORY_CATALOG = {
  badminton: [["Badminton net + post set", "set", 1]],
  table_tennis: [["Table tennis net + post set", "set", 1]],
  basketball_indoor: [["Basketball goal (backboard + ring)", "nos", 2]],
  basketball_outdoor: [["Basketball goal (backboard + ring)", "nos", 2]],
  volleyball_indoor: [["Volleyball net + post set", "set", 1]],
  volleyball_outdoor: [["Volleyball net + post set", "set", 1]],
  beach_volleyball: [["Volleyball net + post set", "set", 1]],
  indoor_cricket_nets: [["Cricket stumps set (2 ends)", "set", 1]],
  cricket_practice_nets: [["Cricket stumps set (2 ends)", "set", 1]],
  box_cricket: [["Cricket stumps set (2 ends)", "set", 1]],
  football_11: [["Football goal with net", "nos", 2]],
  football_7: [["Football goal with net", "nos", 2]],
  football_5_futsal: [["Football goal with net", "nos", 2]],
  tennis: [["Tennis net + post set", "set", 1]],
  padel: [
    ["Padel glass wall/door panel set", "set", 1],
    ["Padel net", "nos", 1],
  ],
  pickleball: [["Pickleball net + post set", "set", 1]],
  hockey_turf: [["Hockey goal with net", "nos", 2]],
  athletic_track_400m: [["Starting block", "nos", 8]],
  archery_range: [["Archery target (butt/boss)", "nos", 1]],
};

// ---------------------------------------------------------------------------
// Recommendation-layer wiring: Sport Selection's D.2/E.4/F.1-F.2/H
// recommendations (recommended_base/structure/flooring/lighting on each
// ProjectSport) are prose, not the take-off calculators' strict enums, so
// each mapper below only offers a one-click "Use recommendation" fill when
// it can confidently parse a match -- otherwise it shows the recommendation
// as a plain hint and leaves the field for the PM to set. G.5 (HVAC) and
// D.3 (Drainage) never had a recommendation layer, so those two forms have
// nothing to wire.
// ---------------------------------------------------------------------------

const SECTION_TEXT_TO_ENUM = {
  "2.5 in x 2.5 in": "shs_2_5",
  "3 in x 3 in": "shs_3",
  "4 in x 4 in": "shs_4",
  "5 in x 5 in": "shs_5",
  "6 in x 6 in": "shs_6",
  "2.5 in gi round": "round_2_5",
  "100x50 rhs": "rhs_100_50",
  "80x40 rhs": "rhs_80_40",
};

function mapStructureType(text) {
  // "A" -> {type:"a"}; "C (tall variant) + D" -> {type:"c", tallVariant:true}
  const m = /^([A-G])\b(\s*\(tall variant\))?/i.exec(text || "");
  if (!m) return null;
  return { type: m[1].toLowerCase(), tallVariant: !!m[2] };
}

function mapSection(text) {
  return SECTION_TEXT_TO_ENUM[(text || "").trim().toLowerCase()] ?? null;
}

function parseLeadingNumber(text) {
  const m = /(\d+(?:\.\d+)?)/.exec(text || "");
  return m ? Number(m[1]) : null;
}

function mapBaseType(text) {
  const t = (text || "").trim().toLowerCase();
  if (t.startsWith("pcc")) return "pcc";
  if (t.startsWith("wbm")) return "wbm";
  if (t.startsWith("rcc")) return "rcc";
  if (t.startsWith("asphalt")) return "asphalt";
  return null;
}

function mapPileHeight(text) {
  if (!/turf/i.test(text || "")) return null;
  const m = /(\d+)(?:-(\d+))?\s*mm/i.exec(text || "");
  if (!m) return null;
  if (m[2]) return "50_60mm_fifa_quality_pro"; // e.g. "50-60 mm"
  const table = { 30: "30mm", 40: "40mm", 50: "50mm_fifa_quality" };
  return table[Number(m[1])] ?? null;
}

function parseFixtureSpec(spec) {
  const w = /([\d,]+)\s*W/i.exec(spec || "");
  const lm = /([\d,]+)\s*lm/i.exec(spec || "");
  return {
    wattage: w ? Number(w[1].replace(/,/g, "")) : null,
    lumens: lm ? Number(lm[1].replace(/,/g, "")) : null,
  };
}

function RecommendationBanner({ label, text, why, onUse, note }) {
  if (!text) return null;
  return (
    <div className="bg-emerald-50 border border-emerald-100 rounded px-3 py-2 text-xs flex items-center justify-between gap-3">
      <p className="text-emerald-800">
        <span className="font-semibold">{label}:</span> {text}
        {why && <span className="text-emerald-600"> — {why}</span>}
        {note && <span className="text-emerald-500"> ({note})</span>}
      </p>
      {onUse && (
        <button type="button" onClick={onUse} className="shrink-0 text-emerald-700 font-medium hover:underline">
          Use recommendation
        </button>
      )}
    </div>
  );
}

function Field({ label, children, hint }) {
  return (
    <div>
      <label className="block text-xs font-medium text-gray-600">{label}</label>
      {children}
      {hint && <p className="text-[11px] text-gray-400 mt-0.5">{hint}</p>}
    </div>
  );
}

function NumberInput({ value, onChange, ...props }) {
  return (
    <input
      type="number"
      step="any"
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="mt-0.5 w-full rounded border border-gray-300 px-2 py-1.5 text-sm"
      {...props}
    />
  );
}

function TextInput({ value, onChange, ...props }) {
  return (
    <input
      type="text"
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="mt-0.5 w-full rounded border border-gray-300 px-2 py-1.5 text-sm"
      {...props}
    />
  );
}

function SelectInput({ value, onChange, options, ...props }) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="mt-0.5 w-full rounded border border-gray-300 px-2 py-1.5 text-sm"
      {...props}
    >
      {options.map((o) => (
        <option key={o.value} value={o.value}>
          {o.label}
        </option>
      ))}
    </select>
  );
}

function CheckboxField({ label, checked, onChange }) {
  return (
    <label className="flex items-center gap-2 text-sm text-gray-700 mt-1">
      <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} />
      {label}
    </label>
  );
}

function ProjectSportSelect({ value, onChange, projectSports, sportsById }) {
  return (
    <Field label="Sport">
      <SelectInput
        value={value}
        onChange={onChange}
        options={[
          { value: "", label: "Select a sport…" },
          ...projectSports.map((ps) => ({
            value: ps.id,
            label: sportsById[ps.sport_id]?.name ?? ps.sport_id,
          })),
        ]}
      />
    </Field>
  );
}

function BreakdownPanel({ result }) {
  if (!result) return null;
  return (
    <div className="bg-blue-50 border border-blue-100 rounded p-3 text-xs space-y-1">
      <p className="font-semibold text-blue-800">Computed breakdown</p>
      <pre className="whitespace-pre-wrap text-blue-900">{JSON.stringify(result.breakdown, null, 2)}</pre>
      <p className="text-blue-700">{result.lines.length} line(s) added to the Cost Sheet.</p>
    </div>
  );
}

function num(v) {
  return v === "" || v === undefined ? undefined : Number(v);
}

// ---------------------------------------------------------------------------
// Structures (Part E)
// ---------------------------------------------------------------------------

const SECTIONS = [
  "shs_2_5", "shs_3", "shs_4", "shs_5", "shs_6", "rhs_80_40", "rhs_100_50", "round_2", "round_2_5", "round_3",
];
const ROUND_SECTIONS = new Set(["round_2", "round_2_5", "round_3"]);

function StructureForm({ token, costSheetId, projectSports, sportsById, onAdded }) {
  const [f, setF] = useState({
    project_sport_id: "", structure_type: "a", section: "shs_3", wall_thickness_mm: "2.0",
    build_l_ft: "", build_w_ft: "", height_ft: "", column_spacing_ft: "", foundation_depth_ft: "",
    tall_variant: false, steel_rate_per_kg: "", netting_rate_per_sqm: "", concrete_rate_per_cum: "",
    finish_rate_per_kg: "", wind_zone: "", seismic_zone: "", coastal: false,
  });
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const set = (k) => (v) => setF((s) => ({ ...s, [k]: v }));
  const isRound = ROUND_SECTIONS.has(f.section);

  const selectedProjectSport = projectSports.find((ps) => ps.id === f.project_sport_id);
  const rec = selectedProjectSport?.recommended_structure;
  const recStructureType = rec && mapStructureType(rec.structure_type);
  const recSection = rec && mapSection(rec.section);
  const recHeight = rec && parseLeadingNumber(rec.height);
  const recIsVendorQuoteOnly = recStructureType && ["e", "f"].includes(recStructureType.type);

  function useRecommendation() {
    setF((s) => ({
      ...s,
      structure_type: recStructureType.type,
      tall_variant: recStructureType.tallVariant || s.tall_variant,
      section: recSection || s.section,
      height_ft: recHeight != null ? String(recHeight) : s.height_ft,
    }));
  }

  async function submit(e) {
    e.preventDefault();
    setError("");
    try {
      const payload = {
        project_sport_id: f.project_sport_id,
        structure_type: f.structure_type,
        section: f.section,
        wall_thickness_mm: isRound ? null : num(f.wall_thickness_mm),
        build_l_ft: num(f.build_l_ft),
        build_w_ft: num(f.build_w_ft),
        height_ft: num(f.height_ft),
        column_spacing_ft: num(f.column_spacing_ft),
        foundation_depth_ft: num(f.foundation_depth_ft),
        tall_variant: f.tall_variant,
        steel_rate_per_kg: num(f.steel_rate_per_kg),
        netting_rate_per_sqm: num(f.netting_rate_per_sqm),
        concrete_rate_per_cum: num(f.concrete_rate_per_cum),
        finish_rate_per_kg: num(f.finish_rate_per_kg),
        wind_zone: num(f.wind_zone),
        seismic_zone: f.seismic_zone || null,
        coastal: f.coastal,
      };
      const res = await addStructureTakeoff(token, costSheetId, payload);
      setResult(res);
      await onAdded();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <form onSubmit={submit} className="space-y-3">
      <ProjectSportSelect value={f.project_sport_id} onChange={set("project_sport_id")} projectSports={projectSports} sportsById={sportsById} />
      {rec && (
        <RecommendationBanner
          label="E.4 recommends"
          text={`Type ${rec.structure_type}, ${rec.section}, height ${rec.height}`}
          why={rec.why}
          onUse={!recIsVendorQuoteOnly ? useRecommendation : undefined}
          note={recIsVendorQuoteOnly ? "vendor-quote type, not usable in this calculator" : !recSection ? "section not recognised -- pick manually" : undefined}
        />
      )}
      <div className="grid grid-cols-3 gap-2">
        <Field label="Type">
          <SelectInput value={f.structure_type} onChange={set("structure_type")} options={["a", "b", "c", "d", "e", "f", "g"].map((v) => ({ value: v, label: `Type ${v.toUpperCase()}` }))} />
        </Field>
        <Field label="Section">
          <SelectInput value={f.section} onChange={set("section")} options={SECTIONS.map((v) => ({ value: v, label: v.replace(/_/g, " ").toUpperCase() }))} />
        </Field>
        <Field label="Wall thickness (mm)" hint={isRound ? "n/a for round sections" : undefined}>
          <NumberInput value={f.wall_thickness_mm} onChange={set("wall_thickness_mm")} disabled={isRound} />
        </Field>
      </div>
      <div className="grid grid-cols-3 gap-2">
        <Field label="Build L (ft)" hint="blank = sport default"><NumberInput value={f.build_l_ft} onChange={set("build_l_ft")} /></Field>
        <Field label="Build W (ft)" hint="blank = sport default"><NumberInput value={f.build_w_ft} onChange={set("build_w_ft")} /></Field>
        <Field label="Height (ft)"><NumberInput value={f.height_ft} onChange={set("height_ft")} required /></Field>
      </div>
      <div className="grid grid-cols-2 gap-2">
        <Field label="Column spacing (ft)" hint="blank = E.1 default"><NumberInput value={f.column_spacing_ft} onChange={set("column_spacing_ft")} /></Field>
        <Field label="Foundation depth (ft)" hint="blank = E.1 default"><NumberInput value={f.foundation_depth_ft} onChange={set("foundation_depth_ft")} /></Field>
      </div>
      <div className="grid grid-cols-3 gap-2">
        <Field label="Steel Rs/kg"><NumberInput value={f.steel_rate_per_kg} onChange={set("steel_rate_per_kg")} required /></Field>
        <Field label="Netting Rs/sqm"><NumberInput value={f.netting_rate_per_sqm} onChange={set("netting_rate_per_sqm")} required /></Field>
        <Field label="Concrete Rs/cum"><NumberInput value={f.concrete_rate_per_cum} onChange={set("concrete_rate_per_cum")} required /></Field>
      </div>
      <div className="grid grid-cols-3 gap-2">
        <Field label="Finish Rs/kg" hint="paint or galvanising"><NumberInput value={f.finish_rate_per_kg} onChange={set("finish_rate_per_kg")} /></Field>
        <Field label="Wind zone (1-5)"><NumberInput value={f.wind_zone} onChange={set("wind_zone")} min="1" max="5" /></Field>
        <Field label="Seismic zone">
          <SelectInput value={f.seismic_zone} onChange={set("seismic_zone")} options={["", "I", "II", "III", "IV", "V"].map((v) => ({ value: v, label: v || "—" }))} />
        </Field>
      </div>
      <CheckboxField label="Coastal (hot-dip galvanise, +15% MS)" checked={f.coastal} onChange={set("coastal")} />
      {f.structure_type === "c" && (
        <CheckboxField label="Tall variant" checked={f.tall_variant} onChange={set("tall_variant")} />
      )}
      {error && <p className="text-sm text-red-600">{error}</p>}
      <button type="submit" className="bg-blue-600 text-white text-sm rounded px-4 py-2 hover:bg-blue-700">
        Compute &amp; add to Cost Sheet
      </button>
      <BreakdownPanel result={result} />
    </form>
  );
}

// ---------------------------------------------------------------------------
// Base (Part D.1)
// ---------------------------------------------------------------------------

function BaseForm({ token, costSheetId, projectSports, sportsById, onAdded }) {
  const [f, setF] = useState({
    project_sport_id: "", base_type: "pcc", thickness_in: "", build_l_ft: "", build_w_ft: "",
    material_rate_per_cum: "", steel_kg_per_cum: "80", steel_rate_per_kg: "",
  });
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const set = (k) => (v) => setF((s) => ({ ...s, [k]: v }));
  const isRcc = f.base_type === "rcc";

  const selectedProjectSport = projectSports.find((ps) => ps.id === f.project_sport_id);
  const rec = selectedProjectSport?.recommended_base;
  const recBaseType = rec && mapBaseType(rec.recommended);
  const recThickness = rec && parseLeadingNumber(rec.recommended);

  function useRecommendation() {
    setF((s) => ({
      ...s,
      base_type: recBaseType,
      thickness_in: recThickness != null ? String(recThickness) : s.thickness_in,
    }));
  }

  async function submit(e) {
    e.preventDefault();
    setError("");
    try {
      const payload = {
        project_sport_id: f.project_sport_id,
        base_type: f.base_type,
        thickness_in: num(f.thickness_in),
        build_l_ft: num(f.build_l_ft),
        build_w_ft: num(f.build_w_ft),
        material_rate_per_cum: num(f.material_rate_per_cum),
        steel_kg_per_cum: isRcc ? num(f.steel_kg_per_cum) : undefined,
        steel_rate_per_kg: isRcc ? num(f.steel_rate_per_kg) : undefined,
      };
      const res = await addBaseTakeoff(token, costSheetId, payload);
      setResult(res);
      await onAdded();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <form onSubmit={submit} className="space-y-3">
      <ProjectSportSelect value={f.project_sport_id} onChange={set("project_sport_id")} projectSports={projectSports} sportsById={sportsById} />
      {rec && (
        <RecommendationBanner
          label="D.2 recommends"
          text={rec.recommended + (rec.alternative ? ` (alt: ${rec.alternative})` : "")}
          why={rec.why}
          onUse={recBaseType ? useRecommendation : undefined}
          note={!recBaseType ? "not a WBM/Asphalt/PCC/RCC base -- pick manually" : undefined}
        />
      )}
      <div className="grid grid-cols-2 gap-2">
        <Field label="Base type">
          <SelectInput value={f.base_type} onChange={set("base_type")} options={["wbm", "asphalt", "pcc", "rcc"].map((v) => ({ value: v, label: v.toUpperCase() }))} />
        </Field>
        <Field label="Thickness (in)"><NumberInput value={f.thickness_in} onChange={set("thickness_in")} required /></Field>
      </div>
      <div className="grid grid-cols-2 gap-2">
        <Field label="Build L (ft)" hint="blank = sport default"><NumberInput value={f.build_l_ft} onChange={set("build_l_ft")} /></Field>
        <Field label="Build W (ft)" hint="blank = sport default"><NumberInput value={f.build_w_ft} onChange={set("build_w_ft")} /></Field>
      </div>
      <Field label="Material Rs/cum"><NumberInput value={f.material_rate_per_cum} onChange={set("material_rate_per_cum")} required /></Field>
      {isRcc && (
        <div className="grid grid-cols-2 gap-2">
          <Field label="Steel kg/cum" hint="J.3 slab default 80"><NumberInput value={f.steel_kg_per_cum} onChange={set("steel_kg_per_cum")} /></Field>
          <Field label="Steel Rs/kg"><NumberInput value={f.steel_rate_per_kg} onChange={set("steel_rate_per_kg")} required /></Field>
        </div>
      )}
      {error && <p className="text-sm text-red-600">{error}</p>}
      <button type="submit" className="bg-blue-600 text-white text-sm rounded px-4 py-2 hover:bg-blue-700">
        Compute &amp; add to Cost Sheet
      </button>
      <BreakdownPanel result={result} />
    </form>
  );
}

// ---------------------------------------------------------------------------
// Drainage (Part D.3)
// ---------------------------------------------------------------------------

function DrainageForm({ token, costSheetId, projectSports, sportsById, onAdded }) {
  const [f, setF] = useState({
    project_sport_id: "", build_l_ft: "", build_w_ft: "", runoff_coefficient: "0.9",
    rainfall_intensity_mm_per_hr: "", high_rainfall: false, drain_rate_per_m: "", pipe_rate_per_m: "",
    catch_pit_rate_each: "", subsurface_turf_drainage: false, subsurface_pipe_rate_per_m: "",
  });
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const set = (k) => (v) => setF((s) => ({ ...s, [k]: v }));

  async function submit(e) {
    e.preventDefault();
    setError("");
    try {
      const payload = {
        project_sport_id: f.project_sport_id,
        build_l_ft: num(f.build_l_ft),
        build_w_ft: num(f.build_w_ft),
        runoff_coefficient: num(f.runoff_coefficient),
        rainfall_intensity_mm_per_hr: num(f.rainfall_intensity_mm_per_hr),
        high_rainfall: f.high_rainfall,
        drain_rate_per_m: num(f.drain_rate_per_m),
        pipe_rate_per_m: num(f.pipe_rate_per_m),
        catch_pit_rate_each: num(f.catch_pit_rate_each),
        subsurface_turf_drainage: f.subsurface_turf_drainage,
        subsurface_pipe_rate_per_m: num(f.subsurface_pipe_rate_per_m),
      };
      const res = await addDrainageTakeoff(token, costSheetId, payload);
      setResult(res);
      await onAdded();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <form onSubmit={submit} className="space-y-3">
      <ProjectSportSelect value={f.project_sport_id} onChange={set("project_sport_id")} projectSports={projectSports} sportsById={sportsById} />
      <div className="grid grid-cols-2 gap-2">
        <Field label="Build L (ft)" hint="blank = sport default"><NumberInput value={f.build_l_ft} onChange={set("build_l_ft")} /></Field>
        <Field label="Build W (ft)" hint="blank = sport default"><NumberInput value={f.build_w_ft} onChange={set("build_w_ft")} /></Field>
      </div>
      <div className="grid grid-cols-2 gap-2">
        <Field label="Runoff coefficient C" hint="0.9 turf/acrylic, 0.6 grass"><NumberInput value={f.runoff_coefficient} onChange={set("runoff_coefficient")} /></Field>
        <Field label="Rainfall intensity (mm/hr)"><NumberInput value={f.rainfall_intensity_mm_per_hr} onChange={set("rainfall_intensity_mm_per_hr")} required /></Field>
      </div>
      <CheckboxField label="High rainfall (12x12in channel)" checked={f.high_rainfall} onChange={set("high_rainfall")} />
      <div className="grid grid-cols-3 gap-2">
        <Field label="Drain Rs/m"><NumberInput value={f.drain_rate_per_m} onChange={set("drain_rate_per_m")} required /></Field>
        <Field label="Pipe Rs/m" hint="required if Q ≥ 1 l/s"><NumberInput value={f.pipe_rate_per_m} onChange={set("pipe_rate_per_m")} /></Field>
        <Field label="Catch pit Rs/each"><NumberInput value={f.catch_pit_rate_each} onChange={set("catch_pit_rate_each")} required /></Field>
      </div>
      <CheckboxField label="Sub-surface turf drainage" checked={f.subsurface_turf_drainage} onChange={set("subsurface_turf_drainage")} />
      {f.subsurface_turf_drainage && (
        <Field label="Sub-surface pipe Rs/m"><NumberInput value={f.subsurface_pipe_rate_per_m} onChange={set("subsurface_pipe_rate_per_m")} required /></Field>
      )}
      {error && <p className="text-sm text-red-600">{error}</p>}
      <button type="submit" className="bg-blue-600 text-white text-sm rounded px-4 py-2 hover:bg-blue-700">
        Compute &amp; add to Cost Sheet
      </button>
      <BreakdownPanel result={result} />
    </form>
  );
}

// ---------------------------------------------------------------------------
// Turf (Part F.5)
// ---------------------------------------------------------------------------

const PILE_HEIGHTS = ["30mm", "40mm", "50mm_fifa_quality", "50_60mm_fifa_quality_pro", "padel_12mm"];

function TurfForm({ token, costSheetId, projectSports, sportsById, onAdded }) {
  const [f, setF] = useState({
    project_sport_id: "", build_l_ft: "", build_w_ft: "", pile_height: "40mm", cut_length_allowed: true,
    turf_rate_per_sqm: "", sand_rate_per_kg: "", rubber_rate_per_kg: "", sand_kg_per_sqm: "", rubber_kg_per_sqm: "",
    line_marking_sets: "0", line_marking_rate_per_set: "",
  });
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const set = (k) => (v) => setF((s) => ({ ...s, [k]: v }));

  const selectedProjectSport = projectSports.find((ps) => ps.id === f.project_sport_id);
  const rec = selectedProjectSport?.recommended_flooring;
  const recPileHeight = rec && mapPileHeight(rec.selected);

  function useRecommendation() {
    setF((s) => ({ ...s, pile_height: recPileHeight }));
  }

  async function submit(e) {
    e.preventDefault();
    setError("");
    try {
      const payload = {
        project_sport_id: f.project_sport_id,
        build_l_ft: num(f.build_l_ft),
        build_w_ft: num(f.build_w_ft),
        pile_height: f.pile_height,
        cut_length_allowed: f.cut_length_allowed,
        turf_rate_per_sqm: num(f.turf_rate_per_sqm),
        sand_rate_per_kg: num(f.sand_rate_per_kg),
        rubber_rate_per_kg: num(f.rubber_rate_per_kg),
        sand_kg_per_sqm: num(f.sand_kg_per_sqm),
        rubber_kg_per_sqm: num(f.rubber_kg_per_sqm),
        line_marking_sets: Number(f.line_marking_sets || 0),
        line_marking_rate_per_set: num(f.line_marking_rate_per_set),
      };
      const res = await addTurfTakeoff(token, costSheetId, payload);
      setResult(res);
      await onAdded();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <form onSubmit={submit} className="space-y-3">
      <ProjectSportSelect value={f.project_sport_id} onChange={set("project_sport_id")} projectSports={projectSports} sportsById={sportsById} />
      {rec && (
        <RecommendationBanner
          label="F.1/F.2 recommends"
          text={`${rec.selected} (${rec.selected_tier} tier)`}
          why={rec.why}
          onUse={recPileHeight ? useRecommendation : undefined}
          note={!recPileHeight ? "not a turf flooring -- add via Manual line instead" : undefined}
        />
      )}
      <div className="grid grid-cols-2 gap-2">
        <Field label="Build L (ft)" hint="blank = sport default"><NumberInput value={f.build_l_ft} onChange={set("build_l_ft")} /></Field>
        <Field label="Build W (ft)" hint="blank = sport default"><NumberInput value={f.build_w_ft} onChange={set("build_w_ft")} /></Field>
      </div>
      <Field label="Pile height">
        <SelectInput value={f.pile_height} onChange={set("pile_height")} options={PILE_HEIGHTS.map((v) => ({ value: v, label: v.replace(/_/g, " ") }))} />
      </Field>
      <CheckboxField label="Supplier allows cut-length ordering" checked={f.cut_length_allowed} onChange={set("cut_length_allowed")} />
      <div className="grid grid-cols-3 gap-2">
        <Field label="Turf Rs/sqm"><NumberInput value={f.turf_rate_per_sqm} onChange={set("turf_rate_per_sqm")} required /></Field>
        <Field label="Sand Rs/kg"><NumberInput value={f.sand_rate_per_kg} onChange={set("sand_rate_per_kg")} required /></Field>
        <Field label="Rubber Rs/kg" hint="skip for padel"><NumberInput value={f.rubber_rate_per_kg} onChange={set("rubber_rate_per_kg")} /></Field>
      </div>
      <div className="grid grid-cols-2 gap-2">
        <Field label="Sand kg/sqm override" hint="blank = F.5 table"><NumberInput value={f.sand_kg_per_sqm} onChange={set("sand_kg_per_sqm")} /></Field>
        <Field label="Rubber kg/sqm override" hint="blank = F.5 table"><NumberInput value={f.rubber_kg_per_sqm} onChange={set("rubber_kg_per_sqm")} /></Field>
      </div>
      <div className="grid grid-cols-2 gap-2">
        <Field label="Line-marking sets"><NumberInput value={f.line_marking_sets} onChange={set("line_marking_sets")} min="0" /></Field>
        <Field label="Line-marking Rs/set"><NumberInput value={f.line_marking_rate_per_set} onChange={set("line_marking_rate_per_set")} /></Field>
      </div>
      {error && <p className="text-sm text-red-600">{error}</p>}
      <button type="submit" className="bg-blue-600 text-white text-sm rounded px-4 py-2 hover:bg-blue-700">
        Compute &amp; add to Cost Sheet
      </button>
      <BreakdownPanel result={result} />
    </form>
  );
}

// ---------------------------------------------------------------------------
// Wooden flooring (Part F.3)
// ---------------------------------------------------------------------------

function WoodenFlooringForm({ token, costSheetId, projectSports, sportsById, onAdded }) {
  const [f, setF] = useState({
    project_sport_id: "", build_l_ft: "", build_w_ft: "", hardwood_rate_per_sqft: "",
    include_ply: true, ply_rate_per_sqft: "",
    include_battens: true, battens_rate_per_sqft: "",
    include_moisture_barrier: true, moisture_barrier_rate_per_sqft: "",
  });
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const set = (k) => (v) => setF((s) => ({ ...s, [k]: v }));

  async function submit(e) {
    e.preventDefault();
    setError("");
    try {
      const payload = {
        project_sport_id: f.project_sport_id,
        build_l_ft: num(f.build_l_ft),
        build_w_ft: num(f.build_w_ft),
        hardwood_rate_per_sqft: num(f.hardwood_rate_per_sqft),
        include_ply: f.include_ply,
        ply_rate_per_sqft: f.include_ply ? num(f.ply_rate_per_sqft) : undefined,
        include_battens: f.include_battens,
        battens_rate_per_sqft: f.include_battens ? num(f.battens_rate_per_sqft) : undefined,
        include_moisture_barrier: f.include_moisture_barrier,
        moisture_barrier_rate_per_sqft: f.include_moisture_barrier ? num(f.moisture_barrier_rate_per_sqft) : undefined,
      };
      const res = await addWoodenFlooringTakeoff(token, costSheetId, payload);
      setResult(res);
      await onAdded();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <form onSubmit={submit} className="space-y-3">
      <ProjectSportSelect value={f.project_sport_id} onChange={set("project_sport_id")} projectSports={projectSports} sportsById={sportsById} />
      <div className="grid grid-cols-2 gap-2">
        <Field label="Build L (ft)" hint="blank = sport default"><NumberInput value={f.build_l_ft} onChange={set("build_l_ft")} /></Field>
        <Field label="Build W (ft)" hint="blank = sport default"><NumberInput value={f.build_w_ft} onChange={set("build_w_ft")} /></Field>
      </div>
      <Field label="Hardwood 22mm T&G Rs/sqft"><NumberInput value={f.hardwood_rate_per_sqft} onChange={set("hardwood_rate_per_sqft")} required /></Field>

      <div className="grid grid-cols-2 gap-2 items-end">
        <CheckboxField label="12mm plywood underlayer" checked={f.include_ply} onChange={set("include_ply")} />
        {f.include_ply && <NumberInput value={f.ply_rate_per_sqft} onChange={set("ply_rate_per_sqft")} placeholder="Rs/sqft" />}
      </div>
      <div className="grid grid-cols-2 gap-2 items-end">
        <CheckboxField label="Battens/cradles + rubber pads (sprung layer)" checked={f.include_battens} onChange={set("include_battens")} />
        {f.include_battens && <NumberInput value={f.battens_rate_per_sqft} onChange={set("battens_rate_per_sqft")} placeholder="Rs/sqft" />}
      </div>
      <div className="grid grid-cols-2 gap-2 items-end">
        <CheckboxField label="Moisture barrier (DPM)" checked={f.include_moisture_barrier} onChange={set("include_moisture_barrier")} />
        {f.include_moisture_barrier && (
          <NumberInput value={f.moisture_barrier_rate_per_sqft} onChange={set("moisture_barrier_rate_per_sqft")} placeholder="Rs/sqft" />
        )}
      </div>
      <p className="text-[11px] text-gray-400">Base (PCC/RCC/compacted stone) below this is the separate Base (D.1) tab.</p>

      {error && <p className="text-sm text-red-600">{error}</p>}
      <button type="submit" className="bg-blue-600 text-white text-sm rounded px-4 py-2 hover:bg-blue-700">
        Compute &amp; add to Cost Sheet
      </button>
      <BreakdownPanel result={result} />
    </form>
  );
}

// ---------------------------------------------------------------------------
// Acrylic / PU surfacing (Part F.2/F.3)
// ---------------------------------------------------------------------------

function AcrylicPuForm({ token, costSheetId, projectSports, sportsById, onAdded }) {
  const [f, setF] = useState({
    project_sport_id: "", build_l_ft: "", build_w_ft: "", surface_type: "acrylic", coats: "6", rate_per_sqft_per_coat: "",
  });
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const set = (k) => (v) => setF((s) => ({ ...s, [k]: v }));

  async function submit(e) {
    e.preventDefault();
    setError("");
    try {
      const payload = {
        project_sport_id: f.project_sport_id,
        build_l_ft: num(f.build_l_ft),
        build_w_ft: num(f.build_w_ft),
        surface_type: f.surface_type,
        coats: Number(f.coats),
        rate_per_sqft_per_coat: num(f.rate_per_sqft_per_coat),
      };
      const res = await addAcrylicPuTakeoff(token, costSheetId, payload);
      setResult(res);
      await onAdded();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <form onSubmit={submit} className="space-y-3">
      <ProjectSportSelect value={f.project_sport_id} onChange={set("project_sport_id")} projectSports={projectSports} sportsById={sportsById} />
      <div className="grid grid-cols-2 gap-2">
        <Field label="Build L (ft)" hint="blank = sport default"><NumberInput value={f.build_l_ft} onChange={set("build_l_ft")} /></Field>
        <Field label="Build W (ft)" hint="blank = sport default"><NumberInput value={f.build_w_ft} onChange={set("build_w_ft")} /></Field>
      </div>
      <Field label="Surface type">
        <SelectInput
          value={f.surface_type}
          onChange={set("surface_type")}
          options={[
            { value: "acrylic", label: "Acrylic (3-5mm, 5-8 coats)" },
            { value: "pu", label: "PU (5-6mm, single system)" },
          ]}
        />
      </Field>
      <div className="grid grid-cols-2 gap-2">
        <Field label="Coats" hint="PU is usually 1"><NumberInput value={f.coats} onChange={set("coats")} min="1" required /></Field>
        <Field label="Rs/sqft per coat"><NumberInput value={f.rate_per_sqft_per_coat} onChange={set("rate_per_sqft_per_coat")} required /></Field>
      </div>
      <p className="text-[11px] text-gray-400">Sub-base (asphalt/WBM/PCC) below this is the separate Base (D.1) tab.</p>

      {error && <p className="text-sm text-red-600">{error}</p>}
      <button type="submit" className="bg-blue-600 text-white text-sm rounded px-4 py-2 hover:bg-blue-700">
        Compute &amp; add to Cost Sheet
      </button>
      <BreakdownPanel result={result} />
    </form>
  );
}

// ---------------------------------------------------------------------------
// Line marking (Part F.6, standalone multi-set)
// ---------------------------------------------------------------------------

function LineMarkingForm({ token, costSheetId, projectSports, sportsById, onAdded }) {
  const [projectSportId, setProjectSportId] = useState("");
  const [sets, setSets] = useState([{ sport_label: "", style: "painted", rate_per_set: "" }]);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");

  function addSet() {
    if (sets.length >= 4) return; // F.6: "Multipurpose: up to 4"
    setSets((s) => [...s, { sport_label: "", style: "painted", rate_per_set: "" }]);
  }
  function updateSet(i, field, value) {
    setSets((s) => s.map((row, idx) => (idx === i ? { ...row, [field]: value } : row)));
  }
  function removeSet(i) {
    setSets((s) => s.filter((_, idx) => idx !== i));
  }

  async function submit(e) {
    e.preventDefault();
    setError("");
    try {
      const payload = {
        project_sport_id: projectSportId,
        sets: sets.map((s) => ({ sport_label: s.sport_label, style: s.style, rate_per_set: Number(s.rate_per_set) })),
      };
      const res = await addLineMarkingTakeoff(token, costSheetId, payload);
      setResult(res);
      await onAdded();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <form onSubmit={submit} className="space-y-3">
      <ProjectSportSelect value={projectSportId} onChange={setProjectSportId} projectSports={projectSports} sportsById={sportsById} />
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <p className="text-xs font-medium text-gray-600">Sets (up to 4 -- e.g. basketball white, volleyball yellow)</p>
          {sets.length < 4 && (
            <button type="button" onClick={addSet} className="text-xs text-blue-600 hover:underline">
              + Add set
            </button>
          )}
        </div>
        {sets.map((row, i) => (
          <div key={i} className="grid grid-cols-12 gap-2 items-end">
            <div className="col-span-5">
              <TextInput value={row.sport_label} onChange={(v) => updateSet(i, "sport_label", v)} placeholder="e.g. Basketball (white)" />
            </div>
            <div className="col-span-3">
              <SelectInput
                value={row.style}
                onChange={(v) => updateSet(i, "style", v)}
                options={[
                  { value: "painted", label: "Painted (acrylic/hard)" },
                  { value: "inlaid", label: "Inlaid (turf)" },
                ]}
              />
            </div>
            <div className="col-span-3">
              <NumberInput value={row.rate_per_set} onChange={(v) => updateSet(i, "rate_per_set", v)} placeholder="Rs/set" />
            </div>
            {sets.length > 1 && (
              <button type="button" onClick={() => removeSet(i)} className="col-span-1 text-xs text-red-600 hover:underline">
                Remove
              </button>
            )}
          </div>
        ))}
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}
      <button type="submit" className="bg-blue-600 text-white text-sm rounded px-4 py-2 hover:bg-blue-700">
        Compute &amp; add to Cost Sheet
      </button>
      <BreakdownPanel result={result} />
    </form>
  );
}

// ---------------------------------------------------------------------------
// Lighting (Part H)
// ---------------------------------------------------------------------------

function LightingForm({ token, costSheetId, projectSports, sportsById, onAdded }) {
  const [f, setF] = useState({
    project_sport_id: "", build_l_ft: "", build_w_ft: "", lux: "", lumens_per_fixture: "", wattage_per_fixture: "",
    fixture_rate_each: "", uses_poles: false, pole_count: "", pole_height_m: "", cable_length_m: "",
    cable_rate_per_m: "", mcb_panel_rate: "", earthing_rate: "", lightning_arrestor_rate: "",
    tariff_rate_per_kwh: "", hours_per_day: "",
  });
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const set = (k) => (v) => setF((s) => ({ ...s, [k]: v }));

  const selectedProjectSport = projectSports.find((ps) => ps.id === f.project_sport_id);
  const rec = selectedProjectSport?.recommended_lighting;
  const recFixture = rec && parseFixtureSpec(rec.fixture_spec);

  function useRecommendation() {
    setF((s) => ({
      ...s,
      lux: String(rec.lux_level),
      lumens_per_fixture: recFixture.lumens != null ? String(recFixture.lumens) : s.lumens_per_fixture,
      wattage_per_fixture: recFixture.wattage != null ? String(recFixture.wattage) : s.wattage_per_fixture,
      uses_poles: rec.mounting_mode === "poles",
      pole_count: rec.pole_count != null ? String(rec.pole_count) : s.pole_count,
    }));
  }

  async function submit(e) {
    e.preventDefault();
    setError("");
    try {
      const payload = {
        project_sport_id: f.project_sport_id,
        build_l_ft: num(f.build_l_ft),
        build_w_ft: num(f.build_w_ft),
        lux: num(f.lux),
        lumens_per_fixture: num(f.lumens_per_fixture),
        wattage_per_fixture: num(f.wattage_per_fixture),
        fixture_rate_each: num(f.fixture_rate_each),
        uses_poles: f.uses_poles,
        pole_count: f.uses_poles ? Number(f.pole_count) : undefined,
        pole_height_m: num(f.pole_height_m),
        cable_length_m: num(f.cable_length_m),
        cable_rate_per_m: num(f.cable_rate_per_m),
        mcb_panel_rate: num(f.mcb_panel_rate),
        earthing_rate: num(f.earthing_rate),
        lightning_arrestor_rate: num(f.lightning_arrestor_rate),
        tariff_rate_per_kwh: num(f.tariff_rate_per_kwh),
        hours_per_day: num(f.hours_per_day),
      };
      const res = await addLightingTakeoff(token, costSheetId, payload);
      setResult(res);
      await onAdded();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <form onSubmit={submit} className="space-y-3">
      <ProjectSportSelect value={f.project_sport_id} onChange={set("project_sport_id")} projectSports={projectSports} sportsById={sportsById} />
      {rec && (
        <RecommendationBanner
          label="Part H recommends"
          text={`${rec.fixtures} fixtures, ${rec.fixture_spec}, ${rec.mounting_mode}${rec.pole_count ? ` (${rec.pole_count} poles)` : ""}`}
          why={rec.why}
          onUse={useRecommendation}
        />
      )}
      <div className="grid grid-cols-2 gap-2">
        <Field label="Build L (ft)" hint="blank = sport default"><NumberInput value={f.build_l_ft} onChange={set("build_l_ft")} /></Field>
        <Field label="Build W (ft)" hint="blank = sport default"><NumberInput value={f.build_w_ft} onChange={set("build_w_ft")} /></Field>
      </div>
      <div className="grid grid-cols-3 gap-2">
        <Field label="Target lux"><NumberInput value={f.lux} onChange={set("lux")} required /></Field>
        <Field label="Lumens/fixture"><NumberInput value={f.lumens_per_fixture} onChange={set("lumens_per_fixture")} required /></Field>
        <Field label="Watts/fixture"><NumberInput value={f.wattage_per_fixture} onChange={set("wattage_per_fixture")} required /></Field>
      </div>
      <Field label="Fixture Rs/each"><NumberInput value={f.fixture_rate_each} onChange={set("fixture_rate_each")} required /></Field>
      <CheckboxField label="Pole-mounted (open air / Type D / Type G)" checked={f.uses_poles} onChange={set("uses_poles")} />
      {f.uses_poles && (
        <div className="grid grid-cols-2 gap-2">
          <Field label="Pole count"><NumberInput value={f.pole_count} onChange={set("pole_count")} required min="1" /></Field>
          <Field label="Pole height (m)" hint=">10m needs a lightning arrestor"><NumberInput value={f.pole_height_m} onChange={set("pole_height_m")} /></Field>
        </div>
      )}
      <div className="grid grid-cols-2 gap-2">
        <Field label="Cable length (m)"><NumberInput value={f.cable_length_m} onChange={set("cable_length_m")} /></Field>
        <Field label="Cable Rs/m"><NumberInput value={f.cable_rate_per_m} onChange={set("cable_rate_per_m")} /></Field>
      </div>
      <div className="grid grid-cols-3 gap-2">
        <Field label="MCB panel Rs"><NumberInput value={f.mcb_panel_rate} onChange={set("mcb_panel_rate")} /></Field>
        <Field label="Earthing Rs"><NumberInput value={f.earthing_rate} onChange={set("earthing_rate")} /></Field>
        <Field label="Lightning arrestor Rs"><NumberInput value={f.lightning_arrestor_rate} onChange={set("lightning_arrestor_rate")} /></Field>
      </div>
      <div className="grid grid-cols-2 gap-2">
        <Field label="Tariff Rs/kWh" hint="informational only"><NumberInput value={f.tariff_rate_per_kwh} onChange={set("tariff_rate_per_kwh")} /></Field>
        <Field label="Hours/day" hint="informational only"><NumberInput value={f.hours_per_day} onChange={set("hours_per_day")} /></Field>
      </div>
      {error && <p className="text-sm text-red-600">{error}</p>}
      <button type="submit" className="bg-blue-600 text-white text-sm rounded px-4 py-2 hover:bg-blue-700">
        Compute &amp; add to Cost Sheet
      </button>
      <BreakdownPanel result={result} />
    </form>
  );
}

// ---------------------------------------------------------------------------
// HVAC (Part G.5)
// ---------------------------------------------------------------------------

function HvacForm({ token, costSheetId, projectSports, sportsById, onAdded }) {
  const [f, setF] = useState({
    project_sport_id: "", build_l_ft: "", build_w_ft: "", height_ft: "", climate: "moderate",
    ac_rate_per_tr: "", ducting_rate_per_sqft: "", occupancy: "", fresh_air_unit_rate: "",
    coverage_percent: "", acoustic_panel_rate_per_sqm: "",
  });
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const set = (k) => (v) => setF((s) => ({ ...s, [k]: v }));

  async function submit(e) {
    e.preventDefault();
    setError("");
    try {
      const payload = {
        project_sport_id: f.project_sport_id,
        build_l_ft: num(f.build_l_ft),
        build_w_ft: num(f.build_w_ft),
        height_ft: num(f.height_ft),
        climate: f.climate,
        ac_rate_per_tr: num(f.ac_rate_per_tr),
        ducting_rate_per_sqft: num(f.ducting_rate_per_sqft),
        occupancy: f.occupancy ? Number(f.occupancy) : undefined,
        fresh_air_unit_rate: num(f.fresh_air_unit_rate),
        coverage_percent: num(f.coverage_percent),
        acoustic_panel_rate_per_sqm: num(f.acoustic_panel_rate_per_sqm),
      };
      const res = await addHvacTakeoff(token, costSheetId, payload);
      setResult(res);
      await onAdded();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <form onSubmit={submit} className="space-y-3">
      <ProjectSportSelect value={f.project_sport_id} onChange={set("project_sport_id")} projectSports={projectSports} sportsById={sportsById} />
      <div className="grid grid-cols-3 gap-2">
        <Field label="Build L (ft)" hint="blank = sport default"><NumberInput value={f.build_l_ft} onChange={set("build_l_ft")} /></Field>
        <Field label="Build W (ft)" hint="blank = sport default"><NumberInput value={f.build_w_ft} onChange={set("build_w_ft")} /></Field>
        <Field label="Height (ft)"><NumberInput value={f.height_ft} onChange={set("height_ft")} required /></Field>
      </div>
      <Field label="Climate">
        <SelectInput value={f.climate} onChange={set("climate")} options={["hot_humid", "hot_dry", "moderate", "cold"].map((v) => ({ value: v, label: v.replace("_", "-") }))} />
      </Field>
      <div className="grid grid-cols-2 gap-2">
        <Field label="AC Rs/TR"><NumberInput value={f.ac_rate_per_tr} onChange={set("ac_rate_per_tr")} required /></Field>
        <Field label="Ducting Rs/sqft"><NumberInput value={f.ducting_rate_per_sqft} onChange={set("ducting_rate_per_sqft")} required /></Field>
      </div>
      <div className="grid grid-cols-2 gap-2">
        <Field label="Occupancy (persons)"><NumberInput value={f.occupancy} onChange={set("occupancy")} /></Field>
        <Field label="Fresh air Rs/CFM"><NumberInput value={f.fresh_air_unit_rate} onChange={set("fresh_air_unit_rate")} /></Field>
      </div>
      <div className="grid grid-cols-2 gap-2">
        <Field label="Coverage % override" hint="blank = squash/badminton/TT/gym default"><NumberInput value={f.coverage_percent} onChange={set("coverage_percent")} /></Field>
        <Field label="Acoustic panel Rs/sqm"><NumberInput value={f.acoustic_panel_rate_per_sqm} onChange={set("acoustic_panel_rate_per_sqm")} /></Field>
      </div>
      {error && <p className="text-sm text-red-600">{error}</p>}
      <button type="submit" className="bg-blue-600 text-white text-sm rounded px-4 py-2 hover:bg-blue-700">
        Compute &amp; add to Cost Sheet
      </button>
      <BreakdownPanel result={result} />
    </form>
  );
}

// ---------------------------------------------------------------------------
// Accessories (Part I / Module 9)
// ---------------------------------------------------------------------------

function AccessoriesForm({ token, costSheetId, projectSports, sportsById, onAdded }) {
  const [projectSportId, setProjectSportId] = useState("");
  const [rates, setRates] = useState({});
  const [customItems, setCustomItems] = useState([]);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");

  const selectedProjectSport = projectSports.find((ps) => ps.id === projectSportId);
  const sport = selectedProjectSport ? sportsById[selectedProjectSport.sport_id] : null;
  const catalogItems = sport ? ACCESSORY_CATALOG[sport.key] ?? [] : [];

  function addCustomItem() {
    setCustomItems((items) => [...items, { item_name: "", unit: "nos", quantity: "1", rate: "" }]);
  }
  function updateCustomItem(i, field, value) {
    setCustomItems((items) => items.map((it, idx) => (idx === i ? { ...it, [field]: value } : it)));
  }
  function removeCustomItem(i) {
    setCustomItems((items) => items.filter((_, idx) => idx !== i));
  }

  async function submit(e) {
    e.preventDefault();
    setError("");
    try {
      const payload = {
        project_sport_id: projectSportId,
        rates: Object.fromEntries(
          catalogItems
            .filter(([name]) => rates[name] !== undefined && rates[name] !== "")
            .map(([name]) => [name, Number(rates[name])])
        ),
        custom_items: customItems
          .filter((it) => it.item_name && it.rate)
          .map((it) => ({
            item_name: it.item_name,
            unit: it.unit || "nos",
            quantity: Number(it.quantity) || 1,
            rate: Number(it.rate),
          })),
      };
      const res = await addAccessoriesTakeoff(token, costSheetId, payload);
      setResult(res);
      setCustomItems([]);
      await onAdded();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <form onSubmit={submit} className="space-y-3">
      <ProjectSportSelect value={projectSportId} onChange={setProjectSportId} projectSports={projectSports} sportsById={sportsById} />

      {sport && catalogItems.length > 0 && (
        <div className="space-y-2">
          <p className="text-xs text-gray-500">
            Auto quantities for {sport.name} ({selectedProjectSport.number_of_courts} court
            {selectedProjectSport.number_of_courts === 1 ? "" : "s"}):
          </p>
          {catalogItems.map(([name, unit, qtyPerCourt]) => (
            <Field key={name} label={name} hint={`${qtyPerCourt * selectedProjectSport.number_of_courts} ${unit} total`}>
              <NumberInput
                value={rates[name] ?? ""}
                onChange={(v) => setRates((r) => ({ ...r, [name]: v }))}
                placeholder="Rs/unit"
              />
            </Field>
          ))}
        </div>
      )}
      {sport && catalogItems.length === 0 && (
        <p className="text-xs text-amber-700 bg-amber-50 rounded px-3 py-2">
          No accessories catalog for {sport.name} yet — add items manually below.
        </p>
      )}

      <div className="space-y-2 border-t border-gray-100 pt-3">
        <div className="flex items-center justify-between">
          <p className="text-xs font-medium text-gray-600">Custom items (optional extras, e.g. scoreboard, umpire chair)</p>
          <button type="button" onClick={addCustomItem} className="text-xs text-blue-600 hover:underline">
            + Add item
          </button>
        </div>
        {customItems.map((item, i) => (
          <div key={i} className="grid grid-cols-12 gap-2 items-end">
            <div className="col-span-5">
              <TextInput value={item.item_name} onChange={(v) => updateCustomItem(i, "item_name", v)} placeholder="Item name" />
            </div>
            <div className="col-span-2">
              <TextInput value={item.unit} onChange={(v) => updateCustomItem(i, "unit", v)} placeholder="Unit" />
            </div>
            <div className="col-span-2">
              <NumberInput value={item.quantity} onChange={(v) => updateCustomItem(i, "quantity", v)} placeholder="Qty" />
            </div>
            <div className="col-span-2">
              <NumberInput value={item.rate} onChange={(v) => updateCustomItem(i, "rate", v)} placeholder="Rs/unit" />
            </div>
            <button
              type="button"
              onClick={() => removeCustomItem(i)}
              className="col-span-1 text-xs text-red-600 hover:underline"
            >
              Remove
            </button>
          </div>
        ))}
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}
      <button
        type="submit"
        disabled={!projectSportId}
        className="bg-blue-600 text-white text-sm rounded px-4 py-2 hover:bg-blue-700 disabled:opacity-50"
      >
        Compute &amp; add to Cost Sheet
      </button>
      <BreakdownPanel result={result} />
    </form>
  );
}

// ---------------------------------------------------------------------------
// Manual line (generic /lines endpoint)
// ---------------------------------------------------------------------------

const WORK_PACKAGES = ["civil", "structure", "flooring", "electrical", "pool", "hvac", "accessories", "scope", "services"];

function ManualLineForm({ token, costSheetId, projectSports, sportsById, labourCategories, onAdded }) {
  const [f, setF] = useState({
    project_sport_id: "", work_package: "civil", category: "", item_name: "", spec: "", unit: "",
    quantity: "", rate: "", labour_category_id: "",
  });
  const [error, setError] = useState("");
  const set = (k) => (v) => setF((s) => ({ ...s, [k]: v }));

  async function submit(e) {
    e.preventDefault();
    setError("");
    try {
      await addCostSheetLine(token, costSheetId, {
        project_sport_id: f.project_sport_id || null,
        work_package: f.work_package,
        category: f.category,
        item_name: f.item_name,
        spec: f.spec || null,
        unit: f.unit,
        quantity: Number(f.quantity),
        rate: Number(f.rate),
        labour_category_id: f.labour_category_id || null,
      });
      setF((s) => ({ ...s, category: "", item_name: "", spec: "", unit: "", quantity: "", rate: "" }));
      await onAdded();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <form onSubmit={submit} className="space-y-3">
      <p className="text-xs text-gray-400">
        For anything without a dedicated calculator -- e.g. flooring types other than turf, accessories, scope items.
      </p>
      <Field label="Sport (optional -- leave blank for a site-wide line)">
        <SelectInput
          value={f.project_sport_id}
          onChange={set("project_sport_id")}
          options={[{ value: "", label: "Site-wide" }, ...projectSports.map((ps) => ({ value: ps.id, label: sportsById[ps.sport_id]?.name ?? ps.sport_id }))]}
        />
      </Field>
      <div className="grid grid-cols-2 gap-2">
        <Field label="Work package">
          <SelectInput value={f.work_package} onChange={set("work_package")} options={WORK_PACKAGES.map((v) => ({ value: v, label: v }))} />
        </Field>
        <Field label="Category"><TextInput value={f.category} onChange={set("category")} required /></Field>
      </div>
      <Field label="Item name"><TextInput value={f.item_name} onChange={set("item_name")} required /></Field>
      <Field label="Spec (optional)"><TextInput value={f.spec} onChange={set("spec")} /></Field>
      <div className="grid grid-cols-3 gap-2">
        <Field label="Unit"><TextInput value={f.unit} onChange={set("unit")} placeholder="sqm, kg, each…" required /></Field>
        <Field label="Quantity"><NumberInput value={f.quantity} onChange={set("quantity")} required /></Field>
        <Field label="Rate"><NumberInput value={f.rate} onChange={set("rate")} required /></Field>
      </div>
      <Field label="Labour category (optional)" hint="blank = blended fallback 22%">
        <SelectInput
          value={f.labour_category_id}
          onChange={set("labour_category_id")}
          options={[{ value: "", label: "— blended fallback —" }, ...labourCategories.map((c) => ({ value: c.id, label: `${c.name} (${c.default_percent}%)` }))]}
        />
      </Field>
      {error && <p className="text-sm text-red-600">{error}</p>}
      <button type="submit" className="bg-blue-600 text-white text-sm rounded px-4 py-2 hover:bg-blue-700">
        Add line
      </button>
    </form>
  );
}

// ---------------------------------------------------------------------------
// Main builder
// ---------------------------------------------------------------------------

export default function CostSheetBuilder({ token, costSheet, projectSports, sports, onBack, onCostSheetUpdated }) {
  const [lines, setLines] = useState([]);
  const [labourCategories, setLabourCategories] = useState([]);
  const [warnings, setWarnings] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [tab, setTab] = useState("structure");
  const [consumptionRows, setConsumptionRows] = useState(null);
  const [showConsumption, setShowConsumption] = useState(false);

  const sportsById = Object.fromEntries(sports.map((s) => [s.id, s]));
  const isDraft = costSheet.status === "draft";

  function load() {
    return Promise.all([
      listCostSheetLines(token, costSheet.id),
      listLabourCategories(token),
      getLabourWarnings(token, costSheet.id).catch(() => []),
    ]).then(([l, lc, w]) => {
      setLines(l);
      setLabourCategories(lc);
      setWarnings(w);
    });
  }

  useEffect(() => {
    load().finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, costSheet.id]);

  async function refresh() {
    setError("");
    try {
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleDelete(lineId) {
    setError("");
    try {
      await deleteCostSheetLine(token, costSheet.id, lineId);
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleRecompute() {
    setError("");
    try {
      const updated = await recomputeCostSheet(token, costSheet.id);
      await load();
      onCostSheetUpdated(updated);
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleVerify() {
    setError("");
    try {
      const updated = await verifyCostSheet(token, costSheet.id);
      onCostSheetUpdated(updated);
    } catch (err) {
      setError(err.message);
    }
  }

  async function toggleConsumptionSheet() {
    if (showConsumption) {
      setShowConsumption(false);
      return;
    }
    setError("");
    try {
      const rows = await getConsumptionSheet(token, costSheet.id);
      setConsumptionRows(rows);
      setShowConsumption(true);
    } catch (err) {
      setError(err.message);
    }
  }

  async function toggleConsumptionSheetRefresh() {
    try {
      setConsumptionRows(await getConsumptionSheet(token, costSheet.id));
    } catch (err) {
      setError(err.message);
    }
  }

  const totalAmount = lines.reduce((sum, l) => sum + l.amount, 0);

  if (loading) {
    return <p className="text-center text-gray-500 mt-10">Loading Cost Sheet…</p>;
  }

  return (
    <div className="bg-white shadow rounded-lg p-6 space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold text-gray-700">
            Cost Sheet Builder -- {costSheet.document_no}
          </h3>
          <p className="text-xs text-gray-400">
            Status: {costSheet.status} · Recomputed total: Rs {costSheet.cost_total.toLocaleString()}
          </p>
        </div>
        <button onClick={onBack} className="text-sm text-blue-600 hover:underline">
          &larr; Back to documents
        </button>
      </div>
      {error && <p className="text-sm text-red-600">{error}</p>}
      {!isDraft && (
        <p className="text-xs text-amber-700 bg-amber-50 rounded px-3 py-2">
          This cost sheet is {costSheet.status} -- lines can no longer be added, removed or recomputed.
        </p>
      )}

      <div className="border border-gray-200 rounded">
        <div className="px-3 py-2 bg-gray-50 border-b border-gray-200 flex items-center justify-between">
          <span className="text-xs font-semibold text-gray-600">Lines ({lines.length})</span>
          <span className="text-xs text-gray-500">Sum of amounts: Rs {totalAmount.toLocaleString()}</span>
        </div>
        <div className="max-h-64 overflow-y-auto divide-y divide-gray-100">
          {lines.length === 0 && <p className="text-xs text-gray-400 px-3 py-3">No lines yet -- use a calculator below.</p>}
          {lines.map((l) => (
            <div key={l.id} className="px-3 py-2 text-xs flex items-center justify-between gap-2">
              <div className="min-w-0">
                <p className="truncate">
                  <span className="text-gray-400">[{l.work_package}/{l.category}]</span> {l.item_name}
                </p>
                <p className="text-gray-400">
                  {l.quantity} {l.unit} x Rs {l.rate} = Rs {l.amount.toLocaleString()}
                </p>
              </div>
              {isDraft && (
                <button onClick={() => handleDelete(l.id)} className="text-red-600 hover:underline shrink-0">
                  Remove
                </button>
              )}
            </div>
          ))}
        </div>
      </div>

      {warnings.length > 0 && (
        <div className="bg-amber-50 border border-amber-100 rounded p-3 space-y-1">
          <p className="text-xs font-semibold text-amber-800">J.2 labour warnings</p>
          {warnings.map((w, i) => (
            <p key={i} className="text-xs text-amber-700">{w}</p>
          ))}
        </div>
      )}

      <div className="flex gap-2">
        <button
          onClick={handleRecompute}
          disabled={!isDraft || lines.length === 0}
          className="bg-gray-700 text-white text-sm rounded px-4 py-2 hover:bg-gray-800 disabled:opacity-50"
        >
          Recompute total (K.1 steps 1-3, 6)
        </button>
        <button
          onClick={handleVerify}
          disabled={!isDraft || costSheet.cost_total <= 0}
          className="bg-green-600 text-white text-sm rounded px-4 py-2 hover:bg-green-700 disabled:opacity-50"
        >
          Verify Cost Sheet
        </button>
        <button
          onClick={toggleConsumptionSheet}
          disabled={lines.length === 0}
          className="bg-gray-100 text-gray-700 text-sm rounded px-4 py-2 hover:bg-gray-200 disabled:opacity-50"
        >
          {showConsumption ? "Hide" : "View"} Consumption Sheet (J.3)
        </button>
      </div>

      {showConsumption && (
        <div className="border border-gray-200 rounded overflow-x-auto">
          <table className="w-full text-xs">
            <thead className="bg-gray-50 text-gray-600">
              <tr>
                <th className="text-left px-2 py-1.5">Category</th>
                <th className="text-left px-2 py-1.5">Item &amp; spec</th>
                <th className="text-right px-2 py-1.5">Unit</th>
                <th className="text-right px-2 py-1.5">Theoretical qty</th>
                <th className="text-right px-2 py-1.5">Wastage %</th>
                <th className="text-right px-2 py-1.5">Order qty</th>
                <th className="text-right px-2 py-1.5">Rate</th>
                <th className="text-right px-2 py-1.5">Amount</th>
                <th className="text-left px-2 py-1.5">Vendor</th>
                <th className="text-left px-2 py-1.5">Delivery</th>
                <th className="text-left px-2 py-1.5">Received</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {consumptionRows?.map((r) => (
                <tr key={r.id}>
                  <td className="px-2 py-1.5">{r.category}</td>
                  <td className="px-2 py-1.5">
                    {r.item_name}
                    {r.spec && <span className="text-gray-400"> ({r.spec})</span>}
                  </td>
                  <td className="text-right px-2 py-1.5">{r.unit}</td>
                  <td className="text-right px-2 py-1.5">{r.theoretical_qty}</td>
                  <td className="text-right px-2 py-1.5">{r.wastage_percent ?? "—"}</td>
                  <td className="text-right px-2 py-1.5">{r.order_qty}</td>
                  <td className="text-right px-2 py-1.5">{r.rate}</td>
                  <td className="text-right px-2 py-1.5">{r.amount.toLocaleString()}</td>
                  <td className="px-2 py-1.5">{r.vendor ?? <span className="text-gray-400">—</span>}</td>
                  <td className="px-2 py-1.5">{r.delivery_date ?? <span className="text-gray-400">—</span>}</td>
                  <td className="px-2 py-1.5">
                    {r.received_qty != null ? `${r.received_qty} (bal. ${r.balance_qty})` : <span className="text-gray-400">—</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="text-[11px] text-gray-400 px-2 py-1.5 bg-gray-50 border-t border-gray-200">
            Vendor / Delivery / Received reflect a real Purchase Order (Part O) once one is raised for that line --
            blank until then.
          </p>
          <div className="p-2">
            <PurchaseOrdersPanel
              token={token}
              costSheetId={costSheet.id}
              consumptionRows={consumptionRows}
              onChanged={toggleConsumptionSheetRefresh}
            />
          </div>
        </div>
      )}

      {isDraft && (
        <div className="border-t border-gray-200 pt-4">
          <div className="flex flex-wrap gap-1 mb-4">
            {TABS.map((t) => (
              <button
                key={t.key}
                onClick={() => setTab(t.key)}
                className={`text-xs rounded px-3 py-1.5 ${
                  tab === t.key ? "bg-blue-600 text-white" : "bg-gray-100 text-gray-600 hover:bg-gray-200"
                }`}
              >
                {t.label}
              </button>
            ))}
          </div>

          {tab === "structure" && <StructureForm token={token} costSheetId={costSheet.id} projectSports={projectSports} sportsById={sportsById} onAdded={refresh} />}
          {tab === "base" && <BaseForm token={token} costSheetId={costSheet.id} projectSports={projectSports} sportsById={sportsById} onAdded={refresh} />}
          {tab === "drainage" && <DrainageForm token={token} costSheetId={costSheet.id} projectSports={projectSports} sportsById={sportsById} onAdded={refresh} />}
          {tab === "turf" && <TurfForm token={token} costSheetId={costSheet.id} projectSports={projectSports} sportsById={sportsById} onAdded={refresh} />}
          {tab === "wooden" && <WoodenFlooringForm token={token} costSheetId={costSheet.id} projectSports={projectSports} sportsById={sportsById} onAdded={refresh} />}
          {tab === "acrylic_pu" && <AcrylicPuForm token={token} costSheetId={costSheet.id} projectSports={projectSports} sportsById={sportsById} onAdded={refresh} />}
          {tab === "line_marking" && <LineMarkingForm token={token} costSheetId={costSheet.id} projectSports={projectSports} sportsById={sportsById} onAdded={refresh} />}
          {tab === "lighting" && <LightingForm token={token} costSheetId={costSheet.id} projectSports={projectSports} sportsById={sportsById} onAdded={refresh} />}
          {tab === "hvac" && <HvacForm token={token} costSheetId={costSheet.id} projectSports={projectSports} sportsById={sportsById} onAdded={refresh} />}
          {tab === "accessories" && <AccessoriesForm token={token} costSheetId={costSheet.id} projectSports={projectSports} sportsById={sportsById} onAdded={refresh} />}
          {tab === "manual" && (
            <ManualLineForm
              token={token}
              costSheetId={costSheet.id}
              projectSports={projectSports}
              sportsById={sportsById}
              labourCategories={labourCategories}
              onAdded={refresh}
            />
          )}
        </div>
      )}
    </div>
  );
}
