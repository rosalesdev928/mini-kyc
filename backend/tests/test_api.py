"""HTTP-level tests: the whole API with a fake OCR and an in-memory repository."""

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.dependencies import get_onboarding_service, get_repository
from app.main import create_app
from app.services.onboarding_service import OnboardingService
from tests.helpers import FakeOcr, FakeRepository, make_blurry_image, make_document_image


@pytest.fixture
def client():
    settings = Settings(auto_migrate=False, ocr_provider="mock", max_upload_bytes=200_000, gemini_api_key="")
    app = create_app(settings)
    repository = FakeRepository()
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_repository] = lambda: repository
    app.dependency_overrides[get_onboarding_service] = lambda: OnboardingService(
        repository, FakeOcr(), settings
    )
    return TestClient(app)


def post(client, *, email="maria@example.com", content=None, filename="dni.png", content_type="image/png"):
    files = {"document": (filename, content if content is not None else make_document_image(), content_type)}
    return client.post("/api/v1/onboarding", data={"email": email}, files=files)


def test_create_onboarding_returns_201_with_extracted_data(client):
    response = post(client)
    assert response.status_code == 201
    body = response.json()
    assert body["full_name"] == "Maria Fernandez Torres"
    assert body["document_number"] == "12345678"
    assert body["status"] == "VERIFIED"
    assert body["created_at"].endswith("Z")


def test_pdf_upload_returns_415(client):
    response = post(client, content=b"%PDF-1.7 not an image", filename="id.pdf", content_type="application/pdf")
    assert response.status_code == 415
    assert response.json()["error"]["code"] == "UNSUPPORTED_FILE_TYPE"


def test_renamed_non_image_is_still_rejected(client):
    response = post(client, content=b"just text", filename="dni.png", content_type="image/png")
    assert response.status_code == 415


def test_blurry_image_returns_422(client):
    response = post(client, content=make_blurry_image())
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "BLURRY_IMAGE"


def test_oversized_file_returns_413(client):
    response = post(client, content=b"\x89PNG\r\n\x1a\n" + b"0" * 250_000)
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "FILE_TOO_LARGE"


def test_invalid_email_returns_422(client):
    response = post(client, email="nope")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_EMAIL"


def test_missing_file_returns_controlled_validation_error(client):
    response = client.post("/api/v1/onboarding", data={"email": "a@b.co"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_unknown_record_returns_404(client):
    response = client.get("/api/v1/onboarding/999")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_health_accepts_head_requests(client):
    assert client.head("/api/v1/health").status_code == 200


def test_health_reports_database_up(client):
    assert client.get("/api/v1/health").json() == {"status": "ok", "database": "up"}


def test_chat_answers_from_the_faq(client):
    response = client.post("/api/v1/chat", json={"question": "Which image formats are accepted?"})
    assert response.status_code == 200
    assert "JPG" in response.json()["answer"]


def test_swagger_docs_are_available(client):
    assert client.get("/docs").status_code == 200
    assert client.get("/openapi.json").json()["info"]["title"].startswith("Mini KYC")
