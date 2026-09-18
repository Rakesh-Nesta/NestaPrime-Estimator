"""Section 18 (Amendment 16 Part 2): ConstructionSequenceStep -- one row
per (sport_id, phase), six fixed phases. Authored via the same
draft-then-review pattern as Quotation.cover_note (Amendment 13):
POST .../draft/{sport_id} never persists, PUT .../{sport_id} is the only
way a Director actually saves a sequence. No network access in tests --
app.services.ai_content is monkeypatched, same discipline as
test_quotation_cover_note.py / test_wa_gateway_integration.py."""

from app.api import construction_sequence as construction_sequence_api
from app.core.security import hash_password
from app.models.user import User, UserRole
from app.services.ai_content import AiContentError


def _login(client, email, password="TestPass!1"):
    res = client.post("/auth/login", data={"username": email, "password": password})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _director_headers(client, director_user):
    return _login(client, "director@test.local")


def _sales_headers(client, db_session):
    user = User(
        name="Test Sales", email="sales-consequence@test.local", hashed_password=hash_password("TestPass!1"),
        role=UserRole.SALES,
    )
    db_session.add(user)
    db_session.commit()
    return _login(client, "sales-consequence@test.local")


def _procurement_headers(client, db_session):
    user = User(
        name="Test Procurement", email="procurement-conseq@test.local", hashed_password=hash_password("TestPass!1"),
        role=UserRole.PROCUREMENT,
    )
    db_session.add(user)
    db_session.commit()
    return _login(client, "procurement-conseq@test.local")


def _ca_tax_headers(client, db_session):
    user = User(
        name="Test CA", email="catax-conseq@test.local", hashed_password=hash_password("TestPass!1"),
        role=UserRole.CA_TAX,
    )
    db_session.add(user)
    db_session.commit()
    return _login(client, "catax-conseq@test.local")


def _badminton_sport_id(client, headers):
    return next(s["id"] for s in client.get("/sports", headers=headers).json() if s["key"] == "badminton")


def _pool_sport_id(client, headers):
    return next(s["id"] for s in client.get("/sports", headers=headers).json() if s["key"] == "swimming_pool_25m")


