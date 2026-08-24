import os

# Respect an externally-set DATABASE_URL (e.g. to run this same suite against
# real Postgres) but default to a fast in-memory SQLite DB for everyday use.
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
TEST_DATABASE_URL = os.environ["DATABASE_URL"]

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app

_is_sqlite = TEST_DATABASE_URL.startswith("sqlite")
_engine_kwargs = (
    {"connect_args": {"check_same_thread": False}, "poolclass": StaticPool}
    if _is_sqlite
    else {}
)


@pytest.fixture()
def db_session():
    engine = create_engine(TEST_DATABASE_URL, **_engine_kwargs)

    if _is_sqlite:

        @event.listens_for(engine, "connect")
        def _enable_fk(dbapi_connection, _):
            dbapi_connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.drop_all(bind=engine)  # clean slate — matters when reusing a real Postgres DB
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture()
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
