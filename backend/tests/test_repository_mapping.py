"""Repository behaviour that does not need a database: row mapping and error translation."""

from datetime import datetime

import mysql.connector
import pytest

from app.core.errors import ConflictError, DatabaseUnavailableError
from app.repositories.onboarding_repository import OnboardingRepository


def make_row(**overrides):
    row = {
        "id": 7,
        "email": "maria@example.com",
        "document_type": "DNI",
        "full_name": "Maria Fernandez Torres",
        "document_number": "12345678",
        "ocr_confidence": 71,
        "status": "NEEDS_REVIEW",
        "original_filename": "dni.png",
        "created_at": datetime(2026, 11, 2, 19, 0, 0),
        "flags": None,
        "review_decision": None,
        "reviewed_by": None,
        "review_comment": None,
        "reviewed_at": None,
    }
    row.update(overrides)
    return row


def test_row_without_review_keeps_the_automatic_status():
    record = OnboardingRepository._to_response(make_row())
    assert record.status == "NEEDS_REVIEW"
    assert record.flags == []
    assert record.created_at.tzinfo is not None


def test_flags_are_split_even_when_the_connector_returns_bytes():
    record = OnboardingRepository._to_response(
        make_row(flags=bytearray(b"LOW_CONFIDENCE,DUPLICATE_IMAGE"))
    )
    assert record.flags == ["LOW_CONFIDENCE", "DUPLICATE_IMAGE"]


def test_operator_decision_replaces_the_automatic_status():
    record = OnboardingRepository._to_response(
        make_row(
            review_decision="REJECTED",
            reviewed_by="Ana",
            review_comment="name does not match",
            reviewed_at=datetime(2026, 11, 2, 19, 30, 0),
        )
    )
    assert record.status == "REJECTED"
    assert record.reviewed_by == "Ana"
    assert record.reviewed_at.tzinfo is not None


class FakeResult:
    def __init__(self, rows):
        self.column_names = list(rows[0].keys()) if rows else []
        self._rows = [tuple(row.values()) for row in rows]

    def fetchall(self):
        return self._rows


class FakeCursor:
    def __init__(self, error: Exception | None, rows=()):
        self._error = error
        self._rows = list(rows)
        self.calls: list[tuple] = []

    def callproc(self, name, args):
        self.calls.append((name, args))
        if self._error:
            raise self._error

    def stored_results(self):
        return iter([FakeResult(self._rows)] if self._rows else [])


class FakeConnection:
    def __init__(self, error: Exception | None, rows=()):
        self._error = error
        self.cursor_instance = FakeCursor(error, rows)
        self.closed = False

    def cursor(self):
        return self.cursor_instance

    def commit(self):
        pass

    def close(self):
        self.closed = True


class FakePool:
    def __init__(self, error: Exception | None, rows=()):
        self.connection = FakeConnection(error, rows)

    def get_connection(self):
        return self.connection


def test_business_rule_violation_from_a_procedure_becomes_a_conflict():
    error = mysql.connector.Error(msg="This record was already reviewed", errno=1644, sqlstate="45000")
    repository = OnboardingRepository(FakePool(error))
    with pytest.raises(ConflictError) as raised:
        repository.review(1, "APPROVED", "Ana", None)
    assert raised.value.message == "This record was already reviewed"


def test_other_database_errors_become_service_unavailable_and_the_connection_is_released():
    pool = FakePool(mysql.connector.Error(msg="Lost connection", errno=2013, sqlstate="HY000"))
    repository = OnboardingRepository(pool)
    with pytest.raises(DatabaseUnavailableError):
        repository.list_pending_reviews()
    assert pool.connection.closed


# ---------- admin read model ----------


def test_effective_status_from_the_view_wins_over_the_raw_columns():
    erased = OnboardingRepository._to_response(
        make_row(status="VERIFIED", effective_status="ERASED", erased_at=datetime(2026, 11, 3))
    )
    assert erased.status == "ERASED"
    decided = OnboardingRepository._to_response(
        make_row(review_decision="APPROVED", effective_status="APPROVED")
    )
    assert decided.status == "APPROVED"


def test_search_maps_rows_and_reads_the_total_from_the_first_row():
    from app.schemas import AdminFilters

    rows = [make_row(id=2, total_count=7), make_row(id=1, total_count=7)]
    pool = FakePool(None, rows)
    items, total = OnboardingRepository(pool).search(AdminFilters("NEEDS_REVIEW", "50%_x"), 25, 0)
    assert [item.id for item in items] == [2, 1] and total == 7
    name, args = pool.connection.cursor_instance.calls[0]
    assert name == "sp_admin_search"
    assert args[:2] == ("NEEDS_REVIEW", "50\\%\\_x")  # LIKE wildcards are escaped


def test_search_without_rows_returns_an_empty_page():
    from app.schemas import AdminFilters

    items, total = OnboardingRepository(FakePool(None)).search(AdminFilters(), 25, 0)
    assert items == [] and total == 0


def test_stats_are_read_from_one_row_and_default_to_zero():
    from decimal import Decimal

    row = {
        "total": 4,
        "verified": Decimal("2"),
        "needs_review": Decimal("1"),
        "approved": Decimal("1"),
        "rejected": Decimal("0"),
        "erased": Decimal("0"),
        "avg_confidence": Decimal("91.2500"),
    }
    stats = OnboardingRepository(FakePool(None, [row])).stats()
    assert (stats.total, stats.verified, stats.needs_review, stats.avg_confidence) == (4, 2, 1, 91.25)
    assert OnboardingRepository(FakePool(None)).stats().total == 0


def test_daily_counts_are_zero_filled_for_the_whole_range():
    from datetime import date, timedelta, timezone

    today = datetime.now(timezone.utc).date()
    rows = [{"day": today - timedelta(days=1), "total": 3}]
    series = OnboardingRepository(FakePool(None, rows)).daily_counts(3)
    assert [point.total for point in series] == [0, 3, 0]
    assert series[-1].day == today


def test_events_are_mapped_with_utc_timestamps():
    rows = [
        {"event_type": b"REGISTERED", "actor": None, "detail": b"NEEDS_REVIEW",
         "occurred_at": datetime(2026, 11, 2, 19), "sort_order": 1},
        {"event_type": "APPROVED", "actor": "Ana", "detail": "ok",
         "occurred_at": datetime(2026, 11, 2, 20), "sort_order": 3},
    ]
    events = OnboardingRepository(FakePool(None, rows)).list_events(7)
    assert [event.event_type for event in events] == ["REGISTERED", "APPROVED"]
    assert events[0].detail == "NEEDS_REVIEW" and events[1].actor == "Ana"
    assert events[0].occurred_at.tzinfo is not None
