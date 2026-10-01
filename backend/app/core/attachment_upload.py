"""P4 contract v7, Section 4: reliable mobile uploads -- the chunked-upload protocol.

Every guarantee here traces to a specific numbered fix in the contract (Section 0):
  * declared_sha256 is REQUIRED for the chunked path and checked at completion (item 1).
  * every endpoint re-checks session ownership AND the target document's role/ownership (item 2).
  * every status-dependent decision uses SELECT ... FOR UPDATE or an atomic compare-and-swap,
    never an unlocked read (revision 4, Section 0.A).
  * the fencing token (completion_attempt) moves atomically with BOTH the uploading->completing
    transition AND, per revision 7, the completing->uploading recovery transition -- never left to
    drift (Section 0.A, revision 5 and 7).
  * chunk promotion locks session-then-chunk, both held through the check and the rename, and uses
    attempt-specific temp files with a fenced, atomic promotion (revision 5/6, Section 0.B).
  * finalization is five ordered steps, file-before-receipt, using a DETERMINISTIC final path --
    final_attachment_path(session_id, completion_attempt) -- recomputable by cleanup with zero
    extra persistence, never a freshly-generated id that would exist only in a crashed worker's
    own memory (revision 6/7, Section 0.A).
  * cleanup deletes an orphaned final-path file only when the attempt is irrevocably superseded
    AND a fresh check against attachments finds no row referencing that exact path -- never on
    absence of a row alone (revision 7, Section 0.B).
"""

import hashlib
import os
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models.attachment import Attachment
from app.models.attachment_upload_session import (
    AttachmentUploadChunk,
    AttachmentUploadSession,
    ChunkStatus,
    UploadSessionStatus,
)

MAX_FILE_SIZE_BYTES = 100 * 1024 * 1024  # matches attachments.py's own M.3 cap
RECOVERY_CUTOFF = timedelta(minutes=5)  # Section 4: "a completing session idle past a short window"
ABANDONED_SESSION_CUTOFF = timedelta(hours=24)  # matches the existing abandoned-session precedent


class UploadProtocolError(Exception):
    """Raised for any refusal that isn't a plain 404/403 -- the API layer maps this to the right
    HTTP status. Kept separate from HTTPException so this module has no FastAPI dependency."""

    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


# --- storage layout --------------------------------------------------------------------------


