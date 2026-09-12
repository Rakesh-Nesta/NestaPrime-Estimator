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
  const colors = strength === "formal" ? "bg-green-500/10 text-green-400" : "bg-amber-500/10 text-amber-400";
  return <span className={`rounded px-1.5 py-0.5 ${colors}`}>{strength}</span>;
}

export default function AttachmentsPanel({ token, docType, docId }) {
  const [attachments, setAttachments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [tag, setTag] = useState("approval_evidence");
  const [approvalStrength, setApprovalStrength] = useState("");
  const [signatoryName, setSignatoryName] = useState("");
  const [signatoryDesignation, setSignatoryDesignation] = useState("");
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
      await uploadAttachment(token, {
        docType, docId, tag, approvalStrength: approvalStrength || undefined,
        signatoryName: signatoryName || undefined, signatoryDesignation: signatoryDesignation || undefined,
        file,
      });
      setFile(null);
      setFileInputKey((k) => k + 1);
      setSignatoryName("");
      setSignatoryDesignation("");
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

  if (loading) return <p className="text-xs text-text-secondary">Loading attachments…</p>;

  return (
    <div className="border border-dashed border-border-dark bg-surface-raised text-text-primary rounded p-3 space-y-2 bg-surface-raised">
      <div>
        <p className="text-xs font-semibold text-text-secondary">Attachments (M.3)</p>
        <p className="text-[11px] text-text-secondary">
          Images, PDF, DOCX, XLSX, .eml, DWG · max 100 MB each. Images are kept as uploaded — auto-compression to a
          5 MB preview isn't built yet.
        </p>
      </div>
      {error && <p className="text-xs text-red-400">{error}</p>}
      {attachments.length === 0 && <p className="text-xs text-text-secondary">No attachments yet.</p>}
      {attachments.map((a) => (
        <div
          key={a.id}
          className="flex flex-wrap items-center justify-between gap-2 text-xs bg-surface rounded px-2 py-1 border border-border-dark"
        >
          <span className="flex flex-wrap items-center gap-1">
            <span className="font-medium">{a.original_filename}</span>
            <span className="text-text-secondary">({formatBytes(a.original_size)})</span>
            <span>· {a.tag}</span>
            <StrengthBadge strength={a.approval_strength} />
            {a.signatory_name && (
              <span className="text-text-secondary">
                · signed by {a.signatory_name} ({a.signatory_designation})
              </span>
            )}
            <span>· v{a.version}</span>
            <span className="text-text-secondary">· {new Date(a.uploaded_at).toLocaleString()}</span>
          </span>
          <div className="flex items-center gap-2">
            <button onClick={() => handleDownload(a)} className="text-gold hover:underline">
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
                  className="text-green-400 hover:underline disabled:opacity-50 disabled:no-underline"
                >
                  {superseding ? "Uploading…" : "Confirm"}
                </button>
                <button
                  onClick={() => {
                    setSupersedingId(null);
                    setSupersedeFile(null);
                    setError("");
                  }}
                  className="text-text-secondary hover:underline"
                >
                  Cancel
                </button>
              </>
            ) : (
              <button onClick={() => setSupersedingId(a.id)} className="text-text-secondary hover:underline">
                Supersede
              </button>
            )}
          </div>
        </div>
      ))}

      <div className="flex flex-wrap items-center gap-2 pt-1">
        <select value={tag} onChange={(e) => setTag(e.target.value)} className="rounded border border-border-dark bg-surface-raised text-text-primary px-2 py-1 text-xs">
          {TAGS.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
        <select
          value={approvalStrength}
          onChange={(e) => setApprovalStrength(e.target.value)}
          className="rounded border border-border-dark bg-surface-raised text-text-primary px-2 py-1 text-xs"
        >
          <option value="">strength: n/a</option>
          <option value="informal">informal</option>
          <option value="formal">formal</option>
        </select>
        {tag === "approval_evidence" && (
          <>
            <input
              value={signatoryName}
              onChange={(e) => setSignatoryName(e.target.value)}
              placeholder="Signatory name (optional)"
              className="rounded border border-border-dark bg-surface-raised text-text-primary px-2 py-1 text-xs w-40"
            />
            <input
              value={signatoryDesignation}
              onChange={(e) => setSignatoryDesignation(e.target.value)}
              placeholder="Designation (optional)"
              className="rounded border border-border-dark bg-surface-raised text-text-primary px-2 py-1 text-xs w-36"
            />
          </>
        )}
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
          className="bg-gold text-white text-xs rounded px-3 py-1 hover:bg-gold-hover disabled:opacity-50"
        >
          {uploading ? "Uploading…" : "Upload"}
        </button>
      </div>
      {tag === "approval_evidence" && (
        <p className="text-[11px] text-text-secondary">
          Formal evidence is required before "Won" for Government/Tender clients or quotations ≥ Rs 25 L (M.3);
          Informal is enough below that. Naming a signatory is optional, but if given it must match an active,
          in-date entry in Client signatories (Part O) or the upload is rejected.
        </p>
      )}
    </div>
  );
}
