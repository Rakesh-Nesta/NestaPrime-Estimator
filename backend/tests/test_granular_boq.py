"""Blueprint Ledger gap #19: Part L's Format row calls for a 'BOQ-style
itemised schedule (item no., description, unit, qty, rate, amount)
instead of packages' -- previously the Tender-Mode Quotation PDF gave
each sport/package a single lump-sum 'Lot' row. _granular_boq_rows_for_sport
(app/api/pdf_documents.py) now breaks that into one row per
(work_package, category) group of the sport's own CostSheetLine rows,
apportioning the sport's already-computed SELLING amount by each group's
COST share -- never printing a cost rate -- and falling back to the old
lump-sum row when a sport has no priced CostSheetLine data to group
(direct explicit choice with the user: category-grouped, not a full
per-line take-off, 2026-09-10)."""

import io
import uuid

from pypdf import PdfReader

from app.api.pdf_documents import _granular_boq_rows_for_sport
from app.pdf_utils import format_inr


def _login(client, email, password="TestPass!1"):
    res = client.post("/auth/login", data={"username": email, "password": password})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _director_headers(client, director_user):
    return _login(client, "director@test.local")


def _create_gov_project_and_sport(client, headers, name="Granular BOQ Test Corp"):
    client_res = client.post("/clients", json={"name": name, "type": "government"}, headers=headers)
    assert client_res.status_code == 201, client_res.text
    client_id = client_res.json()["id"]

    project_res = client.post(
        "/projects",
        json={
            "client_id": client_id, "city": "Bengaluru", "site_condition": "level", "soil_type": "normal",
            "building_status": "open_air", "site_access": "good", "power_available": "yes",
            "water_available": True, "package": "standard",
        },
        headers=headers,
    )
    assert project_res.status_code == 201, project_res.text
    project_id = project_res.json()["id"]
    assert project_res.json()["tender_mode"] is True

    sport_id = next(s["id"] for s in client.get("/sports", headers=headers).json() if s["key"] == "badminton")
    sport_res = client.post(
        f"/projects/{project_id}/sports",
        json={"sport_id": sport_id, "building_status": "open_air"},
        headers=headers,
    )
    assert sport_res.status_code == 201, sport_res.text
    project_sport_id = sport_res.json()["id"]

    return project_id, project_sport_id


def _create_gov_project_with_sport(client, headers, name="Granular BOQ Test Corp"):
    project_id, project_sport_id = _create_gov_project_and_sport(client, headers, name)

    cs_res = client.post(f"/projects/{project_id}/cost-sheets", json={}, headers=headers)
    assert cs_res.status_code == 201, cs_res.text
    cost_sheet_id = cs_res.json()["id"]
    # E.5 auto-adds a "Structural engineer design & sign-off" line for every
    # Government/tender project -- removed so these tests see only the
    # lines they add themselves.
    for line in client.get(f"/cost-sheets/{cost_sheet_id}/lines", headers=headers).json():
        client.delete(f"/cost-sheets/{cost_sheet_id}/lines/{line['id']}", headers=headers)

    return project_id, project_sport_id, cost_sheet_id


def _add_line(client, headers, cost_sheet_id, project_sport_id, work_package, category, item_name, unit, quantity, rate):
    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/lines",
        json={
            "project_sport_id": project_sport_id, "work_package": work_package, "category": category,
            "item_name": item_name, "unit": unit, "quantity": quantity, "rate": rate,
        },
        headers=headers,
    )
    assert res.status_code == 201, res.text
    return res.json()


def _pdf_text(response) -> str:
    reader = PdfReader(io.BytesIO(response.content))
    return "\n".join(page.extract_text() for page in reader.pages)


# ---------------------------------------------------------------------------
# Direct tests of the grouping/apportionment helper -- exact math, isolated
# from the rest of the document chain.
# ---------------------------------------------------------------------------


