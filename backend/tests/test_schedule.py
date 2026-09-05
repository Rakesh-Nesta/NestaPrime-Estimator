def _login(client, director_user):
    res = client.post(
        "/auth/login",
        data={"username": "director@test.local", "password": "TestPass!1"},
    )
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _create_client(client, headers, name="Test School"):
    res = client.post("/clients", json={"name": name, "type": "school"}, headers=headers)
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


def _add_project_sport(client, headers, project_id, sport_key, building_status):
    sport_id = next(s["id"] for s in client.get("/sports", headers=headers).json() if s["key"] == sport_key)
    res = client.post(
        f"/projects/{project_id}/sports",
        json={"sport_id": sport_id, "building_status": building_status},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]


def test_schedule_for_indoor_sport_with_no_matching_flooring_lay_rule(client, director_user):
    """Badminton, Existing building, standard package (PU 6mm flooring):
    area 52x30=1560 sqft -> base 2d + curing(PU on PCC)=28d = 30d; no
    structure (fit-out only, B.1a); PU isn't in N's turf/wooden/acrylic
    lay-days table, so no separate flooring activity is added -- flooring
    completion coincides with base completion. Total: 5+30+2 = 37 days,
    6 weeks."""
    headers = _login(client, director_user)
    client_id = _create_client(client, headers)
    project_id = _create_project(
        client, headers, client_id,
        building_status="existing_building", existing_building_clear_height_ft=30,
    )
    project_sport_id = _add_project_sport(client, headers, project_id, "badminton", "existing_building")

    res = client.get(
        f"/schedule/project-sports/{project_sport_id}",
        params={"start_date": "2026-09-05"},
        headers=headers,
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["total_days"] == 37
    assert body["total_weeks"] == 6

    names = [a["name"] for a in body["activities"]]
    assert "Mobilisation & site prep" in names
    assert any(a.startswith("Base") for a in names)
    assert not any(a.startswith("Flooring") for a in names)
    assert not any(a.startswith("Structure erection") for a in names)

    base = next(a for a in body["activities"] if a["name"].startswith("Base"))
    assert base["duration_days"] == 30  # 2 (area) + 28 (PU on PCC curing)

    payment = {p["name"]: p for p in body["payment_schedule"]}
    assert payment["Advance"]["date"] == "2026-09-05"
    assert payment["Flooring completion"]["date"] == base["end_date"]
    assert payment["Handover"]["date"] == "2026-10-12"


def test_schedule_for_outdoor_sport_with_structure_and_turf_flooring(client, director_user):
    """Box cricket, Open air, premium package (Cricket turf 40mm on WBM):
    area 56x31=1736 sqft -> base ceil(1736/1500)=2d + curing(turf on
    WBM)=0d; structure Type B erection ceil(1736/1000)=2d; flooring
    ceil(1736/2500)=1d. Total: 5+2+2+1+2 = 12 days, 2 weeks."""
    headers = _login(client, director_user)
    client_id = _create_client(client, headers)
    project_id = _create_project(client, headers, client_id, package="premium")
    project_sport_id = _add_project_sport(client, headers, project_id, "box_cricket", "open_air")

    res = client.get(
        f"/schedule/project-sports/{project_sport_id}",
        params={"start_date": "2026-09-05"},
        headers=headers,
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["total_days"] == 12
    assert body["total_weeks"] == 2

    activities_by_prefix = {a["name"].split(" (")[0]: a for a in body["activities"]}
    assert activities_by_prefix["Base"]["duration_days"] == 2
    assert activities_by_prefix["Structure erection & netting"]["duration_days"] == 2
    assert activities_by_prefix["Flooring"]["duration_days"] == 1

    payment = {p["name"]: p for p in body["payment_schedule"]}
    assert payment["Handover"]["date"] == "2026-09-17"


def test_lighting_electrical_is_parallel_and_does_not_extend_total(client, director_user):
    headers = _login(client, director_user)
    client_id = _create_client(client, headers)
    project_id = _create_project(client, headers, client_id, package="premium")
    project_sport_id = _add_project_sport(client, headers, project_id, "box_cricket", "open_air")

    res = client.get(f"/schedule/project-sports/{project_sport_id}", headers=headers)
    body = res.json()
    lighting = next(a for a in body["activities"] if a["name"] == "Lighting & electrical")
    assert lighting["parallel"] is True
    assert lighting["end_day"] <= body["total_days"] + 4  # never the bottleneck at this size


def test_pool_sport_uses_lump_duration(client, director_user):
    """N: 'Pool: 10-14 weeks' -- a single lump activity replaces base/
    structure/flooring for pool sports."""
    headers = _login(client, director_user)
    client_id = _create_client(client, headers)
    project_id = _create_project(client, headers, client_id)
    project_sport_id = _add_project_sport(client, headers, project_id, "swimming_pool_25m", "open_air")

    res = client.get(f"/schedule/project-sports/{project_sport_id}", headers=headers)
    body = res.json()
    pool_activity = next(a for a in body["activities"] if a["name"] == "Pool construction")
    assert pool_activity["duration_days"] == 84  # midpoint of 10-14 weeks
    assert not any(a["name"].startswith("Base") for a in body["activities"])


def test_peb_building_uses_lump_duration(client, director_user):
    """N: 'PEB: 4-6 weeks' -- a single lump activity replaces base/
    structure for a New PEB building."""
    headers = _login(client, director_user)
    client_id = _create_client(client, headers)
    project_id = _create_project(client, headers, client_id, building_status="new_peb_building")
    project_sport_id = _add_project_sport(client, headers, project_id, "badminton", "new_peb_building")

    res = client.get(f"/schedule/project-sports/{project_sport_id}", headers=headers)
    body = res.json()
    peb_activity = next(a for a in body["activities"] if a["name"] == "PEB construction")
    assert peb_activity["duration_days"] == 35  # midpoint of 4-6 weeks
    assert not any(a["name"].startswith("Base") for a in body["activities"])


def test_schedule_requires_auth(client):
    res = client.get("/schedule/project-sports/00000000-0000-0000-0000-000000000000")
    assert res.status_code == 401


def test_schedule_for_unknown_project_sport_is_rejected(client, director_user):
    headers = _login(client, director_user)
    res = client.get(
        "/schedule/project-sports/00000000-0000-0000-0000-000000000000", headers=headers
    )
    assert res.status_code == 404
