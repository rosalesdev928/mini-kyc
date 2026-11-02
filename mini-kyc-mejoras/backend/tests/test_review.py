"""Duplicate detection and the operator review rules (service level, in-memory repository)."""

import pytest

from app.core.config import Settings
from app.core.errors import NotFoundError, NotPendingReviewError
from app.schemas import ExtractedDocument
from app.services.onboarding_service import OnboardingService
from tests.helpers import FakeOcr, FakeRepository, make_document_image


def doc(**overrides) -> ExtractedDocument:
    values = dict(
        is_identity_document=True,
        is_legible=True,
        document_type="DNI",
        full_name="Maria Fernandez Torres",
        document_number="12345678",
        confidence=0.97,
    )
    values.update(overrides)
    return ExtractedDocument(**values)


def build(ocr_result=None, **settings):
    repository = FakeRepository()
    service = OnboardingService(repository, FakeOcr(ocr_result), Settings(**settings))
    return service, repository


def test_clean_record_has_no_flags():
    service, _ = build()
    record = service.process("a@example.com", "dni.png", make_document_image())
    assert record.status == "VERIFIED"
    assert record.flags == []


def test_low_confidence_and_bad_number_are_flagged():
    service, _ = build(doc(confidence=0.5, document_number="12AB"))
    record = service.process("a@example.com", "dni.png", make_document_image())
    assert record.status == "NEEDS_REVIEW"
    assert record.flags == ["LOW_CONFIDENCE", "INVALID_DOCUMENT_NUMBER"]


def test_same_document_under_another_email_is_flagged():
    service, _ = build()
    service.process("first@example.com", "a.png", make_document_image(tag="one"))
    second = service.process("second@example.com", "b.png", make_document_image(tag="two"))
    assert second.status == "NEEDS_REVIEW"
    assert second.flags == ["DUPLICATE_DOCUMENT"]


def test_same_photo_under_another_email_is_flagged():
    service, _ = build()
    photo = make_document_image(tag="same")
    service.process("first@example.com", "a.png", photo)
    second = service.process("second@example.com", "b.png", photo)
    assert "DUPLICATE_IMAGE" in second.flags
    assert second.status == "NEEDS_REVIEW"


def test_same_email_uploading_again_is_not_a_duplicate():
    service, _ = build()
    photo = make_document_image(tag="retry")
    service.process("same@example.com", "a.png", photo)
    again = service.process("same@example.com", "a.png", photo)
    assert again.status == "VERIFIED"
    assert again.flags == []


def test_duplicate_check_can_be_turned_off():
    service, _ = build(duplicate_check_enabled=False)
    photo = make_document_image(tag="off")
    service.process("first@example.com", "a.png", photo)
    assert service.process("second@example.com", "b.png", photo).status == "VERIFIED"


def flagged_record(service):
    return service.process("low@example.com", "x.png", make_document_image(tag="low"))


def test_pending_list_only_contains_records_needing_review():
    service, _ = build(doc(confidence=0.4))
    pending_record = flagged_record(service)
    assert [r.id for r in service.list_pending_reviews()] == [pending_record.id]


def test_approve_records_the_decision():
    service, _ = build(doc(confidence=0.4))
    record = flagged_record(service)
    reviewed = service.review(record.id, "APPROVED", "  Ana  ", "  looks fine  ")
    assert reviewed.status == "APPROVED"
    assert reviewed.reviewed_by == "Ana"
    assert reviewed.review_comment == "looks fine"
    assert service.list_pending_reviews() == []


def test_verified_records_cannot_be_reviewed():
    service, _ = build()
    record = service.process("ok@example.com", "x.png", make_document_image())
    with pytest.raises(NotPendingReviewError):
        service.review(record.id, "REJECTED", "Ana", None)


def test_a_record_cannot_be_reviewed_twice():
    service, _ = build(doc(confidence=0.4))
    record = flagged_record(service)
    service.review(record.id, "REJECTED", "Ana", "blurry name")
    with pytest.raises(NotPendingReviewError):
        service.review(record.id, "APPROVED", "Luis", None)


def test_reviewing_an_unknown_record_is_not_found():
    service, _ = build()
    with pytest.raises(NotFoundError):
        service.review(999, "APPROVED", "Ana", None)
