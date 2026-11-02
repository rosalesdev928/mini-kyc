"""HTTP-level tests: the whole API with a fake OCR and an in-memory repository."""

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.dependencies import get_onboarding_service, get_repository
from app.main import create_app
from app.schemas import ExtractedDocument
from app.services.onboarding_service import OnboardingService
from tests.helpers import FakeOcr, FakeRepository, make_blurry_image, make_document_image


def make_client(ocr: FakeOcr | None = None, **settings_overrides) -> TestClient:
    values = dict(
        auto_migrate=False,
        ocr_provider="mock",
        max_upload_bytes=200_000,
        gemini_api_key="",
        review_api_key="",
        data_retention_days=0,  # no background job in tests
        rate_limit_uploads_per_minute=0,  # limits are switched on only by the tests that exercise them
        rate_limit_history_per_minute=0,
    )
    values.update(settings_overrides)
    settings = Settings(**values)
    app = create_app(settings)
    repository = FakeRepository()
    service = OnboardingService(repository, ocr or FakeOcr(), settings)
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_repository] = lambda: repository
    app.dependency_overrides[get_onboarding_service] = lambda: service
    return TestClient(app)


@pytest.fixture
def client():
    return make_client()


def post(
    client, *, email="maria@example.com", content=None, filename="dni.png", content_type="image/png", headers=None
):
    files = {"document": (filename, content if content is not None else make_document_image(), content_type)}
    return client.post("/api/v1/onboarding", data={"email": email}, files=files, headers=headers)


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


def test_there_is_no_public_lookup_by_record_id(client):
    """Sequential ids would let anyone walk through other people's data: records are read by email (masked)
    or through the protected admin endpoints."""
    post(client)
    assert client.get("/api/v1/onboarding/1").status_code == 404


def test_history_lookup_masks_the_document_number(client):
    post(client, email="maria@example.com")
    response = client.get("/api/v1/onboarding", params={"email": "maria@example.com"})
    assert response.status_code == 200
    assert response.json()[0]["document_number"] == "*****678"


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


# ---------- request id ----------


def test_every_response_carries_a_request_id(client):
    response = client.get("/api/v1/health")
    assert response.headers["x-request-id"]


def test_client_supplied_request_id_is_echoed_after_sanitizing(client):
    response = client.get("/api/v1/health", headers={"X-Request-ID": "trace-42 <script>"})
    assert response.headers["x-request-id"] == "trace-42script"


# ---------- operator review ----------

OPERATOR = {"X-Review-Key": "secret"}


def low_confidence_ocr() -> FakeOcr:
    return FakeOcr(
        ExtractedDocument(
            is_identity_document=True,
            is_legible=True,
            document_type="DNI",
            full_name="Maria Fernandez Torres",
            document_number="12345678",
            confidence=0.5,
        )
    )


def test_review_endpoints_are_disabled_without_a_configured_key(client):
    response = client.get("/api/v1/reviews/pending", headers=OPERATOR)
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "REVIEW_DISABLED"


def test_review_endpoints_reject_a_missing_or_wrong_key():
    client = make_client(review_api_key="secret")
    assert client.get("/api/v1/reviews/pending").status_code == 401
    wrong = client.get("/api/v1/reviews/pending", headers={"X-Review-Key": "nope"})
    assert wrong.status_code == 401
    assert wrong.json()["error"]["code"] == "UNAUTHORIZED"


def test_operator_can_list_and_approve_a_flagged_record():
    client = make_client(low_confidence_ocr(), review_api_key="secret")
    created = post(client).json()
    assert created["status"] == "NEEDS_REVIEW"
    assert created["flags"] == ["LOW_CONFIDENCE"]

    pending = client.get("/api/v1/reviews/pending", headers=OPERATOR)
    assert [record["id"] for record in pending.json()] == [created["id"]]

    decision = {"decision": "APPROVED", "reviewer": "Ana", "comment": "name matches the photo"}
    reviewed = client.post(f"/api/v1/reviews/{created['id']}", json=decision, headers=OPERATOR)
    assert reviewed.status_code == 200
    assert reviewed.json()["status"] == "APPROVED"
    assert reviewed.json()["reviewed_by"] == "Ana"
    assert client.get("/api/v1/reviews/pending", headers=OPERATOR).json() == []


def test_a_record_cannot_be_reviewed_twice_over_http():
    client = make_client(low_confidence_ocr(), review_api_key="secret")
    record_id = post(client).json()["id"]
    url = f"/api/v1/reviews/{record_id}"
    assert client.post(url, json={"decision": "REJECTED"}, headers=OPERATOR).status_code == 200
    second = client.post(url, json={"decision": "APPROVED"}, headers=OPERATOR)
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "NOT_PENDING_REVIEW"


def test_review_validates_the_decision_and_the_record():
    client = make_client(low_confidence_ocr(), review_api_key="secret")
    record_id = post(client).json()["id"]
    bad = client.post(f"/api/v1/reviews/{record_id}", json={"decision": "MAYBE"}, headers=OPERATOR)
    assert bad.status_code == 422
    assert bad.json()["error"]["code"] == "VALIDATION_ERROR"
    missing = client.post("/api/v1/reviews/999", json={"decision": "APPROVED"}, headers=OPERATOR)
    assert missing.status_code == 404


# ---------- security: headers and abuse protection ----------


def test_security_headers_are_sent_on_every_response(client):
    response = client.get("/api/v1/health")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert "default-src 'self'" in response.headers["content-security-policy"]


def test_swagger_pages_are_exempt_from_the_csp_but_keep_the_other_headers(client):
    response = client.get("/docs")
    assert "content-security-policy" not in response.headers
    assert response.headers["x-content-type-options"] == "nosniff"


