"""Test helpers: synthetic images and in-memory fakes (no network, no database)."""

import io

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from app.schemas import ExtractedDocument, NewOnboarding, OnboardingResponse


def make_document_image(width: int = 900, height: int = 570, fmt: str = "PNG", tag: str = "") -> bytes:
    """A sharp, synthetic ID-like card (clearly fake: it says SAMPLE).

    `tag` is printed in a corner so that tests can create images with different hashes.
    """
    image = Image.new("RGB", (width, height), (236, 240, 244))
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=26)
    draw.rectangle([20, 20, width - 20, height - 20], outline=(30, 60, 90), width=4)
    lines = ["SAMPLE ID CARD", "NOT A REAL DOCUMENT", "DNI 12345678", "FERNANDEZ TORRES", "MARIA"]
    for index, text in enumerate(lines):
        draw.text((50, 50 + index * 65), text, font=font, fill=(20, 40, 70))
    draw.rectangle([620, 120, 840, 380], fill=(150, 160, 175))
    if tag:
        draw.text((50, height - 60), tag, font=ImageFont.load_default(size=14), fill=(20, 40, 70))
    return _encode(image, fmt)


def make_blurry_image() -> bytes:
    sharp = Image.open(io.BytesIO(make_document_image()))
    return _encode(sharp.filter(ImageFilter.GaussianBlur(5)), "PNG")


def _encode(image: Image.Image, fmt: str) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, fmt)
    return buffer.getvalue()


class FakeOcr:
    def __init__(self, result: ExtractedDocument | None = None):
        self.calls = 0
        self.result = result or ExtractedDocument(
            is_identity_document=True,
            is_legible=True,
            document_type="DNI",
            full_name="Maria Fernandez Torres",
            document_number="12345678",
            confidence=0.97,
        )

    def extract(self, image_bytes: bytes, mime_type: str) -> ExtractedDocument:
        self.calls += 1
        return self.result


class FakeRepository:
    """In-memory stand-in for OnboardingRepository (same behaviour as the stored procedures)."""

    def __init__(self):
        self.created: list[NewOnboarding] = []
        self.records: dict[int, OnboardingResponse] = {}
        self._signature: dict[int, tuple[str, str, str]] = {}  # id -> (document number, image hash, email)

    def create(self, new_record: NewOnboarding) -> OnboardingResponse:
        from datetime import datetime, timezone

        self.created.append(new_record)
        record = OnboardingResponse(
            id=len(self.created),
            email=new_record.email,
            document_type=new_record.document_type,
            full_name=new_record.full_name,
            document_number=new_record.document_number,
            ocr_confidence=new_record.ocr_confidence,
            status=new_record.status,
            flags=list(new_record.flags),
            original_filename=new_record.original_filename,
            created_at=datetime.now(timezone.utc),
        )
        self.records[record.id] = record
        self._signature[record.id] = (
            new_record.document_number, new_record.image_sha256, new_record.email
        )
        return record

    def find_duplicate_signals(self, document_number: str, image_sha256: str, email: str):
        from app.schemas import DuplicateSignals

        others = [sig for sig in self._signature.values() if sig[2] != email]
        return DuplicateSignals(
            same_number_other_email=sum(sig[0] == document_number for sig in others),
            same_image_other_email=sum(sig[1] == image_sha256 for sig in others),
        )

    def get_by_id(self, onboarding_id: int):
        return self.records.get(onboarding_id)

    def list_by_email(self, email: str, limit: int = 20):
        return [r for r in self.records.values() if r.email == email][:limit]

    def list_pending_reviews(self, limit: int = 50):
        return [r for r in self.records.values() if r.status == "NEEDS_REVIEW"][:limit]

    def review(self, onboarding_id: int, decision: str, reviewer: str, comment: str | None):
        from datetime import datetime, timezone

        updated = self.records[onboarding_id].model_copy(
            update={
                "status": decision,
                "reviewed_by": reviewer,
                "review_comment": comment,
                "reviewed_at": datetime.now(timezone.utc),
            }
        )
        self.records[onboarding_id] = updated
        return updated

    def ping(self) -> bool:
        return True
