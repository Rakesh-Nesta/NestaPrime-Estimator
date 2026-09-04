import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.user import User, UserRole
from app.core.security import hash_password

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
