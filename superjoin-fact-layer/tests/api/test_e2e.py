from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from superjoin.api.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_full_evaluator_workflow(client):
    pdf_path = Path("tests/fixtures/sample.pdf")
    assert pdf_path.exists(), "Sample PDF fixture does not exist"

    doc_id = None
    try:
        # Step 1: POST PDF -> upload and trigger full processing pipeline
        with open(pdf_path, "rb") as f:
            upload_resp = client.post(
                "/api/v1/documents",
                files={"file": ("evaluator_test.pdf", f, "application/pdf")}
            )
        assert upload_resp.status_code == 201
        upload_data = upload_resp.json()
        assert "document_id" in upload_data
        doc_id = upload_data["document_id"]
        assert upload_data["status"] == "processed"
        assert upload_data["page_count"] >= 1

        # Step 2: GET document -> retrieve metadata
        doc_resp = client.get(f"/api/v1/documents/{doc_id}")
        assert doc_resp.status_code == 200
        doc_meta = doc_resp.json()
        assert doc_meta["document_id"] == doc_id
        assert doc_meta["status"] == "processed"
        assert doc_meta["page_count"] >= 1

        # Step 3: GET facts -> inspect extracted facts for this document
        facts_resp = client.get(f"/api/v1/documents/{doc_id}/facts")
        assert facts_resp.status_code == 200
        facts_data = facts_resp.json()
        assert "items" in facts_data
        assert "total" in facts_data

        # Step 4: GET individual fact -> verify provenance traceability
        if facts_data["total"] > 0:
            first_fact_id = facts_data["items"][0]["fact_id"]
            fact_resp = client.get(f"/api/v1/facts/{first_fact_id}")
            assert fact_resp.status_code == 200
            fact_data = fact_resp.json()
            assert fact_data["fact_id"] == first_fact_id
            assert "evidence" in fact_data
            assert len(fact_data["evidence"]) > 0
            assert "page" in fact_data["evidence"][0]

        # Step 5: GET relationships -> inspect cross-document relations
        rels_resp = client.get(f"/api/v1/relationships?document_id={doc_id}")
        assert rels_resp.status_code == 200
        assert "items" in rels_resp.json()

        # Step 6: POST query -> ask natural language query and verify grounded evidence
        query_resp = client.post(
            "/api/v1/query",
            json={"query": "financial and operational metrics in document"}
        )
        assert query_resp.status_code == 200
        q_data = query_resp.json()
        assert q_data["status"] in ("answered", "ambiguous")
        assert len(q_data["facts"]) > 0
        assert len(q_data["facts"][0]["evidence"]) > 0
    finally:
        # Cleanup temporary uploaded file and generated artifacts
        for p in [
            Path("data/input/evaluator_test.pdf"),
            Path(f"data/parsed/{doc_id}.json") if doc_id else None,
            Path(f"data/facts/{doc_id}.json") if doc_id else None,
        ]:
            if p and p.exists():
                p.unlink(missing_ok=True)
