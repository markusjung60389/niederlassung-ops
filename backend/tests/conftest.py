import os
import tempfile
import uuid
from pathlib import Path

import pytest

# Must be set before app.config is imported anywhere.
_TMP_DIR = Path(tempfile.mkdtemp(prefix="remscheid-ops-tests-"))
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP_DIR / 'test.db'}"
os.environ["UPLOADS_DIR"] = str(_TMP_DIR / "uploads")
os.environ["AUTH_MODE"] = "dev"
os.environ["APP_ENV"] = "test"
os.environ.pop("AUTH_DEV_DEFAULT_USER_ID", None)

from fastapi.testclient import TestClient  # noqa: E402

from app.database import Base, engine  # noqa: E402
from app.main import app  # noqa: E402

MANAGER = "user-branch-manager"
HSE = "user-hse"
VIEWER = "user-viewer"
BRANCH = "branch-remscheid"


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def clean_tables(client):
    """Keeps the seeded branch/roles/users, clears everything else per test."""
    keep = {"branches", "roles", "users", "alembic_version"}
    with engine.begin() as connection:
        for table in reversed(Base.metadata.sorted_tables):
            if table.name not in keep:
                connection.execute(table.delete())
    yield


def auth(user_id: str) -> dict[str, str]:
    return {"X-User-Id": user_id}


def make_employee(client, name: str = "Erika Muster", branch_id: str = BRANCH) -> str:
    response = client.post(
        "/api/employees",
        headers=auth(MANAGER),
        json={"branch_id": branch_id, "full_name": name, "role": "Monteurin"},
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def make_record(client, **overrides) -> dict:
    payload = {
        "title": f"Unterweisung {uuid.uuid4().hex[:6]}",
        "category": "training_instruction",
        "branch_id": BRANCH,
        "owner_user_id": MANAGER,
        "legal_basis": "DGUV Vorschrift 1",
        "control_type": "training",
        "due_date": "2026-12-01",
        "review_date": "2026-12-01",
    }
    payload.update(overrides)
    response = client.post("/api/compliance-records", headers=auth(MANAGER), json=payload)
    assert response.status_code == 200, response.text
    return response.json()


def make_account(client, **overrides) -> dict:
    payload = {"name": f"Kunde {uuid.uuid4().hex[:6]}", "branch_id": BRANCH}
    payload.update(overrides)
    response = client.post("/api/accounts", headers=auth(MANAGER), json=payload)
    assert response.status_code == 201, response.text
    return response.json()
