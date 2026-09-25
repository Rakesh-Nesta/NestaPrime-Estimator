"""Amendment 54 (Section 58): what a client-facing Quotation says about the work.

Shared by the Quotation PDF (app/api/pdf_documents.py), the cover-note draft and
the quotation's own `pdf_gaps` note (app/api/documents.py). It lives here, and
imports no API module that imports documents.py, so those two can both use it.

The rule that runs through all of it: text on a client's document comes from
what a Director configured or from this quotation's own data. Anything unset is
left out of the PDF -- never printed as "not configured" -- and is reported to
the person preparing the quotation through `pdf_gaps`."""

import uuid
from datetime import date

from sqlalchemy.orm import Session

from app.api.schedule import get_schedule
from app.api.settings import get_current_setting_value
from app.models.client import Client
from app.models.client_signatory import ClientSignatory
from app.models.document import EstimateOption, Quotation, QuotationLine
from app.models.package_content import PackageContent
from app.models.project import Project
from app.models.sport import ProjectSport, Sport

DEFAULT_COMPANY_NAME = "NestaPrime Sports Infrastructure"
SIGNATORY_NAME_KEY = "company_signatory_name"
SIGNATORY_DESIGNATION_KEY = "company_signatory_designation"
COMPANY_NAME_KEY = "company_legal_name"

# The bank fields the Quotation PDF prints as "Payment to" (kept in step with
# pdf_documents._COMPANY_BANK_KEYS by a test).
BANK_SETTING_LABELS = {
    "company_bank_name": "Bank",
    "company_bank_account_name": "Account name",
    "company_bank_account_number": "Account no.",
    "company_bank_ifsc": "IFSC",
}


def quotation_sport_rows(db: Session, quotation: Quotation) -> list[dict]:
    """One row per sport the quotation covers, in its line order."""
    rows = []
    qlines = db.query(QuotationLine).filter(QuotationLine.quotation_id == quotation.id).all()
    for qline in qlines:
        option = db.query(EstimateOption).filter(EstimateOption.id == qline.estimate_option_id).first()
        project_sport = db.query(ProjectSport).filter(ProjectSport.id == option.project_sport_id).first()
        sport = db.query(Sport).filter(Sport.id == project_sport.sport_id).first()
        rows.append({"sport": sport, "project_sport": project_sport, "option": option})
    return rows


def is_enhanced(quotation: Quotation, project: Project) -> bool:
    """The new sections (scope of work, cover-letter block, warranty without an
    invented duration) appear only on a quotation the client has not yet been
    sent, and never in tender mode (a BOQ). What a client already received does
    not change under them."""
    return quotation.sent_at is None and not project.tender_mode


def package_content_for(db: Session, sport: Sport, option: EstimateOption) -> PackageContent | None:
    return (
        db.query(PackageContent)
        .filter(PackageContent.sport_id == sport.id, PackageContent.tier == option.package)
        .first()
    )


def active_signatory(db: Session, client_id: uuid.UUID, today: date | None = None) -> ClientSignatory | None:
    """The client's first active authorised signatory (Part O): active, authorised
    on or before today, and not expired."""
    today = today or date.today()
    rows = (
        db.query(ClientSignatory)
        .filter(
            ClientSignatory.client_id == client_id,
            ClientSignatory.is_active.is_(True),
            ClientSignatory.authorization_date <= today,
        )
        .order_by(ClientSignatory.authorization_date, ClientSignatory.name)
        .all()
    )
    for row in rows:
        if row.expiry_date is None or row.expiry_date >= today:
            return row
    return None


def addressee(db: Session, client: Client) -> tuple[str, str | None] | None:
    """(name, designation or None): the first active signatory, else the client's
    contact name, else nobody."""
    signatory = active_signatory(db, client.id)
    if signatory is not None:
        return signatory.name, signatory.designation
    if client.contact_name:
        return client.contact_name, None
    return None


def company_name(db: Session) -> str:
    return get_current_setting_value(db, COMPANY_NAME_KEY) or DEFAULT_COMPANY_NAME


def signatory_settings(db: Session) -> tuple[str | None, str | None]:
    name = get_current_setting_value(db, SIGNATORY_NAME_KEY) or None
    designation = get_current_setting_value(db, SIGNATORY_DESIGNATION_KEY) or None
    return name, designation


def _tier_label(option: EstimateOption) -> str:
    return option.package.value.capitalize()


