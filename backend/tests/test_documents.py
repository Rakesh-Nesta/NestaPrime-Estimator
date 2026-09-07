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
        name="Test Sales",
        email="sales@test.local",
        hashed_password=hash_password("TestPass!1"),
        role=UserRole.SALES,
    )
    db_session.add(user)
    db_session.commit()
    return _login(client, "sales@test.local")


def _create_client_record(client, headers, client_type="school", name="Test School"):
    res = client.post("/clients", json={"name": name, "type": client_type}, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()["id"]


def _create_project(client, headers, client_id, **overrides):
    fields = {
        "client_id": client_id,
        "city": "Mumbai",
        "site_condition": "level",
        "soil_type": "normal",
        "building_status": "open_air",
        "site_access": "good",
        "power_available": "yes",
        "water_available": True,
        "package": "standard",
        **overrides,
    }
    res = client.post("/projects", json=fields, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()["id"]


def _add_project_sport(client, headers, project_id, sport_key="badminton", building_status="open_air"):
    sport_id = next(s["id"] for s in client.get("/sports", headers=headers).json() if s["key"] == sport_key)
    res = client.post(
        f"/projects/{project_id}/sports",
        json={"sport_id": sport_id, "building_status": building_status},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]


def _verified_cost_sheet(client, headers, project_id, cost_total=850000):
    create_res = client.post(f"/projects/{project_id}/cost-sheets", json={"cost_total": cost_total}, headers=headers)
    assert create_res.status_code == 201, create_res.text
    cost_sheet_id = create_res.json()["id"]
    verify_res = client.post(f"/cost-sheets/{cost_sheet_id}/verify", headers=headers)
    assert verify_res.status_code == 200, verify_res.text
    return verify_res.json()


def _full_project_setup(client, headers, client_type="government"):
    client_id = _create_client_record(client, headers, client_type=client_type, name="Municipal Corp")
    project_id = _create_project(client, headers, client_id)
    project_sport_id = _add_project_sport(client, headers, project_id)
    return project_id, project_sport_id


# ---------------------------------------------------------------------------
# Cost Sheets
# ---------------------------------------------------------------------------


def test_cost_sheet_numbering_reuses_project_suffix(client, director_user):
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers)
    project_id = _create_project(client, headers, client_id)
    project_no = client.get(f"/projects/{project_id}", headers=headers).json()["project_no"]

    cs = _verified_cost_sheet(client, headers, project_id)
    expected_suffix = project_no.split("-", 1)[1]
    assert cs["document_no"] == f"CS-{expected_suffix}-R1"
    assert cs["status"] == "verified"


def test_only_one_active_cost_sheet_per_project(client, director_user):
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers)
    project_id = _create_project(client, headers, client_id)
    client.post(f"/projects/{project_id}/cost-sheets", json={"cost_total": 100000}, headers=headers)

    res = client.post(f"/projects/{project_id}/cost-sheets", json={"cost_total": 200000}, headers=headers)
    assert res.status_code == 400


def test_revising_a_verified_cost_sheet_creates_r2_and_supersedes_r1(client, director_user):
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers)
    project_id = _create_project(client, headers, client_id)
    cs1 = _verified_cost_sheet(client, headers, project_id, cost_total=100000)

    revise_res = client.post(f"/cost-sheets/{cs1['id']}/revise", json={"cost_total": 150000}, headers=headers)
    assert revise_res.status_code == 201, revise_res.text
    cs2 = revise_res.json()
    assert cs2["revision_major"] == 2
    assert cs2["status"] == "draft"
    assert cs2["document_no"].endswith("-R2")

    old = client.get(f"/cost-sheets/{cs1['id']}", headers=headers).json()
    assert old["status"] == "superseded"


def test_cannot_revise_a_draft_cost_sheet(client, director_user):
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers)
    project_id = _create_project(client, headers, client_id)
    create_res = client.post(f"/projects/{project_id}/cost-sheets", json={"cost_total": 100000}, headers=headers)

    res = client.post(f"/cost-sheets/{create_res.json()['id']}/revise", json={"cost_total": 150000}, headers=headers)
    assert res.status_code == 400


def test_sales_cannot_access_cost_sheets(client, db_session):
    headers = _sales_headers(client, db_session)
    res = client.get("/projects/00000000-0000-0000-0000-000000000000/cost-sheets", headers=headers)
    assert res.status_code == 403