def test_director_can_save_a_phase_and_read_it_back(client, director_user):
    headers = _director_headers(client, director_user)
    sport_id = _badminton_sport_id(client, headers)

    res = client.put(
        f"/construction-sequence/{sport_id}",
        json={"steps": [{"phase": "site_prep", "description": "Clear and level the site."}]},
        headers=headers,
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert len(body) == 1
    assert body[0]["phase"] == "site_prep"
    assert body[0]["description"] == "Clear and level the site."

    listed = client.get("/construction-sequence", params={"sport_id": sport_id}, headers=headers).json()
    assert len(listed) == 1


def test_save_is_partial_and_upserts_by_phase_not_duplicating(client, director_user):
    headers = _director_headers(client, director_user)
    sport_id = _badminton_sport_id(client, headers)

    client.put(
        f"/construction-sequence/{sport_id}",
        json={"steps": [{"phase": "site_prep", "description": "First version."}]},
        headers=headers,
    )
    res = client.put(
        f"/construction-sequence/{sport_id}",
        json={
            "steps": [
                {"phase": "site_prep", "description": "Revised version."},
                {"phase": "flooring", "description": "Lay the flooring."},
            ]
        },
        headers=headers,
    )
    assert res.status_code == 200, res.text

    listed = client.get("/construction-sequence", params={"sport_id": sport_id}, headers=headers).json()
    assert len(listed) == 2
    by_phase = {row["phase"]: row for row in listed}
    assert by_phase["site_prep"]["description"] == "Revised version."
    assert by_phase["flooring"]["description"] == "Lay the flooring."


def test_steps_are_returned_in_fixed_phase_order_not_save_order(client, director_user):
    headers = _director_headers(client, director_user)
    sport_id = _badminton_sport_id(client, headers)

    client.put(
        f"/construction-sequence/{sport_id}",
        json={
            "steps": [
                {"phase": "accessories_finishing", "description": "Install the ring."},
                {"phase": "site_prep", "description": "Excavate."},
                {"phase": "lighting", "description": "Mount floodlights."},
            ]
        },
        headers=headers,
    )
    listed = client.get("/construction-sequence", params={"sport_id": sport_id}, headers=headers).json()
    assert [row["phase"] for row in listed] == ["site_prep", "lighting", "accessories_finishing"]


def test_scoped_per_sport(client, director_user):
    headers = _director_headers(client, director_user)
    badminton_id = _badminton_sport_id(client, headers)
    pool_id = _pool_sport_id(client, headers)

    client.put(
        f"/construction-sequence/{badminton_id}",
        json={"steps": [{"phase": "site_prep", "description": "Badminton prep."}]},
        headers=headers,
    )
    client.put(
        f"/construction-sequence/{pool_id}",
        json={"steps": [{"phase": "site_prep", "description": "Pool prep."}]},
        headers=headers,
    )

    badminton_only = client.get("/construction-sequence", params={"sport_id": badminton_id}, headers=headers).json()
    assert len(badminton_only) == 1
    assert badminton_only[0]["description"] == "Badminton prep."


def test_a_sport_with_nothing_saved_returns_an_empty_list(client, director_user):
    headers = _director_headers(client, director_user)
    sport_id = _badminton_sport_id(client, headers)
    listed = client.get("/construction-sequence", params={"sport_id": sport_id}, headers=headers).json()
    assert listed == []


def test_save_requires_an_existing_sport(client, director_user):
    headers = _director_headers(client, director_user)
    res = client.put(
        "/construction-sequence/00000000-0000-0000-0000-000000000000",
        json={"steps": [{"phase": "site_prep", "description": "x"}]},
        headers=headers,
    )
    assert res.status_code == 404


def test_sales_can_read_but_not_write(client, director_user, db_session):
    director_headers = _director_headers(client, director_user)
    sport_id = _badminton_sport_id(client, director_headers)
    client.put(
        f"/construction-sequence/{sport_id}",
        json={"steps": [{"phase": "site_prep", "description": "x"}]},
        headers=director_headers,
    )

    sales_headers = _sales_headers(client, db_session)
    read_res = client.get("/construction-sequence", params={"sport_id": sport_id}, headers=sales_headers)
    assert read_res.status_code == 200, read_res.text

    write_res = client.put(
        f"/construction-sequence/{sport_id}",
        json={"steps": [{"phase": "site_prep", "description": "y"}]},
        headers=sales_headers,
    )
    assert write_res.status_code == 403


def test_procurement_can_read_but_not_write(client, director_user, db_session):
    director_headers = _director_headers(client, director_user)
    sport_id = _badminton_sport_id(client, director_headers)

    procurement_headers = _procurement_headers(client, db_session)
    read_res = client.get("/construction-sequence", params={"sport_id": sport_id}, headers=procurement_headers)
    assert read_res.status_code == 200, read_res.text

    write_res = client.put(
        f"/construction-sequence/{sport_id}",
        json={"steps": [{"phase": "site_prep", "description": "x"}]},
        headers=procurement_headers,
    )
    assert write_res.status_code == 403


def test_ca_tax_cannot_read_or_write(client, director_user, db_session):
    director_headers = _director_headers(client, director_user)
    sport_id = _badminton_sport_id(client, director_headers)

    ca_tax_headers = _ca_tax_headers(client, db_session)
    read_res = client.get("/construction-sequence", params={"sport_id": sport_id}, headers=ca_tax_headers)
    assert read_res.status_code == 403

    write_res = client.put(
        f"/construction-sequence/{sport_id}",
        json={"steps": [{"phase": "site_prep", "description": "x"}]},
        headers=ca_tax_headers,
    )
    assert write_res.status_code == 403


def test_draft_requires_auth(client):
    assert client.post("/construction-sequence/draft/00000000-0000-0000-0000-000000000000").status_code == 401


def test_draft_not_configured_fails_fast(client, director_user, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "anthropic_api_key", "")
    headers = _director_headers(client, director_user)
    sport_id = _badminton_sport_id(client, headers)

    res = client.post(f"/construction-sequence/draft/{sport_id}", headers=headers)
    assert res.status_code == 503
    assert "not configured" in res.json()["detail"].lower()


def test_draft_success_returns_all_six_phases_without_saving(client, director_user, monkeypatch):
    headers = _director_headers(client, director_user)
    sport_id = _badminton_sport_id(client, headers)

    captured_prompt = {}

    def _fake_generate_text(prompt, max_tokens=400):
        captured_prompt["prompt"] = prompt
        return (
            "site_prep: Clear and level the plot.\n"
            "sub_base: Compact the base layer.\n"
            "flooring: Lay the court flooring.\n"
            "structure_fixtures: Install posts and net.\n"
            "lighting: Mount floodlights.\n"
            "accessories_finishing: Fit the accessories and line-mark."
        )

    monkeypatch.setattr(construction_sequence_api.ai_content, "generate_text", _fake_generate_text)

    res = client.post(f"/construction-sequence/draft/{sport_id}", headers=headers)
    assert res.status_code == 200, res.text
    body = res.json()
    assert [s["phase"] for s in body["steps"]] == [
        "site_prep", "sub_base", "flooring", "structure_fixtures", "lighting", "accessories_finishing",
    ]
    assert body["steps"][0]["description"] == "Clear and level the plot."
    assert "badminton" in captured_prompt["prompt"].lower()

    # Never persisted by the draft endpoint itself.
    listed = client.get("/construction-sequence", params={"sport_id": sport_id}, headers=headers).json()
    assert listed == []


def test_draft_service_failure_surfaces_as_503(client, director_user, monkeypatch):
    headers = _director_headers(client, director_user)
    sport_id = _badminton_sport_id(client, headers)

    def _boom(prompt, max_tokens=400):
        raise AiContentError("AI drafting returned 401: invalid api key")

    monkeypatch.setattr(construction_sequence_api.ai_content, "generate_text", _boom)

    res = client.post(f"/construction-sequence/draft/{sport_id}", headers=headers)
    assert res.status_code == 503
    assert "invalid api key" in res.json()["detail"].lower()


def test_sales_cannot_draft(client, director_user, db_session):
    director_headers = _director_headers(client, director_user)
    sport_id = _badminton_sport_id(client, director_headers)

    sales_headers = _sales_headers(client, db_session)
    res = client.post(f"/construction-sequence/draft/{sport_id}", headers=sales_headers)
    assert res.status_code == 403
