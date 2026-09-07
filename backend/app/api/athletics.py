import math
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.documents import CostSheetLineOut, _line_to_out
from app.api.site_works import _get_cost_sheet, _labour_category
from app.core.auth import require_roles
from app.db.session import get_db
from app.models.document import CostSheet, CostSheetLine, WorkPackage
from app.models.rate_item import RateSource
from app.models.sport import ProjectSport

athletics_router = APIRouter(tags=["athletics"])

COST_ROLES = ("pm", "director")

# G.3: "Lanes (4/6/8) x 1.22 m -> track width." World Athletics' own
# standard 400m/8-lane geometry: straight 84.39 m, raised kerb radius
# 36.5 m. The official 400m race distance is measured on a line 30 cm
# outside the physical kerb (radius 36.8 m): 2x84.39 + 2*pi*36.8 =~
# 400.0 m. The kerb itself -- what curbing material is actually ordered
# to -- is shorter, at the 36.5 m radius: 2x84.39 + 2*pi*36.5 =~ 398.1 m,
# the figure this module computes as kerb_length_m. These are the real
# World Athletics reference dimensions, not an invented default -- used
# unless the caller overrides them for a non-standard (e.g. school
# 200/250 m) oval, which the blueprint gives no formula for at all.
LANE_WIDTH_M = 1.22
STANDARD_INNER_RADIUS_M = 36.5
STANDARD_STRAIGHT_LENGTH_M = 84.39


def _get_project_sport(db: Session, cost_sheet: CostSheet, project_sport_id: uuid.UUID) -> ProjectSport:
    project_sport = (
        db.query(ProjectSport)
        .filter(ProjectSport.id == project_sport_id, ProjectSport.project_id == cost_sheet.project_id)
        .first()
    )
    if not project_sport:
        raise HTTPException(status_code=404, detail="Sport selection not on this project")
    return project_sport


class FieldEventIn(BaseModel):
    event_name: str = Field(min_length=1)  # e.g. "Long jump pit", "Shot put circle", "Discus cage", "High jump"
    rate: float = Field(gt=0)  # supply & install lump sum


class AthleticsTakeoffRequest(BaseModel):
    project_sport_id: uuid.UUID
    lanes: int = Field(gt=0, le=12)
    inner_radius_m: float = Field(default=STANDARD_INNER_RADIUS_M, gt=0)
    straight_length_m: float = Field(default=STANDARD_STRAIGHT_LENGTH_M, gt=0)
    track_surface_rate_per_sqm: float = Field(gt=0)
    kerb_rate_per_m: float = Field(gt=0)
    drainage_rate_per_m: float = Field(gt=0)
    field_events: list[FieldEventIn] = Field(default_factory=list)  # G.3: "field events checklist"


class AthleticsTakeoffOut(BaseModel):
    breakdown: dict
    lines: list[CostSheetLineOut]


@athletics_router.post("/cost-sheets/{cost_sheet_id}/athletics", response_model=AthleticsTakeoffOut, status_code=201)
def add_athletics_takeoff(
    cost_sheet_id: uuid.UUID,
    payload: AthleticsTakeoffRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*COST_ROLES)),
):
    """G.3: an oval track is two straights plus two semicircular curves
    (the two curves combine into one full circle/annulus). track_width =
    lanes x 1.22m; the kerb is the raised inner edge (perimeter at
    inner_radius); the drainage ring runs the outer perimeter (at
    inner_radius + track_width); the synthetic surface area is the two
    straight bands plus the curved annulus between inner and outer
    radius. D-zone area (the two curved 'D'-shaped end regions, which
    together form a circle of the inner radius) is reported for infield
    layout only -- the blueprint gives no cost basis for it, so no line
    is fabricated for it. Field events are a genuine checklist (blueprint's
    own word): named, optionally selected, priced as a flat supply &
    install line each -- the blueprint gives no pit/circle/cage
    dimensions to compute instead."""
    cost_sheet = _get_cost_sheet(db, cost_sheet_id)
    project_sport = _get_project_sport(db, cost_sheet, payload.project_sport_id)

    track_width_m = payload.lanes * LANE_WIDTH_M
    inner_r = payload.inner_radius_m
    outer_r = inner_r + track_width_m
    straight = payload.straight_length_m

    kerb_length_m = 2 * straight + 2 * math.pi * inner_r
    outer_perimeter_m = 2 * straight + 2 * math.pi * outer_r
    track_surface_area_sqm = 2 * straight * track_width_m + math.pi * (outer_r**2 - inner_r**2)
    d_zone_area_sqm = math.pi * inner_r**2  # the two curved ends combined = one circle at the kerb radius

    civil_category = _labour_category(db, "civil_base_site_prep")

    lines_to_create = [
        CostSheetLine(
            cost_sheet_id=cost_sheet_id,
            project_sport_id=payload.project_sport_id,
            work_package=WorkPackage.FLOORING,
            category="Athletic track",
            item_name=f"Synthetic track surface ({payload.lanes} lanes)",
            unit="sqm",
            quantity=round(track_surface_area_sqm, 2),
            rate=payload.track_surface_rate_per_sqm,
            source=RateSource.MANUAL,
        ),
        CostSheetLine(
            cost_sheet_id=cost_sheet_id,
            project_sport_id=payload.project_sport_id,
            work_package=WorkPackage.CIVIL,
            category="Athletic track",
            item_name="Track kerb (edging)",
            unit="m",
            quantity=round(kerb_length_m, 2),
            rate=payload.kerb_rate_per_m,
            source=RateSource.MANUAL,
            labour_category_id=civil_category.id if civil_category else None,
        ),
        CostSheetLine(
            cost_sheet_id=cost_sheet_id,
            project_sport_id=payload.project_sport_id,
            work_package=WorkPackage.CIVIL,
            category="Athletic track",
            item_name="Drainage ring (perimeter channel)",
            unit="m",
            quantity=round(outer_perimeter_m, 2),
            rate=payload.drainage_rate_per_m,
            source=RateSource.MANUAL,
            labour_category_id=civil_category.id if civil_category else None,
        ),
    ]

    for event in payload.field_events:
        lines_to_create.append(
            CostSheetLine(
                cost_sheet_id=cost_sheet_id,
                project_sport_id=payload.project_sport_id,
                work_package=WorkPackage.ACCESSORIES,
                category="Athletic track",
                item_name=f"{event.event_name} (supply & install)",
                unit="set",
                quantity=1,
                rate=event.rate,
                source=RateSource.MANUAL,
            )
        )

    for line in lines_to_create:
        db.add(line)
    db.commit()
    for line in lines_to_create:
        db.refresh(line)

    return AthleticsTakeoffOut(
        breakdown={
            "lanes": payload.lanes,
            "track_width_m": round(track_width_m, 2),
            "inner_radius_m": inner_r,
            "outer_radius_m": round(outer_r, 2),
            "straight_length_m": straight,
            "kerb_length_m": round(kerb_length_m, 2),
            "outer_perimeter_m": round(outer_perimeter_m, 2),
            "track_surface_area_sqm": round(track_surface_area_sqm, 2),
            "d_zone_area_sqm": round(d_zone_area_sqm, 2),
            "field_events_count": len(payload.field_events),
        },
        lines=[_line_to_out(line) for line in lines_to_create],
    )
