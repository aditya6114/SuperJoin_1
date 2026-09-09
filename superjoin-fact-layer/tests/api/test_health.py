import pytest
from fastapi.testclient import TestClient
from superjoin.api.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_health_root(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "superjoin-fact-layer"


def test_health_api_v1(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "superjoin-fact-layer"


def test_openapi_documentation(client):
    docs_resp = client.get("/docs")
    assert docs_resp.status_code == 200

    openapi_resp = client.get("/openapi.json")
    assert openapi_resp.status_code == 200
    schema = openapi_resp.json()
    assert schema["info"]["title"] == "Superjoin Fact Knowledge Layer API"
    assert schema["info"]["version"] == "0.1.0"
    tag_names = [t["name"] for t in schema["tags"]]
    assert "Documents" in tag_names
    assert "Facts" in tag_names
    assert "Relationships" in tag_names
    assert "Query" in tag_names
    assert "System" in tag_names
