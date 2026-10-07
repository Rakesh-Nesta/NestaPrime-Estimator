import { useState } from "react";
import { draftValue, editDraft, newDraft, submitDraft } from "./identifierEditorDraft";
import { IDENTIFIER_RULE, MOBILE_HINT, identifierLines } from "./userIdentifiers";

// Amendment 61 Part B (Section 64 items 10-11): the Email and Mobile number fields shared by BOTH People screens
// (UserManagement.jsx for the Director and PM, AdminPeoplePanel.jsx for the Admin), so the create form, the identifier-edit
// form and the way identifiers are shown cannot drift apart. The server is authoritative for what a mobile number is and
// says so in plain words when it refuses one; the hints below only tell people what the server accepts.

const INPUT_CLASS = "mt-1 w-full rounded border border-border-dark bg-surface-raised text-text-primary px-2 py-1 text-sm";

/** The two identifier inputs. Neither is individually required: the rule is "at least one", checked on submit. */
export function IdentifierFields({ idPrefix, email, mobile, onChange }) {
  return (
    <>
      <div>
        <label htmlFor={`${idPrefix}-email`} className="block text-xs text-text-secondary">Email</label>
        <input
          id={`${idPrefix}-email`}
          type="text"
          inputMode="email"
          autoCapitalize="none"
          autoComplete="off"
          spellCheck={false}
          value={email}
          onChange={(e) => onChange("email", e.target.value)}
          className={INPUT_CLASS}
        />
      </div>
      <div>
        <label htmlFor={`${idPrefix}-mobile`} className="block text-xs text-text-secondary">Mobile number</label>
        <input
          id={`${idPrefix}-mobile`}
          type="tel"
          inputMode="tel"
          autoComplete="off"
          value={mobile}
          onChange={(e) => onChange("mobile", e.target.value)}
          aria-describedby={`${idPrefix}-mobile-hint`}
          className={INPUT_CLASS}
        />
        <p id={`${idPrefix}-mobile-hint`} className="mt-1 text-[11px] text-text-secondary">{MOBILE_HINT}</p>
      </div>
    </>
  );
}

/** How an account's identifiers read in a list: only the ones present, so a mobile-only account never shows an empty email. */
export function IdentifierText({ user, stacked = false, separator = " · " }) {
  const lines = identifierLines(user);
  if (lines.length === 0) return <span className="italic">no sign-in identifier</span>;
  return (
    <>
      {lines.map((line, index) => (
        <span key={line.kind} data-identifier={line.kind} className={stacked ? "block" : undefined}>
          {!stacked && index > 0 && separator}
          {line.value}
        </span>
      ))}
    </>
  );
}

/**
 * Inline editor for ONE account's identifiers. It remembers only the boxes the person edited (identifierEditorDraft.js) and
 * builds the PATCH body from those: untouched boxes are omitted and follow the refreshed list, a blanked box is sent as an
 * explicit "" to clear it, and an edit that would leave neither is refused before any request. It hands the body to `onSave`
 * and shows whatever the server answers (a malformed number, a duplicate) in place.
 */
export function IdentifierEditor({ user, serverError, onSave, onCancel }) {
  const [draft, setDraft] = useState(newDraft);
  const [localError, setLocalError] = useState("");
  const [saving, setSaving] = useState(false);
  const idPrefix = `edit-${user.id}`;

  async function submit(e) {
    e.preventDefault();
    const result = submitDraft(draft, user);
    if (!result.ok) {
      setLocalError(result.error);
      return;
    }
    if (result.unchanged) {
      onCancel();
      return;
    }
    setLocalError("");
    setSaving(true);
    try {
      await onSave(result.payload);
    } finally {
      setSaving(false);
    }
  }

  const message = localError || serverError;
  return (
    <form onSubmit={submit} aria-label={`Sign-in details of ${user.name}`} className="mt-2 border border-gold/30 bg-gold/5 rounded p-2.5 space-y-2 text-left">
      <p className="text-[11px] text-text-secondary">{IDENTIFIER_RULE} Leave a box empty to remove that way of signing in.</p>
      <div className="grid grid-cols-1 gap-2">
        <IdentifierFields
          idPrefix={idPrefix}
          email={draftValue(draft, user, "email")}
          mobile={draftValue(draft, user, "mobile")}
          onChange={(field, value) => setDraft((current) => editDraft(current, field, value))}
        />
      </div>
      {message && <p role="alert" className="text-xs text-red-400">{message}</p>}
      <div className="flex items-center gap-3">
        <button type="submit" disabled={saving} className="bg-gold text-base text-xs rounded px-3 py-1 hover:bg-gold-hover disabled:opacity-50">
          {saving ? "Saving…" : "Save"}
        </button>
        <button type="button" onClick={onCancel} className="text-xs text-text-secondary hover:underline">
          Cancel
        </button>
      </div>
    </form>
  );
}