def test_granular_boq_groups_by_category_and_apportions_by_cost_share(client, director_user, db_session):
    headers = _director_headers(client, director_user)
    _project_id, project_sport_id, cost_sheet_id = _create_gov_project_with_sport(client, headers)

    # Two lines in the same (work_package, category) with the SAME unit --
    # must merge into one group with summed quantity.
    _add_line(client, headers, cost_sheet_id, project_sport_id, "structure", "MS structure", "SHS 3x3", "kg", 100, 70)
    _add_line(client, headers, cost_sheet_id, project_sport_id, "structure", "MS structure", "SHS 4x4", "kg", 50, 70)
    # A second, distinct category.
    _add_line(client, headers, cost_sheet_id, project_sport_id, "flooring", "Acrylic PU", "PU coating", "sqm", 200, 1200)

    # cost totals: structure group = 150kg x 70 = 10500; flooring group =
    # 200sqm x 1200 = 240000; sport_line_cost_total = 250500.
    # A clean uniform 1.2x uplift (target selling vs. cost) makes every
    # group's amount an exact multiple of its own cost -- easy to verify.
    sport_ex_gst = 250500.0 * 1.2

    rows = _granular_boq_rows_for_sport(db_session, uuid.UUID(cost_sheet_id), uuid.UUID(project_sport_id), sport_ex_gst)

    assert rows is not None
    assert [r["category"] for r in rows] == ["MS structure", "Acrylic PU"]  # structure work_package sorts before flooring

    structure_row = rows[0]
    assert structure_row["unit"] == "kg"
    assert structure_row["qty"] == 150.0
    assert round(structure_row["amount"], 2) == round(10500 * 1.2, 2) == 12600.0
    assert round(structure_row["rate"], 2) == round(12600.0 / 150.0, 2) == 84.0  # 70 cost x 1.2 uplift

    flooring_row = rows[1]
    assert flooring_row["unit"] == "sqm"
    assert flooring_row["qty"] == 200.0
    assert round(flooring_row["amount"], 2) == round(240000 * 1.2, 2) == 288000.0
    assert round(flooring_row["rate"], 2) == round(288000.0 / 200.0, 2) == 1440.0  # 1200 cost x 1.2 uplift

    # Rows must fully account for the sport's selling amount -- no leftover,
    # no double counting.
    assert round(sum(r["amount"] for r in rows), 2) == round(sport_ex_gst, 2)


def test_granular_boq_falls_back_to_lot_when_a_category_mixes_units(client, director_user, db_session):
    headers = _director_headers(client, director_user)
    _project_id, project_sport_id, cost_sheet_id = _create_gov_project_with_sport(client, headers)

    # Same category, two different units -- summing quantity would be
    # meaningless (kg + each), so this group must fall back to a job-lot row.
    _add_line(client, headers, cost_sheet_id, project_sport_id, "structure", "Mixed items", "Steel", "kg", 10, 100)
    _add_line(client, headers, cost_sheet_id, project_sport_id, "structure", "Mixed items", "Brackets", "each", 5, 50)

    sport_ex_gst = 1250.0  # == cost total; uplift factor 1.0 for a simple check

    rows = _granular_boq_rows_for_sport(db_session, uuid.UUID(cost_sheet_id), uuid.UUID(project_sport_id), sport_ex_gst)

    assert rows is not None
    assert len(rows) == 1
    assert rows[0]["category"] == "Mixed items"
    assert rows[0]["unit"] == "Lot"
    assert rows[0]["qty"] == 1.0
    assert round(rows[0]["amount"], 2) == 1250.0
    assert round(rows[0]["rate"], 2) == 1250.0


def test_granular_boq_returns_none_when_sport_has_no_priced_lines(client, director_user, db_session):
    headers = _director_headers(client, director_user)
    _project_id, project_sport_id, cost_sheet_id = _create_gov_project_with_sport(client, headers)
    # No lines added -- matches a Cost Sheet whose total was entered
    # directly rather than built up from CostSheetLine rows.

    rows = _granular_boq_rows_for_sport(db_session, uuid.UUID(cost_sheet_id), uuid.UUID(project_sport_id), 500000.0)

    assert rows is None


# ---------------------------------------------------------------------------
# End-to-end: the actual Quotation PDF, through the real document chain,
# confirming the grouped rows render correctly and K.3 still holds -- the
# raw cost rate/amount for each line must never appear, only the
# apportioned selling figures.
# ---------------------------------------------------------------------------


