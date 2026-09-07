import math

from app.core.security import hash_password
from app.models.user import User, UserRole

FT_TO_M = 0.3048


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
    res = client.post("/clients", json={"name": "F.4 Natural Grass Client", "type": "school"}, headers=headers)
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


def _add_project_sport(client, headers, project_id, sport_key):
    sport_id = next(s["id"] for s in client.get("/sports", headers=headers).json() if s["key"] == sport_key)
    res = client.post(
        f"/projects/{project_id}/sports",
        json={"sport_id": sport_id, "building_status": "open_air"},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]


def _setup(client, headers, sport_key):
    client_id = _create_client_record(client, headers)
    project_id = _create_project(client, headers, client_id)
    project_sport_id = _add_project_sport(client, headers, project_id, sport_key)
    cost_sheet_id = client.post(f"/projects/{project_id}/cost-sheets", json={}, headers=headers).json()["id"]
    return project_id, project_sport_id, cost_sheet_id


# ---------------------------------------------------------------------------
# F.4 Natural grass & irrigation
# ---------------------------------------------------------------------------


def test_sales_cannot_add_natural_grass(client, director_user, db_session):
    director_headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, director_headers, "football_11")

    sales_headers = _sales_headers(client, db_session)
    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/flooring/natural-grass",
        json={
            "project_sport_id": project_sport_id,
            "topsoil_rate_per_cum": 1200,
            "cover_rate_per_sqm": 150,
            "sprinkler_rate_each": 2500,
            "pump_rate": 45000,
            "tank_rate": 60000,
        },
        headers=sales_headers,
    )
    assert res.status_code == 403


def test_natural_grass_default_sod_produces_five_lines(client, director_user):
    """F.4: 'Topsoil 6in + sand amendment -> sod -> pop-up sprinklers grid
    12m -> pump + 10,000L tank' over football_11's own 360 x 240 ft build
    footprint."""
    headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, headers, "football_11")

    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/flooring/natural-grass",
        json={
            "project_sport_id": project_sport_id,
            "topsoil_rate_per_cum": 1200,
            "cover_rate_per_sqm": 150,
            "sprinkler_rate_each": 2500,
            "pump_rate": 45000,
            "tank_rate": 60000,
        },
        headers=headers,
    )
    assert res.status_code == 201, res.text
    body = res.json()

    L_m = 360 * FT_TO_M
    W_m = 240 * FT_TO_M
    area_sqm = L_m * W_m
    topsoil_volume_cum = area_sqm * (6 * 0.0254)
    sprinkler_count = math.ceil(L_m / 12.0) * math.ceil(W_m / 12.0)

    assert body["breakdown"]["area_sqm"] == round(area_sqm, 2)
    assert body["breakdown"]["topsoil_volume_cum"] == round(topsoil_volume_cum, 3)
    assert body["breakdown"]["sprinkler_count"] == sprinkler_count
    assert "maintenance_note" in body["breakdown"]

    lines = body["lines"]
    assert len(lines) == 5
    item_names = {line["item_name"] for line in lines}
    assert item_names == {
        "Topsoil (6in) + sand amendment",
        "Sod",
        f"Pop-up sprinklers @ 12m grid",
        "Irrigation pump",
        "Water tank (10,000 L)",
    }

    topsoil = next(line for line in lines if "Topsoil" in line["item_name"])
    assert topsoil["unit"] == "cum"
    assert topsoil["quantity"] == round(topsoil_volume_cum, 3)
    assert topsoil["work_package"] == "flooring"

    sprinklers = next(line for line in lines if "sprinkler" in line["item_name"])
    assert sprinklers["unit"] == "nos"
    assert sprinklers["quantity"] == sprinkler_count

    pump = next(line for line in lines if line["item_name"] == "Irrigation pump")
    assert pump["unit"] == "set" and pump["quantity"] == 1

    tank = next(line for line in lines if "Water tank" in line["item_name"])
    assert tank["unit"] == "set" and tank["quantity"] == 1
    assert tank["rate"] == 60000


def test_natural_grass_seed_cover_uses_seed_label(client, director_user):
    """F.4: '(or seed, 6-8 wks)' -- seed is an alternative to sod, not an
    additional line."""
    headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, headers, "football_7")

    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/flooring/natural-grass",
        json={
            "project_sport_id": project_sport_id,
            "cover_type": "seed",
            "topsoil_rate_per_cum": 1200,
            "cover_rate_per_sqm": 40,
            "sprinkler_rate_each": 2500,
            "pump_rate": 45000,
            "tank_rate": 60000,
        },
        headers=headers,
    )
    assert res.status_code == 201, res.text
    lines = res.json()["lines"]
    assert len(lines) == 5
    cover_line = next(line for line in lines if line["item_name"].startswith("Seed"))
    assert cover_line["item_name"] == "Seed (6-8 week germination)"


def test_natural_grass_requires_all_rates(client, director_user):
    headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, headers, "football_11")

    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/flooring/natural-grass",
        json={"project_sport_id": project_sport_id, "topsoil_rate_per_cum": 1200},
        headers=headers,
    )
    assert res.status_code == 422


