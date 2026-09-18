import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.core.auth import require_roles
from app.db.session import get_db
from app.models.accessory_catalog_item import AccessoryCatalogItem
from app.models.construction_sequence_step import ConstructionPhase, ConstructionSequenceStep
from app.models.flooring_guide import FlooringGuide
from app.models.package_content import PackageContent
from app.models.sport import Sport
from app.services import ai_content

construction_sequence_router = APIRouter(prefix="/construction-sequence", tags=["construction-sequence"])

# Section 18 spec, Decision/point 6: same read gate as the rest of the
# Build Guide (Section 16); authoring (including drafting) gated the
# same as the rest of Sports & Scope Admin -- Director/Admin only.
READ_ROLES = ("sales", "pm", "director", "procurement", "site_engineer")
WRITE_ROLES = ("director",)

PHASE_ORDER = list(ConstructionPhase)

CONSTRUCTION_SEQUENCE_DISCLAIMER = (
    "General build sequence -- confirm against site conditions with a qualified site "
    "engineer before execution."
)


class ConstructionSequenceStepOut(BaseModel):
    id: uuid.UUID
    sport_id: uuid.UUID
    phase: ConstructionPhase
    description: str
    updated_by_id: uuid.UUID | None

    model_config = ConfigDict(from_attributes=True)


def _sorted_by_phase(steps: list[ConstructionSequenceStep]) -> list[ConstructionSequenceStep]:
    return sorted(steps, key=lambda s: PHASE_ORDER.index(s.phase))


@construction_sequence_router.get("", response_model=list[ConstructionSequenceStepOut])
def list_construction_sequence(
    sport_id: uuid.UUID | None = None,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*READ_ROLES)),
):
    query = db.query(ConstructionSequenceStep)
    if sport_id is not None:
        query = query.filter(ConstructionSequenceStep.sport_id == sport_id)
    return _sorted_by_phase(query.all())


class ConstructionSequenceStepIn(BaseModel):
    phase: ConstructionPhase
    description: str = Field(min_length=1)


class ConstructionSequenceSaveRequest(BaseModel):
    steps: list[ConstructionSequenceStepIn] = Field(min_length=1)


@construction_sequence_router.put("/{sport_id}", response_model=list[ConstructionSequenceStepOut])
def save_construction_sequence(
    sport_id: uuid.UUID,
    payload: ConstructionSequenceSaveRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*WRITE_ROLES)),
):
    """Upserts only the phases named in the request -- a partial save (a
    Director editing one phase at a time) leaves the other phases already
    on record untouched, same spirit as PATCH's exclude_unset elsewhere
    in this app."""
    if not db.query(Sport).filter(Sport.id == sport_id).first():
        raise HTTPException(status_code=404, detail="Sport not found")

    existing_by_phase = {
        s.phase: s
        for s in db.query(ConstructionSequenceStep).filter(ConstructionSequenceStep.sport_id == sport_id).all()
    }
    for step_in in payload.steps:
        step = existing_by_phase.get(step_in.phase)
        if step is None:
            step = ConstructionSequenceStep(sport_id=sport_id, phase=step_in.phase)
            db.add(step)
            existing_by_phase[step_in.phase] = step
        step.description = step_in.description
        step.updated_by_id = current_user.id

    db.commit()
    return _sorted_by_phase(list(existing_by_phase.values()))


class ConstructionSequenceDraftStep(BaseModel):
    phase: ConstructionPhase
    description: str


class ConstructionSequenceDraftOut(BaseModel):
    steps: list[ConstructionSequenceDraftStep]


@construction_sequence_router.post("/draft/{sport_id}", response_model=ConstructionSequenceDraftOut)
def draft_construction_sequence(
    sport_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*WRITE_ROLES)),
):
    """Returns a suggested six-phase sequence -- never saved by this
    endpoint. The Director still has to review it and PUT
    .../construction-sequence/{sport_id} themselves to keep it, same
    pattern as draft_quotation_cover_note (Amendment 13). Grounded only
    in this sport's own real data (dimensions, accessory catalog,
    flooring guide, package tiers) -- never invented dimensions or
    materials the sport doesn't actually have on record."""
    sport = db.query(Sport).filter(Sport.id == sport_id).first()
    if not sport:
        raise HTTPException(status_code=404, detail="Sport not found")

    accessories = (
        db.query(AccessoryCatalogItem)
        .filter(AccessoryCatalogItem.sport_id == sport_id, AccessoryCatalogItem.is_active.is_(True))
        .order_by(AccessoryCatalogItem.item_name)
        .all()
    )
    flooring = db.query(FlooringGuide).filter(FlooringGuide.sport_id == sport_id).first()
    packages = db.query(PackageContent).filter(PackageContent.sport_id == sport_id).all()

    lines = [
        f"Sport: {sport.name} ({sport.category.value})",
        f"Playing dimensions: {sport.playing_dims}. Build dimensions: {sport.build_dims}.",
    ]
    if accessories:
        lines.append(
            "Accessories: " + ", ".join(f"{a.item_name} ({a.quantity_per_court} {a.unit})" for a in accessories)
        )
    if flooring:
        lines.append(
            f"Flooring -- primary: {flooring.primary_spec}"
            + (f"; alternative: {flooring.secondary_spec}" if flooring.secondary_spec else "")
            + (f"; budget option: {flooring.budget_spec}" if flooring.budget_spec else "")
            + f". Rationale: {flooring.rationale}"
        )
    for pkg in packages:
        lines.append(
            f"{pkg.tier.value} tier -- structure: {pkg.structure_description} "
            f"lighting: {pkg.lighting_description} scope: {pkg.scope_description}"
        )
    context = "\n".join(lines)

    phase_keys = ", ".join(p.value for p in PHASE_ORDER)
    prompt = (
        "You are drafting a physical construction sequence for a sports facility, for "
        "review by a construction professional before it is used -- this is a draft, not "
        "final guidance. Use ONLY the real sport data below; do not invent dimensions or "
        "materials it doesn't mention. Cover general good-practice build order and "
        "activities for each phase.\n\n"
        f"Real data for this sport:\n{context}\n\n"
        f"Write exactly one line per phase, in this exact order: {phase_keys}. Each line "
        "must start with the phase key followed by a colon, then a plain-language "
        "1-2 sentence description of what happens in that phase for this specific sport. "
        "No markdown, no extra commentary, no blank lines."
    )
    try:
        raw = ai_content.generate_text(prompt, max_tokens=700)
    except ai_content.AiContentError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    parsed: dict[ConstructionPhase, str] = {}
    for line in raw.splitlines():
        line = line.strip()
        if not line or ":" not in line:
            continue
        key, _, description = line.partition(":")
        key = key.strip().lower()
        for phase in PHASE_ORDER:
            if phase.value == key:
                parsed[phase] = description.strip()
                break

    return ConstructionSequenceDraftOut(
        steps=[ConstructionSequenceDraftStep(phase=phase, description=parsed.get(phase, "")) for phase in PHASE_ORDER]
    )
