import uuid
from enum import Enum

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.documents import CostSheetLineOut, _line_to_out
from app.api.site_works import FT_TO_M, STEEL_KG_PER_CUM_SLAB_DEFAULT, _get_cost_sheet, _labour_category
from app.core.auth import require_roles
from app.db.session import get_db
from app.models.document import CostSheet, CostSheetLine, WorkPackage
from app.models.rate_item import RateSource
from app.models.sport import ProjectSport

pool_router = APIRouter(tags=["pool"])

COST_ROLES = ("pm", "director")

# D.2-ish structure/base matrix (line 234) and G.1's own "Shell" row:
# "RCC / FRP liner" -- "RCC 8-12in shell". Midpoint used only as the
# Pydantic default, fully overridable.
SHELL_THICKNESS_IN_DEFAULT = 10.0
# Standard blinding-layer allowance under an RCC shell, the same role PCC
# plays under D.1's own base take-off -- not given a figure by G.1
# itself, so a conventional 100mm/4in is used, documented and fixed
# (not exposed as an input -- there is nothing about this project that
# would change it, unlike shell thickness which genuinely varies by depth).
PCC_BLINDING_THICKNESS_M = 0.10
# Standard working/over-dig margin below the pool's deepest point so the
# shell and blinding layer have room to be built -- a conventional
# allowance, not a blueprint figure.
EXCAVATION_MARGIN_M = 0.30

# Structure Type G (pool boundary fence) is already a full take-off in
# the Structures (E) tab (sports.py already recommends it for every pool
# sport); Lighting (H) already has pool's own pole count (6) and lux
# table (practice 300 / match 500); Part N's schedule estimator already
# treats pool sports as a lump 10-14 week construction activity. None of
# that is duplicated here.


def _get_project_sport(db: Session, cost_sheet: CostSheet, project_sport_id: uuid.UUID) -> ProjectSport:
    project_sport = (
        db.query(ProjectSport)
        .filter(ProjectSport.id == project_sport_id, ProjectSport.project_id == cost_sheet.project_id)
        .first()
    )
    if not project_sport:
        raise HTTPException(status_code=404, detail="Sport selection not on this project")
    return project_sport


class LinerType(str, Enum):
    RCC = "rcc"
    FRP = "frp"


class PoolShellIn(BaseModel):
    length_ft: float = Field(gt=0)
    width_ft: float = Field(gt=0)
    shallow_depth_ft: float = Field(gt=0)
    deep_depth_ft: float = Field(gt=0)
    liner_type: LinerType = LinerType.RCC
    shell_thickness_in: float = Field(default=SHELL_THICKNESS_IN_DEFAULT, gt=0)  # RCC only
    steel_kg_per_cum: float = Field(default=STEEL_KG_PER_CUM_SLAB_DEFAULT, gt=0)  # RCC only

    # RCC path
    excavation_rate_per_cum: float | None = Field(default=None, gt=0)
    pcc_rate_per_cum: float | None = Field(default=None, gt=0)
    rcc_rate_per_cum: float | None = Field(default=None, gt=0)  # RCC M25 + waterproofing admixture, one line
    steel_rate_per_kg: float | None = Field(default=None, gt=0)
    plaster_rate_per_sqm: float | None = Field(default=None, gt=0)
    tile_rate_per_sqm: float | None = Field(default=None, gt=0)
    coping_rate_per_m: float | None = Field(default=None, gt=0)

    # FRP path -- a complete supplied system, priced per sqm of wetted surface
    frp_shell_rate_per_sqm: float | None = Field(default=None, gt=0)


class PoolFiltrationIn(BaseModel):
    turnover_hours: float = Field(default=5.0, gt=0)  # G.1: "Turnover 4-6h"
    pump_rate: float = Field(gt=0)  # lump sum -- sized off flow_rate_m3_per_hr in the breakdown, an engineer/vendor call
    sand_filter_rate: float = Field(gt=0)
    pipework_length_m: float | None = Field(default=None, gt=0)
    pipework_rate_per_m: float | None = Field(default=None, gt=0)
    plant_room_area_sqft: float | None = Field(default=None, gt=0)
    plant_room_rate_per_sqft: float | None = Field(default=None, gt=0)
    skimmer_count: int | None = Field(default=None, gt=0)
    skimmer_rate_each: float | None = Field(default=None, gt=0)
    balancing_tank_rate: float | None = Field(default=None, gt=0)


