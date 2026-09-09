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
    assert data["status"] in ("answered", "ambiguous")
    assert len(data["facts"]) > 0
    assert "equity_share_capital" in [f["predicate"] for f in data["facts"]]
    # Evidence must be grounded
    first_fact = data["facts"][0]
    assert len(first_fact["evidence"]) > 0


def test_query_conflict_detection(client):
    # Query for conflicts across the corpus
    response = client.post(
        "/api/v1/query",
        json={"query": "Are there conflicting figures or discrepancies?"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ("answered", "ambiguous")
    assert "answer" in data
    # Check if contradiction relationships are properly reported
    if data["relationships"]:
        assert any(r["relationship_type"] == "CONTRADICTS" for r in data["relationships"])


def test_query_no_results(client):
    response = client.post(
        "/api/v1/query",
        json={"query": "What was the hyperdrive warp speed of Mars colony in year 3045?"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "no_results"
    assert data["answer"] == "No matching evidence was found."
    assert data["facts"] == []
    assert data["relationships"] == []


def test_query_document_scope_filter(client):
    list_resp = client.get("/api/v1/documents")
    docs = list_resp.json()["items"]
    if len(docs) >= 1:
        target_doc = docs[0]["document_id"]
        response = client.post(
            "/api/v1/query",
            json={
                "query": "reported financial figures",
                "document_ids": [target_doc]
            }
        )
        assert response.status_code == 200
        data = response.json()
        for f in data["facts"]:
            assert f["document_id"] == target_doc
