"""Data access for onboarding records. Every operation goes through a stored procedure."""

import logging
from datetime import timezone
from typing import Any

import mysql.connector
from mysql.connector import pooling

from app.core.errors import DatabaseUnavailableError
from app.schemas import NewOnboarding, OnboardingResponse

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
            logger.error("Stored procedure %s failed: %s", name, exc)
            raise DatabaseUnavailableError("The record could not be stored or read.") from exc
        finally:
            connection.close()

    @staticmethod
    def _to_response(row: dict[str, Any]) -> OnboardingResponse:
        return OnboardingResponse(
            id=row["id"],
            email=row["email"],
            document_type=row["document_type"],
            full_name=row["full_name"],
            document_number=row["document_number"],
            ocr_confidence=float(row["ocr_confidence"]),
            status=row["status"],
            original_filename=row["original_filename"],
            created_at=row["created_at"].replace(tzinfo=timezone.utc),  # stored as UTC
        )