class TreatmentType(str, Enum):
    CHLORINE = "chlorine"
    SALT = "salt"
    UV = "uv"
    OZONE = "ozone"


class PoolTreatmentIn(BaseModel):
    treatment_type: TreatmentType
    dosing_system_rate: float = Field(gt=0)
    test_kit_rate: float = Field(gt=0)


class PoolSafetyItemIn(BaseModel):
    item_name: str = Field(min_length=1)  # e.g. "Ladder", "Lane ropes (set)", "Blocks", "Lifeguard chair", "Depth markers"
    quantity: int = Field(gt=0)
    rate: float = Field(gt=0)


class PoolDeckIn(BaseModel):
    deck_width_ft: float = Field(gt=0)
    anti_slip_tile_rate_per_sqm: float = Field(gt=0)
    channel_drain_rate_per_m: float = Field(gt=0)
    safety_items: list[PoolSafetyItemIn] = Field(default_factory=list)


class WaterSource(str, Enum):
    BOREWELL = "borewell"
    TANKER = "tanker"


class PoolWaterIn(BaseModel):
    source: WaterSource
    water_rate_per_cum: float = Field(gt=0)


class PoolOptionIn(BaseModel):
    option_name: str = Field(min_length=1)  # e.g. "Heat pump heating", "Pool cover", "Underwater lights", "PEB cover + dehumidification"
    rate: float = Field(gt=0)


class PoolComplianceItemIn(BaseModel):
    # M.4a/Exclusions: "NestaPrime's own compliance items such as
    # pool-safety signage, lifeguard-requirement note and design NOC
    # documentation are priced as scope lines and are NOT excluded."
    item_name: str = Field(min_length=1)  # e.g. "Pool safety NOC", "Lifeguard requirement note", "Drowning-prevention signage"
    rate: float = Field(gt=0)


class PoolTakeoffRequest(BaseModel):
    project_sport_id: uuid.UUID
    shell: PoolShellIn
    filtration: PoolFiltrationIn | None = None
    treatment: PoolTreatmentIn | None = None
    deck: PoolDeckIn | None = None
    water: PoolWaterIn | None = None
    options: list[PoolOptionIn] = Field(default_factory=list)
    compliance: list[PoolComplianceItemIn] = Field(default_factory=list)


class PoolTakeoffOut(BaseModel):
    breakdown: dict
    lines: list[CostSheetLineOut]


