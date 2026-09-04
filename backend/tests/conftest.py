import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.user import User, UserRole
from app.models.regional_multiplier import RegionalMultiplier
from app.models.sport import Sport
from app.core.security import hash_password
from app.seed_data import REGIONAL_MULTIPLIER_SEED, SPORTS_SEED

# Tests run against the same Postgres container as dev (docker-compose),
# in a separate database so they never touch real data.
TEST_DATABASE_URL = settings.database_url.rsplit("/", 1)[0] + "/nestaprime_estimator_test"

engine = create_engine(TEST_DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db_session():
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        for city, labour, transport, material, climate, rainfall, coastal, wind, seismic, confirmed in REGIONAL_MULTIPLIER_SEED:
            session.add(
                RegionalMultiplier(
                    city=city,
                    labour_multiplier=labour,
                    transport_multiplier=transport,
                    material_multiplier=material,
                    climate_zone=climate,
                    rainfall_zone=rainfall,
                    coastal=coastal,
                    wind_zone=wind,
                    seismic_zone=seismic,
                    is_confirmed=confirmed,
                )
            )
        for key, order, name, category, playing, build, min_height, body in SPORTS_SEED:
            session.add(
                Sport(
                    key=key,
                    display_order=order,
                    name=name,
                    category=category,
                    playing_dims=playing,
                    build_dims=build,
                    min_clear_height_ft=min_height,
                    governing_body=body,
                )
            )
        session.commit()
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture()
def director_user(db_session):
    user = User(
        name="Test Director",
        email="director@test.local",
        hashed_password=hash_password("TestPass!1"),
        role=UserRole.DIRECTOR,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user
