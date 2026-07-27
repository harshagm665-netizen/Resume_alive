"""
db/sqlite_client.py — SQLite-based job cache and deduplication.
Uses WAL mode for better concurrent read performance.
"""

import sqlite3
import json
import threading
from datetime import datetime
from pathlib import Path
from loguru import logger
from config import SQLITE_DB_PATH


class JobDB:
    """SQLite client for caching jobs and resume profiles."""

    def __init__(self, db_path: str = SQLITE_DB_PATH):
        self.db_path = db_path
        self._local = threading.local()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        """Return a thread-local connection with WAL mode enabled."""
        if not hasattr(self._local, "conn") or self._local.conn is None:
            conn = sqlite3.connect(self.db_path, timeout=15)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA busy_timeout=5000")
            conn.execute("PRAGMA synchronous=NORMAL")
            self._local.conn = conn
        return self._local.conn

    def _init_db(self) -> None:
        conn = self._connect()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS jobs (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                dedup_key   TEXT UNIQUE NOT NULL,
                portal      TEXT,
                title       TEXT,
                company     TEXT,
                location    TEXT,
                url         TEXT,
                salary      TEXT,
                experience  TEXT,
                description TEXT,
                posted_date TEXT,
                score       INTEGER DEFAULT 0,
                match_level TEXT DEFAULT '',
                score_reason TEXT DEFAULT '',
                matching_skills TEXT DEFAULT '[]',
                missing_skills  TEXT DEFAULT '[]',
                search_query TEXT DEFAULT '',
                search_location TEXT DEFAULT '',
                user_id     TEXT DEFAULT '',
                created_at  TEXT DEFAULT (datetime('now'))
            );

            CREATE INDEX IF NOT EXISTS idx_jobs_query
                ON jobs(search_query, search_location, user_id);

            CREATE TABLE IF NOT EXISTS resume_profiles (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id    TEXT UNIQUE NOT NULL,
                profile    TEXT NOT NULL,
                filename   TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS search_sessions (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     TEXT,
                query       TEXT,
                location    TEXT,
                total_found INTEGER,
                portals     TEXT,
                has_resume  INTEGER DEFAULT 0,
                created_at  TEXT DEFAULT (datetime('now'))
            );
        """)
        conn.commit()
        logger.info(f"SQLite DB initialized at {self.db_path}")

    # ── Jobs ───────────────────────────────────────────────────────────────────

    def upsert_job(self, job, search_query: str = "", search_location: str = "", user_id: str = "") -> bool:
        """Insert or update a job. Returns True if newly inserted."""
        dedup = job.dedup_key()
        try:
            conn = self._connect()
            conn.execute("""
                INSERT INTO jobs
                    (dedup_key, portal, title, company, location, url, salary,
                     experience, description, posted_date, score, match_level,
                     score_reason, matching_skills, missing_skills,
                     search_query, search_location, user_id)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(dedup_key) DO UPDATE SET
                    score=excluded.score,
                    match_level=excluded.match_level,
                    score_reason=excluded.score_reason,
                    matching_skills=excluded.matching_skills,
                    missing_skills=excluded.missing_skills
            """, (
                dedup, job.portal, job.title, job.company, job.location, job.url,
                job.salary, job.experience, job.description[:1000] if job.description else "",
                job.posted_date, job.score, job.match_level, job.score_reason,
                json.dumps(job.matching_skills), json.dumps(job.missing_skills),
                search_query, search_location, user_id,
            ))
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"DB upsert error: {e}")
            return False

    def bulk_upsert_jobs(self, jobs: list, **kwargs) -> int:
        count = 0
        for job in jobs:
            if self.upsert_job(job, **kwargs):
                count += 1
        return count

    def is_new_job(self, job) -> bool:
        dedup = job.dedup_key()
        conn = self._connect()
        row = conn.execute("SELECT id FROM jobs WHERE dedup_key=?", (dedup,)).fetchone()
        return row is None

    # ── Resume Profiles ────────────────────────────────────────────────────────

    def save_resume_profile(self, user_id: str, profile: dict, filename: str = "") -> None:
        conn = self._connect()
        conn.execute("""
            INSERT INTO resume_profiles (user_id, profile, filename, updated_at)
            VALUES (?, ?, ?, datetime('now'))
            ON CONFLICT(user_id) DO UPDATE SET
                profile=excluded.profile,
                filename=excluded.filename,
                updated_at=excluded.updated_at
        """, (str(user_id), json.dumps(profile), filename))
        conn.commit()
        logger.info(f"Saved resume profile for user {user_id}")

    def get_resume_profile(self, user_id: str) -> dict | None:
        conn = self._connect()
        row = conn.execute(
            "SELECT profile FROM resume_profiles WHERE user_id=?", (str(user_id),)
        ).fetchone()
        if row:
            try:
                return json.loads(row["profile"])
            except Exception:
                pass
        return None

    def delete_resume_profile(self, user_id: str) -> None:
        conn = self._connect()
        conn.execute("DELETE FROM resume_profiles WHERE user_id=?", (str(user_id),))
        conn.commit()

    # ── Search Sessions ────────────────────────────────────────────────────────

    def log_search(self, user_id: str, query: str, location: str,
                   total_found: int, portals: list[str], has_resume: bool) -> None:
        conn = self._connect()
        conn.execute("""
            INSERT INTO search_sessions
                (user_id, query, location, total_found, portals, has_resume)
            VALUES (?,?,?,?,?,?)
        """, (str(user_id), query, location, total_found,
              ",".join(portals), 1 if has_resume else 0))
        conn.commit()


# Singleton
db = JobDB()