# ---------------------------------------------------------------------------
# Estimates
# ---------------------------------------------------------------------------


def test_estimate_cannot_be_created_without_verified_cost_sheet(client, director_user):
    """M.2 rule 1."""
    headers = _director_headers(client, director_user)
    project_id, project_sport_id = _full_project_setup(client, headers, client_type="school")

    res = client.post(
        f"/projects/{project_id}/estimates",
        json={"options": [{"project_sport_id": project_sport_id, "package": "standard", "cost_for_option": 100000}]},
        headers=headers,
    )
    assert res.status_code == 400


def test_estimate_option_price_range_is_gst_inclusive_five_percent_band(client, director_user):
    """M.1: price = cost group at target margin; M.6: GST-inclusive;
    M.1: range_pct 5%. Government target margin is 15% (floor 12 + 3).
    cost 850000 -> selling ex-GST 1,000,000 -> incl GST 1,180,000 ->
    band [1,121,000 , 1,239,000]."""
    headers = _director_headers(client, director_user)
    project_id, project_sport_id = _full_project_setup(client, headers, client_type="government")
    _verified_cost_sheet(client, headers, project_id, cost_total=1)  # unused cost sheet, just to satisfy the gate

    res = client.post(
        f"/projects/{project_id}/estimates",
        json={"options": [{"project_sport_id": project_sport_id, "package": "standard", "cost_for_option": 850000}]},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    option = res.json()["options"][0]
    assert round(option["price_low"], 2) == 1121000.00
    assert round(option["price_high"], 2) == 1239000.00
    assert option["client_status"] == "pending"


def test_estimate_document_number_and_client_status_derivation(client, director_user):
    headers = _director_headers(client, director_user)
    project_id, project_sport_id = _full_project_setup(client, headers, client_type="school")
    project_no = client.get(f"/projects/{project_id}", headers=headers).json()["project_no"]
    _verified_cost_sheet(client, headers, project_id)

    res = client.post(
        f"/projects/{project_id}/estimates",
        json={"options": [{"project_sport_id": project_sport_id, "package": "standard", "cost_for_option": 100000}]},
        headers=headers,
    )
    body = res.json()
    expected_suffix = project_no.split("-", 1)[1]
    assert body["document_no"] == f"EST-{expected_suffix}-R1"
    assert body["client_status"] == "pending"  # M.4a #7: no options approved yet


def test_sales_cannot_create_estimate_but_can_view_it_without_cost(client, db_session, director_user):
    """This build restricts Estimate creation to PM/Director (a per-option
    cost figure must be entered, and Sales must never see cost -- K.3);
    Sales can still view the Estimate afterward with cost stripped."""
    director_headers = _director_headers(client, director_user)
    project_id, project_sport_id = _full_project_setup(client, director_headers, client_type="school")
    _verified_cost_sheet(client, director_headers, project_id)

    sales_headers = _sales_headers(client, db_session)
    create_attempt = client.post(
        f"/projects/{project_id}/estimates",
        json={"options": [{"project_sport_id": project_sport_id, "package": "standard", "cost_for_option": 100000}]},
        headers=sales_headers,
    )
    assert create_attempt.status_code == 403

    create_res = client.post(
        f"/projects/{project_id}/estimates",
        json={"options": [{"project_sport_id": project_sport_id, "package": "standard", "cost_for_option": 100000}]},
        headers=director_headers,
    )
    estimate_id = create_res.json()["id"]

    sales_view = client.get(f"/estimates/{estimate_id}", headers=sales_headers)
    assert sales_view.status_code == 200
    assert sales_view.json()["options"][0]["cost_for_option"] is None
    assert sales_view.json()["options"][0]["price_low"] is not None


def test_estimate_send_sets_status_and_fifteen_day_validity(client, director_user):
    headers = _director_headers(client, director_user)
    project_id, project_sport_id = _full_project_setup(client, headers, client_type="school")
    _verified_cost_sheet(client, headers, project_id)
    estimate = client.post(
        f"/projects/{project_id}/estimates",
        json={"options": [{"project_sport_id": project_sport_id, "package": "standard", "cost_for_option": 100000}]},
        headers=headers,
    ).json()

    res = client.post(f"/estimates/{estimate['id']}/send", headers=headers)
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "sent"
    assert body["sent_at"] is not None
    assert body["expires_at"] is not None


def test_sales_can_record_client_status_on_option(client, db_session, director_user):
    """M.4: Sales may record Client approved/demand/rejected. M.3: needs an
    approval_evidence attachment first (Sales can upload one, e.g. a
    WhatsApp screenshot of the client's approval)."""
    director_headers = _director_headers(client, director_user)
    project_id, project_sport_id = _full_project_setup(client, director_headers, client_type="school")
    _verified_cost_sheet(client, director_headers, project_id)
    estimate = client.post(
        f"/projects/{project_id}/estimates",
        json={"options": [{"project_sport_id": project_sport_id, "package": "standard", "cost_for_option": 100000}]},
        headers=director_headers,
    ).json()
    option_id = estimate["options"][0]["id"]

    sales_headers = _sales_headers(client, db_session)
    client.post(
        "/attachments",
        data={"doc_type": "estimate", "doc_id": estimate["id"], "tag": "approval_evidence", "approval_strength": "informal"},
        files={"file": ("whatsapp-screenshot.png", b"fake-image-bytes", "image/png")},
        headers=sales_headers,
    )
    res = client.patch(
        f"/estimates/{estimate['id']}/options/{option_id}/client-status",
        json={"client_status": "approved"},
        headers=sales_headers,
    )
    assert res.status_code == 200, res.text
    assert res.json()["client_status"] == "approved"
    assert res.json()["cost_for_option"] is None

    updated_estimate = client.get(f"/estimates/{estimate['id']}", headers=director_headers).json()
    assert updated_estimate["client_status"] == "approved"


# ---------------------------------------------------------------------------
# Quotations
# ---------------------------------------------------------------------------


def _approved_estimate(client, headers, client_type="government", cost_for_option=850000):
    project_id, project_sport_id = _full_project_setup(client, headers, client_type=client_type)
    _verified_cost_sheet(client, headers, project_id)
    estimate = client.post(
        f"/projects/{project_id}/estimates",
        json={"options": [{"project_sport_id": project_sport_id, "package": "standard", "cost_for_option": cost_for_option}]},
        headers=headers,
    ).json()
    option_id = estimate["options"][0]["id"]
    # M.3: approving without evidence needs a PM/Director waiver -- these
    # quotation-lifecycle tests aren't about evidence itself.
    client.patch(
        f"/estimates/{estimate['id']}/options/{option_id}/client-status",
        json={"client_status": "approved", "waive_evidence_reason": "test setup"},
        headers=headers,
    )
    return project_id, estimate["id"], option_id


def test_quotation_cannot_be_created_from_pending_option(client, director_user):
    """M.2 rule 2."""
    headers = _director_headers(client, director_user)
    project_id, project_sport_id = _full_project_setup(client, headers, client_type="school")
    _verified_cost_sheet(client, headers, project_id)
    estimate = client.post(
        f"/projects/{project_id}/estimates",
        json={"options": [{"project_sport_id": project_sport_id, "package": "standard", "cost_for_option": 100000}]},
        headers=headers,
    ).json()

    res = client.post(
        f"/projects/{project_id}/quotations",
        json={"estimate_id": estimate["id"], "included_option_ids": [estimate["options"][0]["id"]]},
        headers=headers,
    )
    assert res.status_code == 400


def test_quotation_matches_k2_worked_example_via_document_chain(client, director_user):
    """Government target margin 15% (floor 12 + 3): cost 850000 ->
    selling 1,000,000, margin 15.0%, markup implied -- reproduces K.2's
    own worked example end-to-end through the document chain."""
    headers = _director_headers(client, director_user)
    project_id, estimate_id, option_id = _approved_estimate(client, headers, cost_for_option=850000)

    res = client.post(
        f"/projects/{project_id}/quotations",
        json={"estimate_id": estimate_id, "included_option_ids": [option_id]},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert round(body["selling_price_ex_gst"], 2) == 1000000.00
    assert round(body["margin_percent"], 1) == 15.0
    assert round(body["quotation_total"], 2) == 1180000.00
    assert body["below_floor"] is False
    assert body["status"] == "draft"


def test_quotation_document_number_and_pm_can_release_above_floor(client, director_user):
    headers = _director_headers(client, director_user)
    project_id, estimate_id, option_id = _approved_estimate(client, headers)
    project_no = client.get(f"/projects/{project_id}", headers=headers).json()["project_no"]

    quotation = client.post(
        f"/projects/{project_id}/quotations",
        json={"estimate_id": estimate_id, "included_option_ids": [option_id]},
        headers=headers,
    ).json()
    expected_suffix = project_no.split("-", 1)[1]
    assert quotation["document_no"] == f"NPQ-{expected_suffix}-R1"

    release_res = client.post(f"/quotations/{quotation['id']}/release", headers=headers)
    assert release_res.status_code == 200
    assert release_res.json()["status"] == "released"


def test_pm_cannot_release_below_floor_quotation_only_director_can(client, director_user, db_session):
    """M.1: 'PM or Director release; Director if discount below floor.'"""
    from app.core.security import hash_password
    from app.models.user import User, UserRole

    director_headers = _director_headers(client, director_user)
    project_id, estimate_id, option_id = _approved_estimate(client, director_headers)

    # A large discount pushes margin below the 12% floor.
    quotation = client.post(
        f"/projects/{project_id}/quotations",
        json={
            "estimate_id": estimate_id,
            "included_option_ids": [option_id],
            "discount_type": "amount",
            "discount_value": 200000,
        },
        headers=director_headers,
    ).json()
    assert quotation["below_floor"] is True

    pm_user = User(
        name="Test PM", email="pm@test.local", hashed_password=hash_password("TestPass!1"), role=UserRole.PM
    )
    db_session.add(pm_user)
    db_session.commit()
    pm_headers = _login(client, "pm@test.local")

    pm_attempt = client.post(f"/quotations/{quotation['id']}/release", headers=pm_headers)
    assert pm_attempt.status_code == 403

    director_attempt = client.post(f"/quotations/{quotation['id']}/release", headers=director_headers)
    assert director_attempt.status_code == 200
    assert director_attempt.json()["status"] == "released"


def test_quotation_lifecycle_release_send_mark_won(client, director_user):
    headers = _director_headers(client, director_user)
    project_id, estimate_id, option_id = _approved_estimate(client, headers)
    quotation_id = client.post(
        f"/projects/{project_id}/quotations",
        json={"estimate_id": estimate_id, "included_option_ids": [option_id]},
        headers=headers,
    ).json()["id"]

    # Cannot send before release, cannot mark won before send.
    assert client.post(f"/quotations/{quotation_id}/send", headers=headers).status_code == 400
    assert client.post(f"/quotations/{quotation_id}/mark-won", json={}, headers=headers).status_code == 400

    client.post(f"/quotations/{quotation_id}/release", headers=headers)
    send_res = client.post(f"/quotations/{quotation_id}/send", headers=headers)
    assert send_res.status_code == 200
    assert send_res.json()["status"] == "sent"
    assert send_res.json()["expires_at"] is not None

    won_res = client.post(
        f"/quotations/{quotation_id}/mark-won",
        json={"reason": "Best offer", "waive_evidence_reason": "test setup"},
        headers=headers,
    )
    assert won_res.status_code == 200
    assert won_res.json()["status"] == "won"
    assert won_res.json()["won_lost_reason"] == "Best offer"


def test_quotation_can_be_marked_lost_with_reason(client, director_user):
    headers = _director_headers(client, director_user)
    project_id, estimate_id, option_id = _approved_estimate(client, headers)
    quotation_id = client.post(
        f"/projects/{project_id}/quotations",
        json={"estimate_id": estimate_id, "included_option_ids": [option_id]},
        headers=headers,
    ).json()["id"]
    client.post(f"/quotations/{quotation_id}/release", headers=headers)

    res = client.post(f"/quotations/{quotation_id}/mark-lost", json={"reason": "competitor"}, headers=headers)
    assert res.status_code == 200
    assert res.json()["status"] == "lost"
    assert res.json()["won_lost_reason"] == "competitor"


def test_sales_sees_quotation_without_cost_or_margin(client, db_session, director_user):
    director_headers = _director_headers(client, director_user)
    project_id, estimate_id, option_id = _approved_estimate(client, director_headers)
    quotation_id = client.post(
        f"/projects/{project_id}/quotations",
        json={"estimate_id": estimate_id, "included_option_ids": [option_id]},
        headers=director_headers,
    ).json()["id"]

    sales_headers = _sales_headers(client, db_session)
    res = client.get(f"/quotations/{quotation_id}", headers=sales_headers)
    assert res.status_code == 200
    body = res.json()
    assert body["cost_total"] is None
    assert body["margin_percent"] is None
    assert body["below_floor"] is None
    assert body["quotation_total"] is not None  # client-visible total is fine
