"""Admin dashboard logic (service level, in-memory repository)."""

from datetime import date

import pytest

from app.core.config import Settings
from app.core.errors import ConflictError, InvalidFilterError, NotFoundError
from app.schemas import AdminFilters, ExtractedDocument
from app.services.admin_service import AdminService, build_filters, csv_safe
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
    config = Settings(**settings)
    onboarding = OnboardingService(repository, FakeOcr(ocr_result), config)
    return onboarding, AdminService(repository, config), repository


def register(onboarding, email="a@example.com", tag="one"):
    return onboarding.process(email, "dni.png", make_document_image(tag=tag))


# ---------- filters ----------


def test_filters_are_normalized():
    filters = build_filters(" needs_review ", "  maria  ", date(2026, 1, 1), date(2026, 1, 31))
    assert filters == AdminFilters("NEEDS_REVIEW", "maria", date(2026, 1, 1), date(2026, 1, 31))


def test_unknown_status_is_rejected():
    with pytest.raises(InvalidFilterError):
        build_filters("PENDING", None, None, None)


def test_inverted_date_range_is_rejected():
    with pytest.raises(InvalidFilterError):
        build_filters(None, None, date(2026, 2, 1), date(2026, 1, 1))


# ---------- overview and search ----------


def test_overview_counts_by_status_and_fills_empty_days():
    onboarding, admin, _ = build()
    register(onboarding, "a@example.com", "one")
    overview = admin.overview(days=7)
    assert overview.stats.total == 1 and overview.stats.verified == 1
    assert len(overview.last_days) == 7
    assert overview.last_days[-1].total == 1 and overview.last_days[0].total == 0


def test_search_filters_by_status_text_and_dates():
    onboarding, admin, repository = build()
    register(onboarding, "first@example.com", "one")
    register(onboarding, "second@example.com", "two")  # same number, other email -> NEEDS_REVIEW

    everything = admin.search(AdminFilters(), 25, 0)
    assert everything.total == 2

    pending = admin.search(build_filters("NEEDS_REVIEW", None, None, None), 25, 0)
    assert [item.email for item in pending.items] == ["second@example.com"]

    by_text = admin.search(build_filters(None, "FIRST@", None, None), 25, 0)
    assert [item.email for item in by_text.items] == ["first@example.com"]

    today = repository.records[1].created_at.date()
    assert admin.search(build_filters(None, None, today, today), 25, 0).total == 2
    assert admin.search(build_filters(None, None, date(2000, 1, 1), date(2000, 1, 2)), 25, 0).total == 0


def test_search_paginates_and_reports_the_total():
    onboarding, admin, _ = build()
    for index in range(5):
        register(onboarding, f"user{index}@example.com", f"tag{index}")
    page = admin.search(AdminFilters(), 2, 2)
    assert page.total == 5 and len(page.items) == 2 and page.offset == 2


# ---------- detail and audit trail ----------


def test_detail_includes_the_audit_trail():
    onboarding, admin, _ = build(doc(confidence=0.4))
    record = register(onboarding)
    onboarding.review(record.id, "APPROVED", "Ana", "looks fine")

    detail = admin.detail(record.id)

    assert [event.event_type for event in detail.events] == ["REGISTERED", "FLAGGED", "APPROVED"]
    assert detail.events[-1].actor == "Ana"


def test_detail_of_an_unknown_record_is_not_found():
    _, admin, _ = build()
    with pytest.raises(NotFoundError):
        admin.detail(999)


# ---------- erasure ----------


def test_anonymize_replaces_personal_data_and_logs_it():
    onboarding, admin, _ = build()
    record = register(onboarding, "maria@example.com")

    erased = admin.anonymize(record.id, "  Ana ", "customer request")

    assert erased.status == "ERASED"
    assert erased.full_name == "[erased]"
    assert "maria" not in erased.email
    assert erased.document_number == f"ERASED-{record.id}"
    last = admin.detail(record.id).events[-1]
    assert (last.event_type, last.actor, last.detail) == ("ANONYMIZED", "Ana", "customer request")


def test_anonymize_twice_or_unknown_is_refused():
    onboarding, admin, _ = build()
    record = register(onboarding)
    admin.anonymize(record.id, "Ana", None)
    with pytest.raises(ConflictError):
        admin.anonymize(record.id, "Ana", None)
    with pytest.raises(NotFoundError):
        admin.anonymize(999, "Ana", None)


def test_an_anonymized_record_no_longer_triggers_duplicate_flags():
    onboarding, admin, _ = build()
    first = register(onboarding, "first@example.com", "one")
    admin.anonymize(first.id, "Ana", None)
    second = register(onboarding, "second@example.com", "two")
    assert second.status == "VERIFIED"


# ---------- retention ----------


def test_purge_erases_only_old_records():
    onboarding, admin, repository = build(data_retention_days=30)
    old = register(onboarding, "old@example.com", "one")
    recent = register(onboarding, "recent@example.com", "two")
    repository.age_record(old.id, 45)

    assert admin.purge_expired() == 1
    assert repository.records[old.id].status == "ERASED"
    assert repository.records[recent.id].status != "ERASED"
    assert admin.purge_expired() == 0  # nothing left to erase


def test_purge_is_disabled_with_zero_days():
    onboarding, admin, repository = build(data_retention_days=0)
    old = register(onboarding)
    repository.age_record(old.id, 400)
    assert admin.purge_expired() == 0
    assert repository.records[old.id].status != "ERASED"


# ---------- CSV export ----------


def test_csv_safe_neutralizes_formulas():
    assert csv_safe("=HYPERLINK(\"http://evil\")") == "'=HYPERLINK(\"http://evil\")"
    assert csv_safe("+1") == "'+1"
    assert csv_safe("-2") == "'-2"
    assert csv_safe("@SUM(A1)") == "'@SUM(A1)"
    assert csv_safe("Maria") == "Maria"
    assert csv_safe(None) == ""


def test_export_masks_numbers_and_neutralizes_names():
    onboarding, admin, _ = build(doc(full_name="=cmd|' /C calc'!A0"))
    register(onboarding, "a@example.com")

    text = admin.export_csv(AdminFilters())

    assert text.startswith("﻿id,created_at_utc,email,full_name")
    row = text.splitlines()[1]
    assert "12345678" not in row and "*****678" in row
    assert ",'=cmd" in row


def test_export_is_capped_and_paged(monkeypatch):
    import app.services.admin_service as module

    monkeypatch.setattr(module, "MAX_EXPORT_ROWS", 3)
    monkeypatch.setattr(module, "_EXPORT_PAGE_SIZE", 2)
    onboarding, admin, _ = build()
    for index in range(5):
        register(onboarding, f"user{index}@example.com", f"t{index}")
    lines = admin.export_csv(AdminFilters()).strip().splitlines()
    assert len(lines) == 1 + 3


# ---------- public history is masked ----------


def test_public_history_masks_the_document_number():
    onboarding, _, _ = build()
    register(onboarding, "maria@example.com")
    [record] = onboarding.list_for_email("maria@example.com")
    assert record.document_number == "*****678"
