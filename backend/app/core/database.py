"""MySQL connection pool and the SQL script runner used for migrations."""

import logging
from pathlib import Path

from mysql.connector import pooling

from app.core.config import Settings
from app.core.sql_script import split_sql_script

logger = logging.getLogger(__name__)


def create_pool(settings: Settings) -> pooling.MySQLConnectionPool:
    return pooling.MySQLConnectionPool(
        pool_name="mini_kyc_pool",
        pool_size=settings.db_pool_size,
        host=settings.db_host,
        port=settings.db_port,
        user=settings.db_user,
        password=settings.db_password,
        database=settings.db_name,
        charset="utf8mb4",
        time_zone="+00:00",
        connection_timeout=10,
    )


def run_migrations(settings: Settings) -> None:
    """Apply schema.sql and stored_procedures.sql (both are idempotent)."""
    import mysql.connector

    connection = mysql.connector.connect(
        host=settings.db_host,
        port=settings.db_port,
        user=settings.db_user,
        password=settings.db_password,
        database=settings.db_name,
        charset="utf8mb4",
        connection_timeout=10,
    )
    try:
        cursor = connection.cursor()
        for file_name in ("schema.sql", "stored_procedures.sql"):
            script = (Path(settings.database_dir) / file_name).read_text(encoding="utf-8")
            statements = split_sql_script(script)
            for statement in statements:
                cursor.execute(statement)
            logger.info("Applied %s (%d statements)", file_name, len(statements))
        connection.commit()
    finally:
        connection.close()
