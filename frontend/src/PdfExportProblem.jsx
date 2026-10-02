import { useState } from "react";
import { excludeImageFromDocument, getPdfCheck, restoreImageToDocument } from "./api";

// Shown when a PDF cannot be produced as selected. Nothing is ever dropped silently: each image that cannot be included is
// listed with its reason, and the user either replaces it (upload a new image in the document's Attachments) or explicitly
// removes it from THIS document. The stored attachment is never changed. A busy server keeps the user's place and offers Retry.
const REASON_LABEL = {
  over_image_budget: "too large to embed",
  over_document_budget: "over this document's total image limit",
  unreadable: "cannot be read as an image",
  file_missing: "file missing from storage",
  removed_by_user: "removed from this document",
};

export default function PdfExportProblem({ token, docType, docId, problem, onChanged, onRetry, retrying }) {
  const [working, setWorking] = useState(null);
  const [error, setError] = useState("");
  const [excluded, setExcluded] = useState(problem.excluded || []);

  async function recheck() {
    setError("");
    try {
      const check = await getPdfCheck(token, docType, docId);
      setExcluded(check.excluded);
      if (check.complete) onChanged?.(check);
    } catch (err) {
      setError(err.message);
    }
  }

  async function remove(item) {
    setWorking(item.attachment_id);
    setError("");
    try {
      await excludeImageFromDocument(token, { doc_type: docType, doc_id: docId, attachment_id: item.attachment_id });
      await recheck();
    } catch (err) {
      setError(err.message);
    } finally {
      setWorking(null);
    }
  }

  async function restore(item) {
    setWorking(item.attachment_id);
    setError("");
    try {
      await restoreImageToDocument(token, item.exclusion_id);
      await recheck();
    } catch (err) {
      setError(err.message);
    } finally {
      setWorking(null);
    }
  }

  if (problem.kind === "busy") {
    return (
      <div className="rounded border border-yellow-700 bg-yellow-950/30 p-3 text-xs space-y-2" role="alert">
        <p className="text-yellow-200">PDF generation is busy. Please retry shortly.</p>
        <p className="text-text-secondary">Nothing you entered or selected has been lost.</p>
        <button
          type="button"
          disabled={retrying}
          onClick={onRetry}
          className="rounded bg-gold px-2 py-1 text-black disabled:opacity-50"
        >
          {retrying ? "Retrying…" : "Retry"}
        </button>
      </div>
    );
  }

  const blocking = excluded.filter((e) => !e.user_removed);
  const removed = excluded.filter((e) => e.user_removed);
  return (
    <div className="rounded border border-yellow-700 bg-yellow-950/30 p-3 text-xs space-y-2" role="alert">
      <p className="text-yellow-200 font-medium">
        {blocking.length > 0
          ? "This document cannot be produced yet: some of its selected images cannot be included."
          : "All selected images can now be included."}
      </p>
      {blocking.length > 0 && (
        <p className="text-text-secondary">
          Replace each image (upload a new one in this document&apos;s Attachments), or remove it from this document. The stored file
          is never changed.
        </p>
      )}
      <ul className="space-y-1">
        {blocking.map((item) => (
          <li key={item.attachment_id} className="flex flex-wrap items-center gap-2">
            <span className="font-mono">{item.filename}</span>
            <span className="text-text-secondary">— {REASON_LABEL[item.reason] ?? item.reason}</span>
            <button
              type="button"
              disabled={working === item.attachment_id}
              onClick={() => remove(item)}
              className="text-gold hover:underline disabled:opacity-50"
            >
              Remove from this document
            </button>
          </li>
        ))}
        {removed.map((item) => (
          <li key={item.attachment_id} className="flex flex-wrap items-center gap-2 text-text-secondary">
            <span className="font-mono">{item.filename}</span>
            <span>— removed from this document</span>
            <button
              type="button"
              disabled={working === item.attachment_id}
              onClick={() => restore(item)}
              className="text-gold hover:underline disabled:opacity-50"
            >
              Put back
            </button>
          </li>
        ))}
      </ul>
      {error && <p className="text-red-400">{error}</p>}
      <div className="flex gap-3">
        <button type="button" onClick={recheck} className="text-gold hover:underline">
          Check again
        </button>
        {blocking.length === 0 && (
          <button type="button" disabled={retrying} onClick={onRetry} className="text-gold hover:underline disabled:opacity-50">
            {retrying ? "Working…" : "Continue"}
          </button>
        )}
      </div>
    </div>
  );
}