def test_uploads_are_rate_limited_per_ip():
    client = make_client(rate_limit_uploads_per_minute=2)
    assert post(client).status_code == 201
    assert post(client).status_code == 201
    third = post(client)
    assert third.status_code == 429
    assert third.json()["error"]["code"] == "TOO_MANY_REQUESTS"
    assert int(third.headers["retry-after"]) >= 1
    assert post(client, headers={"X-Forwarded-For": "203.0.113.9"}).status_code == 201  # another IP


def test_wrong_operator_keys_lock_the_ip_out_for_a_while():
    client = make_client(review_api_key="secret", rate_limit_admin_failures=3)
    for _ in range(3):
        assert client.get("/api/v1/admin/overview", headers={"X-Review-Key": "bad"}).status_code == 401
    blocked = client.get("/api/v1/admin/overview", headers=OPERATOR)  # even the right key is refused now
    assert blocked.status_code == 429
    assert blocked.json()["error"]["code"] == "TOO_MANY_REQUESTS"
    assert "retry-after" in blocked.headers
    elsewhere = client.get("/api/v1/admin/overview", headers={**OPERATOR, "X-Forwarded-For": "203.0.113.7"})
    assert elsewhere.status_code == 200


# ---------- admin dashboard ----------

ADMIN_PATHS = (
    "/api/v1/admin/overview",
    "/api/v1/admin/onboardings",
    "/api/v1/admin/export.csv",
    "/api/v1/admin/onboardings/1",
)


def test_admin_endpoints_are_disabled_without_a_configured_key(client):
    for path in ADMIN_PATHS:
        assert client.get(path, headers=OPERATOR).status_code == 503


def test_admin_endpoints_reject_a_missing_or_wrong_key():
    client = make_client(review_api_key="secret")
    for path in ADMIN_PATHS:
        assert client.get(path).status_code == 401
        assert client.get(path, headers={"X-Review-Key": "nope"}).status_code == 401


def test_admin_overview_and_filtered_listing():
    client = make_client(review_api_key="secret")
    post(client, email="a@example.com")

    overview = client.get("/api/v1/admin/overview", headers=OPERATOR).json()
    assert overview["stats"]["total"] == 1 and overview["stats"]["verified"] == 1
    assert len(overview["last_days"]) == 7

    page = client.get(
        "/api/v1/admin/onboardings", params={"status": "VERIFIED", "q": "a@", "limit": 10}, headers=OPERATOR
    ).json()
    assert page["total"] == 1 and page["items"][0]["email"] == "a@example.com"
    empty = client.get("/api/v1/admin/onboardings", params={"status": "REJECTED"}, headers=OPERATOR).json()
    assert empty["total"] == 0 and empty["items"] == []


def test_admin_listing_validates_its_filters():
    client = make_client(review_api_key="secret")
    unknown = client.get("/api/v1/admin/onboardings", params={"status": "PENDING"}, headers=OPERATOR)
    assert unknown.status_code == 422
    inverted = client.get(
        "/api/v1/admin/onboardings",
        params={"date_from": "2026-02-01", "date_to": "2026-01-01"},
        headers=OPERATOR,
    )
    assert inverted.status_code == 422
    assert inverted.json()["error"]["code"] == "INVALID_FILTER"
    assert client.get("/api/v1/admin/onboardings", params={"limit": 0}, headers=OPERATOR).status_code == 422


def test_admin_csv_export_masks_document_numbers():
    client = make_client(review_api_key="secret")
    post(client)
    response = client.get("/api/v1/admin/export.csv", headers=OPERATOR)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "attachment" in response.headers["content-disposition"]
    assert "*****678" in response.text and "12345678" not in response.text


def test_admin_detail_shows_the_audit_trail_and_unknown_ids_are_404():
    client = make_client(low_confidence_ocr(), review_api_key="secret")
    record_id = post(client).json()["id"]
    client.post(f"/api/v1/reviews/{record_id}", json={"decision": "APPROVED", "reviewer": "Ana"}, headers=OPERATOR)

    detail = client.get(f"/api/v1/admin/onboardings/{record_id}", headers=OPERATOR).json()

    assert detail["record"]["status"] == "APPROVED"
    assert [event["event_type"] for event in detail["events"]] == ["REGISTERED", "FLAGGED", "APPROVED"]
    missing = client.get("/api/v1/admin/onboardings/999", headers=OPERATOR)
    assert missing.status_code == 404 and missing.json()["error"]["code"] == "NOT_FOUND"


def test_admin_can_anonymize_a_record_once():
    client = make_client(review_api_key="secret")
    record_id = post(client, email="maria@example.com").json()["id"]
    url = f"/api/v1/admin/onboardings/{record_id}/anonymize"

    erased = client.post(url, json={"reviewer": "Ana", "reason": "customer request"}, headers=OPERATOR)

    assert erased.status_code == 200
    assert erased.json()["status"] == "ERASED" and erased.json()["full_name"] == "[erased]"
    assert client.post(url, json={}, headers=OPERATOR).status_code == 409
    assert client.post("/api/v1/admin/onboardings/999/anonymize", json={}, headers=OPERATOR).status_code == 404
    assert client.get("/api/v1/onboarding", params={"email": "maria@example.com"}).json() == []


def test_an_anonymized_record_cannot_be_reviewed():
    client = make_client(low_confidence_ocr(), review_api_key="secret")
    record_id = post(client).json()["id"]
    client.post(f"/api/v1/admin/onboardings/{record_id}/anonymize", json={}, headers=OPERATOR)
    response = client.post(f"/api/v1/reviews/{record_id}", json={"decision": "APPROVED"}, headers=OPERATOR)
    assert response.status_code == 409
