import os
import tempfile
from pathlib import Path

import pytest

# app 모듈 import 전에 테스트용 DB·AI 설정 (AI 키 없음 → 규칙 기반 대체 경로)
_TMP = Path(tempfile.mkdtemp(prefix="feedbackcare-test-"))
os.environ["FEEDBACKCARE_DB_URL"] = f"sqlite:///{(_TMP / 'test.db').as_posix()}"
os.environ.pop("FEEDBACKCARE_AI_API_KEY", None)
os.environ.pop("FEEDBACKCARE_AI_ENDPOINT", None)

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.persistence.database import SessionLocal, init_db  # noqa: E402

DATA_DIR = Path(__file__).resolve().parents[2] / "data"


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def agent_headers(client):
    r = client.post("/api/auth/login", json={"login_id": "agent1", "password": "agent1234"})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['token']}"}


@pytest.fixture(scope="session")
def admin_headers(client):
    r = client.post("/api/auth/login", json={"login_id": "admin1", "password": "admin1234"})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['token']}"}


@pytest.fixture()
def db():
    init_db()
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()
