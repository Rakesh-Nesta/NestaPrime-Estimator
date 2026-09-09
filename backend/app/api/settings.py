import uuid
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.api.audit_log import write_audit_log_entry
from app.core.auth import require_roles
from app.db.session import get_db
from app.models.setting import DocumentType, Override, Setting, SettingScope
from app.models.user import User

settings_router = APIRouter(prefix="/settings", tags=["settings"])
overrides_router = APIRouter(prefix="/overrides", tags=["overrides"])

# Q.2 rule 6: "Master Settings screen is Director-only (PM read-only)."
READ_ROLES = ("pm", "director")
WRITE_ROLES = ("director",)
# Overrides are logged by whoever is working the document -- PM/Director,
# consistent with every other cost-adjacent write in this build (K.3).
OVERRIDE_ROLES = ("pm", "director")


def get_current_setting_value(db: Session, key: str, scope_value: str | None = None) -> str | None:
    """The most recent version of `key` whose effective_from has arrived.
    Q.2 rule 1: editing a setting inserts a new version rather than
    mutating the old one, so this never changes what an already-frozen
    document read."""
    today = date.today()
    row = (
        db.query(Setting)
        .filter(Setting.key == key, Setting.scope_value == scope_value, Setting.effective_from <= today)
        .order_by(Setting.effective_from.desc(), Setting.created_at.desc())
        .first()
    )
    return row.value if row else None


def get_gst_rate_percent(db: Session, default: float = 18.0) -> float:
    """K.4: 'The GST rate itself (18%) is a Master Setting (Q.1), not
    hard-coded, in case it ever changes.' Falls back to the blueprint's
    own default when no Setting row exists yet (e.g. a fresh test DB)."""
    value = get_current_setting_value(db, "gst_rate_percent")
    return float(value) if value is not None else default


def get_internal_email_domains(db: Session) -> set[str]:
    """Q.1 Communications 'internal-domain list' -- the domains Cost
    Sheet/consumption-sheet/BOM messages (M.7.2 rule 7) may be emailed
    to. Unlike gst_rate_percent, there's no sensible universal default
    for a company's own email domain, so until the Director sets
    `internal_email_domains` explicitly (comma-separated) this falls
    back to the domains already in use by this installation's own USERS
    -- self-configuring from real data instead of a fabricated default,
    and still fail-closed (a domain nobody here has ever logged in from
    is never treated as internal)."""
    value = get_current_setting_value(db, "internal_email_domains")
    if value:
        return {domain.strip().lower() for domain in value.split(",") if domain.strip()}
    return {
        email.split("@", 1)[1].lower()
        for (email,) in db.query(User.email).all()
        if "@" in email
    }


class SettingOut(BaseModel):
    id: uuid.UUID
    key: str
    scope: SettingScope
    scope_value: str | None
    value: str
    unit: str | None
    effective_from: date
    changed_by_id: uuid.UUID
    reason: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


@settings_router.get("", response_model=list[SettingOut])
def list_current_settings(
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*READ_ROLES)),
):
    """One row per (key, scope_value): its currently-effective version."""
    today = date.today()
    all_rows = (
        db.query(Setting)
        .filter(Setting.effective_from <= today)
        .order_by(Setting.key, Setting.scope_value, Setting.effective_from.desc(), Setting.created_at.desc())
        .all()
    )
    seen: set[tuple[str, str | None]] = set()
    current: list[Setting] = []
    for row in all_rows:
        identity = (row.key, row.scope_value)
        if identity in seen:
            continue
        seen.add(identity)
        current.append(row)
    return current


@settings_router.get("/{key}/history", response_model=list[SettingOut])
def get_setting_history(
    key: str,
    scope_value: str | None = None,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*READ_ROLES)),
):
    rows = (
        db.query(Setting)
        .filter(Setting.key == key, Setting.scope_value == scope_value)
        .order_by(Setting.effective_from.desc(), Setting.created_at.desc())
        .all()
    )
    if not rows:
        raise HTTPException(status_code=404, detail="No such setting")
    return rows


class SettingCreate(BaseModel):
    key: str
    scope: SettingScope = SettingScope.GLOBAL
    scope_value: str | None = None
    value: str
    unit: str | None = None
    effective_from: date | None = None
    reason: str | None = None


