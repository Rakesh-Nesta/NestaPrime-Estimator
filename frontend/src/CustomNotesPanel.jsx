import { useState } from "react";
import { updateProjectNotes } from "./api";

// Amendment 5's Custom Notes component: "a reusable '+ Add Note' button on
// Project Setup, Cost Sheet, and Estimate screens... persisted on the
// Project record" -- one field on Project, not per-screen, so it's added
// once here rather than duplicated per screen. Project Setup itself has no
// project_id yet (it's the creation form -- see ProjectSetup.jsx, which
// navigates away immediately on success), so this renders alongside the
// breadcrumb that already appears on every real project-stage screen
// (Sport, Scope, Documents -- which covers Cost Sheet and Estimate, both
// part of Documents.jsx), reachable from the moment Setup completes.
export default function CustomNotesPanel({ token, project, onNotesSaved }) {
  const [open, setOpen] = useState(Boolean(project.custom_notes));
  const [draft, setDraft] = useState(project.custom_notes || "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  async function handleSave() {
    setSaving(true);
    setError("");
    try {
      const updated = await updateProjectNotes(token, project.id, { custom_notes: draft || null });
      onNotesSaved?.(updated);
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  if (!open) {
    return (
      <div className="bg-surface border-b border-border-dark px-4 sm:px-8 py-1.5 print:hidden">
        <button onClick={() => setOpen(true)} className="text-xs text-gold hover:underline">
          + Add Note
        </button>
      </div>
    );
  }

  return (
    <div className="bg-surface border-b border-border-dark px-4 sm:px-8 py-3 space-y-2 print:hidden">
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold text-text-secondary uppercase tracking-wider">Custom Notes</span>
        <button onClick={() => setOpen(false)} className="text-xs text-text-secondary hover:text-text-primary">
          Hide
        </button>
      </div>
      <textarea
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        rows={3}
        placeholder="Unstructured remarks for this project — appears on the Quotation PDF under Special Remarks."
        className="w-full max-w-2xl rounded border border-border-dark bg-surface-raised text-text-primary px-2 py-1.5 text-sm"
      />
      {error && <p className="text-xs text-red-400">{error}</p>}
      <button
        onClick={handleSave}
        disabled={saving}
        className="text-xs bg-gold text-base rounded px-3 py-1.5 hover:bg-gold-hover disabled:opacity-50"
      >
        {saving ? "Saving…" : "Save note"}
      </button>
    </div>
  );
}
