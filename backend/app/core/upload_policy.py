"""One upload policy for every way a file can enter the system: ordinary upload, supersede, and resumable
(chunked) completion -- including resumable sessions that were opened before this policy existed.

Four concerns live here so the three paths cannot drift apart again:

  1. FILE POLICY    -- safe filename, the blocked-extension deny-list, and an allow-list of supported business
                       formats (anything else is refused with 415).
  2. CONTENT        -- a file must actually look like what its extension says (signature check). A renamed HTML or
                       executable never passes as a PDF. Then an optional malware-scanner hook (fail closed), with
                       quarantine for anything flagged.
  3. LIMITS         -- chunk size and chunk count, open sessions and declared bytes per user, and a global storage
                       cap, enforced under ONE Postgres advisory transaction lock so concurrent requests cannot
                       jointly exceed them (a count-then-insert without the lock is a race).
  4. DOWNLOAD       -- the headers that make a stored file inert in a browser. Stored bytes are never modified, so a
                       signed original is served exactly as it was uploaded.

The numeric limits are PROPOSED policy values pending business acceptance; each is a module constant (the storage cap
is a setting) so changing one is a one-line change."""

import logging
import re
import shlex
import subprocess
import uuid
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.config import settings
from app.core.upload_validators import VALIDATORS

log = logging.getLogger("upload_policy")

MAX_FILE_SIZE_BYTES = 100 * 1024 * 1024  # M.3: "max 100 MB each"
MAX_STORED_FILENAME_LENGTH = 150

# --- proposed limits -----------------------------------------------------------------------------------------------
MIN_CHUNK_BYTES = 64 * 1024  # a session of more than one chunk must use chunks at least this large
MAX_CHUNK_BYTES = 16 * 1024 * 1024  # every chunk body is held in memory, so it is capped
MAX_TOTAL_CHUNKS = 2048
MAX_OPEN_SESSIONS_PER_USER = 10
MAX_OPEN_DECLARED_BYTES_PER_USER = 500 * 1024 * 1024
BODY_OVERHEAD_BYTES = 1024 * 1024  # multipart framing allowance on top of a file/chunk limit
READ_PIECE_BYTES = 1024 * 1024

_QUOTA_LOCK_KEY = 0x4E50_5550_4C4F_4144  # arbitrary constant: "NPUPLOAD"

# Types that can run, or that a browser renders as a page, are never attachments (Amendment 58 item 8).
BLOCKED_ATTACHMENT_EXTENSIONS = frozenset(
    {".html", ".htm", ".xhtml", ".svg", ".js", ".mjs", ".exe", ".msi", ".bat", ".cmd", ".com",
     ".scr", ".ps1", ".sh", ".jar", ".php", ".py", ".vbs", ".dll", ".lnk"}
)


class PolicyViolation(Exception):
    """A refusal with the HTTP status and the reason to show. Callers translate it to their own error type."""

    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


# --- 1. filename / extension ---------------------------------------------------------------------------------------


def safe_filename(raw_name: str | None) -> str:
    """The name kept for an upload: no folders (either slash style), no control or shell-special characters, never
    empty, length capped with the extension kept."""
    name = (raw_name or "").replace("\\", "/").split("/")[-1]
    name = re.sub(r'[\x00-\x1f\x7f<>:"|?*]', "", name).strip(" .")
    if not name:
        return "upload"
    if len(name) > MAX_STORED_FILENAME_LENGTH:
        stem, dot, extension = name.rpartition(".")
        if dot and 0 < len(extension) <= 10:
            name = stem[: MAX_STORED_FILENAME_LENGTH - len(extension) - 1] + "." + extension
        else:
            name = name[:MAX_STORED_FILENAME_LENGTH]
    return name


def check_filename(raw_name: str | None) -> str:
    """The single filename policy. Returns the safe stored name, or raises PolicyViolation.
    400 = a type that must never be attached; 415 = a type that is not a supported business format."""
    name = safe_filename(raw_name)
    extension = Path(name).suffix.lower()
    if extension in BLOCKED_ATTACHMENT_EXTENSIONS:
        raise PolicyViolation(
            400,
            f"Files of type {extension} can't be attached because they can run or open as a web page -- "
            "send a PDF or an image instead",
        )
    if extension not in SUPPORTED_EXTENSIONS:
        raise PolicyViolation(
            415,
            f"Files of type {extension or '(no extension)'} aren't a supported attachment format -- supported: "
            + ", ".join(sorted(SUPPORTED_EXTENSIONS)),
        )
    return name


