"""Amendment 58 (Section 61): a value the database cannot store is a 422, never a raw 500.

Found by an authenticated ZAP scan of the running app: text longer than its column, or containing a NUL
character, ended a write in an unhandled exception on a dozen master-data routes."""

import pytest

from tests.test_attachments import _director_headers


def _vehicle_class(key, name="Tempo", **extra):
    return {"key": key, "name": name, "truck_capacity_tonnes": 5, "rate_per_km": 30, **extra}


@pytest.mark.parametrize(
    "value",
    ["x" * 500, "has a NUL \x00 byte"],
    ids=["longer than the column", "contains a NUL byte"],
)
def test_a_value_the_database_cannot_store_is_refused_with_a_422(client, director_user, value):
    headers = _director_headers(client, director_user)
    res = client.post("/vehicle-classes", json=_vehicle_class("bad-value", name=value), headers=headers)
    assert res.status_code == 422, res.text
    assert "too long" in res.json()["detail"]
    assert "varchar" not in res.text.lower() and "psycopg" not in res.text.lower()  # nothing about the schema


def test_the_write_that_failed_left_nothing_behind_and_the_next_one_works(client, director_user, db_session):
    headers = _director_headers(client, director_user)
    assert client.post("/vehicle-classes", json=_vehicle_class("half-saved", name="y" * 500), headers=headers).status_code == 422
    # In production each request has its own database session, closed (so rolled back) when it ends. The
    # test suite shares one session across requests, so end the failed transaction the same way here.
    db_session.rollback()
    listed = client.get("/vehicle-classes", headers=headers).json()
    assert not any(v["key"] == "half-saved" for v in listed)

    ok = client.post("/vehicle-classes", json=_vehicle_class("fits-fine"), headers=headers)
    assert ok.status_code == 201, ok.text


def test_a_long_setting_value_is_refused_too(client, director_user):
    headers = _director_headers(client, director_user)
    res = client.post("/settings", json={"key": "k" * 500, "value": "1"}, headers=headers)
    assert res.status_code in (422, 400), res.text  # schema-level 422 or the new handler -- never a 500
