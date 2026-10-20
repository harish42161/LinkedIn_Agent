"""Notification Service.

Dispatches hourly discovery run summaries, high-priority match alerts,
and manual intervention requests via Terminal, macOS desktop notifications, and webhooks.
"""

import os
import json
import logging
import subprocess
from typing import Any, Dict, Optional
import requests
from linkedin_job_agent.config import config

logger = logging.getLogger("linkedin_agent.notify")


class NotificationService:
    """Manages multi-channel user alerts and summary dispatches."""

    def __init__(self):
        self.webhook_url = config.webhook_url

    def format_hourly_summary(self, stats: Dict[str, Any]) -> str:
        """Formats summary matching the project specifications."""
        return (
            "=====================================================\n"
            "               Hourly Job Search Summary             \n"
            "=====================================================\n"
            f"- Jobs discovered: {stats.get('jobs_discovered', 0)}\n"
            f"- Relevant jobs: {stats.get('relevant_jobs', 0)}\n"
            f"- High-priority matches: {stats.get('high_priority_matches', 0)}\n"
            f"- Applications submitted: {stats.get('applications_submitted', 0)}\n"
            f"- Awaiting review: {stats.get('awaiting_review', 0)}\n"
            f"- Duplicates skipped: {stats.get('duplicates_skipped', 0)}\n"
            f"- Errors: {stats.get('errors_count', 0)}\n"
            "====================================================="
        )

    def send_hourly_summary(self, stats: Dict[str, Any]):
        """Delivers hourly summary through all configured channels."""
        summary = self.format_hourly_summary(stats)

        # 1. Console / Logger
        print("\n" + summary + "\n")
        logger.info("Hourly search cycle completed successfully.")

        # 2. Native macOS Notification
        if config.system_desktop_notif:
            msg = (f"Discovered: {stats.get('jobs_discovered', 0)} | "
                   f"High Match: {stats.get('high_priority_matches', 0)} | "
                   f"Applied: {stats.get('applications_submitted', 0)}")
            self.send_desktop_notification("LinkedIn Job Agent", msg)

        # 3. Webhook (Slack / Discord)
        if config.webhook_enabled and self.webhook_url:
            self._send_webhook_message(summary)

    def send_high_priority_alert(self, job_data: Dict[str, Any], score: float, status: str):
        """Alerts the user when a high-priority match is found."""
        title = job_data.get("title", "")
        company = job_data.get("company", "")
        text = f"🎯 High-Priority Match ({score}%): {title} at {company} [{status}]"
        logger.info(text)
        if config.system_desktop_notif:
            self.send_desktop_notification("Target Job Match Found", text)

    def send_action_needed_alert(self, job_data: Dict[str, Any], reason: str):
        """Notifies user when manual review or verification is required."""
        title = job_data.get("title", "")
        company = job_data.get("company", "")
        text = f"⚠️ Action Required for {title} at {company}: {reason}"
        logger.warning(text)
        if config.system_desktop_notif:
            self.send_desktop_notification("Action Required", text)

    def send_desktop_notification(self, title: str, message: str):
        """Sends native notification on macOS."""
        try:
            # Escape double quotes for osascript
            safe_title = title.replace('"', '\\"')
            safe_msg = message.replace('"', '\\"')
            script = f'display notification "{safe_msg}" with title "{safe_title}"'
            subprocess.run(["osascript", "-e", script], capture_output=True, timeout=3)
        except Exception as e:
            logger.debug(f"Desktop notification failed: {e}")

    def _send_webhook_message(self, text: str):
        """Sends payload to configured webhook."""
        try:
            payload = {"text": text}
            requests.post(self.webhook_url, json=payload, timeout=5)
        except Exception as e:
            logger.error(f"Failed to post to webhook: {e}")


notification_service = NotificationService()