# --- 2. content ----------------------------------------------------------------------------------------------------

SUPPORTED_EXTENSIONS = frozenset(VALIDATORS)  # the allow-list IS the set of formats that have a structural validator

_MEDIA_TYPES = {
    ".pdf": "application/pdf", ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".gif": "image/gif", ".webp": "image/webp", ".bmp": "image/bmp", ".tif": "image/tiff", ".tiff": "image/tiff",
    ".heic": "image/heic", ".mp4": "video/mp4", ".mov": "video/quicktime", ".m4v": "video/x-m4v",
    ".txt": "text/plain; charset=utf-8", ".csv": "text/csv; charset=utf-8",
}


def validate_content(path: Path, filename: str) -> None:
    """The file must be a COMPLETE, well-formed file of the type its extension claims -- parsed, not merely
    header-matched (see app/core/upload_validators.py for exactly what each format is held to).
    Raises PolicyViolation(415)."""
    extension = Path(filename).suffix.lower()
    validator = VALIDATORS.get(extension)
    if validator is None:
        raise PolicyViolation(415, f"Files of type {extension or '(no extension)'} aren't a supported attachment format")
    try:
        if path.stat().st_size == 0:
            raise ValueError("the file is empty")
        validator(path)
    except ValueError as exc:
        raise PolicyViolation(415, f"The file is not a valid {extension} file ({exc}) -- it was not accepted")
    except Exception as exc:  # noqa: BLE001 - a parser crashing on hostile input is a refusal, never a 500
        log.warning("validator crashed for %s: %r", extension, exc)
        raise PolicyViolation(415, f"The file is not a valid {extension} file -- it was not accepted")


