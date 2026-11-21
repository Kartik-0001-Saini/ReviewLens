"""End-to-end through the HTTP API with the real sample file and a fake AI."""

from pathlib import Path

import pytest
from conftest import FakeLLM
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.llm_client import LLMConfigError
from app.main import app, get_cache, get_llm

SAMPLE_CSV = Path(__file__).resolve().parents[2] / "reviews.csv"


@pytest.fixture
def api(cache):
    """Returns (client, use_llm). Every request gets the FakeLLM most recently passed to use_llm."""
    current = {"llm": FakeLLM()}

    def use_llm(llm):
        current["llm"] = llm
        return llm

    app.dependency_overrides[get_settings] = lambda: Settings(_env_file=None, groq_api_key="test-key", max_upload_bytes=50_000)
    app.dependency_overrides[get_cache] = lambda: cache
    app.dependency_overrides[get_llm] = lambda: current["llm"]
    yield TestClient(app), use_llm
    app.dependency_overrides.clear()


def upload(client, data=None):
    content = SAMPLE_CSV.read_bytes() if data is None else data
    return client.post("/api/analyze", files={"file": ("reviews.csv", content, "text/csv")})


def test_sample_file_end_to_end(api):
    client, use_llm = api
    llm = use_llm(FakeLLM())

    response = upload(client)

    assert response.status_code == 200
    body = response.json()
    reviews = {review["review_id"]: review for review in body["reviews"]}
    assert reviews["R005"]["status"] == "skipped_empty"
    assert reviews["R015"]["status"] == "duplicate" and reviews["R015"]["duplicate_of"] == "R012"
    assert reviews["R015"]["analysis"] == reviews["R012"]["analysis"]  # analysed once, shared
    assert reviews["R022"]["rating"] is None and reviews["R022"]["rating_raw"] == "five"

    assert body["summary"]["total_rows"] == 30
    assert body["summary"]["analysed"] == 28  # 30 rows - 1 empty - 1 duplicate
    assert body["run"]["ai_calls"] == 7  # 6 batches of up to 5 + 1 themes call
    assert body["run"]["cache_hits"] == 0
    assert body["insights"]["source"] == "ai"
    assert [p["product"] for p in body["products"]][0] == "Cotton Bedsheet Set"
    assert llm.stats.requests == 7


def test_second_upload_makes_no_ai_calls(api):
    client, use_llm = api
    upload(client)

    second = use_llm(FakeLLM())
    body = upload(client).json()

    assert second.stats.requests == 0
    assert body["run"]["ai_calls"] == 0
    assert body["run"]["cache_hits"] == 28


def test_reply_on_click(api):
    client, _ = api
    reviews = upload(client).json()["reviews"]
    needs_reply = next(r for r in reviews if r["analysis"] and r["analysis"]["needs_reply"])
    happy = next(r for r in reviews if r["analysis"] and not r["analysis"]["needs_reply"])

    first = client.post("/api/reply", json={"text_hash": needs_reply["text_hash"]})
    again = client.post("/api/reply", json={"text_hash": needs_reply["text_hash"]})

    assert first.status_code == 200 and first.json()["cached"] is False
    assert again.json() == {**first.json(), "cached": True}
    assert client.post("/api/reply", json={"text_hash": happy["text_hash"]}).status_code == 400
    assert client.post("/api/reply", json={"text_hash": "f" * 64}).status_code == 404
    assert client.post("/api/reply", json={"text_hash": "not-a-hash"}).status_code == 422


@pytest.mark.parametrize(
    ("data", "status", "message"),
    [
        (b"name,comment\nA,B\n", 400, "Missing column"),
        (b"", 400, "empty"),
        (b"x" * 60_000, 413, "too large"),
    ],
)
def test_bad_uploads_get_clear_errors(api, data, status, message):
    client, _ = api
    response = upload(client, data)
    assert response.status_code == status
    assert message in response.json()["detail"]


def test_rejected_api_key_is_reported_not_crashed(api):
    client, use_llm = api
    use_llm(FakeLLM(script=[LLMConfigError("Groq rejected the request (HTTP 401): Invalid API Key")]))

    response = upload(client)

    assert response.status_code == 502
    assert "Invalid API Key" in response.json()["detail"]


def test_missing_key_returns_503(tmp_path):
    app.dependency_overrides[get_settings] = lambda: Settings(
        _env_file=None, groq_api_key="", db_path=tmp_path / "cache.db"
    )
    try:
        response = upload(TestClient(app))
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 503
    assert "GROQ_API_KEY" in response.json()["detail"]


def test_health(api):
    client, _ = api
    assert client.get("/api/health").json()["status"] == "ok"
