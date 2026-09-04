def _login(client, director_user):
    res = client.post(
        "/auth/login",
        data={"username": "director@test.local", "password": "TestPass!1"},
    )
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _create_client(client, headers, client_type="school", name="Test School"):
    res = client.post(
        "/clients",
        json={"name": name, "type": client_type},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]


BASE_PROJECT_FIELDS = {
    "city": "Mumbai",
    "site_condition": "level",
    "soil_type": "normal",
    "building_status": "open_air",
    "site_access": "good",
    "power_available": "yes",
    "water_available": True,
    "package": "standard",
}


def test_create_client_requires_auth(client):
    res = client.post("/clients", json={"name": "X", "type": "school"})
    assert res.status_code == 401


def test_create_client_and_project_happy_path(client, director_user):
    headers = _login(client, director_user)
    client_id = _create_client(client, headers)

    res = client.post(
        "/projects",
        json={"client_id": client_id, **BASE_PROJECT_FIELDS},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["project_no"].startswith("P-")
    assert body["tender_mode"] is False


def test_government_client_auto_sets_tender_mode(client, director_user):
    """B.2: Client = Government auto-switches Tender Mode on."""
    headers = _login(client, director_user)
    client_id = _create_client(client, headers, client_type="government", name="Municipal Corp")

    res = client.post(
        "/projects",
        json={"client_id": client_id, **BASE_PROJECT_FIELDS},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    assert res.json()["tender_mode"] is True


def test_non_government_client_never_sets_tender_mode(client, director_user):
    headers = _login(client, director_user)
    for client_type in ["school", "college", "housing_society", "corporate", "club", "individual"]:
        client_id = _create_client(client, headers, client_type=client_type, name=f"Test {client_type}")
        res = client.post(
            "/projects",
            json={"client_id": client_id, **BASE_PROJECT_FIELDS},
            headers=headers,
        )
        assert res.status_code == 201
        assert res.json()["tender_mode"] is False, f"{client_type} incorrectly set tender_mode"


def test_soil_test_required_for_rocky_black_cotton_and_filled(client, director_user):
    """D.4: soil test is mandatory for rocky, black-cotton and filled soils."""
    headers = _login(client, director_user)
    client_id = _create_client(client, headers)

    for soil_type, expected in [
        ("normal", False),
        ("sandy", False),
        ("rocky", True),
        ("black_cotton", True),
        ("filled", True),
    ]:
        fields = {**BASE_PROJECT_FIELDS, "soil_type": soil_type}
        res = client.post("/projects", json={"client_id": client_id, **fields}, headers=headers)
        assert res.status_code == 201
        assert res.json()["soil_test_required"] is expected, f"soil_type={soil_type}"


def test_soil_test_required_for_new_peb_building_and_water_logged_site(client, director_user):
    """D.4: also mandatory for New PEB building and water-logged sites,
    independent of soil type."""
    headers = _login(client, director_user)
    client_id = _create_client(client, headers)

    peb_fields = {**BASE_PROJECT_FIELDS, "building_status": "new_peb_building"}
    res = client.post("/projects", json={"client_id": client_id, **peb_fields}, headers=headers)
    assert res.json()["soil_test_required"] is True

    waterlogged_fields = {**BASE_PROJECT_FIELDS, "site_condition": "water_logged"}
    res = client.post("/projects", json={"client_id": client_id, **waterlogged_fields}, headers=headers)
    assert res.json()["soil_test_required"] is True


def test_project_numbers_are_sequential_within_the_same_month(client, director_user):
    headers = _login(client, director_user)
    client_id = _create_client(client, headers)

    numbers = []
    for _ in range(3):
        res = client.post("/projects", json={"client_id": client_id, **BASE_PROJECT_FIELDS}, headers=headers)
        numbers.append(res.json()["project_no"])

    sequences = [int(n.rsplit("-", 1)[-1]) for n in numbers]
    assert sequences == sorted(sequences)
    assert len(set(numbers)) == 3  # no collisions


def test_existing_building_clear_height_rejected_for_non_existing_status(client, director_user):
    headers = _login(client, director_user)
    client_id = _create_client(client, headers)

    fields = {
        **BASE_PROJECT_FIELDS,
        "building_status": "open_air",
        "existing_building_clear_height_ft": 24,
    }
    res = client.post("/projects", json={"client_id": client_id, **fields}, headers=headers)
    assert res.status_code == 400


def test_project_creation_with_unknown_client_is_rejected(client, director_user):
    headers = _login(client, director_user)
    res = client.post(
        "/projects",
        json={"client_id": "00000000-0000-0000-0000-000000000000", **BASE_PROJECT_FIELDS},
        headers=headers,
    )
    assert res.status_code == 404


def test_regional_multipliers_lists_all_ten_seeded_cities(client, director_user):
    headers = _login(client, director_user)
    res = client.get("/regional-multipliers", headers=headers)
    assert res.status_code == 200
    cities = {row["city"] for row in res.json()}
    assert cities == {
        "Mumbai", "Delhi NCR", "Bengaluru", "Hyderabad", "Chennai",
        "Pune", "Kolkata", "Ahmedabad", "Jaipur", "Lucknow",
    }


def test_mumbai_multiplier_matches_b2_worked_example(client, director_user):
    headers = _login(client, director_user)
    res = client.get("/regional-multipliers", headers=headers)
    mumbai = next(row for row in res.json() if row["city"] == "Mumbai")
    assert mumbai["labour_multiplier"] == 1.25
    assert mumbai["transport_multiplier"] == 1.15
    assert mumbai["material_multiplier"] == 1.10
    assert mumbai["coastal"] is True
    assert mumbai["is_confirmed"] is True


def test_unconfirmed_city_is_clearly_flagged(client, director_user):
    """Cities not in B.2's worked examples must not silently look like real
    data — is_confirmed=False is the signal a reviewer checks for."""
    headers = _login(client, director_user)
    res = client.get("/regional-multipliers", headers=headers)
    bengaluru = next(row for row in res.json() if row["city"] == "Bengaluru")
    assert bengaluru["is_confirmed"] is False