def test_natural_grass_custom_sprinkler_spacing_changes_count(client, director_user):
    headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, headers, "football_11")

    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/flooring/natural-grass",
        json={
            "project_sport_id": project_sport_id,
            "topsoil_rate_per_cum": 1200,
            "cover_rate_per_sqm": 150,
            "sprinkler_spacing_m": 20,
            "sprinkler_rate_each": 2500,
            "pump_rate": 45000,
            "tank_rate": 60000,
        },
        headers=headers,
    )
    assert res.status_code == 201, res.text
    L_m = 360 * FT_TO_M
    W_m = 240 * FT_TO_M
    expected_count = math.ceil(L_m / 20.0) * math.ceil(W_m / 20.0)
    assert res.json()["breakdown"]["sprinkler_count"] == expected_count


def test_natural_grass_draft_only_guard(client, director_user):
    headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, headers, "football_11")
    payload = {
        "project_sport_id": project_sport_id,
        "topsoil_rate_per_cum": 1200,
        "cover_rate_per_sqm": 150,
        "sprinkler_rate_each": 2500,
        "pump_rate": 45000,
        "tank_rate": 60000,
    }
    client.post(f"/cost-sheets/{cost_sheet_id}/flooring/natural-grass", json=payload, headers=headers)
    client.post(f"/cost-sheets/{cost_sheet_id}/recompute", headers=headers)
    client.post(f"/cost-sheets/{cost_sheet_id}/verify", headers=headers)

    res = client.post(f"/cost-sheets/{cost_sheet_id}/flooring/natural-grass", json=payload, headers=headers)
    assert res.status_code == 400


def test_natural_grass_recompute_and_verify_integration(client, director_user):
    headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, headers, "football_11")

    client.post(
        f"/cost-sheets/{cost_sheet_id}/flooring/natural-grass",
        json={
            "project_sport_id": project_sport_id,
            "topsoil_rate_per_cum": 1200,
            "cover_rate_per_sqm": 150,
            "sprinkler_rate_each": 2500,
            "pump_rate": 45000,
            "tank_rate": 60000,
        },
        headers=headers,
    )
    recomputed = client.post(f"/cost-sheets/{cost_sheet_id}/recompute", headers=headers)
    assert recomputed.status_code == 200, recomputed.text
    assert recomputed.json()["cost_total"] > 0


# ---------------------------------------------------------------------------
# F.4 Hockey water-based turf irrigation
# ---------------------------------------------------------------------------


def test_sales_cannot_add_hockey_irrigation(client, director_user, db_session):
    director_headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, director_headers, "hockey_turf")

    sales_headers = _sales_headers(client, db_session)
    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/flooring/hockey-irrigation",
        json={"project_sport_id": project_sport_id, "cannon_rate_each": 80000, "pump_rate": 60000, "tank_rate": 120000},
        headers=sales_headers,
    )
    assert res.status_code == 403


def test_hockey_irrigation_defaults_to_six_cannons(client, director_user):
    """F.4: 'Hockey water-based turf: sprinkler cannons x6 + 50,000L
    tank + pump.'"""
    headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, headers, "hockey_turf")

    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/flooring/hockey-irrigation",
        json={"project_sport_id": project_sport_id, "cannon_rate_each": 80000, "pump_rate": 60000, "tank_rate": 120000},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["breakdown"]["cannon_count"] == 6

    lines = body["lines"]
    assert len(lines) == 3
    cannon = next(line for line in lines if line["item_name"] == "Sprinkler cannon")
    assert cannon["quantity"] == 6 and cannon["unit"] == "nos" and cannon["rate"] == 80000

    tank = next(line for line in lines if "Water tank" in line["item_name"])
    assert tank["item_name"] == "Water tank (50,000 L)"
    assert tank["quantity"] == 1 and tank["rate"] == 120000

    pump = next(line for line in lines if line["item_name"] == "Irrigation pump")
    assert pump["quantity"] == 1 and pump["rate"] == 60000


def test_hockey_irrigation_cannon_count_overridable(client, director_user):
    headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, headers, "hockey_turf")

    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/flooring/hockey-irrigation",
        json={
            "project_sport_id": project_sport_id,
            "cannon_count": 8,
            "cannon_rate_each": 80000,
            "pump_rate": 60000,
            "tank_rate": 120000,
        },
        headers=headers,
    )
    assert res.status_code == 201, res.text
    assert res.json()["breakdown"]["cannon_count"] == 8
    cannon = next(line for line in res.json()["lines"] if line["item_name"] == "Sprinkler cannon")
    assert cannon["quantity"] == 8


def test_hockey_irrigation_requires_all_rates(client, director_user):
    headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, headers, "hockey_turf")

    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/flooring/hockey-irrigation",
        json={"project_sport_id": project_sport_id, "cannon_rate_each": 80000},
        headers=headers,
    )
    assert res.status_code == 422


def test_hockey_irrigation_draft_only_guard(client, director_user):
    headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, headers, "hockey_turf")
    payload = {"project_sport_id": project_sport_id, "cannon_rate_each": 80000, "pump_rate": 60000, "tank_rate": 120000}
    client.post(f"/cost-sheets/{cost_sheet_id}/flooring/hockey-irrigation", json=payload, headers=headers)
    client.post(f"/cost-sheets/{cost_sheet_id}/recompute", headers=headers)
    client.post(f"/cost-sheets/{cost_sheet_id}/verify", headers=headers)

    res = client.post(f"/cost-sheets/{cost_sheet_id}/flooring/hockey-irrigation", json=payload, headers=headers)
    assert res.status_code == 400
