from fastapi.testclient import TestClient

from app.main import create_app


def test_health_endpoint():
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_index_renders_setup_guidance_without_credentials():
    client = TestClient(create_app())

    response = client.get("/")

    assert response.status_code == 200
    assert "Read Doc Analytics" in response.text
    assert "GOOGLE_CLIENT_ID" in response.text

