"""Data access for onboarding records. Every operation goes through a stored procedure."""

import logging
from datetime import timezone
from typing import Any

import mysql.connector
from mysql.connector import pooling

from app.core.errors import ConflictError, DatabaseUnavailableError
from app.schemas import DuplicateSignals, NewOnboarding, OnboardingResponse

logger = logging.getLogger(__name__)


class OnboardingRepository:
    def __init__(self, pool: pooling.MySQLConnectionPool):
        self._pool = pool

    def create(self, new_record: NewOnboarding) -> OnboardingResponse:
        rows = self._call_procedure(
            "sp_create_onboarding",
            (
                new_record.email,
                new_record.document_type,
                new_record.full_name,
                new_record.document_number,
                new_record.ocr_confidence,
                new_record.status,
                new_record.image_sha256,
                new_record.original_filename,
            ),
            commit=True,
        )
        record = self._to_response(rows[0])
        # Flags are written right after the record (one small procedure call each).
        for code in new_record.flags:
            self._call_procedure("sp_add_onboarding_flag", (record.id, code), commit=True)
        return record.model_copy(update={"flags": list(new_record.flags)}) if new_record.flags else record

    def find_duplicate_signals(
        self, document_number: str, image_sha256: str, email: str
    ) -> DuplicateSignals:
        rows = self._call_procedure(
            "sp_find_duplicate_signals", (document_number, image_sha256, email)
        )
        if not rows:
            return DuplicateSignals()
        return DuplicateSignals(
            same_number_other_email=int(rows[0]["same_number_other_email"] or 0),
            same_image_other_email=int(rows[0]["same_image_other_email"] or 0),
        )

    def list_pending_reviews(self, limit: int = 50) -> list[OnboardingResponse]:
        rows = self._call_procedure("sp_list_pending_reviews", (limit,))
        return [self._to_response(row) for row in rows]

    def review(
        self, onboarding_id: int, decision: str, reviewer: str, comment: str | None
    ) -> OnboardingResponse:
        rows = self._call_procedure(
            "sp_review_onboarding", (onboarding_id, decision, reviewer, comment), commit=True
        )
        return self._to_response(rows[0])

    def get_by_id(self, onboarding_id: int) -> OnboardingResponse | None:
        rows = self._call_procedure("sp_get_onboarding_by_id", (onboarding_id,))
        return self._to_response(rows[0]) if rows else None

    def list_by_email(self, email: str, limit: int = 20) -> list[OnboardingResponse]:
        rows = self._call_procedure("sp_list_onboardings_by_email", (email, limit))
        return [self._to_response(row) for row in rows]

    def ping(self) -> bool:
        try:
            connection = self._pool.get_connection()
        except mysql.connector.Error:
            return False
        try:
            connection.ping(reconnect=False)
            return True
        except mysql.connector.Error:
            return False
        finally:
            connection.close()

    # ---------- internals ----------

    def _call_procedure(
        self, name: str, args: tuple[Any, ...], *, commit: bool = False
    ) -> list[dict[str, Any]]:
        try:
            connection = self._pool.get_connection()
        except mysql.connector.Error as exc:
            logger.error("Could not get a database connection: %s", exc)
            raise DatabaseUnavailableError("The database is not reachable right now.") from exc

        try:
            cursor = connection.cursor()
            cursor.callproc(name, args)
            rows: list[dict[str, Any]] = []
            for result in cursor.stored_results():
                columns = result.column_names
                rows.extend(dict(zip(columns, row)) for row in result.fetchall())
            if commit:
                connection.commit()
            return rows
        except mysql.connector.Error as exc:
            # SQLSTATE 45000 is how our procedures report a broken business rule (SIGNAL).
            if getattr(exc, "sqlstate", None) == "45000":
                raise ConflictError(getattr(exc, "msg", None) or "The operation is not allowed.") from exc
            logger.error("Stored procedure %s failed: %s", name, exc)
            raise DatabaseUnavailableError("The record could not be stored or read.") from exc
        finally:
            connection.close()

    @staticmethod
    def _to_response(row: dict[str, Any]) -> OnboardingResponse:
        flags_text = _as_text(row.get("flags"))
        review_decision = _as_text(row.get("review_decision"))
        reviewed_at = row.get("reviewed_at")
        return OnboardingResponse(
            id=row["id"],
            email=row["email"],
            document_type=row["document_type"],
            full_name=row["full_name"],
            document_number=row["document_number"],
            ocr_confidence=float(row["ocr_confidence"]),
            # the operator's decision, when there is one, replaces the automatic status
            status=review_decision or row["status"],
            flags=[code for code in (flags_text or "").split(",") if code],
            original_filename=row["original_filename"],
            created_at=row["created_at"].replace(tzinfo=timezone.utc),  # stored as UTC
            reviewed_by=_as_text(row.get("reviewed_by")),
            review_comment=_as_text(row.get("review_comment")),
            reviewed_at=reviewed_at.replace(tzinfo=timezone.utc) if reviewed_at else None,
        )


def _as_text(value: Any) -> str | None:
    """MySQL can return GROUP_CONCAT / ENUM values as bytes depending on the connector build."""
    if value is None:
        return None
    if isinstance(value, (bytes, bytearray)):
        return bytes(value).decode("utf-8")
    return str(value)
