"""Test helpers: synthetic images and in-memory fakes (no network, no database)."""

import io
from datetime import datetime, timedelta, timezone

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from app.schemas import (
    AdminFilters,
    AdminStats,
    DailyCount,
    DuplicateSignals,
    ExtractedDocument,
    NewOnboarding,
    OnboardingEvent,
    OnboardingResponse,
)


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
        self._events: dict[int, list[OnboardingEvent]] = {}

    # ---------- onboarding ----------

    def create(self, new_record: NewOnboarding) -> OnboardingResponse:
        self.created.append(new_record)
        now = datetime.now(timezone.utc)
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
            created_at=now,
        )
        self.records[record.id] = record
        self._signature[record.id] = (
            new_record.document_number, new_record.image_sha256, new_record.email
        )
        events = [OnboardingEvent(event_type="REGISTERED", detail=new_record.status, occurred_at=now)]
        events += [
            OnboardingEvent(event_type="FLAGGED", detail=code, occurred_at=now) for code in new_record.flags
        ]
        self._events[record.id] = events
        return record

    def find_duplicate_signals(self, document_number: str, image_sha256: str, email: str):
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
        now = datetime.now(timezone.utc)
        updated = self.records[onboarding_id].model_copy(
            update={
                "status": decision,
                "reviewed_by": reviewer,
                "review_comment": comment,
                "reviewed_at": now,
            }
        )
        self.records[onboarding_id] = updated
        self._events[onboarding_id].append(
            OnboardingEvent(event_type=decision, actor=reviewer, detail=comment, occurred_at=now)
        )
        return updated

    # ---------- admin dashboard ----------

    def stats(self) -> AdminStats:
        records = list(self.records.values())
        count = lambda status: sum(r.status == status for r in records)  # noqa: E731
        average = sum(r.ocr_confidence for r in records) / len(records) if records else 0.0
        return AdminStats(
            total=len(records),
            verified=count("VERIFIED"),
            needs_review=count("NEEDS_REVIEW"),
            approved=count("APPROVED"),
            rejected=count("REJECTED"),
            erased=count("ERASED"),
            avg_confidence=round(average, 2),
        )

    def daily_counts(self, days: int):
        today = datetime.now(timezone.utc).date()
        series = [today - timedelta(days=offset) for offset in range(days - 1, -1, -1)]
        return [
            DailyCount(day=day, total=sum(r.created_at.date() == day for r in self.records.values()))
            for day in series
        ]

    def search(self, filters: AdminFilters, limit: int, offset: int):
        query = filters.query.lower()
        matches = [
            r
            for r in sorted(self.records.values(), key=lambda r: (r.created_at, r.id), reverse=True)
            if (not filters.status or r.status == filters.status)
            and (
                not query
                or query in r.email.lower()
                or query in r.full_name.lower()
                or query in r.document_number.lower()
            )
            and (filters.date_from is None or r.created_at.date() >= filters.date_from)
            and (filters.date_to is None or r.created_at.date() <= filters.date_to)
        ]
        return matches[offset : offset + limit], len(matches)

    def list_events(self, onboarding_id: int):
        return list(self._events.get(onboarding_id, []))

    def anonymize(self, onboarding_id: int, actor: str, reason: str | None):
        from app.core.errors import ConflictError

        record = self.records.get(onboarding_id)
        if record is None:
            raise ConflictError("Onboarding record not found")
        if record.status == "ERASED":
            raise ConflictError("This record was already anonymized")
        erased = record.model_copy(
            update={
                "status": "ERASED",
                "email": f"erased-{onboarding_id}@anonymized.invalid",
                "full_name": "[erased]",
                "document_number": f"ERASED-{onboarding_id}",
                "original_filename": None,
                "review_comment": None,
            }
        )
        self.records[onboarding_id] = erased
        self._signature[onboarding_id] = (erased.document_number, f"erased:{onboarding_id}", erased.email)
        self._events[onboarding_id].append(
            OnboardingEvent(
                event_type="ANONYMIZED", actor=actor, detail=reason, occurred_at=datetime.now(timezone.utc)
            )
        )
        return erased

    def list_expired_ids(self, older_than_days: int, limit: int = 200):
        cutoff = datetime.now(timezone.utc) - timedelta(days=older_than_days)
        return [
            r.id for r in self.records.values() if r.status != "ERASED" and r.created_at < cutoff
        ][:limit]

    def age_record(self, onboarding_id: int, days: int) -> None:
        """Test helper: pretend the record was created `days` days ago."""
        record = self.records[onboarding_id]
        self.records[onboarding_id] = record.model_copy(
            update={"created_at": record.created_at - timedelta(days=days)}
        )

    def ping(self) -> bool:
        return True
