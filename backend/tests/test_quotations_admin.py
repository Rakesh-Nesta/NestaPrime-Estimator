"""Amendment 6b (Section 9): "admin reviews all quotations and daily
activity" -- a cross-project browse of every quotation, filterable, with a
CSV export (Director-approved 14 Sept 2026 addition to the original
browse-and-drill scope).

Amendment 49 (Section 53): the list opened from Director-only to Sales/PM/
Director -- Sales rows carry no cost/margin/below-floor (the per-project
view's K.3 rule) -- and rows name the originating lead. The CSV export stays
Director-only."""

from app.core.security import hash_password
from app.models.user import User, UserRole


def _login(client, email, password="TestPass!1"):
    res = client.post("/auth/login", data={"username": email, "password": password})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _director_headers(client, director_user):
    return _login(client, "director@test.local")


def _sales_headers(client, db_session):
    user = User(
        name="Test Sales", email="sales-qa@test.local", hashed_password=hash_password("TestPass!1"),
        role=UserRole.SALES,
    )
    db_session.add(user)
    db_session.commit()
    return _login(client, "sales-qa@test.local")


def _role_headers(client, db_session, role, email):
    user = User(name=f"Test {role.value}", email=email, hashed_password=hash_password("TestPass!1"), role=role)
    db_session.add(user)
    db_session.commit()
    return _login(client, email)


