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


class FakeCursor:
    def __init__(self, error: Exception | None):
        self._error = error

    def callproc(self, name, args):
        if self._error:
            raise self._error

    def stored_results(self):
        return iter(())


class FakeConnection:
    def __init__(self, error: Exception | None):
        self._error = error
        self.closed = False

    def cursor(self):
        return FakeCursor(self._error)

    def commit(self):
        pass

    def close(self):
        self.closed = True


class FakePool:
    def __init__(self, error: Exception | None):
        self.connection = FakeConnection(error)

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
