from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from superjoin.api.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_upload_invalid_extension(client):
    response = client.post(
        "/api/v1/documents",
        files={"file": ("test.txt", b"plain text", "text/plain")}
    )
    assert response.status_code == 400
    err = response.json()["error"]
    assert err["code"] == "INVALID_FILE_TYPE"


def test_upload_empty_file(client):
    response = client.post(
        "/api/v1/documents",
        files={"file": ("empty.pdf", b"", "application/pdf")}
    )
    assert response.status_code == 400
    err = response.json()["error"]
    assert err["code"] == "EMPTY_FILE"


def test_upload_invalid_pdf_signature(client):
    response = client.post(
        "/api/v1/documents",
        files={"file": ("fake.pdf", b"NOT A VALID PDF", "application/pdf")}
    )
    assert response.status_code == 400
    err = response.json()["error"]
    assert err["code"] == "INVALID_PDF_SIGNATURE"


def test_upload_valid_pdf_and_inspect_results(client):
    pdf_path = Path("tests/fixtures/sample.pdf")
    assert pdf_path.exists(), "Sample PDF fixture missing"

    doc_id = None
    try:
        # 1. Upload valid PDF
        with open(pdf_path, "rb") as f:
            upload_resp = client.post(
                "/api/v1/documents",
                files={"file": ("evaluator_doc.pdf", f, "application/pdf")}
            )
        assert upload_resp.status_code == 201
        data = upload_resp.json()
        assert "document_id" in data
        assert data["status"] == "processed"
        assert data["message"] == "Document processed successfully"
        doc_id = data["document_id"]

        # 2. Inspect single document results
        results_resp = client.get(f"/api/v1/documents/{doc_id}/results")
        assert results_resp.status_code == 200
        res_data = results_resp.json()
        assert "document" in res_data
        assert res_data["document"]["document_id"] == doc_id
        assert "facts" in res_data
        assert "relationships" in res_data

    finally:
        # Clean up temporary test artifacts
        for p in [
            Path("data/input/evaluator_doc.pdf"),
            Path(f"data/parsed/{doc_id}.json") if doc_id else None,
            Path(f"data/facts/{doc_id}.json") if doc_id else None,
        ]:
            if p and p.exists():
                p.unlink(missing_ok=True)


def test_get_document_results_existing(client):
    # Use one of the existing parsed documents
    doc_id = "01-delhivery-prospectus-2022-excerpt-0d7e71"
    response = client.get(f"/api/v1/documents/{doc_id}/results")
    assert response.status_code == 200
    data = response.json()
    assert data["document"]["document_id"] == doc_id
    assert len(data["facts"]) > 0

    first_fact = data["facts"][0]
    assert "fact_id" in first_fact
    assert "subject" in first_fact
    assert "predicate" in first_fact
    assert "value" in first_fact
    assert "evidence" in first_fact
    assert "page" in first_fact["evidence"]


def test_get_document_results_not_found(client):
    response = client.get("/api/v1/documents/non_existent_doc_12345/results")
    assert response.status_code == 404
    data = response.json()
    assert data["error"]["code"] == "DOCUMENT_NOT_FOUND"


def test_get_corpus_results(client):
    response = client.get("/api/v1/results")
    assert response.status_code == 200
    data = response.json()
    assert "documents" in data
    assert "facts" in data
    assert "relationships" in data
    assert len(data["documents"]) > 0
    assert len(data["facts"]) > 0
    assert len(data["relationships"]) > 0

    first_rel = data["relationships"][0]
    assert "fact_a" in first_rel
    assert "fact_b" in first_rel
    assert "type" in first_rel
    assert "confidence" in first_rel
    assert "reason" in first_rel


def test_get_corpus_results_filtered(client):
    doc_a = "01-delhivery-prospectus-2022-excerpt-0d7e71"
    response = client.get(f"/api/v1/results?document_ids={doc_a}")
    assert response.status_code == 200
    data = response.json()
    for doc in data["documents"]:
        assert doc["document_id"] == doc_a
    for f in data["facts"]:
        assert f["document_id"] == doc_a


def test_list_facts_endpoint(client):
    doc_a = "01-delhivery-prospectus-2022-excerpt-0d7e71"
    response = client.get(f"/api/v1/facts?document_id={doc_a}&limit=10")
    assert response.status_code == 200
    data = response.json()
    assert "total" in data
    assert data["total"] > 0
    assert len(data["facts"]) <= 10
    first_fact = data["facts"][0]
    assert "fact_id" in first_fact
    assert "subject" in first_fact
    assert "predicate" in first_fact
    assert "value" in first_fact
    assert "evidence" in first_fact


def test_get_single_fact_endpoint(client):
    rf = client.get("/api/v1/facts?limit=1")
    assert rf.status_code == 200
    fact_id = rf.json()["facts"][0]["fact_id"]

    response = client.get(f"/api/v1/facts/{fact_id}")
    assert response.status_code == 200
    fact = response.json()
    assert fact["fact_id"] == fact_id
    assert "subject" in fact
    assert "predicate" in fact
    assert "value" in fact


def test_list_relationships_embedded_facts_endpoint(client):
    response = client.get("/api/v1/relationships?limit=5")
    assert response.status_code == 200
    data = response.json()
    assert "total" in data
    assert data["total"] > 0
    assert len(data["relationships"]) > 0

    first_rel = data["relationships"][0]
    assert "relationship_id" in first_rel
    assert "type" in first_rel
    assert "confidence" in first_rel
    assert "reason" in first_rel

    # Validate that fact_a and fact_b are ACTUAL FACTS (dicts with subject, predicate, value)
    assert isinstance(first_rel["fact_a"], dict), "fact_a must be an actual fact object, not just an ID"
    assert "fact_id" in first_rel["fact_a"]
    assert "subject" in first_rel["fact_a"]
    assert "predicate" in first_rel["fact_a"]
    assert "value" in first_rel["fact_a"]

    assert isinstance(first_rel["fact_b"], dict), "fact_b must be an actual fact object, not just an ID"
    assert "fact_id" in first_rel["fact_b"]
    assert "subject" in first_rel["fact_b"]
    assert "predicate" in first_rel["fact_b"]
    assert "value" in first_rel["fact_b"]


def test_get_single_relationship_endpoint(client):
    rr = client.get("/api/v1/relationships?limit=1")
    assert rr.status_code == 200
    rel_id = rr.json()["relationships"][0]["relationship_id"]

    response = client.get(f"/api/v1/relationships/{rel_id}")
    assert response.status_code == 200
    rel = response.json()
    assert rel["relationship_id"] == rel_id
    assert isinstance(rel["fact_a"], dict)
    assert isinstance(rel["fact_b"], dict)
    assert "subject" in rel["fact_a"]
    assert "subject" in rel["fact_b"]