def pdf_gaps(db: Session, quotation: Quotation) -> list[str]:
    """Plain sentences naming what this quotation's PDF will leave out. Empty when
    nothing is missing. Carries no amounts and never blocks anything."""
    gaps: list[str] = []
    project = db.query(Project).filter(Project.id == quotation.project_id).first()
    client = db.query(Client).filter(Client.id == project.client_id).first()

    if is_enhanced(quotation, project):
        for row in quotation_sport_rows(db, quotation):
            if package_content_for(db, row["sport"], row["option"]) is None:
                gaps.append(
                    f"No package content is set for {row['sport'].name} ({_tier_label(row['option'])}) "
                    "-- the Scope of work leaves it out."
                )
        if not quotation.cover_note:
            gaps.append("There is no cover note, so the PDF has no letter block.")
        else:
            name, designation = signatory_settings(db)
            if name is None:
                gaps.append("No authorised signatory is set, so the letter has no sign-off name.")
            elif designation is None:
                gaps.append("The authorised signatory has no designation, so the sign-off shows the name only.")
        from app.api.pdf_documents import _warranty_years

        if client is not None and _warranty_years(db, client.type) is None:
            gaps.append(
                f"No warranty duration is set for {client.type.value.replace('_', ' ')} clients, "
                "so the warranty table has no duration column."
            )

    missing = [label for key, label in BANK_SETTING_LABELS.items() if not get_current_setting_value(db, key)]
    if len(missing) == len(BANK_SETTING_LABELS):
        gaps.append("Bank details are not set, so the PDF has no 'Payment to' block.")
    elif missing:
        gaps.append(f"Bank details are incomplete (not set: {', '.join(missing)}).")
    return gaps


# ---------------------------------------------------------------------------
# The AI cover-note draft
# ---------------------------------------------------------------------------


def cover_note_facts(db: Session, quotation: Quotation, current_user) -> dict:
    """Only facts that are actually set; the prompt mentions nothing else."""
    project = db.query(Project).filter(Project.id == quotation.project_id).first()
    client = db.query(Client).filter(Client.id == project.client_id).first()
    who = addressee(db, client)
    sports = []
    for row in quotation_sport_rows(db, quotation):
        sport, project_sport, option = row["sport"], row["project_sport"], row["option"]
        content = package_content_for(db, sport, option)
        weeks = None
        try:
            weeks = get_schedule(
                project_sport_id=project_sport.id, start_date=None, mobilisation_days=None,
                db=db, current_user=current_user,
            ).total_weeks
        except Exception:  # noqa: BLE001 -- a timeline we cannot compute is simply not mentioned
            weeks = None
        sports.append(
            {
                "name": sport.name,
                "courts": project_sport.number_of_courts,
                "dims": sport.playing_dims,
                "tier": _tier_label(option),
                "flooring": content.flooring_description if content else None,
                "structure": content.structure_description if content else None,
                "lighting": content.lighting_description if content else None,
                "scope": [ln.strip() for ln in content.scope_description.splitlines() if ln.strip()] if content else [],
                "warranty_years": content.warranty_years if content else None,
                "weeks": weeks,
            }
        )
    return {
        "client": client.name,
        "addressee": (f"{who[0]}, {who[1]}" if who and who[1] else who[0]) if who else None,
        "site": project.site_address or project.city,
        "sports": sports,
        "validity_days": 30,
        "total": float(quotation.quotation_total),
    }


def build_cover_note_prompt(facts: dict) -> str:
    lines = [
        "Write the body of a cover letter for a sports infrastructure quotation from NestaPrime. "
        "Write two short paragraphs, about 120 to 160 words in total, plain text, no headings and no bullet points. "
        "Use ONLY the facts listed below and do not invent anything else: no past projects, certifications, awards, "
        "guarantees, delivery dates, or any price other than the quotation total if it is listed. "
        "Do not write a greeting, a sign-off, a signatory or any placeholder such as [Name] -- the document prints "
        "those itself. If something is not listed below, do not mention it.",
        "",
        "Facts:",
        f"- Client: {facts['client']}",
    ]
    if facts.get("addressee"):
        lines.append(f"- Addressed to: {facts['addressee']}")
    if facts.get("site"):
        lines.append(f"- Site: {facts['site']}")
    for sport in facts["sports"]:
        parts = [f"{sport['name']}"]
        if sport.get("courts"):
            parts.append(f"{sport['courts']} court{'s' if sport['courts'] != 1 else ''}")
        if sport.get("dims"):
            parts.append(f"{sport['dims']} ft")
        parts.append(f"{sport['tier']} package")
        line = "- Sport: " + ", ".join(parts) + "."
        if sport.get("flooring"):
            line += f" Flooring: {sport['flooring']}."
        if sport.get("structure"):
            line += f" Structure: {sport['structure']}."
        if sport.get("lighting"):
            line += f" Lighting: {sport['lighting']}."
        if sport.get("scope"):
            line += " Scope: " + "; ".join(sport["scope"]) + "."
        if sport.get("warranty_years") is not None:
            line += f" Warranty: {sport['warranty_years']} year(s)."
        if sport.get("weeks"):
            line += f" Estimated timeline: {sport['weeks']} week(s) from mobilisation."
        lines.append(line)
    lines.append(f"- The quotation is valid for {facts['validity_days']} days from the date it is sent.")
    lines.append(f"- Quotation total (single lump sum, incl. GST): Rs {facts['total']:,.0f}")
    return "\n".join(lines)
