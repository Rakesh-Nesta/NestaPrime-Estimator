"""Amendment 23 (Section 29): create_with_retry closes a real race in
_generate_project_no/_po_number -- neither locks a row nor uses a DB
sequence, so two concurrent requests can compute the identical number
and the second commit used to surface as a raw, unhandled
IntegrityError (500).

No mocking here (this codebase tests against the real Postgres test
database, not fakes) -- the collision is engineered by controlling
what our own build() callable returns on each call, which is the
standard way to test retry logic deterministically without needing
genuine multi-threaded concurrency."""

import uuid

from app.core.db_retry import create_with_retry
from app.core.security import hash_password
from app.models.project import BuildingStatus, Package, Project, SiteCondition
from app.models.user import User, UserRole


def _login(client, email, password="TestPass!1"):
    res = client.post("/auth/login", data={"username": email, "password": password})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _director_headers(client, director_user):
    return _login(client, "director@test.local")


def _create_client_record(client, headers, name="Retry Test Client"):
    res = client.post("/clients", json={"name": name, "type": "school"}, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()["id"]


def _project(client_id: uuid.UUID, project_no: str) -> Project:
    return Project(
        project_no=project_no,
        client_id=client_id,
        city="Mumbai",
        site_condition=SiteCondition.LEVEL,
        building_status=BuildingStatus.OPEN_AIR,
        package=Package.STANDARD,
    )


def test_create_with_retry_recovers_from_one_collision(client, director_user, db_session):
    headers = _director_headers(client, director_user)
    client_id = uuid.UUID(_create_client_record(client, headers))

    # Simulate a number a concurrent request already committed, before
    # our own attempt gets to build().
    already_taken = Project(
        project_no="P-RETRY-0001", client_id=client_id, city="Mumbai",
        site_condition=SiteCondition.LEVEL, building_status=BuildingStatus.OPEN_AIR,
        package=Package.STANDARD,
    )
    db_session.add(already_taken)
    db_session.commit()

    calls = {"n": 0}

    def build():
        calls["n"] += 1
        # First attempt collides (same number a concurrent request just
        # took); second attempt uses a genuinely free number -- exactly
        # what a real retry recomputing _generate_project_no would see.
        project_no = "P-RETRY-0001" if calls["n"] == 1 else "P-RETRY-0002"
        project = _project(client_id, project_no)
        db_session.add(project)
        return project

    result = create_with_retry(db_session, build)
    assert calls["n"] == 2
    assert result.project_no == "P-RETRY-0002"

    # The failed first attempt left no trace.
    all_numbers = {p.project_no for p in db_session.query(Project).filter(Project.client_id == client_id).all()}
    assert all_numbers == {"P-RETRY-0001", "P-RETRY-0002"}


def test_create_with_retry_gives_up_after_max_attempts(client, director_user, db_session):
    headers = _director_headers(client, director_user)
    client_id = uuid.UUID(_create_client_record(client, headers))

    already_taken = Project(
        project_no="P-RETRY-0099", client_id=client_id, city="Mumbai",
        site_condition=SiteCondition.LEVEL, building_status=BuildingStatus.OPEN_AIR,
        package=Package.STANDARD,
    )
    db_session.add(already_taken)
    db_session.commit()

    calls = {"n": 0}

    def always_collides():
        calls["n"] += 1
        project = _project(client_id, "P-RETRY-0099")  # never a free number
        db_session.add(project)
        return project

    try:
        create_with_retry(db_session, always_collides, attempts=2)
        assert False, "expected an IntegrityError"
    except Exception as exc:
        assert "IntegrityError" in type(exc).__name__

    assert calls["n"] == 2
    # Only the one real, pre-existing row survives -- no partial/zombie rows.
    all_numbers = [p.project_no for p in db_session.query(Project).filter(Project.client_id == client_id).all()]
    assert all_numbers == ["P-RETRY-0099"]


def test_creating_two_projects_normally_still_gets_sequential_numbers(client, director_user):
    """Regression check: the retry wrapper doesn't change ordinary,
    non-colliding creation behavior."""
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers, name="Sequential Test Client")

    fields = {
        "client_id": client_id, "city": "Mumbai", "site_condition": "level", "soil_type": "normal",
        "building_status": "open_air", "site_access": "good", "power_available": "yes",
        "water_available": True, "package": "standard",
    }
    first = client.post("/projects", json=fields, headers=headers)
    second = client.post("/projects", json=fields, headers=headers)
    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    assert first.json()["project_no"] != second.json()["project_no"]
