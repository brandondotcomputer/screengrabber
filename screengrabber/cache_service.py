from datetime import datetime, timezone
import logging
import sqlite3
from pathlib import Path
from typing import Optional, Tuple
from contextlib import contextmanager
import threading


class CacheService:
    def __init__(self, db_path: str | Path) -> None:
        """Initialize the cache service with the path to the SQLite database.

        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = Path(db_path)
        self._connection_lock = threading.Lock()
        self._logger = logging.getLogger(__name__)
        self._init_db()

    def _init_db(self) -> None:
        """Initialize the database and create the screengrabs table if it doesn't exist."""
        self._logger.info("Initializing cache database...")

        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS screengrabs (
                    account_name TEXT NOT NULL,
                    status_id TEXT NOT NULL,
                    cached_at TIMESTAMP NOT NULL,
                    s3_path TEXT NOT NULL,
                    PRIMARY KEY (account_name, status_id)
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_account_name 
                ON screengrabs(account_name)
            """)

    @contextmanager
    def _get_connection(self):
        """Thread-safe context manager for database connections."""
        with self._connection_lock:
            conn = sqlite3.connect(self.db_path)
            try:
                yield conn
                conn.commit()
            finally:
                conn.close()

    def exists(self, account_name: str, status_id: str) -> bool:
        """Check if a record exists for the given account_name and status_id.

        Args:
            account_name: The account name to check
            status_id: The status ID to check

        Returns:
            bool: True if the record exists, False otherwise
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT 1 FROM screengrabs WHERE account_name = ? AND status_id = ?",
                (account_name, status_id),
            )
            return cursor.fetchone() is not None

    def get_if_exists(
        self, account_name: str, status_id: str
    ) -> Optional[Tuple[str, str, datetime, str]]:
        """Get the full record if it exists.

        Args:
            account_name: The account name to look up
            status_id: The status ID to look up

        Returns:
            Optional[Tuple[str, str, datetime, str]]: Tuple of (account_name, status_id, cached_at, s3_path) if found,
                                                     None otherwise
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                """SELECT account_name, status_id, cached_at, s3_path 
                   FROM screengrabs WHERE account_name = ? AND status_id = ?""",
                (account_name, status_id),
            )
            result = cursor.fetchone()
            if result:
                return (
                    result[0],
                    result[1],
                    datetime.fromisoformat(result[2]).replace(tzinfo=timezone.utc),
                    result[3],
                )
            return None

    def get_s3_path(self, account_name: str, status_id: str) -> Optional[str]:
        """Get the S3 path for a given account_name and status_id if it exists.

        Args:
            account_name: The account name to look up
            status_id: The status ID to look up

        Returns:
            Optional[str]: The S3 path if found, None otherwise
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT s3_path FROM screengrabs WHERE account_name = ? AND status_id = ?",
                (account_name, status_id),
            )
            result = cursor.fetchone()
            return result[0] if result else None

    def add(self, account_name: str, status_id: str, s3_path: str) -> None:
        """Add a new record to the cache.

        Args:
            account_name: The account name to add
            status_id: The status ID to add
            s3_path: The S3 path where the content is stored
        """
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO screengrabs 
                (account_name, status_id, cached_at, s3_path)
                VALUES (?, ?, ?, ?)
                """,
                (account_name, status_id, datetime.utcnow(), s3_path),
            )


# Usage example:
if __name__ == "__main__":
    cache = CacheService("cache.db")

    # Check if entry exists
    exists = cache.exists("user123", "status456")

    # Add new entry
    if not exists:
        cache.add("user123", "status456", "s3://bucket/path/to/file.png")

    # Get S3 path
    s3_path = cache.get_s3_path("user123", "status456")
