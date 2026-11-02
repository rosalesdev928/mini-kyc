"""Integration tests against a REAL MySQL 8: migrations, stored procedures and the whole service.

They are skipped by default. CI runs them against a MySQL service container; locally:
    RUN_DB_TESTS=1 DB_HOST=127.0.0.1 DB_USER=root DB_PASSWORD=... DB_NAME=mini_kyc pytest tests/test_mysql_integration.py
The default collation of the official mysql:8 image (utf8mb4_0900_ai_ci) is the same one that broke the
first deployment, so these tests also guard against that bug.
"""

import os
import random
import uuid

import pytest

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_DB_TESTS") != "1", reason="set RUN_DB_TESTS=1 and the DB_* variables to run"
)

from app.core.config import Settings  # noqa: E402
from app.core.database import create_pool, run_migrations  # noqa: E402
from app.core.errors import ConflictError, NotPendingReviewError  # noqa: E402
from app.repositories.onboarding_repository import OnboardingRepository  # noqa: E402
from app.schemas import ExtractedDocument  # noqa: E402
from app.services.onboarding_service import OnboardingService  # noqa: E402
from tests.helpers import FakeOcr, make_document_image  # noqa: E402


@pytest.fixture(scope="module")
def settings():
    config = Settings()
    run_migrations(config)
    return config


@pytest.fixture(scope="module")
def repository(settings):
    return OnboardingRepository(create_pool(settings))


def unique_email() -> str:
    return f"user-{uuid.uuid4().hex[:10]}@example.com"


def unique_number() -> str:
    return str(random.randint(10_000_000, 99_999_999))


def unique_image() -> bytes:
    return make_document_image(tag=uuid.uuid4().hex)


def service_for(repository, settings, number: str, confidence: float = 0.97) -> OnboardingService:
    extracted = ExtractedDocument(
        is_identity_document=True,
        is_legible=True,
        document_type="DNI",
        full_name="María Fernández Peña",  # accents: checks utf8mb4 end to end
        document_number=number,
        confidence=confidence,
    )
    return OnboardingService(repository, FakeOcr(extracted), settings)


def test_migrations_are_idempotent(settings):
    run_migrations(settings)  # the app runs them on every start


def test_create_get_and_list_roundtrip(repository, settings):
    email = unique_email()
    service = service_for(repository, settings, unique_number())

    created = service.process(email, "dni.png", unique_image())

    assert created.status == "VERIFIED"
    assert created.flags == []
    assert created.full_name == "María Fernández Peña"
    assert created.created_at.tzinfo is not None
    assert service.get(created.id) == created
    assert [record.id for record in service.list_for_email(email)] == [created.id]


def test_review_flags_are_stored_with_the_record(repository, settings):
    service = service_for(repository, settings, unique_number(), confidence=0.4)

    created = service.process(unique_email(), "dni.png", unique_image())

    assert created.status == "NEEDS_REVIEW"
    assert repository.get_by_id(created.id).flags == ["LOW_CONFIDENCE"]


def test_duplicate_document_under_another_email_is_flagged(repository, settings):
    number = unique_number()
    service = service_for(repository, settings, number)
    first = service.process(unique_email(), "a.png", unique_image())
    second = service.process(unique_email(), "b.png", unique_image())

    assert first.status == "VERIFIED"
    assert second.status == "NEEDS_REVIEW"
    assert second.flags == ["DUPLICATE_DOCUMENT"]
    signals = repository.find_duplicate_signals(number, "0" * 64, "someone-else@example.com")
    assert signals.same_number_other_email >= 2 and signals.same_image_other_email == 0


def test_same_photo_under_another_email_is_flagged(repository, settings):
    photo = unique_image()
    service = service_for(repository, settings, unique_number())
    service.process(unique_email(), "a.png", photo)
    second = service_for(repository, settings, unique_number()).process(unique_email(), "b.png", photo)

    assert second.flags == ["DUPLICATE_IMAGE"]


def test_operator_review_flow(repository, settings):
    service = service_for(repository, settings, unique_number(), confidence=0.4)
    created = service.process(unique_email(), "dni.png", unique_image())
    assert created.id in [record.id for record in service.list_pending_reviews()]

    reviewed = service.review(created.id, "APPROVED", "Ana", "name matches")

    assert reviewed.status == "APPROVED"
    assert reviewed.reviewed_by == "Ana"
    assert reviewed.review_comment == "name matches"
    assert reviewed.reviewed_at is not None
    assert created.id not in [record.id for record in service.list_pending_reviews()]
    with pytest.raises(NotPendingReviewError):
        service.review(created.id, "REJECTED", "Luis", None)


def test_stored_procedure_enforces_the_review_rules_itself(repository, settings):
    """Even if the service were bypassed, the procedure refuses invalid or repeated decisions."""
    created = service_for(repository, settings, unique_number(), confidence=0.4).process(
        unique_email(), "dni.png", unique_image()
    )
    with pytest.raises(ConflictError):
        repository.review(created.id, "MAYBE", "Ana", None)
    repository.review(created.id, "REJECTED", "Ana", None)
    with pytest.raises(ConflictError):
        repository.review(created.id, "APPROVED", "Ana", None)
    with pytest.raises(ConflictError):
        repository.review(999_999_999, "APPROVED", "Ana", None)
