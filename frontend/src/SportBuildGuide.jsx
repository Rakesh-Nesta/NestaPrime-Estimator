import { useEffect, useState } from "react";
import { listAccessoryCatalog, listConstructionSequence, listFlooringGuides, listPackageContents, listSports } from "./api";

// Section 16 (Amendment 16): assembles the real, already-verified per-sport
// build reference (accessories, flooring, package-tier descriptions) that
// already drives real Cost Sheets -- no new content authored, just brought
// into Education for a new Sales person who doesn't yet know what a sport
// needs. onSportDataChange lifts the assembled data to the parent so the
// chat tab can ground its own answers in the same real data (single source
// of truth, per the approved spec), not a separate copy.
const PACKAGE_TIER_ORDER = ["budget", "standard", "premium"];
const PACKAGE_TIER_LABELS = { budget: "Budget", standard: "Standard", premium: "Premium" };

// Section 18 (Amendment 16 Part 2): same six fixed phases as
// SportsScopeAdmin.jsx's CONSTRUCTION_PHASES -- kept as a small local
// duplicate rather than a shared import, same pattern as PACKAGE_TIER_*
// above already being duplicated per file in this app.
const CONSTRUCTION_PHASE_ORDER = ["site_prep", "sub_base", "flooring", "structure_fixtures", "lighting", "accessories_finishing"];
const CONSTRUCTION_PHASE_LABELS = {
  site_prep: "Site preparation",
  sub_base: "Sub-base",
  flooring: "Flooring",
  structure_fixtures: "Structure & fixtures",
  lighting: "Lighting",
  accessories_finishing: "Accessories & finishing",
};
const CONSTRUCTION_SEQUENCE_DISCLAIMER =
  "General build sequence -- confirm against site conditions with a qualified site engineer before execution.";

function summarizeForChat(sport, accessories, flooringGuide, packageContents, constructionSteps) {
  const lines = [`\n\n=== Build Guide: ${sport.name} (${sport.category}) ===`];
  lines.push(`Playing dimensions: ${sport.playing_dims}. Build dimensions: ${sport.build_dims}.`);
  if (accessories.length) {
    lines.push(
      "Accessories needed: " +
        accessories.map((a) => `${a.item_name} (${a.quantity_per_court} ${a.unit})`).join(", ")
    );
  }
  if (flooringGuide) {
    lines.push(
      `Flooring -- primary: ${flooringGuide.primary_spec}` +
        (flooringGuide.secondary_spec ? `; alternative: ${flooringGuide.secondary_spec}` : "") +
        (flooringGuide.budget_spec ? `; budget option: ${flooringGuide.budget_spec}` : "") +
        `. Why: ${flooringGuide.rationale}`
    );
  }
  for (const tier of PACKAGE_TIER_ORDER) {
    const pc = packageContents.find((p) => p.tier === tier);
    if (!pc) continue;
    lines.push(
      `${PACKAGE_TIER_LABELS[tier]} tier -- Structure: ${pc.structure_description} Lighting: ${pc.lighting_description} Scope: ${pc.scope_description}` +
        (pc.warranty_years ? ` Warranty: ${pc.warranty_years} years.` : "")
    );
  }
  if (constructionSteps.length) {
    lines.push(
      "Construction sequence -- " +
        constructionSteps.map((s) => `${CONSTRUCTION_PHASE_LABELS[s.phase]}: ${s.description}`).join(" ") +
        ` (${CONSTRUCTION_SEQUENCE_DISCLAIMER})`
    );
  }
  return lines.join("\n");
}

