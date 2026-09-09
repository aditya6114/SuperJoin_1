import io
import pytest
from fastapi.testclient import TestClient
from superjoin.api.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_upload_invalid_extension(client):
    response = client.post(
        "/api/v1/documents",
        files={"file": ("test.txt", b"Hello world", "text/plain")}
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
        files={"file": ("not_a_pdf.pdf", b"NOT A PDF FILE", "application/pdf")}
    )
    assert response.status_code == 400
    err = response.json()["error"]
    assert err["code"] == "INVALID_PDF_SIGNATURE"


def test_list_documents(client):
    response = client.get("/api/v1/documents?page=1&page_size=20")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert data["page"] == 1
    assert data["page_size"] == 20
    assert data["total"] > 0
    # Check item structure
    first = data["items"][0]
    assert "document_id" in first
    assert "filename" in first
    assert "status" in first


def test_get_document_existing(client):
    # Retrieve first available document from list
    list_resp = client.get("/api/v1/documents")
    assert list_resp.status_code == 200
    items = list_resp.json()["items"]
    assert len(items) > 0

    doc_id = items[0]["document_id"]
    response = client.get(f"/api/v1/documents/{doc_id}")
    assert response.status_code == 200
    doc = response.json()
    assert doc["document_id"] == doc_id
    assert doc["status"] == "processed"
    assert doc["page_count"] > 0
    assert doc["fact_count"] >= 0


def test_get_document_not_found(client):
    response = client.get("/api/v1/documents/non_existent_doc_12345")
    assert response.status_code == 404
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "DOCUMENT_NOT_FOUND"
