"""Duplicate Checker for LinkedIn Job Application Automation Agent.

Ensures that the agent never repeatedly applies to the same opportunity,
evaluating Job IDs, canonical URLs, and normalized company+title signatures.
"""

import re
import logging
from typing import Any, Dict, Optional, Tuple
from linkedin_job_agent.database_manager import DatabaseManager, db_manager

logger = logging.getLogger("linkedin_agent.dedupe")


class DuplicateChecker:
    """Detects duplicate job listings and prevents redundant application submissions."""

    def __init__(self, db: Optional[DatabaseManager] = None):
        self.db = db if db else db_manager

    @staticmethod
    def normalize_string(text: str) -> str:
        """Lowercases and cleans special characters for fuzzy matching."""
        if not text:
            return ""
        return re.sub(r"[^a-zA-Z0-9\s]", "", text).lower().strip()

    @staticmethod
    def extract_canonical_url(url: str) -> str:
        """Strips tracking query parameters from LinkedIn URLs."""
        if not url:
            return ""
        # Cut off query params like ?refId=... or ?trackingId=...
        return url.split("?")[0].rstrip("/")

    def check_duplicate(self, job_data: Dict[str, Any], for_submission: bool = False) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """Checks if a job has already been registered or applied to.

        Args:
            job_data: Job metadata dictionary.
            for_submission: If True, only returns duplicate if already applied or in active review.

        Returns:
            (is_duplicate, reason, existing_record)
        """
        job_id = str(job_data.get("job_id", "")).strip()
        url = job_data.get("job_url", "")
        canonical_url = self.extract_canonical_url(url)
        title = self.normalize_string(job_data.get("title", ""))
        company = self.normalize_string(job_data.get("company", ""))
        location = self.normalize_string(job_data.get("location", ""))

        with self.db.get_connection() as conn:
            cursor = conn.cursor()

            # 1. Exact Job ID Match
            if job_id:
                cursor.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,))
                row = cursor.fetchone()
                if row:
                    rec = dict(row)
                    status = rec.get("status", "")
                    if for_submission:
                        if status in ("Applied", "Interview Scheduled", "Awaiting Approval"):
                            return True, f"Application already submitted or in progress (Status: {status})", rec
                    else:
                        return True, f"Duplicate job ID '{job_id}' (Current status: {status})", rec

            # 2. Canonical URL Match
            if canonical_url:
                cursor.execute("SELECT * FROM jobs WHERE canonical_url = ?", (canonical_url,))
                row = cursor.fetchone()
                if row:
                    rec = dict(row)
                    status = rec.get("status", "")
                    if for_submission:
                        if status in ("Applied", "Interview Scheduled", "Awaiting Approval"):
                            return True, f"Application already submitted or in progress (Status: {status})", rec
                    else:
                        return True, f"Duplicate canonical URL '{canonical_url}' (Status: {status})", rec

            # 3. Fuzzy Signature Match (Company + Title match within same location)
            if company and title:
                cursor.execute("SELECT * FROM jobs WHERE status IN ('Applied', 'Awaiting Approval', 'Ready for Application')")
                active_rows = cursor.fetchall()
                for r in active_rows:
                    active_rec = dict(r)
                    act_comp = self.normalize_string(active_rec.get("company", ""))
                    act_title = self.normalize_string(active_rec.get("title", ""))
                    if act_comp == company and act_title == title:
                        return True, f"Identical role already in progress at '{active_rec.get('company')}' for '{active_rec.get('title')}'", active_rec

        return False, "Unique job opportunity", None

    def is_already_applied(self, job_id: str) -> bool:
        """Returns True if the candidate has already submitted an application."""
        job = self.db.get_job_by_id(job_id)
        if not job:
            return False
        return job.get("status") in ("Applied", "Interview Scheduled")

    def is_in_progress(self, job_id: str) -> bool:
        """Returns True if the application is queued or awaiting manual review."""
        job = self.db.get_job_by_id(job_id)
        if not job:
            return False
        return job.get("status") in ("Ready for Application", "Awaiting Approval")


duplicate_checker = DuplicateChecker()