@pool_router.post("/cost-sheets/{cost_sheet_id}/pool", response_model=PoolTakeoffOut, status_code=201)
def add_pool_takeoff(
    cost_sheet_id: uuid.UUID,
    payload: PoolTakeoffRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*COST_ROLES)),
):
    """G.1: Shell (required) computes the pool's own volume and wetted
    surface once, which Filtration and Water both reuse -- flow_rate =
    volume / turnover_hours (G.1's own formula) and fill volume = the
    shell's own volume, rather than asking for either again. Deck area
    is the perimeter x deck width ring around the shell. Treatment,
    Deck's named safety items, Options and Compliance all have no
    formula or dimension in the blueprint, so each is a flat named-item
    list priced as entered -- the same pattern as Accessories/Track's
    field events/Gym's equipment list."""
    cost_sheet = _get_cost_sheet(db, cost_sheet_id)
    _get_project_sport(db, cost_sheet, payload.project_sport_id)

    shell = payload.shell
    L_m = shell.length_ft * FT_TO_M
    W_m = shell.width_ft * FT_TO_M
    shallow_m = shell.shallow_depth_ft * FT_TO_M
    deep_m = shell.deep_depth_ft * FT_TO_M
    avg_depth_m = (shallow_m + deep_m) / 2
    perimeter_m = 2 * (L_m + W_m)

    volume_cum = L_m * W_m * avg_depth_m
    wetted_surface_sqm = (L_m * W_m) + 2 * (L_m + W_m) * avg_depth_m

    lines_to_create: list[CostSheetLine] = []
    civil_category = _labour_category(db, "civil_base_site_prep")
    pool_mep_category = _labour_category(db, "pool_mep")

    if shell.liner_type == LinerType.FRP:
        if shell.frp_shell_rate_per_sqm is None:
            raise HTTPException(status_code=422, detail="frp_shell_rate_per_sqm is required for an FRP liner shell")
        lines_to_create.append(
            CostSheetLine(
                cost_sheet_id=cost_sheet_id, project_sport_id=payload.project_sport_id, work_package=WorkPackage.POOL,
                category="Pool shell", item_name="FRP liner shell (supplied system)", unit="sqm",
                quantity=round(wetted_surface_sqm, 2), rate=shell.frp_shell_rate_per_sqm, source=RateSource.MANUAL,
            )
        )
    else:
        missing = [
            name
            for name, value in (
                ("excavation_rate_per_cum", shell.excavation_rate_per_cum),
                ("pcc_rate_per_cum", shell.pcc_rate_per_cum),
                ("rcc_rate_per_cum", shell.rcc_rate_per_cum),
                ("steel_rate_per_kg", shell.steel_rate_per_kg),
                ("plaster_rate_per_sqm", shell.plaster_rate_per_sqm),
                ("tile_rate_per_sqm", shell.tile_rate_per_sqm),
                ("coping_rate_per_m", shell.coping_rate_per_m),
            )
            if value is None
        ]
        if missing:
            raise HTTPException(status_code=422, detail=f"Missing rates for an RCC shell: {', '.join(missing)}")

        excavation_cum = L_m * W_m * (deep_m + EXCAVATION_MARGIN_M)
        pcc_cum = L_m * W_m * PCC_BLINDING_THICKNESS_M
        shell_thickness_m = shell.shell_thickness_in * 0.0254
        rcc_cum = wetted_surface_sqm * shell_thickness_m
        steel_kg = rcc_cum * shell.steel_kg_per_cum

        lines_to_create.extend(
            [
                CostSheetLine(
                    cost_sheet_id=cost_sheet_id, project_sport_id=payload.project_sport_id, work_package=WorkPackage.POOL,
                    category="Pool shell", item_name="Excavation", unit="cum", quantity=round(excavation_cum, 2),
                    rate=shell.excavation_rate_per_cum, source=RateSource.MANUAL,
                    labour_category_id=civil_category.id if civil_category else None,
                ),
                CostSheetLine(
                    cost_sheet_id=cost_sheet_id, project_sport_id=payload.project_sport_id, work_package=WorkPackage.POOL,
                    category="Pool shell", item_name="PCC blinding", unit="cum", quantity=round(pcc_cum, 2),
                    rate=shell.pcc_rate_per_cum, source=RateSource.MANUAL,
                    labour_category_id=civil_category.id if civil_category else None,
                ),
                CostSheetLine(
                    cost_sheet_id=cost_sheet_id, project_sport_id=payload.project_sport_id, work_package=WorkPackage.POOL,
                    category="Pool shell", item_name=f"RCC M25 shell + waterproofing admixture ({shell.shell_thickness_in:g}in)",
                    unit="cum", quantity=round(rcc_cum, 3), rate=shell.rcc_rate_per_cum, source=RateSource.MANUAL,
                    labour_category_id=civil_category.id if civil_category else None,
                ),
                CostSheetLine(
                    cost_sheet_id=cost_sheet_id, project_sport_id=payload.project_sport_id, work_package=WorkPackage.POOL,
                    category="Pool shell", item_name=f"Reinforcement steel @ {shell.steel_kg_per_cum:g}kg/cum",
                    unit="kg", quantity=round(steel_kg, 2), rate=shell.steel_rate_per_kg, source=RateSource.MANUAL,
                    labour_category_id=civil_category.id if civil_category else None,
                ),
                CostSheetLine(
                    cost_sheet_id=cost_sheet_id, project_sport_id=payload.project_sport_id, work_package=WorkPackage.POOL,
                    category="Pool shell", item_name="Waterproof plaster", unit="sqm", quantity=round(wetted_surface_sqm, 2),
                    rate=shell.plaster_rate_per_sqm, source=RateSource.MANUAL,
                ),
                CostSheetLine(
                    cost_sheet_id=cost_sheet_id, project_sport_id=payload.project_sport_id, work_package=WorkPackage.POOL,
                    category="Pool shell", item_name="Pool tiles/mosaic", unit="sqm", quantity=round(wetted_surface_sqm, 2),
                    rate=shell.tile_rate_per_sqm, source=RateSource.MANUAL,
                ),
                CostSheetLine(
                    cost_sheet_id=cost_sheet_id, project_sport_id=payload.project_sport_id, work_package=WorkPackage.POOL,
                    category="Pool shell", item_name="Coping", unit="m", quantity=round(perimeter_m, 2),
                    rate=shell.coping_rate_per_m, source=RateSource.MANUAL,
                ),
            ]
        )

    flow_rate_m3_per_hr = None
    if payload.filtration is not None:
        f = payload.filtration
        flow_rate_m3_per_hr = volume_cum / f.turnover_hours
        lines_to_create.append(
            CostSheetLine(
                cost_sheet_id=cost_sheet_id, project_sport_id=payload.project_sport_id, work_package=WorkPackage.POOL,
                category="Filtration", item_name=f"Circulation pump (sized for {round(flow_rate_m3_per_hr, 1)} m3/hr)",
                unit="set", quantity=1, rate=f.pump_rate, source=RateSource.MANUAL,
                labour_category_id=pool_mep_category.id if pool_mep_category else None,
            )
        )
        lines_to_create.append(
            CostSheetLine(
                cost_sheet_id=cost_sheet_id, project_sport_id=payload.project_sport_id, work_package=WorkPackage.POOL,
                category="Filtration", item_name="Sand filter", unit="set", quantity=1, rate=f.sand_filter_rate,
                source=RateSource.MANUAL, labour_category_id=pool_mep_category.id if pool_mep_category else None,
            )
        )
        if f.pipework_length_m is not None:
            if f.pipework_rate_per_m is None:
                raise HTTPException(status_code=422, detail="pipework_rate_per_m is required when pipework_length_m is given")
            lines_to_create.append(
                CostSheetLine(
                    cost_sheet_id=cost_sheet_id, project_sport_id=payload.project_sport_id, work_package=WorkPackage.POOL,
                    category="Filtration", item_name="Pipework", unit="m", quantity=f.pipework_length_m,
                    rate=f.pipework_rate_per_m, source=RateSource.MANUAL,
                    labour_category_id=pool_mep_category.id if pool_mep_category else None,
                )
            )
        if f.plant_room_area_sqft is not None:
            if f.plant_room_rate_per_sqft is None:
                raise HTTPException(status_code=422, detail="plant_room_rate_per_sqft is required when plant_room_area_sqft is given")
            lines_to_create.append(
                CostSheetLine(
                    cost_sheet_id=cost_sheet_id, project_sport_id=payload.project_sport_id, work_package=WorkPackage.POOL,
                    category="Filtration", item_name="Plant room", unit="sqft", quantity=f.plant_room_area_sqft,
                    rate=f.plant_room_rate_per_sqft, source=RateSource.MANUAL,
                    labour_category_id=civil_category.id if civil_category else None,
                )
            )
        if f.skimmer_count is not None:
            if f.skimmer_rate_each is None:
                raise HTTPException(status_code=422, detail="skimmer_rate_each is required when skimmer_count is given")
            lines_to_create.append(
                CostSheetLine(
                    cost_sheet_id=cost_sheet_id, project_sport_id=payload.project_sport_id, work_package=WorkPackage.POOL,
                    category="Filtration", item_name="Skimmers / overflow gutter", unit="nos", quantity=f.skimmer_count,
                    rate=f.skimmer_rate_each, source=RateSource.MANUAL,
                    labour_category_id=pool_mep_category.id if pool_mep_category else None,
                )
            )
        if f.balancing_tank_rate is not None:
            lines_to_create.append(
                CostSheetLine(
                    cost_sheet_id=cost_sheet_id, project_sport_id=payload.project_sport_id, work_package=WorkPackage.POOL,
                    category="Filtration", item_name="Balancing tank", unit="set", quantity=1,
                    rate=f.balancing_tank_rate, source=RateSource.MANUAL,
                    labour_category_id=pool_mep_category.id if pool_mep_category else None,
                )
            )

    if payload.treatment is not None:
        t = payload.treatment
        lines_to_create.append(
            CostSheetLine(
                cost_sheet_id=cost_sheet_id, project_sport_id=payload.project_sport_id, work_package=WorkPackage.POOL,
                category="Treatment", item_name=f"{t.treatment_type.value.capitalize()} dosing system", unit="set",
                quantity=1, rate=t.dosing_system_rate, source=RateSource.MANUAL,
                labour_category_id=pool_mep_category.id if pool_mep_category else None,
            )
        )
        lines_to_create.append(
            CostSheetLine(
                cost_sheet_id=cost_sheet_id, project_sport_id=payload.project_sport_id, work_package=WorkPackage.POOL,
                category="Treatment", item_name="Pool test kit", unit="set", quantity=1, rate=t.test_kit_rate,
                source=RateSource.MANUAL,
            )
        )

    deck_area_sqm = None
    if payload.deck is not None:
        d = payload.deck
        deck_width_m = d.deck_width_ft * FT_TO_M
        deck_area_sqm = perimeter_m * deck_width_m
        lines_to_create.append(
            CostSheetLine(
                cost_sheet_id=cost_sheet_id, project_sport_id=payload.project_sport_id, work_package=WorkPackage.POOL,
                category="Deck & safety", item_name="Anti-slip deck tiles", unit="sqm", quantity=round(deck_area_sqm, 2),
                rate=d.anti_slip_tile_rate_per_sqm, source=RateSource.MANUAL,
            )
        )
        lines_to_create.append(
            CostSheetLine(
                cost_sheet_id=cost_sheet_id, project_sport_id=payload.project_sport_id, work_package=WorkPackage.POOL,
                category="Deck & safety", item_name="Channel drain", unit="m", quantity=round(perimeter_m, 2),
                rate=d.channel_drain_rate_per_m, source=RateSource.MANUAL,
                labour_category_id=civil_category.id if civil_category else None,
            )
        )
        for item in d.safety_items:
            lines_to_create.append(
                CostSheetLine(
                    cost_sheet_id=cost_sheet_id, project_sport_id=payload.project_sport_id, work_package=WorkPackage.ACCESSORIES,
                    category="Deck & safety", item_name=item.item_name, unit="nos", quantity=item.quantity,
                    rate=item.rate, source=RateSource.MANUAL,
                )
            )

    if payload.water is not None:
        w = payload.water
        lines_to_create.append(
            CostSheetLine(
                cost_sheet_id=cost_sheet_id, project_sport_id=payload.project_sport_id, work_package=WorkPackage.POOL,
                category="Water", item_name=f"Water fill (initial) -- {w.source.value}", unit="cum",
                quantity=round(volume_cum, 2), rate=w.water_rate_per_cum, source=RateSource.MANUAL,
            )
        )

    for option in payload.options:
        lines_to_create.append(
            CostSheetLine(
                cost_sheet_id=cost_sheet_id, project_sport_id=payload.project_sport_id, work_package=WorkPackage.POOL,
                category="Options", item_name=option.option_name, unit="set", quantity=1, rate=option.rate,
                source=RateSource.MANUAL,
            )
        )

    for item in payload.compliance:
        lines_to_create.append(
            CostSheetLine(
                cost_sheet_id=cost_sheet_id, project_sport_id=payload.project_sport_id, work_package=WorkPackage.SCOPE,
                category="Compliance", item_name=item.item_name, unit="set", quantity=1, rate=item.rate,
                source=RateSource.MANUAL,
            )
        )

    for line in lines_to_create:
        db.add(line)
    db.commit()
    for line in lines_to_create:
        db.refresh(line)

    return PoolTakeoffOut(
        breakdown={
            "volume_cum": round(volume_cum, 2),
            "wetted_surface_sqm": round(wetted_surface_sqm, 2),
            "perimeter_m": round(perimeter_m, 2),
            "avg_depth_m": round(avg_depth_m, 2),
            "flow_rate_m3_per_hr": round(flow_rate_m3_per_hr, 2) if flow_rate_m3_per_hr is not None else None,
            "deck_area_sqm": round(deck_area_sqm, 2) if deck_area_sqm is not None else None,
            "delegated_note": (
                "Pool boundary fence (Type G, mandatory): use the Structures (E) tab. "
                "Lighting: use the Lighting (H) tab (pool already has a 6-pole default and its own "
                "300/500 lux practice/match figures). Schedule: Part N already treats pool sports as a "
                "10-14 week lump construction activity."
            ),
        },
        lines=[_line_to_out(line) for line in lines_to_create],
    )
