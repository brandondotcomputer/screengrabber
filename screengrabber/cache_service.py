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
            conn.execute("PRAGMA foreign_keys = 1")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS twitter_screengrabs (
                    account_name TEXT NOT NULL,
                    status_id TEXT NOT NULL,
                    cached_at TIMESTAMP NOT NULL,
                    s3_path TEXT NOT NULL,
                    PRIMARY KEY (account_name, status_id)
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_twitter_screengrabs_account_name 
                ON twitter_screengrabs(account_name)
            """)
            conn.execute("""
                
                CREATE TABLE IF NOT EXISTS twitter_screengrab_medias (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    status_id TEXT NOT NULL,
                    cached_at TIMESTAMP NOT NULL,
                    s3_path TEXT NOT NULL,
                    source_url TEXT NOT NULL,
                    media_type TEXT NOT NULL,
                    FOREIGN KEY (status_id) REFERENCES twitter_screengrabs(status_id)
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_twitter_screengrabs_medias_status_id
                ON twitter_screengrab_medias(status_id)
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

    def get_twitter_screengrab_if_exists(
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
                   FROM twitter_screengrabs WHERE account_name = ? AND status_id = ?""",
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

    def add_twitter_screengrab(
        self, account_name: str, status_id: str, s3_path: str
    ) -> None:
        """Add a new record to the cache."""
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO twitter_screengrabs 
                (account_name, status_id, cached_at, s3_path)
                VALUES (?, ?, ?, ?)
                """,
                (account_name, status_id, datetime.utcnow(), s3_path),
            )

    def add_twitter_screengrab_media(
        self, status_id: str, s3_path: str, source_url: str, media_type: str
    ) -> None:
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO twitter_screengrab_medias 
                (status_id, s3_path, source_url, media_type, cached_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (status_id, s3_path, source_url, media_type, datetime.utcnow()),
            )

    def get_twitter_screengrab_medias(self, status_id: str) -> list[dict[str, any]]:
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT id, status_id, s3_path, source_url, media_type, cached_at
                FROM twitter_screengrab_medias
                WHERE status_id = ?
            """,
                (status_id,),
            )

            results = cursor.fetchall()
            return [
                {
                    "id": row[0],
                    "status_id": row[1],
                    "s3_path": row[2],
                    "source_url": row[3],
                    "media_type": row[4],
                    "cached_at": datetime.fromisoformat(row[5]).replace(
                        tzinfo=timezone.utc
                    ),
                }
                for row in results
            ]
