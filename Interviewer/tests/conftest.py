import os
import sys

import pytest
from httpx import ASGITransport, AsyncClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
os.environ.setdefault("MOCK_LLM", "true")
os.environ.setdefault("MOCK_ASR", "true")

from app.main import app
from app.db import init_db


@pytest.fixture(scope="session", autouse=True)
def _init_db():
    init_db()


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
