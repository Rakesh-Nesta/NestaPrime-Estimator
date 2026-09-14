from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.audit_log import write_audit_log_entry
from app.core.auth import require_roles
from app.db.session import get_db
from app.models.field_setting import FieldSetting, FieldSettingState

field_settings_router = APIRouter(prefix="/field-settings", tags=["field-settings"])

# Amendment 5 Phase 2 (Section 6): read access matches whoever can
# actually create a project (New Project Setup needs these to know what
# to show) -- a narrower gate than Master Settings' own PM-read/
# Director-write split, since this isn't the admin screen itself, just
# the data it manages. Write stays Director-only, same as every other
# Master Settings row (Q.2 rule 6).
READ_ROLES = ("sales", "pm", "director")
WRITE_ROLES = ("director",)

# The only field_keys this wave governs -- see Section-6-phase2-specs.md
# for why exactly these five (soil type/distance/court count/site
# access/power, all named by Amendment 2 itself as T&C candidates) and
# not e.g. building_status (one of Amendment 2's own "kept 5") or
# water_available (boolean, doesn't fit the None-option model).
GOVERNED_FIELD_KEYS = ("soil_type", "distance_km", "number_of_courts", "site_access", "power_available")


class FieldSettingUpdate(BaseModel):
    state: FieldSettingState


class FieldSettingOut(BaseModel):
    field_key: str
    state: FieldSettingState


def get_field_state(db: Session, field_key: str) -> FieldSettingState:
    """A governed field with no row yet is COMPULSORY -- today's actual
    behavior, unchanged until a Director deliberately opts it down."""
    row = db.query(FieldSetting).filter(FieldSetting.field_key == field_key).first()
    return row.state if row else FieldSettingState.COMPULSORY


@field_settings_router.get("", response_model=list[FieldSettingOut])
def list_field_settings(
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*READ_ROLES)),
):
    return [FieldSettingOut(field_key=key, state=get_field_state(db, key)) for key in GOVERNED_FIELD_KEYS]


@field_settings_router.patch("/{field_key}", response_model=FieldSettingOut)
def update_field_setting(
    field_key: str,
    payload: FieldSettingUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*WRITE_ROLES)),
):
    if field_key not in GOVERNED_FIELD_KEYS:
        raise HTTPException(status_code=404, detail=f"'{field_key}' is not a field this app governs")

    row = db.query(FieldSetting).filter(FieldSetting.field_key == field_key).first()
    old_state = row.state.value if row else FieldSettingState.COMPULSORY.value
    if row is None:
        row = FieldSetting(field_key=field_key, state=payload.state)
        db.add(row)
    else:
        row.state = payload.state

    if old_state != payload.state.value:
        write_audit_log_entry(
            db, current_user, "field_setting", None, field_key,
            old_value=old_state, new_value=payload.state.value, request=request,
        )

    db.commit()
    db.refresh(row)
    return FieldSettingOut(field_key=row.field_key, state=row.state)
