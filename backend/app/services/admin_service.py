"""Business logic of the admin dashboard: statistics, filtered listing, audit trail, CSV export and erasure."""

import csv
import io
import logging
from datetime import date

from app.core.config import Settings
from app.core.errors import ConflictError, InvalidFilterError, NotFoundError
from app.repositories.onboarding_repository import OnboardingRepository
from app.schemas import (
    AdminFilters,
    AdminOverview,
    AdminPage,
    OnboardingDetail,
    OnboardingResponse,
    mask_document_number,
)

logger = logging.getLogger(__name__)

STATUS_FILTERS = ("VERIFIED", "NEEDS_REVIEW", "APPROVED", "REJECTED", "ERASED")
MAX_EXPORT_ROWS = 5000
_EXPORT_PAGE_SIZE = 500
_RETENTION_BATCH = 200
_RETENTION_MAX_BATCHES = 10
CSV_COLUMNS = (
    "id",
    "created_at_utc",
    "email",
    "full_name",
    "document_type",
    "document_number_masked",
    "ocr_confidence",
    "status",
    "review_flags",
    "reviewed_by",
    "reviewed_at_utc",
)


def build_filters(
    status: str | None, query: str | None, date_from: date | None, date_to: date | None
) -> AdminFilters:
    cleaned_status = (status or "").strip().upper()
    if cleaned_status and cleaned_status not in STATUS_FILTERS:
        raise InvalidFilterError(f"Unknown status filter. Use one of: {', '.join(STATUS_FILTERS)}.")
    if date_from and date_to and date_from > date_to:
        raise InvalidFilterError("The start date must not be after the end date.")
    return AdminFilters(
        status=cleaned_status,
        query=(query or "").strip()[:100],
        date_from=date_from,
        date_to=date_to,
    )


def csv_safe(value: str | None) -> str:
    """Neutralize spreadsheet formulas: a cell that starts with = + - @ (or a tab / CR) would be executed by Excel."""
    text = value or ""
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


class AdminService:
    def __init__(self, repository: OnboardingRepository, settings: Settings):
        self._repository = repository
        self._settings = settings

    def overview(self, days: int = 7) -> AdminOverview:
        return AdminOverview(
            stats=self._repository.stats(), last_days=self._repository.daily_counts(days)
        )

    def search(self, filters: AdminFilters, limit: int, offset: int) -> AdminPage:
        items, total = self._repository.search(filters, limit, offset)
        return AdminPage(items=items, total=total, limit=limit, offset=offset)

    def detail(self, onboarding_id: int) -> OnboardingDetail:
        record = self._repository.get_by_id(onboarding_id)
        if record is None:
            raise NotFoundError(f"Onboarding record {onboarding_id} was not found.")
        return OnboardingDetail(record=record, events=self._repository.list_events(onboarding_id))

    def anonymize(self, onboarding_id: int, reviewer: str, reason: str | None) -> OnboardingResponse:
        record = self._repository.get_by_id(onboarding_id)
        if record is None:
            raise NotFoundError(f"Onboarding record {onboarding_id} was not found.")
        if record.status == "ERASED":
            raise ConflictError("This record was already anonymized.")
        return self._repository.anonymize(
            onboarding_id, reviewer.strip() or "operator", (reason or "").strip() or None
        )

    def export_csv(self, filters: AdminFilters) -> str:
        """The filtered records as CSV text. Document numbers are masked and formulas are neutralized."""
        buffer = io.StringIO()
        writer = csv.writer(buffer, lineterminator="\n")
        writer.writerow(CSV_COLUMNS)
        exported = 0
        while exported < MAX_EXPORT_ROWS:
            page_size = min(_EXPORT_PAGE_SIZE, MAX_EXPORT_ROWS - exported)
            items, _ = self._repository.search(filters, page_size, exported)
            for record in items:
                writer.writerow(
                    [
                        record.id,
                        record.created_at.isoformat(),
                        csv_safe(record.email),
                        csv_safe(record.full_name),
                        record.document_type,
                        mask_document_number(record.document_number),
                        f"{record.ocr_confidence:.1f}",
                        record.status,
                        "|".join(record.flags),
                        csv_safe(record.reviewed_by),
                        record.reviewed_at.isoformat() if record.reviewed_at else "",
                    ]
                )
            exported += len(items)
            if len(items) < page_size:
                break
        return "﻿" + buffer.getvalue()  # BOM: Excel then opens the accents correctly

    def purge_expired(self) -> int:
        """Retention policy: anonymize the records older than DATA_RETENTION_DAYS. Returns how many were erased."""
        days = self._settings.data_retention_days
        if days <= 0:
            return 0
        erased = 0
        for _ in range(_RETENTION_MAX_BATCHES):
            ids = self._repository.list_expired_ids(days, _RETENTION_BATCH)
            if not ids:
                break
            for onboarding_id in ids:
                try:
                    self._repository.anonymize(onboarding_id, "retention-policy", f"Older than {days} days")
                    erased += 1
                except ConflictError:
                    continue  # erased by someone else in the meantime
        if erased:
            logger.info("Retention policy: %d record(s) anonymized (older than %d days)", erased, days)
        return erased
