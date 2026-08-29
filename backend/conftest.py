import os

# Run all tests against a throwaway database so we never touch gate.db.
os.environ["DATABASE_URL"] = "sqlite:///./test_gate.db"
if os.path.exists("test_gate.db"):
    os.remove("test_gate.db")

import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c