def scan_file(path: Path) -> None:
    """Optional malware-scanner hook: settings.upload_scan_command is run as `<command> <path>` -- exit 0 = clean,
    1 = infected (quarantined and refused, 422), anything else, a timeout or a missing binary = the scanner failed,
    so the upload is refused (503): FAIL CLOSED. With no command configured the scan is skipped unless
    settings.upload_scan_required is true, in which case every upload is refused until a scanner is configured."""
    command = (settings.upload_scan_command or "").strip()
    if not command:
        if settings.upload_scan_required:
            raise PolicyViolation(503, "Uploads are paused: a malware scanner is required but not configured")
        # NOT scanned is not the same as clean: the file is accepted on structural validation alone, and that is logged.
        log.warning("upload accepted but not malware-scanned (no scanner configured): %s", path.name)
        return
    try:
        result = subprocess.run(
            [*shlex.split(command), str(path)], capture_output=True, timeout=settings.upload_scan_timeout_seconds, check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        log.error("upload scanner failed to run: %s", exc)
        raise PolicyViolation(503, "The malware scan could not be completed -- the upload was not accepted; try again later")
    if result.returncode == 0:
        return
    if result.returncode == 1:
        raise PolicyViolation(422, "The file was flagged by the malware scan and has been quarantined")
    log.error("upload scanner returned %s", result.returncode)
    raise PolicyViolation(503, "The malware scan could not be completed -- the upload was not accepted; try again later")


def quarantine_dir() -> Path:
    return Path(settings.attachment_storage_root) / "_quarantine"


def quarantine(path: Path, reason: str) -> Path:
    """Move a flagged file out of every servable location. Nothing in the app ever serves from _quarantine."""
    target_dir = quarantine_dir()
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{datetime.now(UTC):%Y%m%dT%H%M%S}_{uuid.uuid4().hex[:8]}.quarantined"
    path.replace(target)
    log.warning("upload quarantined: %s (%s)", target.name, reason)
    return target


def inspect_file(path: Path, filename: str) -> None:
    """Content signature, then scanner. A scanner verdict of 'infected' quarantines the file. The caller removes the
    file on any other refusal."""
    validate_content(path, filename)
    try:
        scan_file(path)
    except PolicyViolation as violation:
        if violation.status_code == 422 and path.exists():
            quarantine(path, violation.detail)
        raise


# --- 3. limits (atomic) --------------------------------------------------------------------------------------------


def validate_chunking(declared_size: int, chunk_size: int) -> int:
    """Returns total_chunks, or raises PolicyViolation(422)."""
    if chunk_size <= 0:
        raise PolicyViolation(422, "chunk_size must be positive")
    if chunk_size > MAX_CHUNK_BYTES:
        raise PolicyViolation(422, f"chunk_size must be at most {MAX_CHUNK_BYTES // (1024 * 1024)} MiB")
    if chunk_size < MIN_CHUNK_BYTES and declared_size > chunk_size:
        raise PolicyViolation(422, f"chunk_size must be at least {MIN_CHUNK_BYTES // 1024} KiB for a multi-chunk upload")
    total = (declared_size + chunk_size - 1) // chunk_size
    if total > MAX_TOTAL_CHUNKS:
        raise PolicyViolation(422, f"chunk_size too small: the upload would need {total} chunks (limit {MAX_TOTAL_CHUNKS})")
    return total


def lock_quota(db: Session) -> None:
    """Serialize every quota decision. Held until the caller's commit/rollback (a transaction-level lock), so the
    count-then-insert that follows cannot interleave with another request's."""
    db.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": _QUOTA_LOCK_KEY})


def _open_declared(db: Session):
    from app.models.attachment_upload_session import AttachmentUploadSession as S

    return S.status.in_(("uploading", "completing")), S


def enforce_open_session_limits(db: Session, user_id: uuid.UUID, declared_size: int) -> None:
    """Call AFTER lock_quota(). 429 when the user already has too many open sessions or declared bytes."""
    cond, S = _open_declared(db)
    count, declared = db.execute(
        select(func.count(), func.coalesce(func.sum(S.declared_size), 0)).where(cond, S.created_by_id == user_id)
    ).one()
    if count >= MAX_OPEN_SESSIONS_PER_USER:
        raise PolicyViolation(
            429, f"Too many open upload sessions (limit {MAX_OPEN_SESSIONS_PER_USER}) -- finish or wait for the "
            "abandoned ones to expire",
        )
    if declared + declared_size > MAX_OPEN_DECLARED_BYTES_PER_USER:
        raise PolicyViolation(
            429, f"Open uploads would exceed the {MAX_OPEN_DECLARED_BYTES_PER_USER // (1024 * 1024)} MiB declared "
            "bytes limit per user -- finish the current uploads first",
        )


def enforce_storage_cap(db: Session, extra_bytes: int) -> None:
    """Call AFTER lock_quota(). 413 when stored attachments plus open declarations plus this file exceed the cap."""
    cap = settings.attachment_storage_cap_bytes
    if not cap or cap <= 0:
        return
    from app.models.attachment import Attachment

    cond, S = _open_declared(db)
    stored = db.execute(select(func.coalesce(func.sum(Attachment.original_size), 0))).scalar() or 0
    open_declared = db.execute(select(func.coalesce(func.sum(S.declared_size), 0)).where(cond)).scalar() or 0
    if stored + open_declared + extra_bytes > cap:
        raise PolicyViolation(413, "File storage is full -- this upload was not accepted; contact an administrator")


def storage_health(db: Session) -> dict:
    """Numbers for monitoring (printed by the cleanup script's --report)."""
    from app.models.attachment import Attachment

    cond, S = _open_declared(db)
    open_count, open_bytes, oldest = db.execute(
        select(func.count(), func.coalesce(func.sum(S.declared_size), 0), func.min(S.created_at)).where(cond)
    ).one()
    stored = db.execute(select(func.coalesce(func.sum(Attachment.original_size), 0))).scalar() or 0
    quarantined = len(list(quarantine_dir().glob("*.quarantined"))) if quarantine_dir().exists() else 0
    if settings.upload_scan_command.strip():
        scanner = "active"
    elif settings.upload_scan_required:
        scanner = "required-but-not-configured-uploads-refused"
    else:
        scanner = "disabled-uploads-are-not-scanned"
    return {
        "scanner": scanner,
        "open_sessions": open_count,
        "open_declared_bytes": int(open_bytes),
        "oldest_open_session_at": oldest.isoformat() if oldest else None,
        "stored_attachment_bytes": int(stored),
        "storage_cap_bytes": settings.attachment_storage_cap_bytes,
        "quarantined_files": quarantined,
    }


# --- 4. download ---------------------------------------------------------------------------------------------------


def download_headers() -> dict:
    return {
        "X-Content-Type-Options": "nosniff",
        "Content-Security-Policy": "default-src 'none'; sandbox",
        "Cache-Control": "private, no-store",
    }


def download_media_type(filename: str) -> str:
    return _MEDIA_TYPES.get(Path(filename).suffix.lower(), "application/octet-stream")
