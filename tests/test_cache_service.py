import pytest
from datetime import datetime
import sqlite3
import threading
import time
from screengrabber.cache_service import CacheService


@pytest.fixture
def temp_db_path(tmp_path):
    """Provide a temporary database path for each test."""
    return tmp_path / "test_cache.db"


@pytest.fixture
def cache_service(temp_db_path):
    """Provide a fresh CacheService instance for each test."""
    service = CacheService(temp_db_path)
    yield service
    # Cleanup
    if temp_db_path.exists():
        temp_db_path.unlink()


def test_init_creates_db_and_table(temp_db_path):
    """Test that initializing CacheService creates the database and table."""
    cache = CacheService(temp_db_path)  # noqa: F841

    # Verify database file was created
    assert temp_db_path.exists()

    # Verify table structure
    with sqlite3.connect(temp_db_path) as conn:
        cursor = conn.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='screengrabs'
        """)
        assert cursor.fetchone() is not None

        # Verify index exists
        cursor = conn.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='index' AND name='idx_account_name'
        """)
        assert cursor.fetchone() is not None


def test_add_and_exists(cache_service):
    """Test adding entries and checking their existence."""
    # Test non-existent entry
    assert not cache_service.exists("test_user", "status123")

    # Add entry
    cache_service.add("test_user", "status123", "s3://test/path.png")

    # Verify entry exists
    assert cache_service.exists("test_user", "status123")


def test_get_s3_path(cache_service):
    """Test retrieving S3 paths."""
    # Test non-existent path
    assert cache_service.get_s3_path("test_user", "status123") is None

    # Add entry
    s3_path = "s3://test/path.png"
    cache_service.add("test_user", "status123", s3_path)

    # Verify retrieved path
    assert cache_service.get_s3_path("test_user", "status123") == s3_path


def test_add_updates_existing_entry(cache_service):
    """Test that adding an entry with existing primary key updates the record."""
    # Add initial entry
    cache_service.add("test_user", "status123", "s3://test/path1.png")

    # Add entry with same primary key but different s3_path
    new_path = "s3://test/path2.png"
    cache_service.add("test_user", "status123", new_path)

    # Verify updated path
    assert cache_service.get_s3_path("test_user", "status123") == new_path


def test_concurrent_access(cache_service):
    """Test concurrent access to the cache service."""

    def worker(user_id):
        """Worker function for concurrent testing."""
        for i in range(5):
            status_id = f"status_{user_id}_{i}"
            s3_path = f"s3://test/{user_id}/path_{i}.png"
            cache_service.add(f"user_{user_id}", status_id, s3_path)
            time.sleep(0.01)  # Small delay to increase chance of concurrent access
            assert cache_service.exists(f"user_{user_id}", status_id)
            assert cache_service.get_s3_path(f"user_{user_id}", status_id) == s3_path

    # Create and start threads
    threads = []
    for i in range(5):
        thread = threading.Thread(target=worker, args=(i,))
        threads.append(thread)
        thread.start()

    # Wait for all threads to complete
    for thread in threads:
        thread.join()

    # Verify all entries
    for i in range(5):
        for j in range(5):
            status_id = f"status_{i}_{j}"
            expected_path = f"s3://test/{i}/path_{j}.png"
            assert cache_service.exists(f"user_{i}", status_id)
            assert cache_service.get_s3_path(f"user_{i}", status_id) == expected_path


def test_cached_at_timestamp(cache_service):
    """Test that cached_at timestamp is set correctly."""
    before_add = datetime.utcnow()

    # Add entry
    cache_service.add("test_user", "status123", "s3://test/path.png")

    after_add = datetime.utcnow()

    # Check timestamp directly in database
    with sqlite3.connect(cache_service.db_path) as conn:
        cursor = conn.execute(
            "SELECT cached_at FROM screengrabs WHERE account_name = ? AND status_id = ?",
            ("test_user", "status123"),
        )
        timestamp = datetime.fromisoformat(cursor.fetchone()[0])

        # Verify timestamp is between before_add and after_add
        assert before_add <= timestamp <= after_add


def test_get_if_exists(cache_service):
    """Test retrieving full records with get_if_exists."""
    # Test non-existent record
    assert cache_service.get_if_exists("test_user", "status123") is None

    # Add entry
    before_add = datetime.utcnow()
    cache_service.add("test_user", "status123", "s3://test/path.png")
    after_add = datetime.utcnow()

    # Get and verify record
    record = cache_service.get_if_exists("test_user", "status123")
    assert record is not None

    account_name, status_id, cached_at, s3_path = record
    assert account_name == "test_user"
    assert status_id == "status123"
    assert before_add <= cached_at <= after_add
    assert s3_path == "s3://test/path.png"


def test_invalid_inputs(cache_service):
    """Test handling of invalid inputs."""
    with pytest.raises(sqlite3.IntegrityError):
        # Test NULL values for NOT NULL columns
        cache_service.add(None, "status123", "s3://test/path.png")

    with pytest.raises(sqlite3.IntegrityError):
        cache_service.add("test_user", None, "s3://test/path.png")

    with pytest.raises(sqlite3.IntegrityError):
        cache_service.add("test_user", "status123", None)
