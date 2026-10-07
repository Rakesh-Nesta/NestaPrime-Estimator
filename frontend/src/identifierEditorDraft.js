// Amendment 61 Part B: the DRAFT of one "Edit sign-in" session (what the person typed), as pure functions.
//
// The draft holds ONLY the boxes the person intentionally edited in this session ({} when none). A box not in the draft shows,
// and is judged by, the account as the People list shows it NOW -- so when an earlier save completes and the list refreshes
// under the open editor, an untouched box follows the refresh instead of keeping an out-of-date copy that submitting would
// write back. Submitting builds the PATCH from the touched boxes only (see buildIdentifierPatch).

import { buildIdentifierPatch } from "./userIdentifiers.js";

export function newDraft() {
  return {};
}

export function editDraft(draft, field, value) {
  return { ...draft, [field]: value };
}

export function isTouched(draft, field) {
  return Object.prototype.hasOwnProperty.call(draft, field);
}

/** What a box shows: what the person typed there, else the account's current value. */
export function draftValue(draft, user, field) {
  return isTouched(draft, field) ? draft[field] : user?.[field] || "";
}

export function submitDraft(draft, user) {
  const edited = { email: draftValue(draft, user, "email"), mobile: draftValue(draft, user, "mobile") };
  return buildIdentifierPatch(user, edited, { email: isTouched(draft, "email"), mobile: isTouched(draft, "mobile") });
}
