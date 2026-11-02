import pytest

from app.core.config import Settings
from app.core.errors import (
    BlurryImageError,
    ExtractionFailedError,
    InvalidEmailError,
    NotAnIdentityDocumentError,
    UnsupportedFileTypeError,
)
from app.schemas import ExtractedDocument
from app.services.onboarding_service import (
    OnboardingService,
    is_valid_document_number,
    normalize_document_number,
    normalize_email,
)
from tests.helpers import FakeOcr, FakeRepository, make_blurry_image, make_document_image


def build_service(ocr: FakeOcr | None = None):
    repository = FakeRepository()
    ocr = ocr or FakeOcr()
    return OnboardingService(repository, ocr, Settings()), repository, ocr


def extracted(**overrides) -> ExtractedDocument:
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


def test_happy_path_stores_a_verified_record():
    service, repository, ocr = build_service()
    result = service.process("  Maria@Example.COM ", "dni.png", make_document_image())

    assert result.status == "VERIFIED"
    assert result.email == "maria@example.com"
    assert result.ocr_confidence == 97.0
    assert ocr.calls == 1
    assert len(repository.created) == 1
    assert repository.created[0].document_number == "12345678"


def test_low_confidence_needs_review():
    service, _, _ = build_service(FakeOcr(extracted(confidence=0.6)))
    assert service.process("a@b.co", "x.png", make_document_image()).status == "NEEDS_REVIEW"


def test_malformed_dni_number_needs_review():
    service, _, _ = build_service(FakeOcr(extracted(document_number="12AB")))
    assert service.process("a@b.co", "x.png", make_document_image()).status == "NEEDS_REVIEW"


def test_invalid_email_never_reaches_ocr_or_database():
    service, repository, ocr = build_service()
    with pytest.raises(InvalidEmailError):
        service.process("not-an-email", "x.png", make_document_image())
    assert ocr.calls == 0 and repository.created == []


def test_unsupported_file_never_reaches_ocr():
    service, _, ocr = build_service()
    with pytest.raises(UnsupportedFileTypeError):
        service.process("a@b.co", "x.pdf", b"%PDF-1.4 ...")
    assert ocr.calls == 0


def test_blurry_image_is_rejected_before_ocr():
    service, _, ocr = build_service()
    with pytest.raises(BlurryImageError):
        service.process("a@b.co", "x.png", make_blurry_image())
    assert ocr.calls == 0


def test_model_says_not_an_identity_document():
    service, repository, _ = build_service(FakeOcr(extracted(is_identity_document=False)))
    with pytest.raises(NotAnIdentityDocumentError):
        service.process("a@b.co", "x.png", make_document_image())
    assert repository.created == []


def test_model_says_illegible():
    service, _, _ = build_service(FakeOcr(extracted(is_legible=False)))
    with pytest.raises(BlurryImageError):
        service.process("a@b.co", "x.png", make_document_image())


def test_missing_fields_fail_extraction():
    service, repository, _ = build_service(FakeOcr(extracted(document_number=None)))
    with pytest.raises(ExtractionFailedError):
        service.process("a@b.co", "x.png", make_document_image())
    assert repository.created == []


def test_normalizers():
    assert normalize_email(" USER@Mail.com ") == "user@mail.com"
    assert normalize_document_number("12 345 678", "DNI") == "12345678"
    assert normalize_document_number("12345678-9", "DNI") == "12345678"
    assert is_valid_document_number("12345678", "DNI")
    assert not is_valid_document_number("1234", "DNI")
    assert is_valid_document_number("AB123456", "PASSPORT")
