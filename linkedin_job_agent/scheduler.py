"""Hourly Automation Scheduler.

Orchestrates the hourly end-to-end job discovery, deduplication, scoring,
and application submission cycle with fault-tolerance and emergency stop handling.
"""

import time
import signal
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional
import schedule
from linkedin_job_agent.config import config
from linkedin_job_agent.database_manager import DatabaseManager, db_manager
from linkedin_job_agent.duplicate_checker import DuplicateChecker, duplicate_checker
from linkedin_job_agent.job_search import JobSearchEngine, job_search_engine
from linkedin_job_agent.job_matcher import JobMatcher, job_matcher
from linkedin_job_agent.application_submitter import ApplicationSubmitter, application_submitter
from linkedin_job_agent.notification_service import NotificationService, notification_service
from linkedin_job_agent.linkedin_auth import auth_manager

logger = logging.getLogger("linkedin_agent.scheduler")


class HourlyJobScheduler:
    """Manages recurring hourly execution of the job automation pipeline."""

    def __init__(self):
        self.db = db_manager
        self.search_engine = job_search_engine
        self.matcher = job_matcher
        self.dedupe = duplicate_checker
        self.submitter = application_submitter
        self.notifier = notification_service
        self._running = False
        self._emergency_stop = False

    def is_stopped(self) -> bool:
        """Returns True if emergency stop or user pause is triggered."""
        return self._emergency_stop or config.emergency_stop

    def set_emergency_stop(self, stop: bool = True):
        """Toggles the emergency stop kill switch."""
        self._emergency_stop = stop
        logger.warning(f"🚨 Emergency Stop set to: {stop}")

    def execute_single_cycle(self) -> Dict[str, Any]:
        """Executes one full discovery, matching, and submission iteration."""
        if self.is_stopped():
            logger.warning("Pipeline execution paused due to Emergency Stop flag.")
            return {"status": "PAUSED", "reason": "Emergency stop enabled"}

        logger.info("Starting hourly job search and evaluation cycle...")
        run_id = self.db.start_hourly_run()

        stats = {
            "jobs_discovered": 0,
            "relevant_jobs": 0,
            "high_priority_matches": 0,
            "applications_submitted": 0,
            "awaiting_review": 0,
            "duplicates_skipped": 0,
            "errors_count": 0,
        }

        try:
            # 1. Search LinkedIn for postings in last 1 hour (fallback to 24h)
            discovered_jobs = self.search_engine.search_jobs(time_window="r3600")
            stats["jobs_discovered"] = len(discovered_jobs)

            for job in discovered_jobs:
                if self.is_stopped():
                    logger.warning("Cycle interrupted by emergency stop.")
                    break

                try:
                    job_id = job.get("job_id")

                    # 2. Check Deduplication
                    is_dup, dup_reason, existing = self.dedupe.check_duplicate(job)
                    if is_dup:
                        stats["duplicates_skipped"] += 1
                        logger.debug(f"Skipping duplicate job {job_id}: {dup_reason}")
                        continue

                    # 3. Resume-Based Scoring
                    match_result = self.matcher.evaluate_job(job)
                    score = match_result.score

                    job["match_score"] = score
                    job["match_explanation"] = match_result.explanation
                    job["match_breakdown"] = match_result.breakdown

                    if score >= config.good_match_threshold:
                        stats["relevant_jobs"] += 1

                    if score >= config.high_priority_threshold:
                        stats["high_priority_matches"] += 1

                    # 4. Save to Database
                    is_new, current_status = self.db.upsert_job(job)

                    # 5. Evaluate Application Submission
                    if score >= config.minimum_match_score:
                        status, msg = self.submitter.process_application(job, score)
                        if status == "Applied":
                            stats["applications_submitted"] += 1
                            self.notifier.send_high_priority_alert(job, score, "Applied")
                        elif status == "Awaiting Approval":
                            stats["awaiting_review"] += 1
                            self.notifier.send_action_needed_alert(job, msg)
                    elif score >= config.good_match_threshold:
                        self.db.update_job_status(job_id, "Shortlisted", details="Good match saved for candidate consideration.")
                    else:
                        self.db.update_job_status(job_id, "Rejected", details=match_result.explanation)

                except Exception as item_err:
                    stats["errors_count"] += 1
                    logger.error(f"Error processing job item: {item_err}")

        except Exception as cycle_err:
            stats["errors_count"] += 1
            logger.error(f"Critical error in hourly cycle: {cycle_err}")

        # 6. Finalize Run Record and Dispatch Notifications
        summary_text = self.notifier.format_hourly_summary(stats)
        self.db.finish_hourly_run(run_id, stats, summary_text)
        self.notifier.send_hourly_summary(stats)

        return stats

    def start_hourly_loop(self):
        """Starts continuous hourly daemon loop."""
        self._running = True
        logger.info(f"Hourly Job Scheduler started (Interval: {config.search_frequency_hours} hour / {config.search_interval_seconds}s)")

        # Execute first cycle immediately
        self.execute_single_cycle()

        # Schedule recurring execution
        schedule.every(config.search_frequency_hours).hours.do(self.execute_single_cycle)

        # Register termination handlers
        def handle_exit(signum, frame):
            logger.info("Received termination signal. Shutting down scheduler gracefully...")
            self._running = False

        signal.signal(signal.SIGINT, handle_exit)
        signal.signal(signal.SIGTERM, handle_exit)

        while self._running:
            schedule.run_pending()
            time.sleep(1)

        logger.info("Hourly Job Scheduler stopped.")


scheduler = HourlyJobScheduler()
