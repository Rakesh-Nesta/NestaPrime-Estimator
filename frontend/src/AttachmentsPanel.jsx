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

// M.3: "images, PDF, DOCX, XLSX, email .eml, DWG/PDF drawings"
const ACCEPT = ".jpg,.jpeg,.png,.gif,.webp,.pdf,.doc,.docx,.xls,.xlsx,.eml,.dwg";
const MAX_FILE_SIZE_BYTES = 100 * 1024 * 1024; // M.3: "max 100 MB each"

function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function StrengthBadge({ strength }) {
  if (!strength) return null;
  const colors = strength === "formal" ? "bg-green-50 text-green-700" : "bg-amber-50 text-amber-700";
  return <span className={`rounded px-1.5 py-0.5 ${colors}`}>{strength}</span>;
}

export default function AttachmentsPanel({ token, docType, docId }) {
  const [attachments, setAttachments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [tag, setTag] = useState("approval_evidence");
  const [approvalStrength, setApprovalStrength] = useState("");
  const [file, setFile] = useState(null);
  const [fileInputKey, setFileInputKey] = useState(0);
  const [uploading, setUploading] = useState(false);
  const [supersedingId, setSupersedingId] = useState(null);
  const [supersedeFile, setSupersedeFile] = useState(null);
  const [superseding, setSuperseding] = useState(false);

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

  function pickFile(selected, setter) {
    setError("");
    if (selected && selected.size > MAX_FILE_SIZE_BYTES) {
      setError(`${selected.name} is ${formatBytes(selected.size)} — attachments are limited to 100 MB (M.3).`);
      setter(null);
      return;
    }
    setter(selected || null);
  }

  async function handleUpload() {
    setError("");
    if (!file) return;
    setUploading(true);
    try {
      await uploadAttachment(token, { docType, docId, tag, approvalStrength: approvalStrength || undefined, file });
      setFile(null);
      setFileInputKey((k) => k + 1);
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setUploading(false);
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
    setSuperseding(true);
    try {
      await supersedeAttachment(token, attachmentId, { file: supersedeFile });
      setSupersedingId(null);
      setSupersedeFile(null);
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setSuperseding(false);
    }
  }

  if (loading) return <p className="text-xs text-gray-400">Loading attachments…</p>;

  return (
    <div className="border border-dashed border-gray-300 rounded p-3 space-y-2 bg-gray-50">
      <div>
        <p className="text-xs font-semibold text-gray-600">Attachments (M.3)</p>
        <p className="text-[11px] text-gray-400">
          Images, PDF, DOCX, XLSX, .eml, DWG · max 100 MB each. Images are kept as uploaded — auto-compression to a
          5 MB preview isn't built yet.
        </p>
      </div>
      {error && <p className="text-xs text-red-600">{error}</p>}
      {attachments.length === 0 && <p className="text-xs text-gray-400">No attachments yet.</p>}
      {attachments.map((a) => (
        <div
          key={a.id}
          className="flex flex-wrap items-center justify-between gap-2 text-xs bg-white rounded px-2 py-1 border border-gray-200"
        >
          <span className="flex flex-wrap items-center gap-1">
            <span className="font-medium">{a.original_filename}</span>
            <span className="text-gray-400">({formatBytes(a.original_size)})</span>
            <span>· {a.tag}</span>
            <StrengthBadge strength={a.approval_strength} />
            <span>· v{a.version}</span>
            <span className="text-gray-400">· {new Date(a.uploaded_at).toLocaleString()}</span>
          </span>
          <div className="flex items-center gap-2">
            <button onClick={() => handleDownload(a)} className="text-blue-600 hover:underline">
              Download
            </button>
            {supersedingId === a.id ? (
              <>
                <input
                  type="file"
                  accept={ACCEPT}
                  onChange={(e) => pickFile(e.target.files[0], setSupersedeFile)}
                  className="text-xs"
                />
                <button
                  onClick={() => handleSupersede(a.id)}
                  disabled={!supersedeFile || superseding}
                  className="text-green-700 hover:underline disabled:opacity-50 disabled:no-underline"
                >
                  {superseding ? "Uploading…" : "Confirm"}
                </button>
                <button
                  onClick={() => {
                    setSupersedingId(null);
                    setSupersedeFile(null);
                    setError("");
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
          accept={ACCEPT}
          onChange={(e) => pickFile(e.target.files[0], setFile)}
          className="text-xs flex-1 min-w-[8rem]"
        />
        <button
          onClick={handleUpload}
          disabled={!file || uploading}
          className="bg-blue-600 text-white text-xs rounded px-3 py-1 hover:bg-blue-700 disabled:opacity-50"
        >
          {uploading ? "Uploading…" : "Upload"}
        </button>
      </div>
      {tag === "approval_evidence" && (
        <p className="text-[11px] text-gray-400">
          Formal evidence is required before "Won" for Government/Tender clients or quotations ≥ Rs 25 L (M.3);
          Informal is enough below that.
        </p>
      )}
    </div>
  );
}