@settings_router.post("", response_model=SettingOut, status_code=201)
def create_setting_version(
    payload: SettingCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*WRITE_ROLES)),
):
    """Q.2 rule 1: 'editing' a Master Setting is really creating a new
    version, effective from a given date -- Director only."""
    old_value = get_current_setting_value(db, payload.key, payload.scope_value)
    setting = Setting(
        key=payload.key,
        scope=payload.scope,
        scope_value=payload.scope_value,
        value=payload.value,
        unit=payload.unit,
        effective_from=payload.effective_from or date.today(),
        changed_by_id=current_user.id,
        reason=payload.reason,
    )
    db.add(setting)
    db.flush()

    # Q.2 rule 7: "Settings changes are in the audit log (M.5)."
    write_audit_log_entry(
        db, current_user, "setting", setting.id, payload.key,
        old_value=old_value, new_value=payload.value, reason=payload.reason, request=request,
    )

    db.commit()
    db.refresh(setting)
    return setting


class BulkUpdateRequest(BaseModel):
    key_prefix: str
    percent_change: float  # e.g. 6.0 for "+6%", -5.0 for "-5%"
    effective_from: date | None = None
    reason: str


@settings_router.post("/bulk-update", response_model=list[SettingOut])
def bulk_update_settings(
    payload: BulkUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*WRITE_ROLES)),
):
    """Q.2 rule 5: 'Director can apply a % change to a whole category
    (e.g. "steel +6%") with one action and an effective date.' A
    'category' here is every setting whose key starts with key_prefix;
    each gets its own new version, same effective_from and reason."""
    today = date.today()
    all_rows = (
        db.query(Setting)
        .filter(Setting.key.like(f"{payload.key_prefix}%"), Setting.effective_from <= today)
        .order_by(Setting.key, Setting.scope_value, Setting.effective_from.desc(), Setting.created_at.desc())
        .all()
    )
    seen: set[tuple[str, str | None]] = set()
    current: list[Setting] = []
    for row in all_rows:
        identity = (row.key, row.scope_value)
        if identity in seen:
            continue
        seen.add(identity)
        current.append(row)

    if not current:
        raise HTTPException(status_code=404, detail=f"No settings found with key prefix '{payload.key_prefix}'")

    effective_from = payload.effective_from or date.today()
    new_versions = []
    for row in current:
        try:
            new_value = float(row.value) * (1 + payload.percent_change / 100)
        except ValueError:
            continue  # non-numeric setting values aren't bulk-adjustable
        new_setting = Setting(
            key=row.key,
            scope=row.scope,
            scope_value=row.scope_value,
            value=str(round(new_value, 4)),
            unit=row.unit,
            effective_from=effective_from,
            changed_by_id=current_user.id,
            reason=payload.reason,
        )
        db.add(new_setting)
        db.flush()
        new_versions.append(new_setting)

        # Q.2 rule 7: "Settings changes are in the audit log (M.5)."
        write_audit_log_entry(
            db, current_user, "setting", new_setting.id, row.key,
            old_value=row.value, new_value=new_setting.value, reason=payload.reason, request=request,
        )

    db.commit()
    for v in new_versions:
        db.refresh(v)
    return new_versions


# --------------------------------------------------------------------------
# Overrides (Part O OVERRIDES / Q.2 rule 2)
# --------------------------------------------------------------------------


class OverrideCreate(BaseModel):
    document_type: DocumentType
    document_id: uuid.UUID
    setting_key: str
    master_value: str
    override_value: str
    reason: str = Field(min_length=1)


class OverrideOut(BaseModel):
    id: uuid.UUID
    document_type: DocumentType
    document_id: uuid.UUID
    setting_key: str
    master_value: str
    override_value: str
    reason: str
    user_id: uuid.UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


@overrides_router.post("", response_model=OverrideOut, status_code=201)
def create_override(
    payload: OverrideCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*OVERRIDE_ROLES)),
):
    override = Override(
        document_type=payload.document_type,
        document_id=payload.document_id,
        setting_key=payload.setting_key,
        master_value=payload.master_value,
        override_value=payload.override_value,
        reason=payload.reason,
        user_id=current_user.id,
    )
    db.add(override)
    db.commit()
    db.refresh(override)
    return override


@overrides_router.get("", response_model=list[OverrideOut])
def list_overrides(
    document_type: DocumentType,
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*OVERRIDE_ROLES)),
):
    return (
        db.query(Override)
        .filter(Override.document_type == document_type, Override.document_id == document_id)
        .order_by(Override.created_at.desc())
        .all()
    )
