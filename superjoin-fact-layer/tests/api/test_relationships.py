import pytest
from fastapi.testclient import TestClient
from superjoin.api.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_list_relationships(client):
    response = client.get("/api/v1/relationships?page=1&page_size=10")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert data["page"] == 1
    assert data["page_size"] == 10
    assert data["total"] > 0

    first = data["items"][0]
    assert "relationship_id" in first
    assert "relationship_type" in first
    assert "confidence" in first
    assert "reason" in first
    assert "explanation" in first
    assert "evidence_a" in first
    assert "evidence_b" in first


def test_filter_relationships_by_type(client):
    for rel_type in ["CORROBORATES", "CONTRADICTS", "CONTEXTUALLY_RECONCILED", "UNRESOLVED"]:
        response = client.get(f"/api/v1/relationships?relationship_type={rel_type}&page_size=5")
        assert response.status_code == 200
        items = response.json()["items"]
        for item in items:
            assert item["relationship_type"] == rel_type


def test_get_individual_relationship(client):
    list_resp = client.get("/api/v1/relationships?page_size=1")
    items = list_resp.json()["items"]
    assert len(items) > 0

    rel_id = items[0]["relationship_id"]
    response = client.get(f"/api/v1/relationships/{rel_id}")
    assert response.status_code == 200
    rel = response.json()
    assert rel["relationship_id"] == rel_id
    assert "fact_a" in rel
    assert "fact_b" in rel
    assert "evidence_a" in rel
    assert "evidence_b" in rel
    assert "reason" in rel
    assert "explanation" in rel


def test_get_relationship_not_found(client):
    response = client.get("/api/v1/relationships/non_existent_rel_id_9999")
    assert response.status_code == 404
    data = response.json()
    assert data["error"]["code"] == "RELATIONSHIP_NOT_FOUND"
