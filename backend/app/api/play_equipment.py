import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.documents import CostSheetLineOut, _line_to_out
from app.api.site_works import _get_cost_sheet
from app.core.auth import require_roles
from app.db.session import get_db
from app.models.document import CostSheet, CostSheetLine, WorkPackage
from app.models.rate_item import RateSource
from app.models.sport import ProjectSport

play_equipment_router = APIRouter(tags=["play-equipment"])

COST_ROLES = ("pm", "director")

SQFT_TO_SQM = 0.09290304

# G.4: "footprint + 6 ft fall zone each side" (the kids_play_area sport's
# own build-dims rule, C.2) -- the only fall-zone figure the blueprint
# gives anywhere, so it's applied uniformly to every equipment type
# (multi-play unit, swings, slides, see-saw, climbers, spring riders).
# Real playground standards (ASTM F1487/EN 1176, which IS 15650 broadly
# follows) actually vary this by equipment type -- swings need more
# clearance in the swing direction than static climbers -- but the
# blueprint names only this one number, so that variation isn't modelled;
# overridable per item rather than guessed differently per type.
DEFAULT_FALL_ZONE_FT = 6.0

# F.2's own worked figure for the 40mm EPDM system (10mm EPDM wearing +
# 30mm SBR base): "CFH 1.5 m" -- critical fall height, the equipment
# height this surfacing is rated to protect against. Used only for the
# informational IS 15650 compliance note G.4 asks for, not to price
# anything.
EPDM_40MM_CFH_M = 1.5


def _get_project_sport(db: Session, cost_sheet: CostSheet, project_sport_id: uuid.UUID) -> ProjectSport:
    project_sport = (
        db.query(ProjectSport)
        .filter(ProjectSport.id == project_sport_id, ProjectSport.project_id == cost_sheet.project_id)
        .first()
    )
    if not project_sport:
        raise HTTPException(status_code=404, detail="Sport selection not on this project")
    return project_sport


class PlayEquipmentItemIn(BaseModel):
    item_name: str = Field(min_length=1)  # e.g. "Multi-play unit", "Swing set", "Slide", "See-saw", "Climber", "Spring rider"
    footprint_l_ft: float = Field(gt=0)
    footprint_w_ft: float = Field(gt=0)
    fall_zone_ft: float = Field(default=DEFAULT_FALL_ZONE_FT, gt=0)
    equipment_height_m: float | None = Field(default=None, gt=0)  # for the CFH compliance note only
    equipment_rate: float = Field(gt=0)  # supply & install, lump sum
    epdm_rate_per_sqm: float = Field(gt=0)


class PlayEquipmentTakeoffRequest(BaseModel):
    project_sport_id: uuid.UUID
    items: list[PlayEquipmentItemIn] = Field(min_length=1)


class PlayEquipmentTakeoffOut(BaseModel):
    breakdown: dict
    lines: list[CostSheetLineOut]


@play_equipment_router.post(
    "/cost-sheets/{cost_sheet_id}/play-equipment", response_model=PlayEquipmentTakeoffOut, status_code=201
)
def add_play_equipment_takeoff(
    cost_sheet_id: uuid.UUID,
    payload: PlayEquipmentTakeoffRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*COST_ROLES)),
):
    """G.4: each named piece of equipment (multi-play unit, swings,
    slides, see-saw, climbers, spring riders) gets its own footprint x
    fall-zone -> EPDM area auto-calc, plus its own supply & install line.
    The IS 15650 compliance note compares the equipment's own height (if
    given) against the 40mm EPDM system's real CFH rating (1.5 m, F.2) --
    reported, not priced, since the blueprint gives no cost basis for
    non-compliance itself."""
    cost_sheet = _get_cost_sheet(db, cost_sheet_id)
    _get_project_sport(db, cost_sheet, payload.project_sport_id)

    lines_to_create: list[CostSheetLine] = []
    item_breakdowns = []
    total_epdm_area_sqm = 0.0

    for item in payload.items:
        expanded_l_ft = item.footprint_l_ft + 2 * item.fall_zone_ft
        expanded_w_ft = item.footprint_w_ft + 2 * item.fall_zone_ft
        epdm_area_sqm = expanded_l_ft * expanded_w_ft * SQFT_TO_SQM
        total_epdm_area_sqm += epdm_area_sqm

        compliant = None
        if item.equipment_height_m is not None:
            compliant = item.equipment_height_m <= EPDM_40MM_CFH_M

        item_breakdowns.append(
            {
                "item_name": item.item_name,
                "footprint_sqft": round(item.footprint_l_ft * item.footprint_w_ft, 2),
                "fall_zone_ft": item.fall_zone_ft,
                "epdm_area_sqm": round(epdm_area_sqm, 2),
                "equipment_height_m": item.equipment_height_m,
                "epdm_40mm_cfh_m": EPDM_40MM_CFH_M,
                "is_15650_compliant": compliant,
                "note": (
                    "40mm EPDM system (10mm wearing + 30mm SBR base) is rated to CFH 1.5m (F.2); "
                    + (
                        "equipment height not supplied, so compliance isn't checked."
                        if compliant is None
                        else "equipment height is within the rated CFH."
                        if compliant
                        else "equipment height EXCEEDS the rated CFH -- a thicker system or deeper base is needed."
                    )
                ),
            }
        )

        lines_to_create.append(
            CostSheetLine(
                cost_sheet_id=cost_sheet_id,
                project_sport_id=payload.project_sport_id,
                work_package=WorkPackage.ACCESSORIES,
                category="Kids play equipment",
                item_name=f"{item.item_name} (supply & install)",
                unit="set",
                quantity=1,
                rate=item.equipment_rate,
                source=RateSource.MANUAL,
            )
        )
        lines_to_create.append(
            CostSheetLine(
                cost_sheet_id=cost_sheet_id,
                project_sport_id=payload.project_sport_id,
                work_package=WorkPackage.FLOORING,
                category="Kids play equipment",
                item_name=f"{item.item_name} EPDM safety surfacing",
                unit="sqm",
                quantity=round(epdm_area_sqm, 2),
                rate=item.epdm_rate_per_sqm,
                source=RateSource.MANUAL,
            )
        )

    for line in lines_to_create:
        db.add(line)
    db.commit()
    for line in lines_to_create:
        db.refresh(line)

    return PlayEquipmentTakeoffOut(
        breakdown={"items": item_breakdowns, "total_epdm_area_sqm": round(total_epdm_area_sqm, 2)},
        lines=[_line_to_out(line) for line in lines_to_create],
    )
