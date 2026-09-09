"""B.2: 'Client = School -> Package Standard . Payment 40/40/20' -- package
and payment-term defaults auto-derived from a client's type, Director
overridable via Settings, same mechanism pdf_documents.py's own
_warranty_years already uses for that identical table row."""


def _login(client, director_user):
    res = client.post(
        "/auth/login",
        data={"username": "director@test.local", "password": "TestPass!1"},
    )
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _create_client(client, headers, client_type="school", name="Test School", **overrides):
    res = client.post("/clients", json={"name": name, "type": client_type, **overrides}, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()


BASE_PROJECT_FIELDS = {
    "city": "Mumbai",
    "site_condition": "level",
    "soil_type": "normal",
    "building_status": "open_air",
    "site_access": "good",
    "power_available": "yes",
    "water_available": True,
}


def test_school_client_gets_default_payment_terms(client, director_user):
    headers = _login(client, director_user)
    created = _create_client(client, headers, client_type="school")
    assert created["payment_terms"] == "40/40/20"


def test_school_project_gets_default_package_when_omitted(client, director_user):
    headers = _login(client, director_user)
    client_id = _create_client(client, headers, client_type="school")["id"]

    res = client.post("/projects", json={"client_id": client_id, **BASE_PROJECT_FIELDS}, headers=headers)
    assert res.status_code == 201, res.text
    assert res.json()["package"] == "standard"


def test_explicit_payment_terms_overrides_the_default(client, director_user):
    headers = _login(client, director_user)
    created = _create_client(client, headers, client_type="school", payment_terms="30/70")
    assert created["payment_terms"] == "30/70"


def test_explicit_package_overrides_the_default(client, director_user):
    headers = _login(client, director_user)
    client_id = _create_client(client, headers, client_type="school")["id"]

    res = client.post(
        "/projects", json={"client_id": client_id, "package": "premium", **BASE_PROJECT_FIELDS}, headers=headers
    )
    assert res.status_code == 201, res.text
    assert res.json()["package"] == "premium"


def test_client_type_with_no_configured_default_leaves_payment_terms_none(client, director_user):
    headers = _login(client, director_user)
    created = _create_client(client, headers, client_type="corporate", name="Test Corp")
    assert created["payment_terms"] is None


def test_project_creation_fails_without_a_configured_default_or_explicit_package(client, director_user):
    headers = _login(client, director_user)
    client_id = _create_client(client, headers, client_type="corporate", name="Test Corp")["id"]

    res = client.post("/projects", json={"client_id": client_id, **BASE_PROJECT_FIELDS}, headers=headers)
    assert res.status_code == 422
    assert "corporate" in res.json()["detail"]


def test_type_defaults_endpoint_returns_the_school_recommendation(client, director_user):
    headers = _login(client, director_user)
    res = client.get("/clients/type-defaults/school", headers=headers)
    assert res.status_code == 200, res.text
    assert res.json() == {"package": "standard", "payment_terms": "40/40/20"}


def test_type_defaults_endpoint_returns_none_for_an_unconfigured_type(client, director_user):
    headers = _login(client, director_user)
    res = client.get("/clients/type-defaults/corporate", headers=headers)
    assert res.status_code == 200, res.text
    assert res.json() == {"package": None, "payment_terms": None}


def test_director_can_configure_a_default_for_another_client_type(client, director_user):
    headers = _login(client, director_user)
    client.post(
        "/settings", json={"key": "default_payment_terms_corporate", "value": "50/50"}, headers=headers
    )
    client.post("/settings", json={"key": "default_package_corporate", "value": "premium"}, headers=headers)

    defaults_res = client.get("/clients/type-defaults/corporate", headers=headers)
    assert defaults_res.json() == {"package": "premium", "payment_terms": "50/50"}

    created = _create_client(client, headers, client_type="corporate", name="Configured Corp")
    assert created["payment_terms"] == "50/50"

    project_res = client.post(
        "/projects", json={"client_id": created["id"], **BASE_PROJECT_FIELDS}, headers=headers
    )
    assert project_res.status_code == 201, project_res.text
    assert project_res.json()["package"] == "premium"


def test_client_out_includes_payment_terms(client, director_user):
    headers = _login(client, director_user)
    client_id = _create_client(client, headers, client_type="school")["id"]

    res = client.get(f"/clients/{client_id}", headers=headers)
    assert res.status_code == 200
    assert res.json()["payment_terms"] == "40/40/20"


def test_type_defaults_requires_auth(client):
    res = client.get("/clients/type-defaults/school")
    assert res.status_code == 401
