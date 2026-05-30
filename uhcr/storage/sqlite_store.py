"""SQLite persistence store for UHCR job records, configuration, and metrics.

Uses WAL (Write-Ahead Logging) mode for concurrent read support during writes.
Schema is auto-created on first access if the database file does not exist.
"""

from __future__ import annotations

import logging
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    submission_time TEXT NOT NULL,
    completion_time TEXT,
    status TEXT NOT NULL,
    result_size INTEGER,
    worker_id TEXT
);

CREATE TABLE IF NOT EXISTS config (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT NOT NULL,
    metric_name TEXT NOT NULL,
    metric_value REAL NOT NULL,
    recorded_at TEXT NOT NULL,
    FOREIGN KEY (job_id) REFERENCES jobs(id)
);
"""


class SQLiteStore:
    """WAL-mode SQLite store for job records, configuration, and metrics.

    The store auto-creates the database file and schema on first access.
    Thread-safe via sqlite3's check_same_thread=False.

    Args:
        db_path: Path to the SQLite database file. Defaults to ~/.uhcr/data.db.
    """

    def __init__(self, db_path: Optional[str] = None) -> None:
        if db_path is None:
            db_path = os.path.join(os.path.expanduser("~"), ".uhcr", "data.db")

        self._db_path = db_path

        # Ensure the parent directory exists
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)

        # Open connection with thread-safety enabled
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row

        # Enable WAL mode
        self._conn.execute("PRAGMA journal_mode=WAL")

        # Auto-create schema
        self._conn.executescript(_SCHEMA_SQL)
        self._conn.commit()

        logger.info("SQLiteStore initialized at %s", self._db_path)

    @property
    def db_path(self) -> str:
        """The path to the SQLite database file."""
        return self._db_path

    def close(self) -> None:
        """Close the database connection."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None  # type: ignore[assignment]
            logger.info("SQLiteStore connection closed")

    # ─── Job CRUD ────────────────────────────────────────────────────────────

    def record_job(
        self,
        job_id: str,
        submission_time: str,
        status: str,
        completion_time: Optional[str] = None,
        result_size: Optional[int] = None,
        worker_id: Optional[str] = None,
    ) -> None:
        """Insert or replace a job execution record.

        Args:
            job_id: Unique job identifier (UUID4 string).
            submission_time: ISO 8601 timestamp of job submission.
            status: Job status (queued, running, completed, failed, timeout).
            completion_time: ISO 8601 timestamp of job completion (optional).
            result_size: Size of the result in bytes (optional).
            worker_id: ID of the worker that executed the job (optional).
        """
        self._conn.execute(
            """
            INSERT OR REPLACE INTO jobs (id, submission_time, completion_time, status, result_size, worker_id)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (job_id, submission_time, completion_time, status, result_size, worker_id),
        )
        self._conn.commit()

    def get_job(self, job_id: str) -> Optional[Dict[str, object]]:
        """Retrieve a job record by ID.

        Args:
            job_id: The job identifier to look up.

        Returns:
            A dictionary with job fields, or None if not found.
        """
        cursor = self._conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
        row = cursor.fetchone()
        if row is None:
            return None
        return dict(row)

    # ─── Config CRUD ─────────────────────────────────────────────────────────

    def store_config(self, key: str, value: str) -> None:
        """Store or update a configuration key-value pair.

        Args:
            key: Configuration key.
            value: Configuration value.
        """
        updated_at = datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            """
            INSERT OR REPLACE INTO config (key, value, updated_at)
            VALUES (?, ?, ?)
            """,
            (key, value, updated_at),
        )
        self._conn.commit()

    def get_config(self, key: str) -> Optional[str]:
        """Retrieve a configuration value by key.

        Args:
            key: The configuration key to look up.

        Returns:
            The configuration value string, or None if not found.
        """
        cursor = self._conn.execute("SELECT value FROM config WHERE key = ?", (key,))
        row = cursor.fetchone()
        if row is None:
            return None
        return row["value"]

    # ─── Metrics CRUD ────────────────────────────────────────────────────────

    def record_metric(self, job_id: str, metric_name: str, metric_value: float) -> None:
        """Record a performance metric for a job.

        Args:
            job_id: The job this metric belongs to.
            metric_name: Name of the metric (e.g. 'compilation_time', 'execution_time').
            metric_value: Numeric value of the metric.
        """
        recorded_at = datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            """
            INSERT INTO metrics (job_id, metric_name, metric_value, recorded_at)
            VALUES (?, ?, ?, ?)
            """,
            (job_id, metric_name, metric_value, recorded_at),
        )
        self._conn.commit()

    def get_metrics(self, job_id: Optional[str] = None) -> List[Dict[str, object]]:
        """Retrieve metrics, optionally filtered by job ID.

        Args:
            job_id: If provided, only return metrics for this job.
                    If None, return all metrics.

        Returns:
            A list of metric dictionaries.
        """
        if job_id is not None:
            cursor = self._conn.execute(
                "SELECT * FROM metrics WHERE job_id = ? ORDER BY recorded_at",
                (job_id,),
            )
        else:
            cursor = self._conn.execute("SELECT * FROM metrics ORDER BY recorded_at")
        return [dict(row) for row in cursor.fetchall()]
