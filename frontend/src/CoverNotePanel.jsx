import { useState } from "react";
import { draftQuotationCoverNote, updateQuotationCoverNote } from "./api";

// Amendment 13 (Section 12): a Quotation's optional cover_note -- AI can
// draft it, but nothing is saved until a person reviews/edits the text
// here and clicks Save, same review-then-save shape as CustomNotesPanel.
export default function CoverNotePanel({ token, quotation, onSaved }) {
  const [draft, setDraft] = useState(quotation.cover_note || "");
  const [drafting, setDrafting] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  async function handleDraftWithAi() {
    setDrafting(true);
    setError("");
    try {
      const { draft: aiDraft } = await draftQuotationCoverNote(token, quotation.id);
      setDraft(aiDraft);
    } catch (err) {
      setError(err.message);
    } finally {
      setDrafting(false);
    }
  }

  async function handleSave() {
    setSaving(true);
    setError("");
    try {
      const updated = await updateQuotationCoverNote(token, quotation.id, draft || null);
      onSaved?.(updated);
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="bg-surface border-b border-border-dark px-4 sm:px-8 py-3 space-y-2 print:hidden">
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold text-text-secondary uppercase tracking-wider">Cover Note</span>
        <button
          onClick={handleDraftWithAi}
          disabled={drafting}
          className="text-xs bg-surface-raised text-gold border border-gold/40 rounded px-2.5 py-1 hover:bg-gold/10 hover:-translate-y-0.5 transition-all duration-250 ease-out disabled:opacity-50"
        >
          {drafting ? "Drafting…" : "Draft with AI"}
        </button>
      </div>
      <textarea
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        rows={3}
        placeholder="A short introduction paragraph -- appears at the top of the Quotation PDF, right after the header. Leave blank for no change to the PDF."
        className="w-full max-w-2xl rounded border border-border-dark bg-surface-raised text-text-primary px-2 py-1.5 text-sm"
      />
      {error && <p className="text-xs text-red-400">{error}</p>}
      <button
        onClick={handleSave}
        disabled={saving}
        className="text-xs bg-gold text-base rounded px-3 py-1.5 hover:bg-gold-hover hover:-translate-y-0.5 transition-all duration-250 ease-out disabled:opacity-50"
      >
        {saving ? "Saving…" : "Save cover note"}
      </button>
    </div>
  );
}
