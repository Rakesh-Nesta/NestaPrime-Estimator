import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.accessory_catalog_item import AccessoryCatalogItem
from app.models.flooring_guide import FlooringGuide
from app.models.lighting_standard import LightingLuxStandard, SportPoleCount
from app.models.netting_grade import NettingGrade
from app.models.user import User, UserRole
from app.models.margin_policy import MarginPolicy
from app.models.rate_item import LabourCategory
from app.models.regional_multiplier import RegionalMultiplier
from app.models.scope_item import ScopeItem
from app.models.sport import Sport
from app.core.security import hash_password
from app.seed_data import (
    ACCESSORY_CATALOG_SEED,
    FLOORING_GUIDES_SEED,
    LABOUR_CATEGORIES_SEED,
    LIGHTING_LUX_STANDARDS_SEED,
    MARGIN_POLICY_SEED,
    NETTING_GRADES_SEED,
    REGIONAL_MULTIPLIER_SEED,
    SCOPE_ITEMS_SEED,
    SPORT_POLE_COUNTS_SEED,
    SPORTS_SEED,
)

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
        sport_id_by_key: dict[str, object] = {}
        for (
            key, order, name, category, playing, build,
            playing_l, playing_w, build_l, build_w,
            min_height, body,
        ) in SPORTS_SEED:
            sport = Sport(
                key=key,
                display_order=order,
                name=name,
                category=category,
                playing_dims=playing,
                build_dims=build,
                playing_l_ft=playing_l,
                playing_w_ft=playing_w,
                build_l_ft=build_l,
                build_w_ft=build_w,
                min_clear_height_ft=min_height,
                governing_body=body,
            )
            session.add(sport)
            session.flush()  # need sport.id for ACCESSORY_CATALOG_SEED below
            sport_id_by_key[key] = sport.id
        for sport_key, item_name, unit, quantity_per_court in ACCESSORY_CATALOG_SEED:
            session.add(
                AccessoryCatalogItem(
                    sport_id=sport_id_by_key[sport_key],
                    item_name=item_name,
                    unit=unit,
                    quantity_per_court=quantity_per_court,
                )
            )
        for sport_key, primary_spec, secondary_spec, budget_spec, rationale in FLOORING_GUIDES_SEED:
            session.add(
                FlooringGuide(
                    sport_id=sport_id_by_key[sport_key],
                    primary_spec=primary_spec,
                    secondary_spec=secondary_spec,
                    budget_spec=budget_spec,
                    rationale=rationale,
                )
            )
        for category, lux_practice, lux_match, lux_tournament in LIGHTING_LUX_STANDARDS_SEED:
            session.add(
                LightingLuxStandard(
                    category=category, lux_practice=lux_practice, lux_match=lux_match, lux_tournament=lux_tournament,
                )
            )
        for sport_key, pole_count in SPORT_POLE_COUNTS_SEED:
            session.add(SportPoleCount(sport_id=sport_id_by_key[sport_key], pole_count=pole_count))
        for key, order, group, name in SCOPE_ITEMS_SEED:
            session.add(
                ScopeItem(key=key, display_order=order, group=group, name=name)
            )
        for key, name, default_percent in LABOUR_CATEGORIES_SEED:
            session.add(
                LabourCategory(key=key, name=name, default_percent=default_percent)
            )
        for key, name, material, twine, mesh, uv_stabilized, typical_use, rate_per_sqm in NETTING_GRADES_SEED:
            session.add(
                NettingGrade(
                    key=key, name=name, material=material, twine=twine, mesh=mesh,
                    uv_stabilized=uv_stabilized, typical_use=typical_use, rate_per_sqm=rate_per_sqm,
                )
            )
        for client_type, floor_margin_percent, competitive_segment in MARGIN_POLICY_SEED:
            session.add(
                MarginPolicy(
                    client_type=client_type,
                    floor_margin_percent=floor_margin_percent,
                    competitive_segment=competitive_segment,
                )
            )
        session.commit()
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(autouse=True)
def isolated_attachment_storage(tmp_path):
    """Attachments (Part M.3) write real files to disk, and that storage
    root isn't test-database-isolated the way db_session is -- without
    this, every test run would leave orphaned files under the project's
    own backend/uploads/ forever. Redirect to pytest's own tmp_path, which
    pytest cleans up on its own retention schedule."""
    original = settings.attachment_storage_root
    settings.attachment_storage_root = str(tmp_path / "uploads")
    yield
    settings.attachment_storage_root = original


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