def _session_temp_dir(session_id: uuid.UUID) -> Path:
    """Kept entirely separate from any real doc_type/doc_id directory attachments.py's own
    _storage_dir would ever produce -- the leading underscore can never collide with a doc_type
    value, none of which start with one."""
    path = Path(settings.attachment_storage_root) / "_upload_tmp" / str(session_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _chunk_temp_path(session_id: uuid.UUID, chunk_index: int, claimed_attempt: int) -> Path:
    return _session_temp_dir(session_id) / f"chunk_{chunk_index}.attempt_{claimed_attempt}.part"


def _chunk_accepted_path(session_id: uuid.UUID, chunk_index: int) -> Path:
    """The single accepted path for this chunk_index -- only ever written to via an atomic
    rename from a chunk's own attempt-specific temp file, never written to directly."""
    return _session_temp_dir(session_id) / f"chunk_{chunk_index}.accepted"


def _assembly_temp_path(session_id: uuid.UUID, completion_attempt: int) -> Path:
    return _session_temp_dir(session_id) / f"assembled.attempt_{completion_attempt}.tmp"


def final_attachment_path(doc_type: str, doc_id: uuid.UUID, filename: str, session_id: uuid.UUID, completion_attempt: int) -> Path:
    """Revision 7, Section 0.A: a pure function of (session_id, completion_attempt) -- both
    already durable on the session row well before finalization begins -- never a freshly
    generated id that would exist only in a crashed worker's own memory. Cleanup recomputes this
    exact path for any past, now-superseded attempt using nothing but the session row, with no
    need to touch whatever an original crashed worker had in its own memory."""
    from app.api.attachments import _safe_filename, _storage_dir  # local: avoid an import cycle
    from app.models.setting import DocumentType

    safe_name = _safe_filename(filename)
    directory = _storage_dir(DocumentType(doc_type), doc_id)
    return directory / f"{session_id}_{completion_attempt}_{safe_name}"


def _expected_chunk_size(session: AttachmentUploadSession, chunk_index: int) -> int:
    if chunk_index == session.total_chunks - 1:
        remainder = session.declared_size - session.chunk_size * (session.total_chunks - 1)
        return remainder
    return session.chunk_size


# --- session lifecycle ------------------------------------------------------------------------


def start_session(
    db: Session, current_user, doc_type: str, doc_id: uuid.UUID,
    filename: str, declared_size: int, declared_sha256: str, chunk_size: int,
) -> AttachmentUploadSession:
    if declared_size <= 0 or declared_size > MAX_FILE_SIZE_BYTES:
        raise UploadProtocolError(413, "declared_size must be > 0 and within the 100 MB limit (M.3)")
    if chunk_size <= 0:
        raise UploadProtocolError(422, "chunk_size must be positive")
    if len(declared_sha256) != 64:
        raise UploadProtocolError(422, "declared_sha256 is required for the chunked upload path")

    total_chunks = (declared_size + chunk_size - 1) // chunk_size
    session = AttachmentUploadSession(
        doc_type=doc_type, doc_id=doc_id, filename=filename, declared_size=declared_size,
        declared_sha256=declared_sha256.lower(), chunk_size=chunk_size, total_chunks=total_chunks,
        status=UploadSessionStatus.UPLOADING.value, completion_attempt=0,
        created_by_id=current_user.id,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def get_session(db: Session, session_id: uuid.UUID) -> AttachmentUploadSession:
    session = db.get(AttachmentUploadSession, session_id)
    if session is None:
        raise UploadProtocolError(404, "Upload session not found")
    return session


def session_status(db: Session, session: AttachmentUploadSession) -> dict:
    written = (
        db.query(AttachmentUploadChunk.chunk_index)
        .filter(
            AttachmentUploadChunk.session_id == session.id,
            AttachmentUploadChunk.status == ChunkStatus.WRITTEN.value,
        )
        .all()
    )
    return {
        "id": session.id,
        "status": session.status,
        "chunk_size": session.chunk_size,
        "total_chunks": session.total_chunks,
        "written_chunk_indexes": sorted(row[0] for row in written),
        "resulting_attachment_id": session.resulting_attachment_id,
        "declared_sha256": session.declared_sha256,
    }


# --- chunk upload: claim (locked, committed) -> write (unlocked) -> promote (fenced, locked) ---


def claim_chunk(db: Session, session_id: uuid.UUID, chunk_index: int) -> int:
    """Locks the session row, confirms status='uploading', then claims (or re-claims) the chunk
    row -- bumping claimed_attempt on a retry of the same index. Commits, releasing the lock,
    BEFORE any byte is written to disk (Section 4's own shared locking protocol)."""
    _recover_if_stuck(db, session_id)
    session = db.execute(
        select(AttachmentUploadSession).where(AttachmentUploadSession.id == session_id).with_for_update()
    ).scalar_one_or_none()
    if session is None:
        db.rollback()
        raise UploadProtocolError(404, "Upload session not found")
    # Captured before any rollback below: db.rollback() expires session's attributes AND releases
    # the row lock just taken above, so a concurrent purge of this same (abandoned) session could
    # delete the row in that exact window -- reading session.status/total_chunks straight into an
    # f-string AFTER rollback would then raise ObjectDeletedError instead of the clean 409/422
    # this function means to return (caught for real by test_cleanup_cannot_race_an_active_session).
    status, total_chunks = session.status, session.total_chunks
    if status != UploadSessionStatus.UPLOADING.value:
        db.rollback()
        raise UploadProtocolError(409, f"Session is '{status}' -- chunk writes are only accepted while uploading")
    if not (0 <= chunk_index < total_chunks):
        db.rollback()
        raise UploadProtocolError(422, f"chunk_index must be in [0, {total_chunks})")

    chunk = db.execute(
        select(AttachmentUploadChunk)
        .where(AttachmentUploadChunk.session_id == session_id, AttachmentUploadChunk.chunk_index == chunk_index)
        .with_for_update()
    ).scalar_one_or_none()
    if chunk is None:
        chunk = AttachmentUploadChunk(
            session_id=session_id, chunk_index=chunk_index, received_bytes=0,
            status=ChunkStatus.PENDING_WRITE.value, claimed_attempt=1,
        )
        db.add(chunk)
        claimed_attempt = 1
    else:
        chunk.claimed_attempt += 1
        chunk.status = ChunkStatus.PENDING_WRITE.value
        claimed_attempt = chunk.claimed_attempt
    session.last_activity_at = datetime.now(UTC)
    db.commit()
    return claimed_attempt


def write_and_promote_chunk(db: Session, session_id: uuid.UUID, chunk_index: int, claimed_attempt: int, content: bytes) -> dict:
    """Writes to this attempt's own temp file (never a path any other attempt could also be
    writing to), then locks session-then-chunk together (revision 6 fix) and promotes only if
    both the session is still 'uploading' and claimed_attempt still matches the row's current
    value. A superseded attempt's temp file is discarded, never promoted."""
    temp_path = _chunk_temp_path(session_id, chunk_index, claimed_attempt)
    temp_path.write_bytes(content)

    session = db.execute(
        select(AttachmentUploadSession).where(AttachmentUploadSession.id == session_id).with_for_update()
    ).scalar_one_or_none()
    if session is None or session.status != UploadSessionStatus.UPLOADING.value:
        db.rollback()
        temp_path.unlink(missing_ok=True)
        raise UploadProtocolError(409, "Session moved on before this chunk could be promoted")

    chunk = db.execute(
        select(AttachmentUploadChunk)
        .where(AttachmentUploadChunk.session_id == session_id, AttachmentUploadChunk.chunk_index == chunk_index)
        .with_for_update()
    ).scalar_one_or_none()
    if chunk is None or chunk.claimed_attempt != claimed_attempt:
        db.rollback()
        temp_path.unlink(missing_ok=True)
        return {"promoted": False, "reason": "superseded by a newer retry of this chunk"}

    expected = _expected_chunk_size(session, chunk_index)
    if len(content) != expected:
        db.rollback()
        temp_path.unlink(missing_ok=True)
        raise UploadProtocolError(422, f"Chunk {chunk_index}: expected {expected} bytes, received {len(content)}")

    accepted_path = _chunk_accepted_path(session_id, chunk_index)
    os.replace(temp_path, accepted_path)
    chunk.status = ChunkStatus.WRITTEN.value
    chunk.received_bytes = len(content)
    chunk.received_at = datetime.now(UTC)
    session.last_activity_at = datetime.now(UTC)
    db.commit()
    return {"promoted": True}


# --- completion: five ordered steps, file-before-receipt --------------------------------------


def start_completion(db: Session, session_id: uuid.UUID) -> int:
    """Refuses immediately (reverting status back to 'uploading', no token change -- this is the
    same worker cleanly observing incomplete writes, not a stuck/dead-worker recovery scenario)
    if any chunk is still pending_write or missing. Otherwise atomically transitions
    uploading->completing, bumping completion_attempt in the same statement, and returns this
    attempt's own token."""
    _recover_if_stuck(db, session_id)
    session = db.execute(
        select(AttachmentUploadSession).where(AttachmentUploadSession.id == session_id).with_for_update()
    ).scalar_one_or_none()
    if session is None:
        db.rollback()
        raise UploadProtocolError(404, "Upload session not found")
    # Captured before any rollback below -- same reason as claim_chunk: rollback expires
    # session's attributes and releases the lock just taken, so reading them afterward can race
    # a concurrent purge of this session into an unhandled ObjectDeletedError instead of a 409.
    status, total_chunks = session.status, session.total_chunks
    if status == UploadSessionStatus.COMPLETED.value:
        db.rollback()
        raise UploadProtocolError(200, "already completed")  # caller special-cases this
    if status != UploadSessionStatus.UPLOADING.value:
        db.rollback()
        raise UploadProtocolError(409, f"Session is '{status}' -- cannot start completion")

    chunks = db.query(AttachmentUploadChunk).filter(AttachmentUploadChunk.session_id == session_id).all()
    written = {c.chunk_index for c in chunks if c.status == ChunkStatus.WRITTEN.value}
    if len(written) != total_chunks:
        db.rollback()
        missing = total_chunks - len(written)
        raise UploadProtocolError(409, f"{missing} chunk(s) not yet written -- retry once every chunk is confirmed")

    session.status = UploadSessionStatus.COMPLETING.value
    session.completion_attempt += 1
    session.last_activity_at = datetime.now(UTC)
    attempt_token = session.completion_attempt
    db.commit()
    return attempt_token


def assemble_and_validate(db: Session, session_id: uuid.UUID, attempt_token: int) -> Path:
    """Finalization step 1: assemble this attempt's own temp file from its accepted chunks and
    validate its hash against declared_sha256 -- entirely before any lock, since this is the slow
    step. On a hash mismatch the session is moved to 'failed' via a fenced update (not reverted to
    'uploading' -- the received bytes don't match what was declared, so retrying completion alone
    cannot fix it)."""
    session = db.get(AttachmentUploadSession, session_id)
    assembled_path = _assembly_temp_path(session_id, attempt_token)
    hasher = hashlib.sha256()
    with open(assembled_path, "wb") as out:
        for index in range(session.total_chunks):
            chunk_bytes = _chunk_accepted_path(session_id, index).read_bytes()
            hasher.update(chunk_bytes)
            out.write(chunk_bytes)
    if hasher.hexdigest() != session.declared_sha256:
        db.query(AttachmentUploadSession).filter(
            AttachmentUploadSession.id == session_id,
            AttachmentUploadSession.status == UploadSessionStatus.COMPLETING.value,
            AttachmentUploadSession.completion_attempt == attempt_token,
        ).update({"status": UploadSessionStatus.FAILED.value})
        db.commit()
        assembled_path.unlink(missing_ok=True)
        raise UploadProtocolError(422, "Assembled file does not match declared_sha256 -- upload failed")
    return assembled_path


def finalize_completion(
    db: Session, session_id: uuid.UUID, attempt_token: int, assembled_path: Path, current_user, request=None,
) -> Attachment:
    """Finalization steps 2-4: lock the session, re-check status='completing' AND the exact
    token, place the assembled file at its deterministic final path (an atomic rename -- cheap,
    since assembly already happened), then commit the Attachment row, the stage-advance
    transition and its audit entry (Section 8 case 9), and the fenced session update ALL
    TOGETHER, one transaction. A fence failure rolls back the whole transaction, including the
    Attachment insert and any stage/audit change -- the file already renamed to its final path is
    left on disk, unreferenced, and becomes cleanup's job, never the database's (Section 0.A,
    revision 7). request may be None (direct test callers that don't go through a real HTTP
    request) -- write_audit_log_entry already accepts that."""
    session = db.execute(
        select(AttachmentUploadSession).where(AttachmentUploadSession.id == session_id).with_for_update()
    ).scalar_one_or_none()
    if (
        session is None
        or session.status != UploadSessionStatus.COMPLETING.value
        or session.completion_attempt != attempt_token
    ):
        db.rollback()
        raise UploadProtocolError(409, "This completion attempt was superseded before it could finish")

    final_path = final_attachment_path(session.doc_type, session.doc_id, session.filename, session.id, attempt_token)
    os.replace(assembled_path, final_path)  # step 3 -- the file now exists at its final path

    from app.api.attachments import _advance_stage_if_applicable, _safe_filename
    from app.models.setting import DocumentType

    new_attachment = Attachment(
        id=uuid.uuid4(),
        doc_type=DocumentType(session.doc_type),
        doc_id=session.doc_id,
        original_filename=_safe_filename(session.filename),
        original_size=session.declared_size,
        original_sha256=session.declared_sha256,
        storage_path=str(final_path),
        tag=_default_tag_for_doc_type(session.doc_type),
        uploaded_by_id=current_user.id,
        version=1,
    )
    db.add(new_attachment)
    db.flush()  # this codebase's sessions run autoflush=False -- the raw UPDATE below references
    # new_attachment.id as a foreign key, so the INSERT must be flushed first or Postgres sees it
    # as not yet existing within this same transaction.
    updated = (
        db.query(AttachmentUploadSession)
        .filter(
            AttachmentUploadSession.id == session_id,
            AttachmentUploadSession.status == UploadSessionStatus.COMPLETING.value,
            AttachmentUploadSession.completion_attempt == attempt_token,
        )
        .update({"status": UploadSessionStatus.COMPLETED.value, "resulting_attachment_id": new_attachment.id})
    )
    if updated == 0:
        db.rollback()  # the file stays at final_path -- unreferenced, cleanup's job (below)
        raise UploadProtocolError(409, "This completion attempt was superseded before it could finish")

    # Same transaction, before the commit below -- a stage/audit failure here rolls back the
    # Attachment insert and the fenced session update too, never leaving one without the others.
    _advance_stage_if_applicable(db, DocumentType(session.doc_type), session.doc_id, current_user, request)

    db.commit()
    # step 5: only now, after the commit above has actually succeeded, clean up temp files.
    purge_session_temp_files(db, session_id)
    return new_attachment


def _default_tag_for_doc_type(doc_type: str):
    from app.models.attachment import AttachmentTag
    from app.models.setting import DocumentType

    if doc_type == DocumentType.PROJECT_STAGE.value:
        return AttachmentTag.PHOTO
    return AttachmentTag.REFERENCE


def purge_session_temp_files(db: Session, session_id: uuid.UUID) -> None:
    """Deletes the session's own temp chunk files and records temp_files_purged_at. Safe to
    retry -- deleting an already-deleted file is a no-op -- so cleanup's own retryable pass
    (below) can call this again later if the first call never finished."""
    temp_dir = _session_temp_dir(session_id)
    if temp_dir.exists():
        for f in temp_dir.iterdir():
            f.unlink(missing_ok=True)
    db.query(AttachmentUploadSession).filter(AttachmentUploadSession.id == session_id).update(
        {"temp_files_purged_at": datetime.now(UTC)}
    )
    db.commit()


# --- recovery: bumps the token atomically with the status reset (revision 7) ------------------


def recover_stuck_sessions(db: Session, now: datetime | None = None, dry_run: bool = False) -> int:
    """Revision 7 fix (Section 0.A): the token moves in the SAME statement as the status reset,
    with no gap where a stale worker's old token is still valid against a reclaimable session.
    Called two ways: proactively, as the first sweep of the cleanup cron (below), and lazily, by
    _recover_if_stuck, so a client's own retry doesn't have to wait for the next cron tick."""
    now = now or datetime.now(UTC)
    cutoff = now - RECOVERY_CUTOFF
    if dry_run:
        return (
            db.query(AttachmentUploadSession)
            .filter(
                AttachmentUploadSession.status == UploadSessionStatus.COMPLETING.value,
                AttachmentUploadSession.last_activity_at < cutoff,
            )
            .count()
        )
    result = db.execute(
        AttachmentUploadSession.__table__.update()
        .where(
            AttachmentUploadSession.status == UploadSessionStatus.COMPLETING.value,
            AttachmentUploadSession.last_activity_at < cutoff,
        )
        .values(status=UploadSessionStatus.UPLOADING.value, completion_attempt=AttachmentUploadSession.completion_attempt + 1)
    )
    db.commit()
    return result.rowcount or 0


def _recover_if_stuck(db: Session, session_id: uuid.UUID) -> None:
    """Lazy trigger: called at the top of claim_chunk and start_completion so a client's own
    retry recovers a stuck session immediately rather than waiting for the next cron tick. A
    single conditional UPDATE, cheap and a no-op when nothing matches."""
    db.execute(
        AttachmentUploadSession.__table__.update()
        .where(
            AttachmentUploadSession.id == session_id,
            AttachmentUploadSession.status == UploadSessionStatus.COMPLETING.value,
            AttachmentUploadSession.last_activity_at < datetime.now(UTC) - RECOVERY_CUTOFF,
        )
        .values(status=UploadSessionStatus.UPLOADING.value, completion_attempt=AttachmentUploadSession.completion_attempt + 1)
    )
    db.commit()


# --- cleanup: four sweeps, ops-scheduled (Section 4/6) -----------------------------------------


def claim_and_purge_abandoned_sessions(db: Session, now: datetime | None = None, dry_run: bool = False) -> int:
    """Sweep 1: an atomic claim -- a session that receives a chunk (touching last_activity_at)
    inside the cutoff window simply fails this WHERE clause; a chunk that somehow still arrives
    after the claim succeeds is refused by claim_chunk's own locked status='uploading' check,
    not silently accepted into a session about to vanish."""
    now = now or datetime.now(UTC)
    cutoff = now - ABANDONED_SESSION_CUTOFF
    claimed_ids = [
        row[0]
        for row in db.execute(
            select(AttachmentUploadSession.id).where(
                AttachmentUploadSession.status == UploadSessionStatus.UPLOADING.value,
                AttachmentUploadSession.last_activity_at < cutoff,
            )
        ).all()
    ]
    if not claimed_ids or dry_run:
        return len(claimed_ids)
    db.query(AttachmentUploadSession).filter(AttachmentUploadSession.id.in_(claimed_ids)).update(
        {"status": UploadSessionStatus.PURGING.value}, synchronize_session=False
    )
    db.commit()
    for session_id in claimed_ids:
        temp_dir = _session_temp_dir(session_id)
        if temp_dir.exists():
            for f in temp_dir.iterdir():
                f.unlink(missing_ok=True)
            temp_dir.rmdir()
        db.query(AttachmentUploadChunk).filter(AttachmentUploadChunk.session_id == session_id).delete()
        db.query(AttachmentUploadSession).filter(AttachmentUploadSession.id == session_id).delete()
        db.commit()
    return len(claimed_ids)


def purge_completed_session_temp_files(db: Session, dry_run: bool = False) -> int:
    """Sweep 2 (revision 4 fix, Section 0.C): a completed session is never permanently excluded
    from having its temp files swept -- retries deletion for any completed session where
    temp_files_purged_at is still NULL, safe because deleting an already-deleted file is a
    no-op. Never touches the session row, resulting_attachment_id, or the committed Attachment's
    own final-path file -- only the session's own temp chunk directory."""
    ids = [
        row[0]
        for row in db.execute(
            select(AttachmentUploadSession.id).where(
                AttachmentUploadSession.status == UploadSessionStatus.COMPLETED.value,
                AttachmentUploadSession.temp_files_purged_at.is_(None),
            )
        ).all()
    ]
    if not dry_run:
        for session_id in ids:
            purge_session_temp_files(db, session_id)
    return len(ids)


def sweep_orphaned_attempt_temp_files(db: Session, dry_run: bool = False) -> int:
    """Sweep 3 (revision 5 fix, Section 0.B): a chunk-write or assembly attempt superseded
    before it could promote leaves an attempt-specific temp file nothing will ever promote.
    Removes any such file whose embedded attempt number no longer matches its chunk row's or
    session's current value -- never touches an accepted/promoted file (those carry no attempt
    number in their own name at all)."""
    removed = 0
    root = Path(settings.attachment_storage_root) / "_upload_tmp"
    if not root.exists():
        return 0
    for session_dir in root.iterdir():
        if not session_dir.is_dir():
            continue
        try:
            session_id = uuid.UUID(session_dir.name)
        except ValueError:
            continue
        session = db.get(AttachmentUploadSession, session_id)
        if session is None:
            continue  # sweep 1 already deletes the dir alongside the row; nothing stale to find
        claimed_by_index = {
            c.chunk_index: c.claimed_attempt
            for c in db.query(AttachmentUploadChunk).filter(AttachmentUploadChunk.session_id == session_id).all()
        }
        for f in session_dir.iterdir():
            if f.name.startswith("chunk_") and f.name.endswith(".part"):
                # chunk_{index}.attempt_{n}.part
                try:
                    index_part, attempt_part = f.stem.split(".")
                    index = int(index_part.removeprefix("chunk_"))
                    attempt = int(attempt_part.removeprefix("attempt_"))
                except (ValueError, IndexError):
                    continue
                if claimed_by_index.get(index) != attempt:
                    if not dry_run:
                        f.unlink(missing_ok=True)
                    removed += 1
            elif f.name.startswith("assembled.attempt_") and f.name.endswith(".tmp"):
                try:
                    attempt = int(f.stem.removeprefix("assembled.attempt_"))
                except ValueError:
                    continue
                if attempt < session.completion_attempt:
                    if not dry_run:
                        f.unlink(missing_ok=True)
                    removed += 1
    return removed


def sweep_orphaned_final_path_files(db: Session, dry_run: bool = False) -> int:
    """Sweep 4 (revision 7, Section 0.A/0.B) -- v7's core deliverable, two guarantees kept
    explicit and conjunctive: a file is only ever removed here if (1) its attempt is irrevocably
    superseded -- N strictly less than the session's CURRENT completion_attempt, a value that can
    only ever increase, so this can never later become false again -- AND (2) a check run at the
    moment of deletion against `attachments` finds no row whose storage_path matches. Absence of
    a row is never sufficient alone: read before condition (1) holds it would only mean "not
    committed yet," not "never will be," and a live completion could still be seconds from
    committing it. This is the one path that can ever delete a final-path file, and it is
    structurally incapable of ever matching a committed Attachment's own file, because doing so
    requires first proving no Attachment row points at that exact path."""
    removed = 0
    sessions = db.query(AttachmentUploadSession).filter(AttachmentUploadSession.completion_attempt >= 1).all()
    for session in sessions:
        for attempt in range(1, session.completion_attempt):  # strictly less than current -- never the live one
            candidate = final_attachment_path(session.doc_type, session.doc_id, session.filename, session.id, attempt)
            if not candidate.exists():
                continue
            referenced = (
                db.query(Attachment.id).filter(Attachment.storage_path == str(candidate)).first() is not None
            )
            if not referenced:
                if not dry_run:
                    candidate.unlink(missing_ok=True)
                removed += 1
    return removed


def run_cleanup(db: Session, dry_run: bool = False) -> dict:
    """Recovery runs first (also triggered lazily, on-demand, by a client's own retry -- see
    _recover_if_stuck) so a stuck session becomes reclaimable before the later sweeps run.
    The one entry point the ops-scheduled script (scripts/cleanup_attachment_upload_sessions.py)
    calls -- matches this codebase's own established convention of a thin CLI wrapper around a
    pure app/core/ function taking a Session (send_daily_follow_up_reminders.py). Never touches a
    completed session's own row, resulting_attachment_id, or the file a committed Attachment's
    storage_path points at -- every sweep either targets a genuinely abandoned session (never
    completed) or a file nothing in `attachments` references."""
    return {
        "stuck_sessions_recovered": recover_stuck_sessions(db, dry_run=dry_run),
        "abandoned_sessions_purged": claim_and_purge_abandoned_sessions(db, dry_run=dry_run),
        "completed_sessions_temp_purged": purge_completed_session_temp_files(db, dry_run=dry_run),
        "orphaned_attempt_temp_files_removed": sweep_orphaned_attempt_temp_files(db, dry_run=dry_run),
        "orphaned_final_path_files_removed": sweep_orphaned_final_path_files(db, dry_run=dry_run),
    }