def _create_client_record(client, headers, name):
    res = client.post("/clients", json={"name": name, "type": "school"}, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()["id"]


def _create_project(client, headers, client_id, **extra):
    fields = {
        "client_id": client_id, "city": "Mumbai", "site_condition": "level", "soil_type": "normal",
        "building_status": "open_air", "site_access": "good", "power_available": "yes",
        "water_available": True, "package": "standard", **extra,
    }
    res = client.post("/projects", json=fields, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()["id"]


def _add_project_sport(client, headers, project_id, sport_key="badminton"):
    sport_id = next(s["id"] for s in client.get("/sports", headers=headers).json() if s["key"] == sport_key)
    res = client.post(
        f"/projects/{project_id}/sports", json={"sport_id": sport_id, "building_status": "open_air"}, headers=headers
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]


def _verified_cost_sheet(client, headers, project_id, cost_total=850000):
    cost_sheet_id = client.post(
        f"/projects/{project_id}/cost-sheets", json={"cost_total": cost_total}, headers=headers
    ).json()["id"]
    res = client.post(f"/cost-sheets/{cost_sheet_id}/verify", headers=headers)
    assert res.status_code == 200, res.text
    return cost_sheet_id


def _sent_estimate(client, headers, project_id, project_sport_id, cost_for_option=850000):
    estimate = client.post(
        f"/projects/{project_id}/estimates",
        json={"options": [{"project_sport_id": project_sport_id, "package": "standard", "cost_for_option": cost_for_option}]},
        headers=headers,
    ).json()
    res = client.post(f"/estimates/{estimate['id']}/send", headers=headers)
    assert res.status_code == 200, res.text
    return res.json()


def _approve_option(client, headers, estimate_id, option_id):
    res = client.patch(
        f"/estimates/{estimate_id}/options/{option_id}/client-status",
        json={"client_status": "approved", "waive_evidence_reason": "test setup"},
        headers=headers,
    )
    assert res.status_code == 200, res.text


def _released_quotation(client, headers, project_id, estimate_id, option_id):
    quotation = client.post(
        f"/projects/{project_id}/quotations",
        json={"estimate_id": estimate_id, "included_option_ids": [option_id]},
        headers=headers,
    ).json()
    res = client.post(f"/quotations/{quotation['id']}/release", headers=headers)
    assert res.status_code == 200, res.text
    return res.json()


def _won_opportunity_for(client, headers, client_id, lead_name):
    """A Won Opportunity linked to the client -- the only way a project gets
    an opportunity_id (Amendment 44 Phase C)."""
    opp = client.post(
        "/opportunities", json={"lead_name": lead_name, "next_follow_up_date": "2099-01-01"}, headers=headers
    ).json()
    assert client.patch(f"/opportunities/{opp['id']}/stage", json={"stage": "won"}, headers=headers).status_code == 200
    res = client.patch(f"/opportunities/{opp['id']}/link-client", json={"client_id": client_id}, headers=headers)
    assert res.status_code == 200, res.text
    return opp["id"]


def _quotation_for_new_project(client, headers, client_name, lead_name=None):
    client_id = _create_client_record(client, headers, client_name)
    extra = {}
    if lead_name:
        extra["opportunity_id"] = _won_opportunity_for(client, headers, client_id, lead_name)
    project_id = _create_project(client, headers, client_id, **extra)
    project_sport_id = _add_project_sport(client, headers, project_id)
    _verified_cost_sheet(client, headers, project_id)
    estimate = _sent_estimate(client, headers, project_id, project_sport_id)
    option_id = estimate["options"][0]["id"]
    _approve_option(client, headers, estimate["id"], option_id)
    quotation = _released_quotation(client, headers, project_id, estimate["id"], option_id)
    return project_id, quotation


# ---------------------------------------------------------------------------
# GET /quotations
# ---------------------------------------------------------------------------


def test_director_lists_all_quotations_across_projects(client, director_user):
    headers = _director_headers(client, director_user)
    project_a, quotation_a = _quotation_for_new_project(client, headers, "All-Quotations Client A")
    project_b, quotation_b = _quotation_for_new_project(client, headers, "All-Quotations Client B")

    res = client.get("/quotations", headers=headers)
    assert res.status_code == 200, res.text
    doc_nos = {row["document_no"] for row in res.json()}
    assert quotation_a["document_no"] in doc_nos
    assert quotation_b["document_no"] in doc_nos

    row_a = next(r for r in res.json() if r["document_no"] == quotation_a["document_no"])
    assert row_a["project_id"] == project_a
    assert row_a["client_name"] == "All-Quotations Client A"
    assert row_a["sports"] == ["Badminton"]
    assert row_a["status"] == "released"
    # Director sees the full K.3 figures.
    assert row_a["cost_total"] is not None
    assert row_a["margin_percent"] is not None
    assert row_a["below_floor"] is not None


def test_sales_can_list_quotations_but_without_cost_margin_or_floor(client, director_user, db_session):
    director = _director_headers(client, director_user)
    project_id, quotation = _quotation_for_new_project(client, director, "Sales View Client")

    sales = _sales_headers(client, db_session)
    res = client.get("/quotations", headers=sales)
    assert res.status_code == 200, res.text
    row = next(r for r in res.json() if r["document_no"] == quotation["document_no"])

    # K.3: the same fields the per-project view strips for Sales are absent...
    assert row["cost_total"] is None
    assert row["margin_percent"] is None
    assert row["below_floor"] is None
    # ...while the client-facing price stays visible.
    assert row["quotation_total"] > 0
    assert row["selling_after_discount"] > 0
    assert row["client_name"] == "Sales View Client"
    # And it agrees with what Sales already sees on the project's own quotation.
    per_project = client.get(f"/projects/{project_id}/quotations", headers=sales).json()[0]
    assert per_project["cost_total"] is None and per_project["margin_percent"] is None
    assert per_project["quotation_total"] == row["quotation_total"]


def test_pm_sees_cost_and_margin_in_the_list(client, director_user, db_session):
    director = _director_headers(client, director_user)
    _project, quotation = _quotation_for_new_project(client, director, "PM View Client")

    pm = _role_headers(client, db_session, UserRole.PM, "pm-qa@test.local")
    res = client.get("/quotations", headers=pm)
    assert res.status_code == 200, res.text
    row = next(r for r in res.json() if r["document_no"] == quotation["document_no"])
    assert row["cost_total"] is not None
    assert row["margin_percent"] is not None
    assert row["below_floor"] is not None


def test_other_roles_still_cannot_list_quotations(client, db_session):
    for role, email in (
        (UserRole.PROCUREMENT, "procurement-qa@test.local"),
        (UserRole.SITE_ENGINEER, "engineer-qa@test.local"),
        (UserRole.CA_TAX, "catax-qa@test.local"),
    ):
        headers = _role_headers(client, db_session, role, email)
        assert client.get("/quotations", headers=headers).status_code == 403, role


def test_sales_pending_list_matches_the_overview_tile(client, director_user, db_session):
    """Amendment 49: the Overview's 'Pending quotations' tile becomes a link
    to this list for Sales/PM, so the two numbers must agree."""
    director = _director_headers(client, director_user)
    _quotation_for_new_project(client, director, "Tile Match Client A")
    _quotation_for_new_project(client, director, "Tile Match Client B")

    sales = _sales_headers(client, db_session)
    listed = client.get("/quotations", params={"status_group": "pending"}, headers=sales).json()
    tile = client.get("/dashboard", headers=sales).json()["summary"]["pending_quotations_count"]
    assert len(listed) == tile


def test_row_names_the_originating_lead_only_when_there_is_one(client, director_user):
    headers = _director_headers(client, director_user)
    _p1, with_lead = _quotation_for_new_project(client, headers, "Lead Link Client", lead_name="Coach Ramesh")
    _p2, without_lead = _quotation_for_new_project(client, headers, "No Lead Client")

    rows = {r["document_no"]: r for r in client.get("/quotations", headers=headers).json()}
    assert rows[with_lead["document_no"]]["lead_name"] == "Coach Ramesh"
    assert rows[with_lead["document_no"]]["opportunity_id"] is not None
    assert rows[without_lead["document_no"]]["lead_name"] is None
    assert rows[without_lead["document_no"]]["opportunity_id"] is None


def test_lead_fields_are_visible_to_sales_too(client, director_user, db_session):
    director = _director_headers(client, director_user)
    _p, quotation = _quotation_for_new_project(client, director, "Sales Lead View Client", lead_name="Principal Mehta")

    sales = _sales_headers(client, db_session)
    rows = client.get("/quotations", headers=sales).json()
    row = next(r for r in rows if r["document_no"] == quotation["document_no"])
    assert row["lead_name"] == "Principal Mehta"


def test_quotations_require_auth(client):
    assert client.get("/quotations").status_code == 401


def test_filter_by_project_id_returns_only_that_project(client, director_user):
    headers = _director_headers(client, director_user)
    project_a, quotation_a = _quotation_for_new_project(client, headers, "Filter Client A")
    _project_b, quotation_b = _quotation_for_new_project(client, headers, "Filter Client B")

    res = client.get("/quotations", params={"project_id": project_a}, headers=headers)
    assert res.status_code == 200, res.text
    doc_nos = {row["document_no"] for row in res.json()}
    assert quotation_a["document_no"] in doc_nos
    assert quotation_b["document_no"] not in doc_nos


def test_filter_by_status(client, director_user):
    headers = _director_headers(client, director_user)
    _project, quotation = _quotation_for_new_project(client, headers, "Status Filter Client")

    released = client.get("/quotations", params={"status": "released"}, headers=headers).json()
    assert quotation["document_no"] in {r["document_no"] for r in released}

    won = client.get("/quotations", params={"status": "won"}, headers=headers).json()
    assert quotation["document_no"] not in {r["document_no"] for r in won}


def test_status_group_pending_matches_dashboard_definition(client, director_user):
    """Amendment 12 (Section 11): 'Pending Quotation' nav shortcut --
    status_group=pending must match dashboard.py's own DRAFT/RELEASED/
    SENT definition exactly, and never include a WON one."""
    headers = _director_headers(client, director_user)
    _project, released = _quotation_for_new_project(client, headers, "Status Group Pending Client")

    pending = client.get("/quotations", params={"status_group": "pending"}, headers=headers).json()
    assert released["document_no"] in {r["document_no"] for r in pending}

    client.post(f"/quotations/{released['id']}/send", headers=headers)
    won_res = client.post(
        f"/quotations/{released['id']}/mark-won",
        json={"waive_evidence_reason": "test setup"},
        headers=headers,
    )
    assert won_res.status_code == 200, won_res.text

    pending_after = client.get("/quotations", params={"status_group": "pending"}, headers=headers).json()
    assert released["document_no"] not in {r["document_no"] for r in pending_after}

    old_after = client.get("/quotations", params={"status_group": "old"}, headers=headers).json()
    assert released["document_no"] in {r["document_no"] for r in old_after}


def test_explicit_status_takes_priority_over_status_group(client, director_user):
    headers = _director_headers(client, director_user)
    _project, quotation = _quotation_for_new_project(client, headers, "Status Priority Client")

    # status=released with a contradictory status_group=old -- explicit
    # status should win, matching a single-select dropdown UI's own
    # expectation that a concrete choice always overrides a quick filter.
    res = client.get(
        "/quotations", params={"status": "released", "status_group": "old"}, headers=headers
    ).json()
    assert quotation["document_no"] in {r["document_no"] for r in res}


# ---------------------------------------------------------------------------
# GET /quotations/export
# ---------------------------------------------------------------------------


def test_export_csv_contains_the_filtered_quotation(client, director_user):
    headers = _director_headers(client, director_user)
    _project, quotation = _quotation_for_new_project(client, headers, "CSV Export Client")

    res = client.get("/quotations/export", headers=headers)
    assert res.status_code == 200, res.text
    assert res.headers["content-type"].startswith("text/csv")
    body = res.text
    assert quotation["document_no"] in body
    assert "CSV Export Client" in body


def test_sales_cannot_export_all_quotations(client, db_session):
    headers = _sales_headers(client, db_session)
    res = client.get("/quotations/export", headers=headers)
    assert res.status_code == 403


def test_pm_cannot_export_all_quotations(client, db_session):
    """Amendment 49: the list opened to Sales/PM, the CSV export did not --
    it is a bulk dump of the cost/margin fields."""
    headers = _role_headers(client, db_session, UserRole.PM, "pm-export-qa@test.local")
    assert client.get("/quotations/export", headers=headers).status_code == 403
