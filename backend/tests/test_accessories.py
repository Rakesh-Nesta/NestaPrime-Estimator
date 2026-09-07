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
        name="Test Sales", email="sales@test.local", hashed_password=hash_password("TestPass!1"), role=UserRole.SALES
    )
    db_session.add(user)
    db_session.commit()
    return _login(client, "sales@test.local")


def _create_client_record(client, headers):
    res = client.post("/clients", json={"name": "Accessories Client", "type": "school"}, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()["id"]


def _create_project(client, headers, client_id):
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
    }
    res = client.post("/projects", json=fields, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()["id"]


def _add_project_sport(client, headers, project_id, sport_key="badminton", number_of_courts=1):
    sport_id = next(s["id"] for s in client.get("/sports", headers=headers).json() if s["key"] == sport_key)
    res = client.post(
        f"/projects/{project_id}/sports",
        json={"sport_id": sport_id, "building_status": "open_air", "number_of_courts": number_of_courts},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]


def _setup(client, headers, sport_key="badminton", number_of_courts=1):
    client_id = _create_client_record(client, headers)
    project_id = _create_project(client, headers, client_id)
    project_sport_id = _add_project_sport(client, headers, project_id, sport_key=sport_key, number_of_courts=number_of_courts)
    cost_sheet_id = client.post(f"/projects/{project_id}/cost-sheets", json={}, headers=headers).json()["id"]
    return project_id, project_sport_id, cost_sheet_id


def test_sales_cannot_add_accessories(client, director_user, db_session):
    director_headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, director_headers)

    sales_headers = _sales_headers(client, db_session)
    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/accessories",
        json={"project_sport_id": project_sport_id, "rates": {"Badminton net + post set": 8000}},
        headers=sales_headers,
    )
    assert res.status_code == 403


def test_catalog_quantity_for_single_court(client, director_user):
    headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, headers, sport_key="badminton")

    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/accessories",
        json={"project_sport_id": project_sport_id, "rates": {"Badminton net + post set": 8000}},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    lines = res.json()["lines"]
    assert len(lines) == 1
    assert lines[0]["item_name"] == "Badminton net + post set"
    assert lines[0]["quantity"] == 1
    assert lines[0]["rate"] == 8000
    assert lines[0]["work_package"] == "accessories"
    assert lines[0]["labour_category_id"] is None


def test_catalog_quantity_scales_with_number_of_courts(client, director_user):
    """Module 9's per-court items multiply by the sport selection's own
    number_of_courts (Module 1) -- 2 basketball goals per court, 3 courts
    -> 6 goals."""
    headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, headers, sport_key="basketball_outdoor", number_of_courts=3)

    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/accessories",
        json={"project_sport_id": project_sport_id, "rates": {"Basketball goal (backboard + ring)": 25000}},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    lines = res.json()["lines"]
    assert len(lines) == 1
    assert lines[0]["quantity"] == 6
    assert res.json()["breakdown"]["number_of_courts"] == 3


def test_sport_with_multiple_catalog_items(client, director_user):
    headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, headers, sport_key="padel")

    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/accessories",
        json={
            "project_sport_id": project_sport_id,
            "rates": {"Padel glass wall/door panel set": 150000, "Padel net": 12000},
        },
        headers=headers,
    )
    assert res.status_code == 201, res.text
    items = {line["item_name"] for line in res.json()["lines"]}
    assert items == {"Padel glass wall/door panel set", "Padel net"}


def test_missing_rate_for_a_catalog_item_is_rejected(client, director_user):
    headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, headers, sport_key="padel")

    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/accessories",
        json={"project_sport_id": project_sport_id, "rates": {"Padel net": 12000}},
        headers=headers,
    )
    assert res.status_code == 422
    assert "Padel glass wall/door panel set" in res.json()["detail"]


def test_sport_without_a_catalog_entry_requires_custom_items(client, director_user):
    """Squash has no Module 9 catalog entry -- requesting accessories with
    nothing supplied must be rejected, not silently produce zero lines."""
    headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, headers, sport_key="squash")

    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/accessories",
        json={"project_sport_id": project_sport_id},
        headers=headers,
    )
    assert res.status_code == 422
    assert "No accessories catalog for Squash" in res.json()["detail"]

    with_custom = client.post(
        f"/cost-sheets/{cost_sheet_id}/accessories",
        json={
            "project_sport_id": project_sport_id,
            "custom_items": [{"item_name": "Scoreboard", "unit": "nos", "quantity": 1, "rate": 15000}],
        },
        headers=headers,
    )
    assert with_custom.status_code == 201, with_custom.text
    assert with_custom.json()["lines"][0]["item_name"] == "Scoreboard"


def test_custom_items_add_alongside_catalog_items(client, director_user):
    """A sport with a catalog can still add an extra like an umpire chair
    via custom_items, on top of its auto-generated items."""
    headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, headers, sport_key="tennis")

    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/accessories",
        json={
            "project_sport_id": project_sport_id,
            "rates": {"Tennis net + post set": 20000},
            "custom_items": [{"item_name": "Umpire chair", "unit": "nos", "quantity": 1, "rate": 18000}],
        },
        headers=headers,
    )
    assert res.status_code == 201, res.text
    items = {line["item_name"] for line in res.json()["lines"]}
    assert items == {"Tennis net + post set", "Umpire chair"}


def test_accessories_can_only_be_added_to_a_draft_cost_sheet(client, director_user):
    headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, headers, sport_key="badminton")
    client.post(
        f"/cost-sheets/{cost_sheet_id}/accessories",
        json={"project_sport_id": project_sport_id, "rates": {"Badminton net + post set": 8000}},
        headers=headers,
    )
    client.post(f"/cost-sheets/{cost_sheet_id}/recompute", headers=headers)
    client.post(f"/cost-sheets/{cost_sheet_id}/verify", headers=headers)

    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/accessories",
        json={"project_sport_id": project_sport_id, "rates": {"Badminton net + post set": 8000}},
        headers=headers,
    )
    assert res.status_code == 400


def test_accessories_feed_into_recompute_with_two_percent_contingency(client, director_user):
    """K.1 step 6: accessories carry a 2% contingency work-package."""
    headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, headers, sport_key="badminton")
    client.post(
        f"/cost-sheets/{cost_sheet_id}/accessories",
        json={"project_sport_id": project_sport_id, "rates": {"Badminton net + post set": 8000}},
        headers=headers,
    )

    recomputed = client.post(f"/cost-sheets/{cost_sheet_id}/recompute", headers=headers).json()
    assert recomputed["cost_total"] > 8000  # material + labour fallback + contingency, all above the raw material cost
    verify_res = client.post(f"/cost-sheets/{cost_sheet_id}/verify", headers=headers)
    assert verify_res.status_code == 200


def test_wrong_project_sport_is_rejected(client, director_user):
    headers = _director_headers(client, director_user)
    _, _, cost_sheet_id = _setup(client, headers, sport_key="badminton")

    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/accessories",
        json={
            "project_sport_id": "00000000-0000-0000-0000-000000000000",
            "rates": {"Badminton net + post set": 8000},
        },
        headers=headers,
    )
    assert res.status_code == 404
