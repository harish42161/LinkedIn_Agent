"""Database Manager for LinkedIn Job Application Automation Agent.

Maintains SQLite tables for jobs, application history, hourly runs,
and audit logs with thread-safe connection pooling and WAL mode.
"""

import sqlite3
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from linkedin_job_agent.config import config

logger = logging.getLogger("linkedin_agent.db")


class DatabaseManager:
    """Manages all persistence layers for job discovery, scoring, and applications."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = Path(db_path) if db_path else config.database_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def get_connection(self) -> sqlite3.Connection:
        """Returns SQLite connection with WAL mode and row factory."""
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        return conn

    def _init_db(self):
        """Initializes tables and indices."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # 1. Jobs Table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                job_id TEXT PRIMARY KEY,
                canonical_url TEXT UNIQUE,
                title TEXT NOT NULL,
                company TEXT NOT NULL,
                location TEXT NOT NULL,
                posting_date TEXT,
                experience_required TEXT,
                skills_required TEXT,
                employment_type TEXT DEFAULT 'Full-time',
                job_description TEXT,
                job_url TEXT NOT NULL,
                is_easy_apply INTEGER DEFAULT 0,
                match_score REAL DEFAULT 0.0,
                match_explanation TEXT,
                match_breakdown JSON,
                status TEXT NOT NULL DEFAULT 'Discovered',
                date_discovered TEXT NOT NULL,
                date_applied TEXT,
                error_details TEXT,
                last_processed_at TEXT NOT NULL
            );
            """)

            # 2. Application Audit History
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS application_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT NOT NULL,
                action TEXT NOT NULL,
                status_before TEXT,
                status_after TEXT,
                details TEXT,
                timestamp TEXT NOT NULL,
                FOREIGN KEY (job_id) REFERENCES jobs(job_id) ON DELETE CASCADE
            );
            """)

            # 3. Hourly Run Records
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS hourly_runs (
                run_id INTEGER PRIMARY KEY AUTOINCREMENT,
                start_time TEXT NOT NULL,
                end_time TEXT,
                status TEXT NOT NULL DEFAULT 'RUNNING',
                jobs_discovered INTEGER DEFAULT 0,
                relevant_jobs INTEGER DEFAULT 0,
                high_priority_matches INTEGER DEFAULT 0,
                applications_submitted INTEGER DEFAULT 0,
                awaiting_review INTEGER DEFAULT 0,
                duplicates_skipped INTEGER DEFAULT 0,
                errors_count INTEGER DEFAULT 0,
                error_summary TEXT,
                summary_text TEXT
            );
            """)

            # Indices
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_jobs_match_score ON jobs(match_score);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_jobs_date_discovered ON jobs(date_discovered);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_jobs_company_title ON jobs(company, title);")
            conn.commit()

    def upsert_job(self, job_dict: Dict[str, Any]) -> Tuple[bool, str]:
        """Inserts a new job or updates an existing job.

        Returns (is_new, status).
        """
        now_iso = datetime.now(timezone.utc).isoformat()
        job_id = str(job_dict.get("job_id", "")).strip()
        if not job_id:
            raise ValueError("job_id is required")

        canonical_url = job_dict.get("canonical_url", job_dict.get("job_url", "")).split("?")[0]
        breakdown_json = json.dumps(job_dict.get("match_breakdown", {}))

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT status FROM jobs WHERE job_id = ?", (job_id,))
            existing = cursor.fetchone()

            if existing:
                current_status = existing["status"]
                cursor.execute("""
                UPDATE jobs SET
                    title = COALESCE(?, title),
                    company = COALESCE(?, company),
                    location = COALESCE(?, location),
                    posting_date = COALESCE(?, posting_date),
                    experience_required = COALESCE(?, experience_required),
                    skills_required = COALESCE(?, skills_required),
                    job_description = COALESCE(?, job_description),
                    is_easy_apply = COALESCE(?, is_easy_apply),
                    match_score = COALESCE(?, match_score),
                    match_explanation = COALESCE(?, match_explanation),
                    match_breakdown = COALESCE(?, match_breakdown),
                    last_processed_at = ?
                WHERE job_id = ?
                """, (
                    job_dict.get("title"),
                    job_dict.get("company"),
                    job_dict.get("location"),
                    job_dict.get("posting_date"),
                    job_dict.get("experience_required"),
                    job_dict.get("skills_required"),
                    job_dict.get("job_description"),
                    1 if job_dict.get("is_easy_apply") else 0,
                    job_dict.get("match_score"),
                    job_dict.get("match_explanation"),
                    breakdown_json,
                    now_iso,
                    job_id
                ))
                conn.commit()
                return False, current_status
            else:
                initial_status = job_dict.get("status", "Discovered")
                cursor.execute("""
                INSERT INTO jobs (
                    job_id, canonical_url, title, company, location,
                    posting_date, experience_required, skills_required,
                    employment_type, job_description, job_url, is_easy_apply,
                    match_score, match_explanation, match_breakdown, status,
                    date_discovered, last_processed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    job_id,
                    canonical_url,
                    job_dict.get("title", "Unknown Title"),
                    job_dict.get("company", "Unknown Company"),
                    job_dict.get("location", "Navi Mumbai, India"),
                    job_dict.get("posting_date", now_iso),
                    job_dict.get("experience_required", ""),
                    job_dict.get("skills_required", ""),
                    job_dict.get("employment_type", "Full-time"),
                    job_dict.get("job_description", ""),
                    job_dict.get("job_url", ""),
                    1 if job_dict.get("is_easy_apply") else 0,
                    float(job_dict.get("match_score", 0.0)),
                    job_dict.get("match_explanation", ""),
                    breakdown_json,
                    initial_status,
                    now_iso,
                    now_iso
                ))
                self.log_action(conn, job_id, "DISCOVERED", None, initial_status, "Job discovered by search engine")
                conn.commit()
                return True, initial_status

    def update_job_status(self, job_id: str, new_status: str, details: str = "", error: Optional[str] = None):
        """Updates job status and logs action to audit history."""
        now_iso = datetime.now(timezone.utc).isoformat()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT status FROM jobs WHERE job_id = ?", (job_id,))
            row = cursor.fetchone()
            old_status = row["status"] if row else None

            applied_date = now_iso if new_status == "Applied" else None

            cursor.execute("""
            UPDATE jobs SET
                status = ?,
                date_applied = CASE WHEN ? IS NOT NULL THEN ? ELSE date_applied END,
                error_details = ?,
                last_processed_at = ?
            WHERE job_id = ?
            """, (new_status, applied_date, applied_date, error, now_iso, job_id))

            self.log_action(conn, job_id, f"STATUS_CHANGE_TO_{new_status.upper()}", old_status, new_status, details)
            conn.commit()

    def log_action(self, conn: sqlite3.Connection, job_id: str, action: str,
                   status_before: Optional[str], status_after: Optional[str], details: str = ""):
        """Appends action to application_history."""
        now_iso = datetime.now(timezone.utc).isoformat()
        conn.execute("""
        INSERT INTO application_history (job_id, action, status_before, status_after, details, timestamp)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (job_id, action, status_before, status_after, details, now_iso))

    def get_job_by_id(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a single job dictionary."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,))
            row = cursor.fetchone()
            if not row:
                return None
            res = dict(row)
            if res.get("match_breakdown"):
                try:
                    res["match_breakdown"] = json.loads(res["match_breakdown"])
                except Exception:
                    pass
            return res

    def get_all_jobs(self, limit: int = 1000) -> List[Dict[str, Any]]:
        """Retrieves all jobs ordered by discovery date descending."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM jobs ORDER BY match_score DESC, date_discovered DESC LIMIT ?", (limit,))
            return [dict(r) for r in cursor.fetchall()]

    def get_jobs_by_status(self, status: str) -> List[Dict[str, Any]]:
        """Retrieves jobs with specific status."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM jobs WHERE status = ? ORDER BY match_score DESC", (status,))
            return [dict(r) for r in cursor.fetchall()]

    def count_applications_today(self) -> int:
        """Counts successful submissions today."""
        today_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) AS cnt FROM jobs WHERE status = 'Applied' AND date_applied LIKE ?", (f"{today_date}%",))
            row = cursor.fetchone()
            return row["cnt"] if row else 0

    def start_hourly_run(self) -> int:
        """Records the start of an hourly discovery run and returns run_id."""
        now_iso = datetime.now(timezone.utc).isoformat()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO hourly_runs (start_time, status)
            VALUES (?, 'RUNNING')
            """, (now_iso,))
            conn.commit()
            return cursor.lastrowid

    def finish_hourly_run(self, run_id: int, stats: Dict[str, Any], summary_text: str = ""):
        """Updates the hourly run record upon completion."""
        now_iso = datetime.now(timezone.utc).isoformat()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            UPDATE hourly_runs SET
                end_time = ?,
                status = 'COMPLETED',
                jobs_discovered = ?,
                relevant_jobs = ?,
                high_priority_matches = ?,
                applications_submitted = ?,
                awaiting_review = ?,
                duplicates_skipped = ?,
                errors_count = ?,
                summary_text = ?
            WHERE run_id = ?
            """, (
                now_iso,
                stats.get("jobs_discovered", 0),
                stats.get("relevant_jobs", 0),
                stats.get("high_priority_matches", 0),
                stats.get("applications_submitted", 0),
                stats.get("awaiting_review", 0),
                stats.get("duplicates_skipped", 0),
                stats.get("errors_count", 0),
                summary_text,
                run_id
            ))
            conn.commit()

    def get_dashboard_metrics(self) -> Dict[str, Any]:
        """Calculates aggregated metrics for the Streamlit dashboard."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("SELECT COUNT(*) as total FROM jobs")
            total_discovered = cursor.fetchone()["total"]

            cursor.execute("SELECT COUNT(*) as cnt FROM jobs WHERE match_score >= 85.0")
            relevant_jobs = cursor.fetchone()["cnt"]

            cursor.execute("SELECT COUNT(*) as cnt FROM jobs WHERE match_score >= 95.0")
            high_priority = cursor.fetchone()["cnt"]

            cursor.execute("SELECT COUNT(*) as cnt FROM jobs WHERE status = 'Applied'")
            applied = cursor.fetchone()["cnt"]

            cursor.execute("SELECT COUNT(*) as cnt FROM jobs WHERE status = 'Awaiting Approval'")
            awaiting_approval = cursor.fetchone()["cnt"]

            cursor.execute("SELECT COUNT(*) as cnt FROM jobs WHERE status = 'Application Failed'")
            failed = cursor.fetchone()["cnt"]

            cursor.execute("SELECT COALESCE(SUM(duplicates_skipped), 0) as dupes FROM hourly_runs")
            duplicates_skipped = cursor.fetchone()["dupes"]

            cursor.execute("SELECT * FROM hourly_runs ORDER BY run_id DESC LIMIT 5")
            recent_runs = [dict(r) for r in cursor.fetchall()]

            cursor.execute("""
            SELECT h.*, j.title, j.company 
            FROM application_history h
            LEFT JOIN jobs j ON h.job_id = j.job_id
            ORDER BY h.id DESC LIMIT 15
            """)
            recent_activity = [dict(r) for r in cursor.fetchall()]

            return {
                "total_discovered": total_discovered,
                "relevant_jobs": relevant_jobs,
                "high_priority_matches": high_priority,
                "applications_submitted": applied,
                "awaiting_approval": awaiting_approval,
                "failed_applications": failed,
                "duplicates_skipped": duplicates_skipped,
                "recent_runs": recent_runs,
                "recent_activity": recent_activity
            }


# Singleton database instance
db_manager = DatabaseManager()
