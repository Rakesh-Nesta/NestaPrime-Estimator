import { useState } from "react";
import {
  completeUploadSession, getUploadSessionStatus, startUploadSession, uploadSessionChunk,
} from "./api";

// Proposed only -- the session's own chunk_size, as echoed back by the server on start (or
// re-fetched via status on resume), is what every slicing/indexing decision actually uses. A
// resumed session may have been started under a different proposed value (e.g. this constant
// changed between app versions) -- trusting a local constant instead of the server's own record
// would misalign chunk boundaries against what the server expects for each index.
const PROPOSED_CHUNK_SIZE = 5 * 1024 * 1024; // 5 MB -- small enough to retry cheaply on a flaky mobile connection
const MAX_FILE_SIZE_BYTES = 100 * 1024 * 1024; // matches the existing single-shot cap (M.3)

function storageKey(docType, docId) {
  return `p4-upload-session:${docType}:${docId}`;
}

function readResumable(docType, docId) {
  try {
    const raw = localStorage.getItem(storageKey(docType, docId));
    return raw ? JSON.parse(raw) : null;
  } catch {
    localStorage.removeItem(storageKey(docType, docId));
    return null;
  }
}

async function sha256Hex(file) {
  const buffer = await file.arrayBuffer();
  const digest = await crypto.subtle.digest("SHA-256", buffer);
  return Array.from(new Uint8Array(digest)).map((b) => b.toString(16).padStart(2, "0")).join("");
}

/** P4 contract v7, Section 4: reliable mobile uploads. Four calls against the session
 * lifecycle (start / chunk / status / complete), never a single "upload" request for a large
 * file -- so a dropped connection loses at most one chunk, not the whole upload, and a page
 * reload can resume from wherever the last confirmed chunk left off. */
export default function ChunkedUpload({ token, docType, docId, onUploaded, disabled }) {
  const [file, setFile] = useState(null);
  const [fileInputKey, setFileInputKey] = useState(0);
  const [phase, setPhase] = useState("idle"); // idle | hashing | uploading | completing
  const [progress, setProgress] = useState({ done: 0, total: 0 });
  const [error, setError] = useState("");
  // Lazy initializer -- reads localStorage once, during this component's own first render, to
  // synchronize with that external system. Deliberately not a useEffect+setState pair: docType/
  // docId are stable for this component's whole lifetime in every call site that mounts it (each
  // is rendered once per a stage/document row, keyed by that row's own id), so there is no later
  // prop change this would ever need to re-run for, and a lazy initializer avoids the extra
  // render an effect would cost on every mount for no benefit.
  const [resumable, setResumable] = useState(() => readResumable(docType, docId));
  // { sessionId, filename, declaredSize, declaredSha256, chunkSize }

  function pickFile(selected) {
    setError("");
    if (!selected) {
      setFile(null);
      return;
    }
    if (selected.size > MAX_FILE_SIZE_BYTES) {
      setError(`${selected.name} is over the 100 MB limit (M.3).`);
      setFile(null);
      return;
    }
    setFile(selected);
  }

  async function run() {
    if (!file) return;
    setError("");
    try {
      setPhase("hashing");
      const declaredSha256 = await sha256Hex(file);

      let sessionId;
      let chunkSize; // authoritative -- always from the server, never the local proposed constant
      let alreadyWritten = new Set();
      const isResume = resumable && resumable.declaredSha256 === declaredSha256 && resumable.declaredSize === file.size;
      if (isResume) {
        // A genuine resume: same file (by full hash, not just size+name), a session already
        // exists. Ask the server what's already confirmed -- including its own chunk_size --
        // rather than assuming either.
        try {
          const status = await getUploadSessionStatus(token, resumable.sessionId);
          if (status.status === "uploading" || status.status === "completed") {
            sessionId = resumable.sessionId;
            chunkSize = status.chunk_size;
            alreadyWritten = new Set(status.written_chunk_indexes);
            if (status.status === "completed") {
              // A lost success response -- the retry below (complete) just returns the same receipt.
            }
          }
        } catch {
          // The session is gone (purged, or never existed) -- fall through to starting fresh.
        }
      }
      if (!sessionId) {
        const session = await startUploadSession(token, {
          docType, docId, filename: file.name, declaredSize: file.size, declaredSha256,
          chunkSize: PROPOSED_CHUNK_SIZE,
        });
        sessionId = session.id;
        chunkSize = session.chunk_size; // the server's own record, not necessarily identical in
        // value to what was proposed, and the only thing used from here on
        localStorage.setItem(
          storageKey(docType, docId),
          JSON.stringify({ sessionId, filename: file.name, declaredSize: file.size, declaredSha256, chunkSize }),
        );
      }

      const total = Math.ceil(file.size / chunkSize);
      setPhase("uploading");
      setProgress({ done: alreadyWritten.size, total });
      for (let index = 0; index < total; index++) {
        if (alreadyWritten.has(index)) continue;
        const start = index * chunkSize;
        // The final chunk is whatever remains -- Math.min naturally produces the exact partial
        // size the server's own _expected_chunk_size computes for the last index, no special
        // case needed as long as chunkSize itself is the server's authoritative value.
        const blob = file.slice(start, Math.min(start + chunkSize, file.size));
        const result = await uploadSessionChunk(token, sessionId, index, blob);
        if (result.promoted) {
          setProgress((p) => ({ ...p, done: p.done + 1 }));
        }
        // A superseded-by-a-newer-retry response (promoted: false) is not an error -- the chunk
        // is simply not this attempt's to count; completion only ever needs every INDEX written,
        // regardless of which attempt wrote it.
      }

      setPhase("completing");
      const attachment = await completeUploadSession(token, sessionId);
      localStorage.removeItem(storageKey(docType, docId));
      setResumable(null);
      setFile(null);
      setFileInputKey((k) => k + 1);
      setPhase("idle");
      setProgress({ done: 0, total: 0 });
      onUploaded?.(attachment);
    } catch (err) {
      setError(err.message);
      setPhase("idle");
    }
  }

  function discardResumable() {
    localStorage.removeItem(storageKey(docType, docId));
    setResumable(null);
  }

  const busy = phase !== "idle";
  const label =
    phase === "hashing" ? "Checking file…"
    : phase === "uploading" ? `Uploading ${progress.done}/${progress.total} parts…`
    : phase === "completing" ? "Finishing…"
    : "Upload (resumable)";

  return (
    <div className="flex flex-wrap items-center gap-2">
      {resumable && !file && (
        <div className="flex items-center gap-2 text-xs text-text-secondary bg-surface-raised rounded px-2 py-1 border border-border-dark">
          <span>An interrupted upload of "{resumable.filename}" can resume — re-select the same file.</span>
          <button onClick={discardResumable} className="text-red-400 hover:underline">Discard</button>
        </div>
      )}
      <input
        key={fileInputKey}
        type="file"
        disabled={disabled || busy}
        onChange={(e) => pickFile(e.target.files[0])}
        className="text-xs flex-1 min-w-[8rem]"
      />
      <button
        onClick={run}
        disabled={disabled || !file || busy}
        className="bg-gold text-base text-xs rounded px-3 py-1 hover:bg-gold-hover disabled:opacity-50"
      >
        {label}
      </button>
      {error && <p className="text-red-400 text-xs w-full">{error}</p>}
    </div>
  );
}
