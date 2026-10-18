import os

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("XAU_SECRET_KEY", "test-secret-key-0123456789-abcdefghijkl")

from app import db as dbmod  # noqa: E402
from app.cli import seed_instruments  # noqa: E402
from app.db import Base  # noqa: E402
from app.main import app  # noqa: E402
from app.models import User  # noqa: E402
from app.security import hash_password, login_limiter  # noqa: E402

TEST_URL = os.environ.get("XAU_TEST_DATABASE_URL", "postgresql+psycopg://xau:xau@localhost:5432/xau_lab_test")


@pytest.fixture(scope="session", autouse=True)
def _engine():
    dbmod.configure(TEST_URL)
    yield dbmod.engine()


@pytest.fixture(autouse=True)
def _clean(_engine):
    Base.metadata.drop_all(_engine)
    Base.metadata.create_all(_engine)
    login_limiter.reset()
    yield


@pytest.fixture
def session():
    gen = dbmod.get_db()
    s = next(gen)
    yield s
    s.close()


def make_user(session, email="trader@example.com", password="correct-horse-battery"):
    u = User(email=email, display_name="Trader", password_hash=hash_password(password))
    session.add(u)
    seed_instruments(session)
    session.commit()
    return u


@pytest.fixture
def user(session):
    return make_user(session)


@pytest.fixture
def client(user):
    c = TestClient(app)
    r = c.post("/api/auth/login", json={"email": "trader@example.com", "password": "correct-horse-battery"})
    assert r.status_code == 200, r.text
    return c


@pytest.fixture
def anon():
    return TestClient(app)
