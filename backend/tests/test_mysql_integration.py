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


# ---------- admin dashboard (read model, filters, audit trail, erasure) ----------


def test_admin_stats_count_every_status(repository, settings):
    before = repository.stats()
    verified = service_for(repository, settings, unique_number()).process(unique_email(), "a.png", unique_image())
    flagged = service_for(repository, settings, unique_number(), confidence=0.4).process(
        unique_email(), "b.png", unique_image()
    )
    OnboardingService(repository, FakeOcr(), settings).review(flagged.id, "REJECTED", "Ana", None)

    after = repository.stats()

    assert after.total == before.total + 2
    assert after.verified == before.verified + 1
    assert after.rejected == before.rejected + 1
    assert after.needs_review == before.needs_review
    assert verified.status == "VERIFIED"


def test_daily_counts_include_today(repository, settings):
    service_for(repository, settings, unique_number()).process(unique_email(), "a.png", unique_image())
    series = repository.daily_counts(7)
    assert len(series) == 7 and series[-1].total >= 1


def test_search_filters_and_paginates(repository, settings):
    from app.schemas import AdminFilters

    marker = uuid.uuid4().hex[:8]
    emails = [f"{marker}-{index}@example.com" for index in range(3)]
    for index, email in enumerate(emails):
        service_for(repository, settings, unique_number(), confidence=0.97 if index else 0.4).process(
            email, "dni.png", unique_image()
        )

    everything, total = repository.search(AdminFilters(query=marker), 25, 0)
    assert total == 3 and {item.email for item in everything} == set(emails)

    flagged, flagged_total = repository.search(AdminFilters(status="NEEDS_REVIEW", query=marker), 25, 0)
    assert flagged_total == 1 and flagged[0].email == emails[0]

    first_page, page_total = repository.search(AdminFilters(query=marker), 2, 0)
    second_page, _ = repository.search(AdminFilters(query=marker), 2, 2)
    assert page_total == 3 and len(first_page) == 2 and len(second_page) == 1

    nothing, zero = repository.search(AdminFilters(query=marker, status="APPROVED"), 25, 0)
    assert nothing == [] and zero == 0


def test_search_treats_like_wildcards_literally(repository, settings):
    from app.schemas import AdminFilters

    service_for(repository, settings, unique_number()).process(unique_email(), "dni.png", unique_image())
    _, total = repository.search(AdminFilters(query="%"), 25, 0)
    assert total == 0  # no email, name or number contains a percent sign


def test_event_trail_lists_registration_flags_and_decision(repository, settings):
    service = service_for(repository, settings, unique_number(), confidence=0.4)
    created = service.process(unique_email(), "dni.png", unique_image())
    service.review(created.id, "APPROVED", "Ana", "name matches")

    events = repository.list_events(created.id)

    assert [event.event_type for event in events] == ["REGISTERED", "FLAGGED", "APPROVED"]
    assert events[1].detail == "LOW_CONFIDENCE"
    assert events[2].actor == "Ana" and events[2].detail == "name matches"


def test_anonymize_erases_personal_data_but_keeps_the_audit_trail(repository, settings):
    email = unique_email()
    service = service_for(repository, settings, unique_number(), confidence=0.4)
    created = service.process(email, "dni.png", unique_image())
    service.review(created.id, "APPROVED", "Ana", "the customer phoned us")

    erased = repository.anonymize(created.id, "Luis", "customer request")

    assert erased.status == "ERASED"
    assert erased.full_name == "[erased]"
    assert erased.document_number == f"ERASED-{created.id}"
    assert erased.email == f"erased-{created.id}@anonymized.invalid"
    assert erased.original_filename is None and erased.review_comment is None
    assert repository.list_by_email(email) == []  # the real customer is gone
    events = repository.list_events(created.id)
    assert events[-1].event_type == "ANONYMIZED" and events[-1].actor == "Luis"
    assert repository.stats().erased >= 1


def test_anonymize_is_refused_twice_and_for_unknown_records(repository, settings):
    created = service_for(repository, settings, unique_number()).process(unique_email(), "a.png", unique_image())
    repository.anonymize(created.id, "Luis", None)
    with pytest.raises(ConflictError):
        repository.anonymize(created.id, "Luis", None)
    with pytest.raises(ConflictError):
        repository.anonymize(999_999_999, "Luis", None)


def test_an_anonymized_record_cannot_be_reviewed_even_through_the_procedure(repository, settings):
    created = service_for(repository, settings, unique_number(), confidence=0.4).process(
        unique_email(), "a.png", unique_image()
    )
    repository.anonymize(created.id, "Luis", None)
    with pytest.raises(ConflictError):
        repository.review(created.id, "APPROVED", "Ana", None)
    assert created.id not in [record.id for record in repository.list_pending_reviews(500)]


def test_anonymizing_one_record_keeps_the_other_records_of_the_same_customer(repository, settings):
    email = unique_email()
    first = service_for(repository, settings, unique_number()).process(email, "a.png", unique_image())
    second = service_for(repository, settings, unique_number()).process(email, "b.png", unique_image())

    repository.anonymize(first.id, "Luis", None)

    assert [record.id for record in repository.list_by_email(email)] == [second.id]


def test_retention_lists_only_old_unerased_records(repository, settings):
    created = service_for(repository, settings, unique_number()).process(unique_email(), "a.png", unique_image())
    assert created.id not in repository.list_expired_ids(30, 1000)
    # A cutoff one day in the future (-1) makes every record "expired" without waiting or touching timestamps.
    assert created.id in repository.list_expired_ids(-1, 100_000)
    repository.anonymize(created.id, "retention-policy", "Older than the cutoff")
    assert created.id not in repository.list_expired_ids(-1, 100_000)
