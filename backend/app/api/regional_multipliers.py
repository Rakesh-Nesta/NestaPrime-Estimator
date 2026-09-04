from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.core.auth import require_roles
from app.db.session import get_db
from app.models.regional_multiplier import RegionalMultiplier

router = APIRouter(prefix="/regional-multipliers", tags=["regional-multipliers"])


class RegionalMultiplierOut(BaseModel):
    city: str
    labour_multiplier: float
    transport_multiplier: float
    material_multiplier: float
    climate_zone: str
    rainfall_zone: str
    coastal: bool
    wind_zone: str
    seismic_zone: str
    is_confirmed: bool

    model_config = ConfigDict(from_attributes=True)


@router.get("", response_model=list[RegionalMultiplierOut])
def list_regional_multipliers(
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("sales", "pm", "director")),
):
    """Read-only — B.1's city dropdown reads this to show the auto-effect
    preview (Q.1: Director-only to edit; this endpoint is deliberately
    read-only for everyone else)."""
    return db.query(RegionalMultiplier).order_by(RegionalMultiplier.city).all()
