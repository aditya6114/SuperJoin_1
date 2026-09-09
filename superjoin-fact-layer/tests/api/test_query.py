import pytest
from fastapi.testclient import TestClient
from superjoin.api.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_query_known_fact(client):
    response = client.post(
        "/api/v1/query",
        json={"query": "equity share capital for Company in December 2021"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ("answered", "contradiction_found")
    assert len(data["facts"]) > 0
    assert "equity_share_capital" in [f["predicate"] for f in data["facts"]]

    first_fact = data["facts"][0]
    assert "evidence" in first_fact
    assert "page" in first_fact["evidence"]


def test_query_conflict_detection(client):
    response = client.post(
        "/api/v1/query",
        json={"query": "Are there conflicting figures or discrepancies?"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "contradiction_found"
    assert len(data["relationships"]) > 0
    assert any(r["type"] == "CONTRADICTS" for r in data["relationships"])


def test_query_no_results(client):
    response = client.post(
        "/api/v1/query",
        json={"query": "What was the hyperdrive warp speed of Mars colony in year 3045?"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "no_results"
    assert data["facts"] == []
    assert data["relationships"] == []


def test_query_document_scope_filter(client):
    target_doc = "01-delhivery-prospectus-2022-excerpt-0d7e71"
    response = client.post(
        "/api/v1/query",
        json={
            "query": "equity share capital",
            "document_ids": [target_doc]
        }
    )
    assert response.status_code == 200
    data = response.json()
    for f in data["facts"]:
        assert f["document_id"] == target_doc
