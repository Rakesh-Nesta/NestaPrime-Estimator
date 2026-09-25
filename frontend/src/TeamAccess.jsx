import { useState } from "react";
import RolePermissionsViewer from "./RolePermissionsViewer";
import UserManagementTab from "./UserManagement";

// Amendment 51 (Section 55): the real "Team & Access" screen. Director-only --
// the only role the API lets call /users and /role-permissions. It used to be a
// nav label that opened Master Settings.
const TABS = [
  { key: "people", label: "People" },
  { key: "roles", label: "Roles & permissions" },
];

export default function TeamAccess({ token, currentUser, onBack }) {
  const [tab, setTab] = useState("people");

  return (
    <div className="max-w-2xl mx-auto mt-8 mb-10 space-y-6">
      <div className="bg-surface shadow rounded-lg p-6">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-text-primary">Team &amp; Access</h2>
          {onBack && (
            <button onClick={onBack} className="text-sm text-gold hover:underline">
              &larr; Back
            </button>
          )}
        </div>
        <p className="text-xs text-text-secondary mt-1">
          Who can sign in, and what each role is allowed to do. Director-only.
        </p>
        <div className="flex gap-1 mt-4 border-b border-border-dark overflow-x-auto">
          {TABS.map((t) => (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={`text-sm px-3 py-2 border-b-2 -mb-px whitespace-nowrap ${
                tab === t.key ? "border-gold text-gold font-medium" : "border-transparent text-text-secondary hover:text-text-primary"
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>
      </div>

      {tab === "people" && <UserManagementTab token={token} currentUser={currentUser} />}

      {tab === "roles" && (
        <div className="bg-surface shadow rounded-lg p-6">
          <RolePermissionsViewer token={token} />
        </div>
      )}
    </div>
  );
}
