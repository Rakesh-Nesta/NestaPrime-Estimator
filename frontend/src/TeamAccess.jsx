import { useState } from "react";
import AdminPeoplePanel from "./AdminPeoplePanel";
import RecordOwners from "./RecordOwners";
import RolePermissionsViewer from "./RolePermissionsViewer";
import UserManagementTab from "./UserManagement";

// Amendment 51 (Section 55): the real "Team & Access" screen. It used to be a
// nav label that opened Master Settings. Amendment 59: Admin and Director see
// People and Roles; a PM sees People only (the API lets a PM list and add
// people, and nothing else here). Amendment 60: Director and PM also get
// "Record owners" -- who owns which client, project and enquiry -- which the Admin
// does not (an Admin holds no sales records).
const TABS = [
  { key: "people", label: "People", roles: ["admin", "director", "pm"] },
  { key: "roles", label: "Roles & permissions", roles: ["admin", "director"] },
  { key: "owners", label: "Record owners", roles: ["director", "pm"] },
];

export default function TeamAccess({ token, currentUser, onBack }) {
  const [tab, setTab] = useState("people");
  const isPm = currentUser?.role === "pm";
  const tabs = TABS.filter((t) => t.roles.includes(currentUser?.role));

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
          {isPm
            ? "Add the people who work with you, and see who owns which clients and projects."
            : "Who can sign in, and what each role is allowed to do. Admin and Director."}
        </p>
        <div className="flex gap-1 mt-4 border-b border-border-dark overflow-x-auto">
          {tabs.map((t) => (
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

      {tab === "people" && currentUser?.role === "admin" && (
        <AdminPeoplePanel token={token} currentUser={currentUser} />
      )}
      {tab === "people" && currentUser?.role !== "admin" && (
        <UserManagementTab token={token} currentUser={currentUser} />
      )}

      {tab === "owners" && <RecordOwners token={token} currentUser={currentUser} />}

      {tab === "roles" && !isPm && (
        <div className="bg-surface shadow rounded-lg p-6">
          <RolePermissionsViewer token={token} />
        </div>
      )}
    </div>
  );
}