export default function SportBuildGuide({ token, onSportDataChange }) {
  const [sports, setSports] = useState([]);
  const [sportId, setSportId] = useState("");
  const [loadingSports, setLoadingSports] = useState(true);
  const [loadingGuide, setLoadingGuide] = useState(false);
  const [error, setError] = useState("");
  const [accessories, setAccessories] = useState([]);
  const [flooringGuide, setFlooringGuide] = useState(null);
  const [packageContents, setPackageContents] = useState([]);
  const [constructionSteps, setConstructionSteps] = useState([]);

  useEffect(() => {
    listSports(token)
      .then((rows) => setSports([...rows].sort((a, b) => a.display_order - b.display_order)))
      .catch((err) => setError(err.message))
      .finally(() => setLoadingSports(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  useEffect(() => {
    if (!sportId) {
      onSportDataChange?.(null);
      return;
    }
    setError("");
    setLoadingGuide(true);
    Promise.all([
      listAccessoryCatalog(token, sportId),
      listFlooringGuides(token, sportId),
      listPackageContents(token, sportId),
      listConstructionSequence(token, sportId),
    ])
      .then(([acc, floor, pkg, steps]) => {
        setAccessories(acc);
        setFlooringGuide(floor[0] || null);
        setPackageContents(pkg);
        setConstructionSteps(steps);
        const sport = sports.find((s) => s.id === sportId);
        if (sport) onSportDataChange?.(summarizeForChat(sport, acc, floor[0] || null, pkg, steps));
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoadingGuide(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, sportId]);

  const sport = sports.find((s) => s.id === sportId);

  return (
    <div className="space-y-4">
      <p className="text-xs text-text-secondary">
        What a sport needs from scratch to ready-to-play, pulled live from the same data that already drives real
        Cost Sheets (Sports &amp; Scope Admin) -- not written fresh, so it stays consistent with what a real
        Cost Sheet for this sport would use. Indoor and Outdoor are shown as separate entries where a sport has both.
      </p>

      {loadingSports ? (
        <p className="text-sm text-text-secondary">Loading sports…</p>
      ) : (
        <select
          value={sportId}
          onChange={(e) => setSportId(e.target.value)}
          className="w-full rounded border border-border-dark bg-surface-raised text-text-primary px-3 py-2 text-sm"
        >
          <option value="">Select a sport…</option>
          {sports.map((s) => (
            <option key={s.id} value={s.id}>
              {s.name} ({s.category})
            </option>
          ))}
        </select>
      )}

      {error && <p className="text-xs text-red-400">{error}</p>}
      {loadingGuide && <p className="text-sm text-text-secondary">Loading build guide…</p>}

      {sport && !loadingGuide && (
        <div className="space-y-4">
          <div className="border border-border-dark rounded p-3">
            <h3 className="font-heading font-semibold text-text-primary text-sm">Dimensions</h3>
            <p className="text-sm text-text-secondary mt-1">
              Playing: {sport.playing_dims} · Build: {sport.build_dims}
            </p>
          </div>

          <div className="border border-border-dark rounded p-3">
            <h3 className="font-heading font-semibold text-text-primary text-sm">Accessories needed</h3>
            {accessories.length === 0 ? (
              <p className="text-sm text-text-secondary mt-1">No accessory catalog entries for this sport yet.</p>
            ) : (
              <ul className="text-sm text-text-secondary mt-1 list-disc list-inside space-y-0.5">
                {accessories.map((a) => (
                  <li key={a.id}>
                    {a.item_name} — {a.quantity_per_court} {a.unit} per court
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className="border border-border-dark rounded p-3">
            <h3 className="font-heading font-semibold text-text-primary text-sm">Flooring</h3>
            {flooringGuide ? (
              <div className="text-sm text-text-secondary mt-1 space-y-0.5">
                <p>Primary: {flooringGuide.primary_spec}</p>
                {flooringGuide.secondary_spec && <p>Alternative: {flooringGuide.secondary_spec}</p>}
                {flooringGuide.budget_spec && <p>Budget option: {flooringGuide.budget_spec}</p>}
                <p className="text-xs italic mt-1">Why: {flooringGuide.rationale}</p>
              </div>
            ) : (
              <p className="text-sm text-text-secondary mt-1">No flooring guide recorded for this sport yet.</p>
            )}
          </div>

          <div className="border border-border-dark rounded p-3">
            <h3 className="font-heading font-semibold text-text-primary text-sm">Package tiers</h3>
            {packageContents.length === 0 ? (
              <p className="text-sm text-text-secondary mt-1">No package content recorded for this sport yet.</p>
            ) : (
              <div className="mt-2 space-y-3">
                {PACKAGE_TIER_ORDER.map((tier) => {
                  const pc = packageContents.find((p) => p.tier === tier);
                  if (!pc) return null;
                  return (
                    <div key={tier} className="border-t border-border-dark pt-2 first:border-t-0 first:pt-0">
                      <p className="text-sm font-medium text-gold">{PACKAGE_TIER_LABELS[tier]}</p>
                      <p className="text-xs text-text-secondary mt-0.5">Structure: {pc.structure_description}</p>
                      <p className="text-xs text-text-secondary mt-0.5">Lighting: {pc.lighting_description}</p>
                      <p className="text-xs text-text-secondary mt-0.5">Scope: {pc.scope_description}</p>
                      {pc.warranty_years && (
                        <p className="text-xs text-text-secondary mt-0.5">Warranty: {pc.warranty_years} years</p>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {constructionSteps.length > 0 && (
            <div className="border border-border-dark rounded p-3">
              <h3 className="font-heading font-semibold text-text-primary text-sm">Construction sequence</h3>
              <ol className="text-sm text-text-secondary mt-1 list-decimal list-inside space-y-1">
                {CONSTRUCTION_PHASE_ORDER.map((phase) => {
                  const step = constructionSteps.find((s) => s.phase === phase);
                  if (!step) return null;
                  return (
                    <li key={phase}>
                      <span className="font-medium text-text-primary">{CONSTRUCTION_PHASE_LABELS[phase]}:</span>{" "}
                      {step.description}
                    </li>
                  );
                })}
              </ol>
              <p className="text-[11px] text-text-secondary bg-surface-raised border border-border-dark rounded px-2 py-1.5 mt-2">
                {CONSTRUCTION_SEQUENCE_DISCLAIMER}
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
