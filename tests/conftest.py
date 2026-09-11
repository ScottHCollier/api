from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from api.config import get_settings
from api.database import get_session
from api.main import app
from api.seed import seed_database


@pytest.fixture(scope="session")
def migrated_engine():
    # Only drop the randomly named database this fixture creates, never the dev DB.
    url = get_settings().database_url
    name = f"final_third_test_{uuid4().hex}"
    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as connection:
        connection.execute(text(f'CREATE DATABASE "{name}"'))
    engine = create_engine(url.set(database=name))
    try:
        with engine.begin() as connection:
            config = Config("alembic.ini")
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
        yield engine
    finally:
        engine.dispose()
        with admin.connect() as connection:
            connection.execute(text(f'DROP DATABASE "{name}" WITH (FORCE)'))
        admin.dispose()


@pytest.fixture
def session(migrated_engine):
    with migrated_engine.connect() as connection:
        transaction = connection.begin()
        with Session(bind=connection) as session:
            seed_database(session)
            yield session
        transaction.rollback()


@pytest.fixture
def client(session):
    def override_session():
        yield session

    app.dependency_overrides[get_session] = override_session
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()