def test_quotation_pdf_boq_shows_grouped_rows_with_no_cost_leak(client, director_user):
    headers = _director_headers(client, director_user)
    project_id, project_sport_id, cost_sheet_id = _create_gov_project_with_sport(client, headers)

    _add_line(client, headers, cost_sheet_id, project_sport_id, "structure", "MS structure", "SHS 3x3", "kg", 100, 70)
    _add_line(client, headers, cost_sheet_id, project_sport_id, "flooring", "Acrylic PU", "PU coating", "sqm", 200, 1200)

    recomputed = client.post(f"/cost-sheets/{cost_sheet_id}/recompute", headers=headers).json()
    client.post(f"/cost-sheets/{cost_sheet_id}/verify", headers=headers)

    estimate = client.post(
        f"/projects/{project_id}/estimates",
        json={"options": [{"project_sport_id": project_sport_id, "package": "standard", "cost_for_option": recomputed["cost_total"]}]},
        headers=headers,
    ).json()
    option_id = estimate["options"][0]["id"]
    approve_res = client.patch(
        f"/estimates/{estimate['id']}/options/{option_id}/client-status",
        json={"client_status": "approved", "waive_evidence_reason": "test waiver"},
        headers=headers,
    )
    assert approve_res.status_code == 200, approve_res.text

    quotation = client.post(
        f"/projects/{project_id}/quotations",
        json={"estimate_id": estimate["id"], "included_option_ids": [option_id]},
        headers=headers,
    ).json()
    client.post(f"/quotations/{quotation['id']}/release", headers=headers)
    client.post(f"/quotations/{quotation['id']}/send", headers=headers)

    pdf_res = client.get(f"/quotations/{quotation['id']}/pdf", headers=headers)
    assert pdf_res.status_code == 200
    text = _pdf_text(pdf_res)

    assert "Bill of Quantities (BOQ)" in text
    # Both categories show up as their own BOQ line, not one lump "Badminton
    # (Standard)" row.
    assert "Badminton (Standard) -- MS structure" in text
    assert "Badminton (Standard) -- Acrylic PU" in text

    # K.3: the raw cost-side figures (100kg x Rs70 = Rs7,000; 200sqm x
    # Rs1200 = Rs2,40,000) must never appear -- only the apportioned
    # selling amounts, which are strictly larger (there is a positive
    # target margin).
    assert format_inr(7000) not in text
    assert format_inr(240000) not in text
    assert format_inr(70) not in text
    assert format_inr(1200) not in text


def test_quotation_pdf_boq_falls_back_to_lump_sum_for_a_directly_entered_cost_total(client, director_user):
    """A Cost Sheet whose total was entered directly (no CostSheetLine
    rows) has nothing to group -- the BOQ must still render, as a single
    lump-sum 'Lot' row per sport/package, exactly as it did before this
    change."""
    headers = _director_headers(client, director_user)
    project_id, project_sport_id = _create_gov_project_and_sport(client, headers)

    cs_res = client.post(
        f"/projects/{project_id}/cost-sheets", json={"cost_total": 400000}, headers=headers
    )
    assert cs_res.status_code == 201, cs_res.text
    direct_cost_sheet_id = cs_res.json()["id"]
    client.post(f"/cost-sheets/{direct_cost_sheet_id}/verify", headers=headers)

    estimate = client.post(
        f"/projects/{project_id}/estimates",
        json={"options": [{"project_sport_id": project_sport_id, "package": "standard", "cost_for_option": 400000}]},
        headers=headers,
    ).json()
    option_id = estimate["options"][0]["id"]
    client.patch(
        f"/estimates/{estimate['id']}/options/{option_id}/client-status",
        json={"client_status": "approved", "waive_evidence_reason": "test waiver"},
        headers=headers,
    )

    quotation = client.post(
        f"/projects/{project_id}/quotations",
        json={"estimate_id": estimate["id"], "included_option_ids": [option_id]},
        headers=headers,
    ).json()
    client.post(f"/quotations/{quotation['id']}/release", headers=headers)
    client.post(f"/quotations/{quotation['id']}/send", headers=headers)

    pdf_res = client.get(f"/quotations/{quotation['id']}/pdf", headers=headers)
    assert pdf_res.status_code == 200
    text = _pdf_text(pdf_res)

    assert "Bill of Quantities (BOQ)" in text
    assert "Badminton (Standard)" in text
    assert "Badminton (Standard) --" not in text  # no category suffix -- lump-sum fallback, not a grouped row
