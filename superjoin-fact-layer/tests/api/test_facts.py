import pytest
from fastapi.testclient import TestClient
from superjoin.api.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_get_document_facts(client):
    list_resp = client.get("/api/v1/documents")
    items = list_resp.json()["items"]
    doc_id = items[0]["document_id"]

    response = client.get(f"/api/v1/documents/{doc_id}/facts?page=1&page_size=10")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert len(data["items"]) > 0

    fact = data["items"][0]
    assert "fact_id" in fact
    assert "subject" in fact
    assert "predicate" in fact
    assert "object" in fact
    assert "evidence_ids" in fact
    assert "evidence" in fact
    assert len(fact["evidence"]) > 0

    # Provenance checking: evidence must have evidence_id, page
    ev = fact["evidence"][0]
    assert "evidence_id" in ev
    assert "page" in ev


def test_get_document_facts_filter_predicate(client):
    list_resp = client.get("/api/v1/documents")
    doc_id = list_resp.json()["items"][0]["document_id"]

    # First get any fact to get a known predicate
    all_facts_resp = client.get(f"/api/v1/documents/{doc_id}/facts?page_size=5")
    facts = all_facts_resp.json()["items"]
    if facts:
        known_pred = facts[0]["predicate"]
        filter_resp = client.get(f"/api/v1/documents/{doc_id}/facts?predicate={known_pred}")
        assert filter_resp.status_code == 200
        filtered_items = filter_resp.json()["items"]
        assert len(filtered_items) > 0
        for item in filtered_items:
            assert known_pred.lower() in item["predicate"].lower()


def test_get_document_facts_filter_fact_type(client):
    list_resp = client.get("/api/v1/documents")
    doc_id = list_resp.json()["items"][0]["document_id"]

    response = client.get(f"/api/v1/documents/{doc_id}/facts?fact_type=numerical")
    assert response.status_code == 200
    for item in response.json()["items"]:
        assert item["fact_type"] == "numerical"


def test_get_document_facts_not_found(client):
    response = client.get("/api/v1/documents/non_existent_doc_9999/facts")
    assert response.status_code == 404
    data = response.json()
    assert data["error"]["code"] == "DOCUMENT_NOT_FOUND"


def test_get_individual_fact_provenance(client):
    list_resp = client.get("/api/v1/documents")
    doc_id = list_resp.json()["items"][0]["document_id"]

    facts_resp = client.get(f"/api/v1/documents/{doc_id}/facts?page_size=1")
    fact_id = facts_resp.json()["items"][0]["fact_id"]

    # Retrieve individual fact
    response = client.get(f"/api/v1/facts/{fact_id}")
    assert response.status_code == 200
    fact = response.json()
    assert fact["fact_id"] == fact_id
    assert fact["document_id"] == doc_id
    assert "evidence" in fact
    assert len(fact["evidence"]) > 0


def test_get_individual_fact_not_found(client):
    response = client.get("/api/v1/facts/non_existent_fact_id_9999")
    assert response.status_code == 404
    data = response.json()
    assert data["error"]["code"] == "FACT_NOT_FOUND"
