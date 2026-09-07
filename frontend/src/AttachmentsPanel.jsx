import { useEffect, useState } from "react";
import { downloadAttachmentBlob, listAttachments, supersedeAttachment, uploadAttachment } from "./api";

const TAGS = [
  "approval_evidence",
  "client_demand",
  "gst_opinion",
  "structural_design",
  "soil_report",
  "survey_form",
  "vendor_quote",
  "drawing",
  "photo",
  "product_image",
  "signed_document",
  "delivery_challan",
  "invoice",
  "reference",
];

export default function AttachmentsPanel({ token, docType, docId }) {
  const [attachments, setAttachments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [tag, setTag] = useState("approval_evidence");
  const [approvalStrength, setApprovalStrength] = useState("");
  const [file, setFile] = useState(null);
  const [fileInputKey, setFileInputKey] = useState(0);
  const [supersedingId, setSupersedingId] = useState(null);
  const [supersedeFile, setSupersedeFile] = useState(null);

  function load() {
    return listAttachments(token, docType, docId)
      .then(setAttachments)
      .catch((err) => setError(err.message));
  }

  useEffect(() => {
    setLoading(true);
    load().finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, docType, docId]);

  async function handleUpload() {
    setError("");
    if (!file) return;
    try {
      await uploadAttachment(token, { docType, docId, tag, approvalStrength: approvalStrength || undefined, file });
      setFile(null);
      setFileInputKey((k) => k + 1);
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleDownload(attachment) {
    setError("");
    try {
      const blob = await downloadAttachmentBlob(token, attachment.id);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = attachment.original_filename;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleSupersede(attachmentId) {
    setError("");
    if (!supersedeFile) return;
    try {
      await supersedeAttachment(token, attachmentId, { file: supersedeFile });
      setSupersedingId(null);
      setSupersedeFile(null);
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  if (loading) return <p className="text-xs text-gray-400">Loading attachments…</p>;

  return (
    <div className="border border-dashed border-gray-300 rounded p-3 space-y-2 bg-gray-50">
      <p className="text-xs font-semibold text-gray-600">Attachments (M.3)</p>
      {error && <p className="text-xs text-red-600">{error}</p>}
      {attachments.length === 0 && <p className="text-xs text-gray-400">No attachments yet.</p>}
      {attachments.map((a) => (
        <div
          key={a.id}
          className="flex flex-wrap items-center justify-between gap-2 text-xs bg-white rounded px-2 py-1 border border-gray-200"
        >
          <span>
            {a.original_filename} · {a.tag}
            {a.approval_strength && <span className="text-amber-700"> · {a.approval_strength}</span>} · v{a.version} ·{" "}
            {new Date(a.uploaded_at).toLocaleString()}
          </span>
          <div className="flex items-center gap-2">
            <button onClick={() => handleDownload(a)} className="text-blue-600 hover:underline">
              Download
            </button>
            {supersedingId === a.id ? (
              <>
                <input type="file" onChange={(e) => setSupersedeFile(e.target.files[0])} className="text-xs" />
                <button onClick={() => handleSupersede(a.id)} className="text-green-700 hover:underline">
                  Confirm
                </button>
                <button
                  onClick={() => {
                    setSupersedingId(null);
                    setSupersedeFile(null);
                  }}
                  className="text-gray-500 hover:underline"
                >
                  Cancel
                </button>
              </>
            ) : (
              <button onClick={() => setSupersedingId(a.id)} className="text-gray-500 hover:underline">
                Supersede
              </button>
            )}
          </div>
        </div>
      ))}

      <div className="flex flex-wrap items-center gap-2 pt-1">
        <select value={tag} onChange={(e) => setTag(e.target.value)} className="rounded border border-gray-300 px-2 py-1 text-xs">
          {TAGS.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
        <select
          value={approvalStrength}
          onChange={(e) => setApprovalStrength(e.target.value)}
          className="rounded border border-gray-300 px-2 py-1 text-xs"
        >
          <option value="">strength: n/a</option>
          <option value="informal">informal</option>
          <option value="formal">formal</option>
        </select>
        <input
          key={fileInputKey}
          type="file"
          onChange={(e) => setFile(e.target.files[0])}
          className="text-xs flex-1 min-w-[8rem]"
        />
        <button
          onClick={handleUpload}
          disabled={!file}
          className="bg-blue-600 text-white text-xs rounded px-3 py-1 hover:bg-blue-700 disabled:opacity-50"
        >
          Upload
        </button>
      </div>
    </div>
  );
}
