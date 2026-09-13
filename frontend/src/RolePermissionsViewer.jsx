import { useState } from "react";
import { ALL_ROLES, CA_TAX_NOTE, FEATURE_AREAS, ROLE_LABELS, SAFETY_CRITICAL_RULES } from "./rolePermissionsData";

// Amendment 6a (Option A): read-only mirror of the backend's hardcoded
// require_roles() checks. There is no editable permission here on purpose --
// see SAFETY_CRITICAL_RULES for why some of this must never become a toggle.
export default function RolePermissionsViewer() {
  const [selectedRole, setSelectedRole] = useState(null); // null = show everything

  return (
    <div className="space-y-4">
      <div>
        <h3 className="text-sm font-semibold text-text-secondary mb-1">Role & Permissions</h3>
        <p className="text-xs text-text-secondary">
          What each role can currently see and do, mirrored from the backend's own access checks —
          view-only. Nothing here can be changed from this screen; a role's actual access changes
          only when the underlying code changes.
        </p>
      </div>

      <div className="flex flex-wrap gap-2">
        <button
          onClick={() => setSelectedRole(null)}
          className={`text-xs rounded px-3 py-1.5 border ${
            selectedRole === null
              ? "bg-gold text-base border-gold font-semibold"
              : "border-border-dark text-text-secondary hover:text-text-primary"
          }`}
        >
          All roles
        </button>
        {ALL_ROLES.map((role) => (
          <button
            key={role}
            onClick={() => setSelectedRole(role)}
            className={`text-xs rounded px-3 py-1.5 border ${
              selectedRole === role
                ? "bg-gold text-base border-gold font-semibold"
                : "border-border-dark text-text-secondary hover:text-text-primary"
            }`}
          >
            {ROLE_LABELS[role]}
          </button>
        ))}
      </div>

      {selectedRole === "ca_tax" && (
        <p className="text-xs text-amber-400 bg-amber-500/10 rounded px-3 py-2">{CA_TAX_NOTE}</p>
      )}

      <div className="space-y-3">
        {FEATURE_AREAS.map((area) => {
          const groups = selectedRole
            ? area.groups.filter((g) => g.roles.includes(selectedRole))
            : area.groups;
          if (groups.length === 0) return null;
          return (
            <div key={area.area} className="border border-border-dark rounded px-4 py-3">
              <h4 className="text-sm font-semibold text-text-primary mb-2">{area.area}</h4>
              <div className="space-y-2">
                {groups.map((g, i) => (
                  <div key={i} className="text-xs">
                    <div className="flex flex-wrap gap-1 mb-1">
                      {g.roles.map((r) => (
                        <span
                          key={r}
                          className={`rounded px-1.5 py-0.5 ${
                            r === selectedRole
                              ? "bg-gold text-base font-semibold"
                              : "bg-surface-raised text-text-secondary"
                          }`}
                        >
                          {ROLE_LABELS[r]}
                        </span>
                      ))}
                    </div>
                    <ul className="list-disc list-inside text-text-secondary space-y-0.5">
                      {g.items.map((item) => (
                        <li key={item}>{item}</li>
                      ))}
                    </ul>
                  </div>
                ))}
              </div>
            </div>
          );
        })}
      </div>

      <div className="border border-gold/40 rounded px-4 py-3 bg-gold-muted">
        <h4 className="text-sm font-semibold text-gold mb-2">Safety-critical rules — not adjustable</h4>
        <p className="text-xs text-text-secondary mb-3">
          These stay hardcoded regardless of role, by design — this is exactly why this screen is a
          viewer and not an editor.
        </p>
        <div className="space-y-3">
          {SAFETY_CRITICAL_RULES.map((rule) => (
            <div key={rule.name}>
              <p className="text-xs font-semibold text-text-primary">{rule.name}</p>
              <p className="text-xs text-text-secondary mt-0.5">{rule.detail}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
