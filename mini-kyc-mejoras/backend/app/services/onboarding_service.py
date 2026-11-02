"""Business logic of the onboarding flow: validate -> OCR -> store."""

import logging
import re

from app.core.config import Settings
from app.core.errors import (
    BlurryImageError,
    ExtractionFailedError,
    InvalidEmailError,
    NotAnIdentityDocumentError,
    NotFoundError,
    NotPendingReviewError,
)
from app.repositories.onboarding_repository import OnboardingRepository
from app.schemas import (
    FLAG_DUPLICATE_DOCUMENT,
    FLAG_DUPLICATE_IMAGE,
    FLAG_INVALID_DOCUMENT_NUMBER,
    FLAG_LOW_CONFIDENCE,
    ExtractedDocument,
    NewOnboarding,
    OnboardingResponse,
)
from app.services.image_validation import validate_upload
from app.services.ocr_service import OcrProvider

logger = logging.getLogger(__name__)

_EMAIL_PATTERN = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")
_DNI_WITH_CHECK_DIGIT = re.compile(r"^(\d{8})-\d$")
_DNI_PATTERN = re.compile(r"^\d{8}$")
_GENERIC_DOCUMENT_PATTERN = re.compile(r"^[A-Z0-9]{5,20}$")


def normalize_email(email: str) -> str:
    cleaned = (email or "").strip().lower()
    if len(cleaned) > 254 or not _EMAIL_PATTERN.match(cleaned):
        raise InvalidEmailError("Enter a valid email address.")
    return cleaned


def normalize_document_number(raw_number: str, document_type: str) -> str:
    cleaned = re.sub(r"[\s.]", "", raw_number).upper()
    if document_type == "DNI":
        match = _DNI_WITH_CHECK_DIGIT.match(cleaned)
        if match:
            return match.group(1)  # drop the printed check digit
    return cleaned


def is_valid_document_number(number: str, document_type: str) -> bool:
    if document_type == "DNI":
        return bool(_DNI_PATTERN.match(number))
    return bool(_GENERIC_DOCUMENT_PATTERN.match(number))


class OnboardingService:
    def __init__(self, repository: OnboardingRepository, ocr: OcrProvider, settings: Settings):
        self._repository = repository
        self._ocr = ocr
        self._settings = settings

    def process(
        self, email: str, filename: str | None, image_bytes: bytes
    ) -> OnboardingResponse:
        normalized_email = normalize_email(email)
        image = validate_upload(image_bytes, self._settings)

        extracted = self._ocr.extract(image.data, image.mime_type)
        self._ensure_usable(extracted)

        number = normalize_document_number(extracted.document_number or "", extracted.document_type)[:30]
        flags = self._review_flags(extracted, number, image.sha256, normalized_email)
        status = "NEEDS_REVIEW" if flags else "VERIFIED"
        logger.info("Onboarding processed: status=%s flags=%s", status, ",".join(flags) or "-")

        return self._repository.create(
            NewOnboarding(
                email=normalized_email,
                document_type=extracted.document_type,
                full_name=(extracted.full_name or "")[:200],
                document_number=number,
                ocr_confidence=round(extracted.confidence * 100, 2),
                status=status,
                image_sha256=image.sha256,
                original_filename=filename[:255] if filename else None,
                flags=tuple(flags),
            )
        )

    def _review_flags(
        self, extracted: ExtractedDocument, number: str, image_sha256: str, email: str
    ) -> list[str]:
        """Reasons why a human should look at the record. No flags = VERIFIED automatically."""
        flags: list[str] = []
        if extracted.confidence < self._settings.min_verified_confidence:
            flags.append(FLAG_LOW_CONFIDENCE)
        if not is_valid_document_number(number, extracted.document_type):
            flags.append(FLAG_INVALID_DOCUMENT_NUMBER)
        # The same document or photo under a different email may be identity reuse.
        # (The same email uploading again is a normal retry and is not flagged.)
        if self._settings.duplicate_check_enabled:
            signals = self._repository.find_duplicate_signals(number, image_sha256, email)
            if signals.same_number_other_email:
                flags.append(FLAG_DUPLICATE_DOCUMENT)
            if signals.same_image_other_email:
                flags.append(FLAG_DUPLICATE_IMAGE)
        return flags

    def get(self, onboarding_id: int) -> OnboardingResponse:
        record = self._repository.get_by_id(onboarding_id)
        if record is None:
            raise NotFoundError(f"Onboarding record {onboarding_id} was not found.")
        return record

    def list_for_email(self, email: str) -> list[OnboardingResponse]:
        return self._repository.list_by_email(normalize_email(email))

    def list_pending_reviews(self) -> list[OnboardingResponse]:
        return self._repository.list_pending_reviews()

    def review(
        self, onboarding_id: int, decision: str, reviewer: str, comment: str | None
    ) -> OnboardingResponse:
        record = self.get(onboarding_id)
        if record.status != "NEEDS_REVIEW":
            raise NotPendingReviewError(
                f"Record {onboarding_id} is {record.status} and cannot be reviewed."
            )
        return self._repository.review(
            onboarding_id, decision, reviewer.strip() or "operator", (comment or "").strip() or None
        )

    @staticmethod
    def _ensure_usable(extracted: ExtractedDocument) -> None:
        if not extracted.is_identity_document:
            raise NotAnIdentityDocumentError(
                "The image does not look like an identity document. Upload a photo of your ID."
            )
        if not extracted.is_legible:
            raise BlurryImageError(
                "The document text is not legible. Retake the photo in good light without glare."
            )
        if not extracted.full_name or not extracted.document_number:
            raise ExtractionFailedError(
                "The name and document number could not be read. Retake the photo showing the whole document."
            )
