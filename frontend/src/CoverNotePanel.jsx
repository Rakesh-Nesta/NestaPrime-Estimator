import { useState } from "react";
import { draftQuotationCoverNote, updateQuotationCoverNote } from "./api";

// Amendment 54 (Section 58): the note now prints as a letter (addressee, subject,
// this note, sign-off) on a quotation not yet sent, the AI draft is two short
// paragraphs from the facts that are set, and `quotation.pdf_gaps` says what the
// PDF will leave out -- a quiet note, never an error and never a block.
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
        rows={6}
        placeholder="The body of the cover letter -- with the addressee, a subject line and a sign-off it prints at the top of the Quotation PDF (until the quotation is sent). Leave blank for no letter."
        className="w-full max-w-2xl rounded border border-border-dark bg-surface-raised text-text-primary px-2 py-1.5 text-sm"
      />
      <p className="text-xs text-text-secondary max-w-2xl">
        &ldquo;Draft with AI&rdquo; writes two short paragraphs from the client, site, sports, package content and
        timeline that are set for this quotation. It is only a draft &mdash; check it before saving.
      </p>
      {error && <p className="text-xs text-red-400">{error}</p>}
      {quotation.pdf_gaps?.length > 0 && (
        <div className="max-w-2xl text-xs text-text-secondary border-l-2 border-border-dark pl-3">
          <p className="mb-0.5">The PDF will leave out:</p>
          <ul className="list-disc list-inside space-y-0.5">
            {quotation.pdf_gaps.map((gap) => (
              <li key={gap} className="break-words">{gap}</li>
            ))}
          </ul>
        </div>
      )}
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
